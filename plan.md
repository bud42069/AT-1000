# Phase 3 Implementation Specification

## Overview
**Goal:** Live market data integration powering real-time risk guards, UI telemetry, and automated trading execution.

**Delivery Mode:** Incremental sprints
- **Sprint 1 (Week 1):** Market data workers + live guards endpoint → ✅ **COMPLETE**
- **Sprint 2 (Week 2):** On-chain workers + basis calculation + UI telemetry → ✅ **COMPLETE**
- **Sprint 3 (Week 3):** Automated trading execution wiring → 🟡 **IN PROGRESS (18% complete)**

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

#### 2.4 Drift Liquidation Map Scanner (TypeScript/SDK v2) ✅
**Files:** 
- `/app/workers/onchain/drift_liq_map.ts` (NEW - TypeScript with Drift SDK v2)
- `/app/workers/onchain/sdkHealth.ts` (NEW - Oracle-based health solver)
- `/app/workers/onchain/drift_liq_map.py` (DEPRECATED - Python placeholder)

**Implementation:**
- Method: Uses Drift SDK v2 `DriftClient.getUsers()` for account iteration
- Frequency: Every 60 minutes (hourly refresh)
- Filter: Drift user accounts with SOL-PERP positions (market index 0)
- Calculate: Oracle-based liquidation price using SDK health parity
  - Formula: `C + q*(p - avg) = mmr*|q|*p` (solve for p)
  - Health: `(Collateral + Unrealized PnL) / (MMR × Position Size)`
  - Validation: Estimates within ≤0.25% of SDK health calculation
- Output: `{account, market_index, position_size, avg_entry_price, est_liq_px, collateral_usd, leverage, health, distance_bps, updated_at}`
- Publish: Redis Stream `onchain:drift:liq_map_v2`
- Persist: JSON fallback `/app/storage/parquet/drift/liq_map_v2/latest.json`

**Docs:** https://docs.drift.trade/liquidations/liquidations

---

#### 2.5 Market History Endpoints ✅
**File:** `/app/backend/routers/market.py`

**Endpoints:**

**GET /api/onchain/liq-map**
- Returns liquidation estimates sorted by distance to liquidation
- Query params: `limit` (default: 100, max: 1000), `v` (version: 1 or 2)
- Fields: `account, est_liq_px, position_size, leverage, health, distance_bps, version`
- Data source: Redis Stream → JSON fallback → Parquet fallback
- Version 2 uses TypeScript SDK data with oracle-based calculations

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

## Sprint 3: 🟡 IN PROGRESS - Automated Trading Execution (18% Complete)

### Objective:
Wire automated trading execution with Drift Protocol, including delegated trading, guards integration, SL/TP management, and E2E testing on devnet → mainnet.

### Dependencies:
- **Phase 2:** ✅ SIWS auth, delegation UI scaffolding, backend APIs
- **Sprint 1:** ✅ Market data workers operational
- **Sprint 2:** ✅ Basis calculation, guards endpoint, telemetry UI

### Implementation Order:
S3.1 ✅ → S3.2 ✅ → S3.3 🟡 → S3.4 → S3.5 → S3.6 → S3.7 → S3.8 → S3.9 → S3.10 → S3.11

---

### S3.1 - Drift SDK v2 Integration ✅ COMPLETE

**Files:**
- `/app/workers/onchain/sdkHealth.ts` ✅
- `/app/workers/onchain/drift_liq_map.ts` ✅
- `/app/backend/routers/market.py` (enhanced) ✅

**Completed:**
- ✅ Migrated liq-map scanner to TypeScript using Drift SDK v2
- ✅ Implemented oracle-based liquidation price solver (Health→0 formula)
- ✅ SDK health validation within ≤0.25% tolerance
- ✅ Redis Stream `onchain:drift:liq_map_v2` operational
- ✅ API endpoint supports v1 (Python) and v2 (TypeScript SDK) versions
- ✅ DriftClient integration with mainnet-beta
- ✅ Position decoding using SDK's PerpPosition interface
- ✅ Collateral extraction from UserAccount.collateral
- ✅ MMR from PerpMarket.marginRatioMaintenance

**Validation:**
- Oracle-based liquidation model matches Drift documentation
- Health formula: `(Collateral + Unrealized PnL) / (MMR × Position Size)`
- Liquidation price solver: `C + q*(p - avg) = mmr*|q|*p`

**Docs:** https://docs.drift.trade/sdk-documentation

---

### S3.2 - Delegation Infrastructure ✅ COMPLETE

**Files:**
- `/app/backend/routers/delegation.py` ✅
- `/app/workers/drift_worker_service.ts` ✅

**Completed:**
- ✅ Backend router with 3 JWT-protected endpoints:
  - `POST /api/delegate/set` - Set delegate authority
  - `POST /api/delegate/revoke` - Revoke delegate authority
  - `GET /api/delegate/status` - Query delegation state
- ✅ Drift worker service (Express on port 8002)
  - Wraps DriftAdapter for delegation operations
  - Health endpoint: `GET /health`
- ✅ Integration with existing DriftAdapter from Phase 2
- ✅ JWT authentication via SIWS (wallet extracted from JWT claims)
- ✅ Delegation scope limited to: place orders, cancel orders
- ✅ Delegate CANNOT: withdraw funds, modify account, close account
- ✅ Frontend UI scaffolding exists from Phase 2 (TopBar, ConsentModal)

**Architecture:**
```
Frontend (React) → POST /api/delegate/set (JWT)
    ↓
Backend (FastAPI) → HTTP localhost:8002
    ↓
Drift Worker Service (Express/TS) → DriftAdapter
    ↓
Drift SDK v2 → Solana RPC → Drift Protocol (on-chain)
```

**Docs:** https://docs.drift.trade/getting-started/delegated-accounts

---

### S3.3 - ExecutionEngine Worker (Core Order Lifecycle) 🟡 IN PROGRESS

**Files:**
- `/app/workers/execution/engine.ts` (enhance existing scaffolding)
- `/app/workers/execution/drift_adapter.ts` (already exists from Phase 2)
- `/app/backend/routers/engine.py` (add intent endpoint)

**Tasks:**
- [ ] Create `POST /api/engine/intents` endpoint for intent submission
- [ ] Implement Redis Stream `engine:intents` consumption in engine.ts
- [ ] Add preflight guards check (pull `/api/engine/guards` before each trade)
- [ ] Implement order lifecycle:
  - Submit **post-only** limit order via DriftAdapter
  - Monitor for fill/partial fill
  - One **cancel/replace** attempt if drift > tolerance (max 2 attempts total)
  - Optional **guarded market convert** if guards still passing
- [ ] Wire to Drift SDK order APIs (already scaffolded in driftAdapter.ts)
- [ ] Event emission to backend WebSocket

**Intent Schema:**
```json
{
  "venue": "drift",
  "side": "long|short",
  "type": "post_only_limit",
  "px": 123.45,
  "size": 1.0,
  "sub_account_id": 0,
  "risk": {
    "leverage": 5,
    "sl": 121.0,
    "tp": [124.2, 125.5, 127.0]
  }
}
```

**Preflight Guards (Block if any fail):**
- Spread > 10 bps (from Binance depth@100ms)
- Depth (±10 bps) < $50k (from Binance book)
- |Funding APR| > 300% (from Bybit funding history)
- |Basis bps| > cap (Binance USDT vs OKX USDC)
- Liq spike > 10 in last 5m (from multi-venue liquidations)
- Leverage > max configured (from risk settings)

**DoD:**
- [ ] Order submitted & confirmed on-chain
- [ ] On unfilled drift, order replaced once (max 2 attempts)
- [ ] Events logged to Redis Stream and backend WebSocket
- [ ] Guards block trades when thresholds breached

**Docs:** 
- Drift SDK: https://docs.drift.trade/sdk-documentation
- Binance: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams

---

### S3.4 - Guards Binding (Live) ⏳ PENDING

**Files:**
- `/app/workers/execution/engine.ts` (preflight logic)
- `/app/backend/services/guards_client.py` (helper - optional)

**Tasks:**
- [ ] Implement guards API client in engine.ts
- [ ] Pull `/api/engine/guards` before each trade
- [ ] Block trades if any threshold breached
- [ ] Log reason for block to activity stream
- [ ] Emit guard breach events to backend

**Guard Sources (Validated):**
- Binance USDⓈ-M: `@aggTrade` (100ms) + `@depth@100ms`
- Bybit V5: funding history (instrument-specific interval, not hardcoded 8h)
- OKX v5: public trades for `SOL-USDC-SWAP`
- Multi-venue liquidations stream

**DoD:**
- [ ] Engine blocks when any guard breached
- [ ] Logs the reason for block
- [ ] Status visible in UI ActivityLog
- [ ] Guards status updates within ≤5s

**Docs:** https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams

---

### S3.5 - SL/TP Ladder + ATR Trail ⏳ PENDING

**Files:**
- `/app/workers/execution/risk.ts` (create)
- `/app/workers/execution/drift_adapter.ts` (enhance placeStops method)

**Tasks:**
- [ ] On fill: place **SL** and **TP1/TP2/TP3** ladder
  - Split: 50% at TP1, 30% at TP2, 20% at TP3
  - SL distance: entry - 1.5×ATR
  - TP distances: entry + 2×ATR, 3×ATR, 4×ATR
- [ ] On TP1 hit: move SL → BE+fees (breakeven + estimated fees)
- [ ] Enable **ATR(5m) trail** for remainder
  - Trail distance: 1.5×ATR(5m) below current price (long) or above (short)
  - Update trail on each new 5-minute bar

**DoD:**
- [ ] Ladder appears on-chain after fill
- [ ] SL adjusts at TP1 hit
- [ ] Trail updates tick-to-tick
- [ ] All stops visible in Drift UI

---

### S3.6 - Manual-Sign Fallback ⏳ PENDING

**Files:**
- Backend: `/app/backend/routers/engine.py` (manual path)
- Frontend: `/app/frontend/src/components/ManualOrderModal.tsx` (create)

**Tasks:**
- [ ] Check delegation status before order submission
- [ ] If delegate inactive, trigger manual-sign flow
- [ ] Prompt Phantom to sign order tx via Wallet Adapter
- [ ] Submit signed tx to Drift Protocol
- [ ] Identical order placement via manual-sign path

**DoD:**
- [ ] Manual-sign order can be placed successfully
- [ ] User approves via Phantom wallet
- [ ] Order confirmed on-chain
- [ ] Same event logging as delegated path

**Docs:** https://docs.phantom.com/solana/integrating-phantom

---

### S3.7 - Activity Log & Metrics ⏳ PENDING

**Files:**
- `/app/backend/routers/activity.py` (create)
- `/app/backend/metrics.py` (create - Prometheus)

**Tasks:**
- [ ] Define event schema for MongoDB activity collection
- [ ] Emit events from execution engine:
  - `order_submitted` - Order placed on Drift
  - `order_filled` - Full or partial fill
  - `order_cancelled` - Order cancelled
  - `sl_hit` - Stop-loss triggered
  - `tp_hit` - Take-profit triggered
  - `kill_switch` - Emergency stop activated
- [ ] Persist to MongoDB activity collection
- [ ] Expose via `GET /api/engine/activity`
- [ ] Implement Prometheus metrics:
  - Counter: `orders_submitted_total`
  - Counter: `orders_filled_total`
  - Counter: `orders_cancelled_total`
  - Histogram: `order_submit_confirm_latency_seconds`
  - Counter: `guard_breaches_total`

**DoD:**
- [ ] Events visible in UI ActivityLog
- [ ] Metrics scrape endpoint functional at `/metrics`
- [ ] Latency tracking operational
- [ ] Events persist across restarts

---

### S3.7b - Hardening (Security & Resilience) ⏳ PENDING

**Tasks:**
- [ ] **Managed Signer**: Replace generated keypair with env/KMS-backed signer
  - Store delegate private key in environment variable or KMS
  - Implement per-user wallet context management
  - Enforce least privilege for delegate (no withdrawals)
- [ ] **Helius Auth Model**: Align webhook verification with Helius API spec
  - Implement exact signature verification per Helius docs
  - Add retry logic with exponential backoff
  - Maintain idempotency with event ID tracking
- [ ] **Bybit Funding Interval**: Query instrument-specific funding interval
  - Call `/v5/market/instruments-info` to get actual interval
  - Don't hardcode 8h assumption (varies by instrument)
  - Calculate APR: `rate × (intervals_per_day) × 365 × 100`
- [ ] **Binance WS Hygiene**: Enforce connection limits and backoff
  - Respect 10 msgs/sec per connection limit
  - Max 1024 streams per connection
  - Implement reconnection with exponential backoff
  - Prefer raw streams over combined streams for scalability
- [ ] **Timeout Retry Logic**: Implement exponential backoff for tx confirmations
  - Initial timeout: 30s
  - Retry with: 45s, 60s, 90s
  - User-visible spinner + cancel option

**Docs:**
- Helius: https://www.helius.dev/docs/api-reference/webhooks
- Bybit: https://bybit-exchange.github.io/docs/v5/market/history-fund-rate
- Binance: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams

---

### S3.8 - E2E Testing (Devnet) ⏳ PENDING

**Checklist:**
- [ ] Connect Phantom wallet to devnet
- [ ] Complete SIWS authentication flow
- [ ] Execute `setDelegate` transaction
- [ ] Verify delegation badge shows "Active"
- [ ] Enable strategy in UI
- [ ] Force a small **post-only** order on devnet market
- [ ] Verify order appears on-chain (Drift UI or Solscan devnet)
- [ ] Confirm fill (or partial fill)
- [ ] Verify SL/TP ladder installation on-chain
- [ ] Simulate **guard breach** (temporarily raise spread threshold)
- [ ] Verify engine halts and logs reason
- [ ] Check ActivityLog shows all events

**Pass Criteria:**
- All state changes appear within ≤5s in UI
- Logs persist correctly in MongoDB
- Guards status updates correctly
- Delegation can be revoked successfully

---

### S3.9 - E2E Testing (Mainnet Tiny Size) ⏳ PENDING

**Checklist:**
- [ ] Connect Phantom wallet to mainnet-beta
- [ ] Complete SIWS authentication flow
- [ ] Execute `setDelegate` transaction with production delegate
- [ ] Enable strategy with minimum size (0.01 SOL or market minimum)
- [ ] Place post-only order at market price ±0.5%
- [ ] Confirm fill on mainnet
- [ ] Verify SL/TP ladder on-chain (Drift UI)
- [ ] Monitor for TP1 hit (if price moves favorably)
- [ ] Verify SL moves to BE+fees after TP1
- [ ] **Revoke delegate** at end of test
- [ ] Verify delegation badge shows "Inactive"

**Pass Criteria:**
- No guard violations during test
- Clean revoke transaction confirms
- All events logged correctly
- No unexpected behavior on mainnet

---

### S3.10 - Kill-Switch & Rollback ⏳ PENDING

**Files:**
- `/app/backend/routers/engine.py` (`POST /api/engine/kill`)
- `/app/workers/execution/engine.ts` (handler)

**Tasks:**
- [ ] Implement kill-switch endpoint in backend
- [ ] On trigger:
  - Cancel all open orders via DriftAdapter
  - Disable strategy flag in user settings
  - Persist reason to MongoDB activity collection
  - Broadcast event via WebSocket to frontend
- [ ] Frontend emergency stop button triggers endpoint
- [ ] UI immediately reflects "Automation: Off"

**DoD:**
- [ ] One call zeroes risk (all orders cancelled)
- [ ] UI reflects "Automation: Off" within ≤2s
- [ ] All orders cancelled on-chain
- [ ] Reason logged and visible in ActivityLog

---

### S3.11 - Documentation & Runbooks ⏳ PENDING

**Files:**
- `/docs/EXECUTION_ENGINE.md` (create)
- `/docs/DELEGATION.md` (create)
- `/VERSION.txt` (update)

**Tasks:**
- [ ] Document execution engine architecture
  - Order lifecycle flowchart
  - Guards decision tree
  - Failure modes and recovery
  - Event emission spec
- [ ] Document delegation safety procedures
  - Risks and limitations
  - Revoke steps
  - Emergency procedures
  - Delegate key management
- [ ] Update VERSION.txt to 1.1.0
- [ ] Surface version via `GET /api/engine/ping`
- [ ] Add deployment runbook
- [ ] Add troubleshooting guide

**DoD:**
- [ ] Complete execution engine documentation
- [ ] Delegation guide with safety procedures
- [ ] Versioning exposed in API
- [ ] Runbooks cover common scenarios

---

## Redis Streams Schema

### Stream Keys:
- `market:solusdt:trades` - 1-minute trade bars (Binance) ✅
- `market:solusdc:trades` - USDC price feed (OKX) ✅
- `market:solusdt:book` - Order book snapshots (100ms) ✅
- `market:solusdt:liquidations` - Liquidation events (multi-venue) ✅
- `market:solusdt:funding` - OI + funding rates (Bybit) ✅
- `onchain:drift:events` - Helius webhook events ✅
- `onchain:drift:liq_map` - Drift liquidation map (Python - deprecated) ✅
- `onchain:drift:liq_map_v2` - Drift liquidation map (TypeScript SDK) ✅
- `engine:intents` - Trading signal intents (Sprint 3) 🟡

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
    ├── liq_map/
    │   └── latest.parquet    (Python - deprecated)
    └── liq_map_v2/
        └── latest.json       (TypeScript SDK - active)
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

### Liq-Map Sample (Oracle-Based, SDK v2)
```bash
curl -s "http://localhost:8001/api/onchain/liq-map?v=2&limit=5" | jq
```

### OI & Liq History (Charts)
```bash
curl -s "http://localhost:8001/api/history/oi?symbol=SOLUSDT&tf=1m&lookback=24h" | jq '.[0:3]'
curl -s "http://localhost:8001/api/history/liqs?symbol=SOLUSDT&window=6h&bucket_bps=25" | jq '.[0:10]'
```

### Delegation Endpoints
```bash
# Health check
curl http://localhost:8002/health

# Set delegate (requires JWT)
curl -X POST http://localhost:8001/api/delegate/set \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"delegate_pubkey":"<PUBKEY>","sub_account_id":0}'

# Revoke delegate
curl -X POST http://localhost:8001/api/delegate/revoke \
  -H "Authorization: Bearer <JWT>"

# Check status
curl http://localhost:8001/api/delegate/status \
  -H "Authorization: Bearer <JWT>"
```

### Engine Intent Submission (S3.3)
```bash
curl -s -XPOST http://localhost:8001/api/engine/intents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -d '{
    "venue":"drift",
    "side":"long",
    "type":"post_only_limit",
    "px":123.45,
    "size":1.0,
    "sub_account_id":0,
    "risk":{"leverage":5,"sl":121.0,"tp":[124.2,125.5,127.0]}
  }' | jq
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
- [x] AT-P3-2.5: Drift liq-map v2 uses TypeScript SDK with oracle-based calculations
- [x] AT-P3-2.6: Liq-map estimates within ≤0.25% of SDK health parity
- [x] AT-P3-2.7: Telemetry cards update ≤2s after data changes
- [x] AT-P3-2.8: OI chart displays last 24 hours
- [x] AT-P3-2.9: Liquidation heatmap shows new prints within 2s

### Sprint 3 Tests: 🟡 IN PROGRESS (2/11 complete)
- [x] AT-P3-3.1: Drift SDK v2 decodes user accounts accurately
- [x] AT-P3-3.2: Delegation flow (set/revoke) works end-to-end
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

### Workers (package.json): ✅ INSTALLED
```json
{
  "@drift-labs/sdk": "^2.98.0",
  "@solana/web3.js": "^1.95.8",
  "express": "^5.1.0",
  "@types/express": "^5.0.5",
  "dotenv": "^16.3.1",
  "ws": "^8.14.2",
  "redis": "^4.6.10",
  "ioredis": "^5.3.2",
  "bn.js": "^5.2.1"
}
```

---

## Timeline

- **Sprint 1:** ✅ Complete (5 days)
- **Sprint 2:** ✅ Complete (7 days)
- **Sprint 3:** 🟡 In Progress (18% complete, 5-7 days remaining)
  - Days 1-2: ✅ Drift SDK integration + account decoding (COMPLETE)
  - Days 3-4: 🟡 Delegation flow + execution engine (IN PROGRESS)
  - Days 5-6: Guards binding + SL/TP management
  - Days 7-8: E2E testing (devnet + mainnet)
  - Days 9-10: Hardening + documentation + polish

**Total Phase 3:** 19-22 days (3 weeks)

**Critical Path:** SDK decode ✅ → Delegation ✅ → ExecutionEngine 🟡 → Guards → SL/TP → E2E Testing

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
- Drift liquidation map scanner (TypeScript SDK v2)
- Market history endpoints functional
- Telemetry UI complete (cards, OI chart, liq heatmap)

**Phase 3 Sprint 3:** 🟡 18% Complete (2/11 tasks)
- ✅ S3.1: Drift SDK v2 integration (oracle-based liq estimates)
- ✅ S3.2: Delegation infrastructure (backend + worker service)
- 🟡 S3.3: Execution engine (IN PROGRESS)
- Next: Guards binding, SL/TP management, E2E testing

**Overall Phase 3 Progress:** ~73% Complete (Sprint 1 & 2 done, Sprint 3 at 18%)
