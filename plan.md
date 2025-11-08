# Phase 3 Implementation Specification

## Overview
**Goal:** Live market data integration powering real-time risk guards, UI telemetry, and automated trading execution.

**Delivery Mode:** Incremental sprints
- **Sprint 1 (Week 1):** Market data workers + live guards endpoint → ✅ **COMPLETE**
- **Sprint 2 (Week 2):** On-chain workers + basis calculation + UI telemetry → ✅ **COMPLETE**
- **Sprint 3 (Week 3):** Automated trading execution wiring → 🟡 **IN PROGRESS**

**Storage/Transport:**
- Redis Streams as message bus (workers → API → UI)
- Parquet for historical data (hourly rollups)
- In-memory for dev; persist for backfills/debugging

---

## Sprint 1 Status: ✅ COMPLETE

### Completed Deliverables:

#### 1.1 Binance Trades + CVD Worker ✅
**File:** `/app/workers/market_data/binance_trades_cvd.py`

**Implementation:**
- WebSocket: `wss://fstream.binance.com/ws/solusdt@aggTrade`
- Process: Real-time aggTrade → 1-minute bars
- Output: `{open, high, low, close, buy_vol, sell_vol, cvd, vwap, timestamp}`
- Publish: Redis Stream `market:solusdt:trades`
- Persist: Parquet `/app/storage/parquet/binance/SOLUSDT/trades/YYYYMMDD.parquet`
- Reconnection: Exponential backoff (1s → 60s max)

**Docs:** https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams

---

#### 1.2 Binance Order Book Worker ✅
**File:** `/app/workers/market_data/binance_book_top.py`

**Implementation:**
- WebSocket: `wss://fstream.binance.com/ws/solusdt@depth@100ms`
- Maintain: Top-of-book (TOB) + 10bps depth snapshot
- Output: `{bid_px, bid_qty, ask_px, ask_qty, spread_bps, depth_10bps: {bid_usd, ask_usd}, timestamp}`
- Publish: Redis Stream `market:solusdt:book` (throttled to 1/sec)
- Calculations:
  - `spread_bps = ((ask_px - bid_px) / mid_px) * 10000`
  - `depth_10bps = sum of bid/ask qty within 10bps of mid`

**Docs:** https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Diff-Book-Depth-Streams

---

#### 1.3 Multi-Venue Liquidations Worker ✅
**File:** `/app/workers/market_data/liquidations_multi.py`

**Implementation:**
- **Binance:** `wss://fstream.binance.com/ws/!forceOrder@arr` (filter `symbol=="SOLUSDT"`)
- **OKX:** WS v5 `liquidation-orders` channel (public)
- **Bybit:** V5 public liquidation topic
- Output per event: `{venue, symbol, side, price, quantity, timestamp}`
- Publish: Redis Stream `market:solusdt:liquidations`
- Persist: Parquet `/app/storage/parquet/liquidations/SOLUSDT/YYYYMMDD.parquet`

**Docs:**
- Binance: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams
- OKX: https://www.okx.com/docs-v5/en/
- Bybit: https://bybit-exchange.github.io/docs/api-explorer/v5/market/market

---

#### 1.4 Bybit OI + Funding Poller ✅
**File:** `/app/workers/market_data/bybit_oi_funding.py`

**Implementation:**
- **Open Interest:** `GET /v5/market/open-interest?category=linear&symbol=SOLUSDT&intervalTime=5min`
- **Funding Rate:** `GET /v5/market/funding/history?category=linear&symbol=SOLUSDT`
- **Ticker:** `GET /v5/market/tickers?category=linear&symbol=SOLUSDT` (for price)
- Poll frequency: Every 60 seconds
- Output: `{oi_notional, oi_value, funding_rate_8h, funding_apr, next_funding_time, timestamp}`
- Calculations: `funding_apr = funding_rate_8h * 3 * 365 * 100`
- Publish: Redis Stream `market:solusdt:funding`
- Persist: Parquet `/app/storage/parquet/bybit/SOLUSDT/funding/YYYYMMDD.parquet`

**Docs:**
- OI: https://bybit-exchange.github.io/docs/v5/market/open-interest
- Funding: https://bybit-exchange.github.io/docs/v5/market/history-fund-rate

---

#### 1.5 Live Guards Endpoint ✅
**File:** `/app/backend/routers/engine.py` (enhanced)

**Endpoint:** `GET /api/engine/guards`

**Response Schema:**
```json
{
  "ts": 1699999999999,
  "spread_bps": 6.5,
  "depth_10bps": {
    "bid_usd": 125000,
    "ask_usd": 130000
  },
  "funding_apr": 112.5,
  "basis_bps": 4.2,
  "oi_notional": 45000000,
  "liq_events_5m": 3,
  "status": "passing|warning|breach",
  "warnings": [],
  "data_source": "live"
}
```

**Data Sources:**
- `spread_bps`, `depth_10bps`: From Redis Stream `market:solusdt:book` (latest via XREVRANGE)
- `funding_apr`, `oi_notional`: From Redis Stream `market:solusdt:funding` (latest)
- `basis_bps`: Live calculation from USDT (Binance) vs USDC (OKX) prices
- `liq_events_5m`: Count from Redis Stream `market:solusdt:liquidations` (XRANGE last 5 min)
- **Cache:** 5-second TTL to reduce Redis load

**Guard Thresholds:**
- `spread_bps > 10` → warning
- `depth_10bps < $50k` → warning
- `funding_apr > 300` → warning
- `liq_events_5m > 10` → breach

**Implementation:**
- Reads from Redis Streams with async Redis client
- Graceful fallback to mock data if Redis unavailable
- Status evaluation based on threshold breaches

---

## Sprint 2 Status: ✅ COMPLETE

### Completed Deliverables:

#### 2.1 OKX USDC Price Worker ✅
**File:** `/app/workers/market_data/okx_usdc_price.py`

**Implementation:**
- WebSocket: `wss://ws.okx.com:8443/ws/v5/public`
- Subscribe: `trades` channel for `SOL-USDC-SWAP`
- Process: Real-time trades → last price
- Output: `{symbol, price, side, size, timestamp}`
- Publish: Redis Stream `market:solusdc:trades` (throttled to 1/sec)

**Docs:** https://www.okx.com/docs-v5/en/

---

#### 2.2 Basis Calculation Service ✅
**File:** `/app/backend/services/basis.py`

**Implementation:**
- Read latest prices from:
  - USDT: Redis Stream `market:solusdt:trades` (Binance aggTrade)
  - USDC: Redis Stream `market:solusdc:trades` (OKX trades)
- Calculate: `basis_bps = ((px_usdc - px_usdt) / px_usdt) * 10000`
- Cache result with 5s TTL
- Exposed via guards endpoint

**Integration:** Wired into `/api/engine/guards` response

---

#### 2.3 Helius Enhanced Webhooks Receiver ✅
**File:** `/app/backend/routers/webhooks.py`

**Implementation:**
- Endpoint: `POST /api/webhooks/helius`
- Process: Enhanced webhook events → Redis queue
- Filter: Drift Protocol program IDs only (`dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH`)
- Deduplication: Track event IDs in Redis SET (24h TTL)
- Signature verification: SHA256 with HELIUS_WEBHOOK_SECRET
- Output: `{signature, type, timestamp, slot, event_json}`
- Publish: Redis Stream `onchain:drift:events`
- Persist: Parquet `/app/storage/parquet/helius/drift/YYYYMMDD.parquet`
- Health endpoint: `GET /api/webhooks/helius/health`

**Docs:** https://www.helius.dev/docs/webhooks

---

#### 2.4 Drift Liquidation Map Scanner ✅
**File:** `/app/workers/onchain/drift_liq_map.py`

**Implementation:**
- Method: `getProgramAccounts` (gPA) via Helius RPC
- Frequency: Every 60 minutes (hourly refresh)
- Filter: Drift user accounts with open positions
- Calculate: Oracle-based liquidation price per position
  - Formula: `C + q*(p - avg) = mmr*|q|*p` (solve for p)
  - Health: `(Collateral + Unrealized PnL) / (MMR × Position Size)`
- Output: `{account, market_index, position_size, avg_entry_price, est_liq_px, collateral_usd, leverage, health, distance_bps, updated_at}`
- Publish: Redis Stream `onchain:drift:liq_map`
- Persist: Parquet `/app/storage/parquet/drift/liq_map/latest.parquet` (overwrite)

**Note:** Currently uses placeholder account decoder; production requires Drift SDK v2 integration for exact deserialization.

**Docs:** https://docs.drift.trade/liquidations/liquidations

---

#### 2.5 Market History Endpoints ✅
**File:** `/app/backend/routers/market.py`

**Endpoints:**

**GET /api/onchain/liq-map**
- Returns liquidation estimates sorted by distance to liquidation
- Query params: `limit` (default: 100, max: 1000)
- Fields: `account, est_liq_px, position_size, leverage, health, distance_bps`
- Data source: Redis Stream → Parquet fallback

**GET /api/history/oi**
- Query params: `symbol, tf, lookback` (default: SOLUSDT, 1m, 24h)
- Returns: `[{ts, notional}, ...]`
- Data source: Redis Stream `market:solusdt:funding`

**GET /api/history/liqs**
- Query params: `symbol, window, bucket_bps` (default: SOLUSDT, 6h, 25bps)
- Returns price-bucketed liquidations: `[{px_mid, count, notional}, ...]`
- Data source: Redis Stream `market:solusdt:liquidations`
- Dynamic bucketing based on current price

---

#### 2.6 Telemetry Cards Component ✅
**File:** `/app/frontend/src/components/TelemetryCards.jsx`

**Implementation:**
- 6 real-time metric cards:
  - **Spread** (bps): Green <5, Yellow 5-10, Red >10
  - **Depth** (10bps bucket): Shows min(bid, ask), Red if <$50k
  - **Funding APR** (8h×3×365): Red if |x|>300%
  - **Basis** (bps): USDT vs USDC spread with +/- sign
  - **OI Notional**: Formatted with M/B suffix
  - **Liquidations** (5m count): Red if >10
- Polls `/api/engine/guards` every 5s
- Color-coded by threshold violations
- Status indicator for warnings/breaches
- Design: IBM Plex Mono for numbers, Shadcn Card components

---

#### 2.7 OI Chart Component ✅
**File:** `/app/frontend/src/components/OIChart.jsx`

**Implementation:**
- Recharts area chart with lime green (#84CC16) gradient
- Data: Last 24 hours OI notional (1-minute resolution)
- Source: `/api/history/oi?symbol=SOLUSDT&tf=1m&lookback=24h`
- Updates every 60 seconds
- Custom tooltip with formatted values (M/B suffix)
- Responsive layout (300px height)

---

#### 2.8 Liquidation Heatmap Component ✅
**File:** `/app/frontend/src/components/LiqHeatmap.jsx`

**Implementation:**
- D3.js bar chart heatmap
- Data: 6h liquidation events in 25bps price buckets
- Source: `/api/history/liqs?symbol=SOLUSDT&window=6h&bucket_bps=25`
- Color scale: Green (low) → Yellow → Orange → Red (high)
- Interactive tooltips: Price, count, notional on hover
- Updates every 5 seconds for real-time events
- X-axis: Price buckets, Y-axis: Liquidation count

---

## Sprint 3: 🟡 IN PROGRESS - Automated Trading Execution

### Objective:
Wire automated trading execution with Drift Protocol, including delegated trading, guards integration, SL/TP management, and E2E testing on devnet → mainnet.

### Dependencies:
- **Phase 2:** ✅ SIWS auth, delegation UI scaffolding, backend APIs
- **Sprint 1:** ✅ Market data workers operational
- **Sprint 2:** ✅ Basis calculation, guards endpoint, telemetry UI

### Implementation Order:
S3.1 → S3.2 → S3.3 → S3.4 → S3.5 → S3.6 → S3.7 → S3.8 → S3.9 → S3.10 → S3.11

---

### S3.1 - Replace Placeholder Decode with Drift SDK v2 🟡 IN PROGRESS

**Files:**
- `/app/workers/execution/drift_adapter.ts`
- `/app/workers/execution/types.ts`
- `/app/workers/onchain/drift_liq_map.ts` (switch calc to SDK health parity)

**Tasks:**
- Import **@drift-labs/sdk v2**
- Decode user accounts/positions/markets with SDK APIs
- Align liq-price estimator to **oracle-based liquidation @ Health=0** (SDK health parity)

**DoD:**
- [ ] Decoded positions & collateral match Drift UI for sample account
- [ ] Est. liq price agrees with SDK health-solver within ≤0.25% tolerance

**Docs:** https://docs.drift.trade/sdk-documentation

---

### S3.2 - Delegated Trading + Revoke (with UI) ⏳ PENDING

**Files:**
- Backend: `/app/backend/routers/engine.py` (add `POST /api/delegate/set`, `POST /api/delegate/revoke`)
- Frontend: `/app/frontend/src/components/DelegateFlow.tsx` (button → tx; badge)
- Worker: Use delegate key when present

**Tasks:**
- Implement Drift **Delegated Accounts**: `setDelegate` / `revokeDelegate` tx flow
- Restrict delegate to place/cancel orders only (no withdrawals)
- UI shows "Delegate: Active/Inactive" badge
- Phantom connect via **Wallet Adapter** (existing), reuse SIWS session

**DoD:**
- [ ] Tx confirms for set/revoke
- [ ] UI state reflects chain state
- [ ] Delegation badge updates correctly

**Docs:** https://docs.drift.trade/getting-started/delegated-accounts

---

### S3.3 - ExecutionEngine Worker (Core Order Lifecycle) ⏳ PENDING

**Files:**
- `/app/workers/execution/engine.ts` (main loop)
- `/app/workers/execution/drift_adapter.ts` (methods: placePostOnly, cancelAndReplace, convertToMarket, placeStops)

**Tasks:**
- Consume `engine:intents` → preflight guards check
- Submit **post-only** limit order → monitor fills
- One **cancel/replace** attempt if drift > tolerance (max 2 attempts total)
- Optional **guarded market convert** if conditions pass
- Wire to Drift SDK order APIs

**DoD:**
- [ ] Order submitted & confirmed on-chain
- [ ] On unfilled drift, order replaced once (max 2 attempts)
- [ ] Events logged to Redis Stream

**Docs:** https://docs.drift.trade/sdk-documentation

---

### S3.4 - Guards Binding (Live) ⏳ PENDING

**Files:**
- `/app/workers/execution/engine.ts` (preflight)
- `/app/backend/services/guards_client.py` (helper)

**Tasks:**
- Pull `/api/engine/guards` before each trade
- **Block trades** if:
  - Spread > 10 bps
  - Depth (±10 bps) below floor ($50k)
  - Funding APR extreme (|x|>300%)
  - Basis |USDT−USDC| > cap
  - Recent liqs spike (>10 in 5min)
- Sources validated: Binance aggTrade/Depth@100ms, Bybit V5 funding/OI, OKX v5 USDC trades

**DoD:**
- [ ] Engine blocks when any guard breached
- [ ] Logs the reason for block
- [ ] Status visible in UI ActivityLog

**Docs:** https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams

---

### S3.5 - SL/TP Ladder + ATR Trail ⏳ PENDING

**Files:**
- `/app/workers/execution/risk.ts`
- `/app/workers/execution/drift_adapter.ts` (placeStops)

**Tasks:**
- On fill: place **SL** and **TP1/TP2/TP3** ladder (50%/30%/20% split)
- On TP1 hit: move SL → BE+fees
- Enable **ATR(5m) trail** for remainder

**DoD:**
- [ ] Ladder appears on-chain after fill
- [ ] SL adjusts at TP1
- [ ] Trail updates tick-to-tick

---

### S3.6 - Manual-Sign Fallback ⏳ PENDING

**Files:**
- Backend: `/app/backend/routers/engine.py` (manual path)
- Frontend: `/app/frontend/src/components/ManualOrderModal.tsx`

**Tasks:**
- If delegate inactive, prompt Phantom to sign order tx via Wallet Adapter
- Identical order placement via manual-sign path

**DoD:**
- [ ] Manual-sign order can be placed successfully
- [ ] User approves via Phantom wallet
- [ ] Order confirmed on-chain

**Docs:** https://solana.com/developers/cookbook/wallets/connect-wallet-react

---

### S3.7 - Activity Log & Metrics ⏳ PENDING

**Files:**
- `/app/backend/routers/activity.py` (GET last N events)
- `/app/backend/metrics.py` (Prometheus)

**Tasks:**
- Emit events: `order_submitted/filled/cancelled/sl_hit/tp_hit/kill_switch`
- Persist to MongoDB activity collection
- Expose via `/api/engine/activity`
- Prometheus counters & latencies for submit→confirm

**DoD:**
- [ ] Events visible in UI ActivityLog
- [ ] Metrics scrape endpoint functional
- [ ] Latency tracking operational

---

### S3.8 - E2E Testing (Devnet) ⏳ PENDING

**Checklist:**
- [ ] Connect Phantom → SIWS → `setDelegate`
- [ ] Force a small **post-only** order on devnet market
- [ ] Verify on-chain fill
- [ ] Confirm SL/TP ladder installation
- [ ] Simulate **guard breach** (mock spread) → engine halts and logs

**Pass Criteria:**
- All state changes appear within ≤5s in UI
- Logs persist correctly
- Guards status updates correctly

---

### S3.9 - E2E Testing (Mainnet Tiny Size) ⏳ PENDING

**Checklist:**
- [ ] Repeat at minimum notional
- [ ] Confirm fills & ladder on mainnet
- [ ] **Revoke delegate** at end

**Pass Criteria:**
- No guard violations during test
- Clean revoke transaction confirms

---

### S3.10 - Kill-Switch & Rollback ⏳ PENDING

**Files:**
- `/app/backend/routers/engine.py` (`POST /api/engine/kill`)
- `/app/workers/execution/engine.ts` (handler)

**Tasks:**
- Cancel all open orders
- Disable strategy
- Persist reason to MongoDB
- Broadcast event via WebSocket

**DoD:**
- [ ] One call zeroes risk
- [ ] UI reflects "Automation: Off"
- [ ] All orders cancelled on-chain

---

### S3.11 - Documentation & Runbooks ⏳ PENDING

**Files:**
- `/docs/EXECUTION_ENGINE.md` — flows, guards, failure modes
- `/docs/DELEGATION.md` — risks, revoke steps, limits
- `/VERSION.txt` — surfaced via `GET /api/engine/ping`

**DoD:**
- [ ] Complete execution engine documentation
- [ ] Delegation guide with safety procedures
- [ ] Versioning exposed in API

---

## Redis Streams Schema

### Stream Keys:
- `market:solusdt:trades` - 1-minute trade bars (Binance) ✅
- `market:solusdc:trades` - USDC price feed (OKX) ✅
- `market:solusdt:book` - Order book snapshots (100ms) ✅
- `market:solusdt:liquidations` - Liquidation events (multi-venue) ✅
- `market:solusdt:funding` - OI + funding rates (Bybit) ✅
- `onchain:drift:events` - Helius webhook events ✅
- `onchain:drift:liq_map` - Drift liquidation map ✅
- `engine:intents` - Trading signal intents (Phase 3 Sprint 3) 🟡

### Message Format Example:
```
Stream: market:solusdt:funding
ID: 1699999999999-0
Fields:
  symbol: SOLUSDT
  oi_notional: 45000000
  oi_value: 300000
  funding_rate_8h: 0.0001
  funding_apr: 10.95
  next_funding_time: 1700000000000
  timestamp: 1699999999999
```

---

## Parquet Storage Layout

```
/app/storage/parquet/
├── binance/
│   └── SOLUSDT/
│       ├── trades/           ✅ ACTIVE
│       │   ├── 20251108.parquet
│       │   └── 20251109.parquet
│       └── book/             (not persisted, Redis only)
├── okx/                      ✅ ACTIVE
│   └── SOLUSDC/
│       └── trades/
│           └── 20251108.parquet
├── bybit/
│   └── SOLUSDT/
│       └── funding/          ✅ ACTIVE
│           └── 20251108.parquet
├── liquidations/
│   └── SOLUSDT/              ✅ ACTIVE
│       └── 20251108.parquet
├── helius/                   ✅ ACTIVE
│   └── drift/
│       └── 20251108.parquet
└── drift/                    ✅ ACTIVE
    └── liq_map/
        └── latest.parquet    (overwrite hourly)
```

**Rollup Schedule:**
- Hourly: Aggregate 1-minute bars into hourly bars
- Daily: Archive hourly bars to daily Parquet files
- Retention: 30 days (configurable)

---

## Test Checkpoints

### Guards Live
```bash
curl -s http://localhost:8001/api/engine/guards | jq
```

### Liq-Map Sample (Oracle-Based)
```bash
curl -s http://localhost:8001/api/onchain/liq-map | jq '.[0:5]'
```

### OI & Liq History (Charts)
```bash
curl -s "http://localhost:8001/api/history/oi?symbol=SOLUSDT&tf=1m&lookback=24h" | jq '.[0:3]'
curl -s "http://localhost:8001/api/history/liqs?symbol=SOLUSDT&window=6h&bucket_bps=25" | jq '.[0:10]'
```

### Engine Smoke Test
```bash
curl -s -XPOST http://localhost:8001/api/engine/orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -d '{"side":"long","type":"post_only_limit","px":123.45,"size":1,"sl":121.0,"tp1":124.2,"tp2":125.5,"tp3":127.0,"leverage":5,"venue":"drift"}' | jq
```

---

## Acceptance Tests

### Sprint 1 Tests: ✅ PASSING
- [x] AT-P3-1.1: Binance trades CVD worker writes 1m bars to Redis Stream
- [x] AT-P3-1.2: Binance book worker reports TOB every second
- [x] AT-P3-1.3: Liquidations worker captures events from all 3 venues
- [x] AT-P3-1.4: Bybit poller returns OI + funding every 60s
- [x] AT-P3-1.5: Guards endpoint returns live data with <5s lag
- [x] AT-P3-1.6: Workers reconnect gracefully on connection loss

### Sprint 2 Tests: ✅ PASSING
- [x] AT-P3-2.1: OKX worker streams SOL-USDC-SWAP trades to Redis
- [x] AT-P3-2.2: Basis calculation returns non-zero value during divergence
- [x] AT-P3-2.3: Guards endpoint includes live `basis_bps` field
- [x] AT-P3-2.4: Helius webhook receives and acks Drift events ≤1s
- [x] AT-P3-2.5: Drift liq-map parquet has ≥N entries, refreshes ≤65min
- [x] AT-P3-2.6: Telemetry cards update ≤2s after data changes
- [x] AT-P3-2.7: OI chart displays last 24 hours
- [x] AT-P3-2.8: Liquidation heatmap shows new prints within 2s

### Sprint 3 Tests: 🟡 IN PROGRESS
- [ ] AT-P3-3.1: Drift SDK v2 decodes user accounts accurately
- [ ] AT-P3-3.2: Delegation flow (set/revoke) works end-to-end
- [ ] AT-P3-3.3: Post-only orders placed and monitored correctly
- [ ] AT-P3-3.4: Guards block trades when thresholds breached
- [ ] AT-P3-3.5: SL/TP ladder installed on fill
- [ ] AT-P3-3.6: Manual-sign fallback functional
- [ ] AT-P3-3.7: Activity log persists all events
- [ ] AT-P3-3.8: Devnet E2E test passes
- [ ] AT-P3-3.9: Mainnet tiny size test passes
- [ ] AT-P3-3.10: Kill-switch cancels all orders
- [ ] AT-P3-3.11: Documentation complete

---

## Dependencies

### Backend (requirements.txt): ✅ INSTALLED
```
fastapi==0.104.1
uvicorn==0.24.0
motor==3.3.2
pydantic==2.5.0
PyJWT==2.8.0
pynacl==1.5.0
base58==2.1.1
fastapi-limiter==0.1.5
websockets==12.0
redis==5.0.1
aioredis==2.0.1
pyarrow==14.0.1
fastparquet==2023.10.1
aiohttp==3.9.1
```

### Frontend (package.json): ✅ INSTALLED
```json
{
  "d3": "^7.9.0",
  "d3-scale": "^4.0.2",
  "d3-array": "^3.2.4",
  "recharts": "^3.3.0",
  "@solana/wallet-adapter-react": "^0.15.35",
  "@solana/wallet-adapter-react-ui": "^0.9.35",
  "@solana/wallet-adapter-phantom": "^0.9.24",
  "@solana/web3.js": "^1.87.6"
}
```

### Workers (package.json): ⏳ TO ADD
```json
{
  "@drift-labs/sdk": "^2.98.0",
  "@solana/web3.js": "^1.95.8",
  "dotenv": "^16.3.1",
  "ws": "^8.14.2",
  "redis": "^4.6.10",
  "bn.js": "^5.2.1"
}
```

---

## Timeline

- **Sprint 1:** ✅ Complete (5 days)
- **Sprint 2:** ✅ Complete (7 days)
- **Sprint 3:** 🟡 In Progress (7-10 days estimated)
  - Days 1-2: Drift SDK integration + account decoding
  - Days 3-4: Delegation flow + execution engine
  - Days 5-6: Guards binding + SL/TP management
  - Days 7-8: E2E testing (devnet + mainnet)
  - Days 9-10: Documentation + polish

**Total Phase 3:** 19-22 days (3 weeks)

**Critical Path:** SDK decode → Delegation → ExecutionEngine → Guards → E2E Testing

---

## Application Status

**Phase 2:** ✅ 100% Complete
- Drift SDK integration operational
- SIWS authentication working
- Frontend fully functional
- Backend APIs responding
- Preview URL: https://solana-autotrader-3.preview.emergentagent.com

**Phase 3 Sprint 1:** ✅ 100% Complete
- All market data workers operational
- Live guards endpoint returning real-time data
- Redis Streams infrastructure working
- Parquet storage configured

**Phase 3 Sprint 2:** ✅ 100% Complete
- Basis calculation (USDT vs USDC) operational
- Helius webhook receiver deployed
- Drift liquidation map scanner running
- Market history endpoints functional
- Telemetry UI complete (cards, OI chart, liq heatmap)

**Phase 3 Sprint 3:** 🟡 In Progress (0% → targeting 100%)
- Next: Drift SDK v2 integration for account decoding
- Then: Delegation flow + execution engine
- Finally: E2E testing on devnet → mainnet

**Overall Phase 3 Progress:** ~67% Complete (Sprint 1 & 2 done, Sprint 3 in progress)
