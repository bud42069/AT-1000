# Phase 3 Implementation Specification

## Overview
**Goal:** Live market data integration powering real-time risk guards and UI telemetry.

**Delivery Mode:** Incremental sprints
- **Sprint 1 (Week 1):** Market data workers + live guards endpoint → MVP
- **Sprint 2 (Week 2):** On-chain workers (Helius + Drift liq map)
- **Sprint 3 (Week 3):** UI telemetry dashboard (cards + charts)

**Storage/Transport:**
- Redis Streams as message bus (workers → API → UI)
- Parquet for historical data (hourly rollups)
- In-memory for dev; persist for backfills/debugging

---

## Priority 1: Market Data Workers (Python asyncio)

### 1.1 Binance Trades + CVD Worker
**File:** `/app/workers/market_data/binance_trades_cvd.py`

**Spec:**
- WebSocket: `wss://fstream.binance.com/ws/solusdt@aggTrade`
- Process: Real-time aggTrade → 1-minute bars
- Output: `{open, high, low, close, buy_vol, sell_vol, cvd, vwap, timestamp}`
- Publish: Redis Stream `market:solusdt:trades`
- Persist: Parquet `/app/storage/parquet/binance/SOLUSDT/trades/YYYYMMDD.parquet`

**Limits:**
- Max 10 msgs/s per connection
- Max 1024 streams per connection
- Reconnect with exponential backoff (1s, 2s, 4s, 8s, max 60s)

**Docs:** https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams

---

### 1.2 Binance Order Book Worker
**File:** `/app/workers/market_data/binance_book_top.py`

**Spec:**
- WebSocket: `wss://fstream.binance.com/ws/solusdt@depth@100ms`
- Maintain: Top-of-book (TOB) + 10bps depth snapshot
- Output: `{bid_px, bid_qty, ask_px, ask_qty, spread_bps, depth_10bps: {bid_usd, ask_usd}, timestamp}`
- Publish: Redis Stream `market:solusdt:book`
- Update frequency: 100ms

**Calculations:**
- `spread_bps = ((ask_px - bid_px) / mid_px) * 10000`
- `depth_10bps = sum of bid/ask qty within 10bps of mid`

**Docs:** https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Diff-Book-Depth-Streams

---

### 1.3 Multi-Venue Liquidations Worker
**File:** `/app/workers/market_data/liquidations_multi.py`

**Spec:**
- **Binance:** `wss://fstream.binance.com/ws/!forceOrder@arr` (filter `symbol=="SOLUSDT"`)
- **OKX:** WS v5 `liquidation-orders` channel (public)
- **Bybit:** V5 public liquidation topic

**Output per event:**
```json
{
  "venue": "binance|okx|bybit",
  "symbol": "SOLUSDT",
  "side": "long|short",
  "price": 150.5,
  "quantity": 10.5,
  "timestamp": 1699999999999
}
```

**Publish:** Redis Stream `market:solusdt:liquidations`
**Persist:** Parquet `/app/storage/parquet/liquidations/SOLUSDT/YYYYMMDD.parquet`

**Docs:**
- Binance: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams
- OKX: https://www.okx.com/docs-v5/en/
- Bybit: https://bybit-exchange.github.io/docs/api-explorer/v5/market/market

---

### 1.4 Bybit OI + Funding Poller
**File:** `/app/workers/market_data/bybit_oi_funding.py`

**Spec:**
- **Open Interest:** `GET /v5/market/open-interest?category=linear&symbol=SOLUSDT&intervalTime=5min`
- **Funding Rate:** `GET /v5/market/history-fund-rate?category=linear&symbol=SOLUSDT`
- Poll frequency: Every 60 seconds
- Output: `{oi_notional, funding_rate_8h, funding_apr, timestamp}`

**Calculations:**
- `funding_apr = funding_rate_8h * 3 * 365`

**Publish:** Redis Stream `market:solusdt:funding`
**Persist:** Parquet `/app/storage/parquet/bybit/SOLUSDT/funding/YYYYMMDD.parquet`

**Docs:**
- OI: https://bybit-exchange.github.io/docs/v5/market/open-interest
- Funding: https://bybit-exchange.github.io/docs/v5/market/history-fund-rate

---

## Priority 2: Live Guards Endpoint

### 2.1 Backend Guards Router Enhancement
**File:** `/app/backend/routers/guards.py` (new file)

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
  "status": "passing|warning|breach"
}
```

**Data Sources:**
- `spread_bps`, `depth_10bps`: From Redis Stream `market:solusdt:book` (latest)
- `funding_apr`: From Redis Stream `market:solusdt:funding` (latest)
- `basis_bps`: Calculate from USDT vs USDC venues (Binance SOLUSDT vs OKX SOL-USDC-SWAP)
- `oi_notional`: From Redis Stream `market:solusdt:funding` (latest)
- `liq_events_5m`: Count from Redis Stream `market:solusdt:liquidations` (last 5 minutes)

**Guard Thresholds:**
- `spread_bps > 10` → warning
- `depth_10bps < $50k` → warning
- `funding_apr > 300` → warning
- `liq_events_5m > 10` → warning

**Implementation:**
- Read from Redis Streams (XREAD with BLOCK 1000)
- Cache last values in memory (TTL 5s)
- Return cached + status evaluation

---

## Priority 3: On-Chain Workers

### 3.1 Helius Enhanced Webhooks Receiver
**File:** `/app/workers/onchain/helius_receiver.py`

**Spec:**
- Endpoint: `POST /api/webhooks/helius` (FastAPI route)
- Process: Enhanced webhook events → Redis queue
- Filter: Drift Protocol program IDs only
- Retry: Exponential backoff per Helius docs
- Output: `{event_type, account, data, timestamp}`

**Publish:** Redis Stream `onchain:drift:events`
**Persist:** Parquet `/app/storage/parquet/helius/drift/YYYYMMDD.parquet`

**Docs:** https://www.helius.dev/docs/api-reference/webhooks

---

### 3.2 Drift Liquidation Map Scanner
**File:** `/app/workers/onchain/drift_liq_map.py`

**Spec:**
- Method: getProgramAccounts (gPA) scans + Drift SDK decode
- Frequency: Every 5 minutes
- Filter: Drift user accounts with open positions
- Calculate: Liquidation price for each position
- Output: `{user, market, size, entry_px, liq_px, distance_bps, timestamp}`

**Publish:** Redis Stream `onchain:drift:liq_map`
**Persist:** Parquet `/app/storage/parquet/drift/liq_map/YYYYMMDD.parquet`

**Docs:** https://docs.drift.trade/trading/funding-rates

---

## Priority 4: UI Telemetry Dashboard

### 4.1 Telemetry Cards Component
**File:** `/app/frontend/src/components/TelemetryCards.jsx`

**Cards:**
1. **Funding APR** (sparkline + current value)
2. **Basis** (bps, USDT vs USDC)
3. **Spread** (bps, color-coded: green <5, yellow 5-10, red >10)
4. **OI Notional** (formatted with M/B suffix)

**Data Source:** Poll `GET /api/engine/guards` every 5s

**Design:**
- Use Shadcn Card component
- Lime green (#84CC16) for positive values
- Red (#F43F5E) for warning values
- Monospace font (IBM Plex Mono) for numbers

---

### 4.2 OI Chart Component
**File:** `/app/frontend/src/components/OIChart.jsx`

**Spec:**
- Chart type: Area chart (Recharts)
- Data: Last 24 hours of OI notional
- X-axis: Time (1-hour intervals)
- Y-axis: OI notional (formatted with M/B)
- Color: Lime green (#84CC16) gradient

**Data Source:** New endpoint `GET /api/market/oi_history?hours=24`

---

### 4.3 Liquidation Heatmap Component
**File:** `/app/frontend/src/components/LiqHeatmap.jsx`

**Spec:**
- Visualization: D3.js heatmap
- Data: Liquidation clusters (price bins × time bins)
- Bins: 50 price levels × 12 time intervals (5-min each)
- Color scale: Green (low) → Yellow → Red (high)
- Tooltip: Show count + total size on hover

**Data Source:** New endpoint `GET /api/market/liq_heatmap?hours=1`

**Binning Logic:**
- Price bins: Current price ± 5% (50 bins)
- Time bins: Last 60 minutes (12 × 5-min bins)
- Aggregate: Count + sum of liquidation sizes per bin

---

## Redis Streams Schema

### Stream Keys:
- `market:solusdt:trades` - 1-minute trade bars
- `market:solusdt:book` - Order book snapshots (100ms)
- `market:solusdt:liquidations` - Liquidation events
- `market:solusdt:funding` - OI + funding rates
- `onchain:drift:events` - Helius webhook events
- `onchain:drift:liq_map` - Drift liquidation map

### Message Format:
```
Stream: market:solusdt:trades
ID: 1699999999999-0
Fields:
  symbol: SOLUSDT
  open: 150.5
  high: 151.2
  low: 150.1
  close: 150.8
  buy_vol: 1500000
  sell_vol: 1400000
  cvd: 100000
  vwap: 150.6
  timestamp: 1699999999999
```

### Consumer Groups:
- `guards-consumer` - Reads for /api/engine/guards
- `telemetry-consumer` - Reads for UI updates
- `signals-consumer` - Reads for trading signals

---

## Parquet Storage Layout

```
/app/storage/parquet/
├── binance/
│   └── SOLUSDT/
│       ├── trades/
│       │   ├── 20251108.parquet
│       │   └── 20251109.parquet
│       └── book/
│           └── 20251108.parquet
├── bybit/
│   └── SOLUSDT/
│       └── funding/
│           └── 20251108.parquet
├── liquidations/
│   └── SOLUSDT/
│       └── 20251108.parquet
├── helius/
│   └── drift/
│       └── 20251108.parquet
└── drift/
    └── liq_map/
        └── 20251108.parquet
```

**Rollup Schedule:**
- Hourly: Aggregate 1-minute bars into hourly bars
- Daily: Archive hourly bars to daily Parquet files
- Retention: 30 days (configurable)

---

## Acceptance Tests

### AT-P3-1: Workers Online
- [ ] Binance trades CVD worker writes 1m bars to Redis Stream
- [ ] Binance book worker reports TOB every 100ms
- [ ] Liquidations worker captures events from all 3 venues
- [ ] Bybit poller returns OI + funding every 60s

### AT-P3-2: Guards Endpoint Live
- [ ] `GET /api/engine/guards` returns non-null values
- [ ] `spread_bps` updated within 5s lag
- [ ] `funding_apr` reflects latest 8h rate
- [ ] `liq_events_5m` counts last 5 minutes

### AT-P3-3: UI Telemetry
- [ ] Telemetry cards update as workers stream data
- [ ] OI chart displays last 24 hours
- [ ] Liquidation heatmap shows new prints within 2s

### AT-P3-4: Performance & Resilience
- [ ] Binance reconnection handles rate limits (no bans)
- [ ] Workers recover from Redis connection loss
- [ ] Parquet files written without data loss

---

## Implementation Checklist

### Sprint 1 (Week 1) - MVP
- [ ] Create `/app/workers/market_data/` directory
- [ ] Implement `binance_trades_cvd.py`
- [ ] Implement `binance_book_top.py`
- [ ] Implement `liquidations_multi.py`
- [ ] Implement `bybit_oi_funding.py`
- [ ] Set up Redis Streams (install redis-py, configure streams)
- [ ] Create `/app/backend/routers/guards.py`
- [ ] Wire guards endpoint to Redis Streams
- [ ] Replace mock values in `/api/engine/guards`
- [ ] Test: All workers → Redis → Guards endpoint
- [ ] Update `requirements.txt` (redis, aioredis, pyarrow, fastparquet)

### Sprint 2 (Week 2) - On-Chain
- [ ] Create `/app/workers/onchain/` directory
- [ ] Implement `helius_receiver.py`
- [ ] Add webhook route to FastAPI server
- [ ] Configure Helius webhook (Drift program IDs)
- [ ] Implement `drift_liq_map.py`
- [ ] Test: Helius events → Redis → Parquet
- [ ] Test: Drift liq map scanner → Redis → Parquet

### Sprint 3 (Week 3) - UI Telemetry
- [ ] Create `TelemetryCards.jsx`
- [ ] Create `OIChart.jsx`
- [ ] Create `LiqHeatmap.jsx`
- [ ] Add new API endpoints: `/api/market/oi_history`, `/api/market/liq_heatmap`
- [ ] Wire telemetry components to App.js
- [ ] Add D3.js to package.json
- [ ] Test: UI updates with live data
- [ ] Polish: Responsive design, loading states, error handling

---

## Dependencies to Add

### Backend (`requirements.txt`):
```
redis==5.0.1
aioredis==2.0.1
pyarrow==14.0.1
fastparquet==2023.10.1
websockets==12.0
aiohttp==3.9.1
```

### Frontend (`package.json`):
```json
{
  "d3": "^7.8.5",
  "d3-scale": "^4.0.2",
  "d3-array": "^3.2.4"
}
```

---

## Monitoring & Observability

### Worker Health Checks:
- Each worker exposes `/health` endpoint (HTTP server on separate port)
- Metrics: messages processed, errors, reconnections, latency

### Redis Monitoring:
- Stream lengths (XLEN)
- Consumer lag (XPENDING)
- Memory usage

### Logs:
- Structured JSON logs with correlation IDs
- Log levels: DEBUG (dev), INFO (prod), ERROR (always)
- Destinations: stdout (captured by supervisor)

---

**Estimated Timeline:**
- Sprint 1 (MVP): 5-7 days
- Sprint 2 (On-chain): 5-7 days
- Sprint 3 (UI): 5-7 days
- **Total: 15-21 days (3 weeks)**

**Critical Path:** Workers → Guards → UI
