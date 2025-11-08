# Phase 3 Implementation Specification

## Overview
**Goal:** Live market data integration powering real-time risk guards and UI telemetry.

**Delivery Mode:** Incremental sprints
- **Sprint 1 (Week 1):** Market data workers + live guards endpoint → ✅ **COMPLETE**
- **Sprint 2 (Week 2):** On-chain workers + basis calculation + UI telemetry → **IN PROGRESS**
- **Sprint 3 (Week 3):** Polish, testing, and optimization

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

#### 1.6 Worker Startup Script ✅
**File:** `/app/workers/start_market_data_workers.sh`

**Features:**
- Starts all 4 market data workers in background
- Checks Redis availability
- Logs to `/var/log/` with separate files per worker
- Provides PID tracking and monitoring commands

**Usage:**
```bash
/app/workers/start_market_data_workers.sh
```

---

## Sprint 2: In Progress (Week 2)

### Priority 1: Basis Calculation (USDT vs USDC)

#### 2.1 OKX USDC Price Worker
**File:** `/app/workers/market_data/okx_usdc_price.py` **[NEW]**

**Spec:**
- WebSocket: `wss://ws.okx.com:8443/ws/v5/public`
- Subscribe: `trades` channel for `SOL-USDC-SWAP`
- Process: Real-time trades → calculate last price
- Output: `{symbol, price, side, size, timestamp}`
- Publish: Redis Stream `market:solusdc:trades`

**Implementation:**
- Connect to OKX v5 public WebSocket
- Subscribe message:
  ```json
  {
    "op": "subscribe",
    "args": [{"channel": "trades", "instId": "SOL-USDC-SWAP"}]
  }
  ```
- Extract last trade price
- Update Redis Stream every trade (throttle to 1/sec for guards consumption)

**Docs:** https://www.okx.com/docs-v5/en/

---

#### 2.2 Basis Calculation Service
**File:** `/app/backend/services/basis.py` **[NEW]**

**Spec:**
- Read latest prices from:
  - USDT: Redis Stream `market:solusdt:trades` (Binance aggTrade)
  - USDC: Redis Stream `market:solusdc:trades` (OKX trades)
- Calculate: `basis_bps = ((px_usdc - px_usdt) / px_usdt) * 10000`
- Cache result with 5s TTL
- Expose via guards endpoint

**Implementation:**
```python
async def calculate_basis() -> float:
    usdt_px = await get_latest_price('market:solusdt:trades')
    usdc_px = await get_latest_price('market:solusdc:trades')
    if usdt_px and usdc_px:
        return ((usdc_px - usdt_px) / usdt_px) * 10000
    return 0.0
```

**Integration:** Wire into `/api/engine/guards` response

**DoD:**
- [ ] OKX worker streaming SOL-USDC-SWAP trades to Redis
- [ ] Basis calculation returns non-zero value during venue divergence
- [ ] Guards endpoint includes live `basis_bps` field
- [ ] Smoke test: `curl http://localhost:8001/api/engine/guards | jq '.basis_bps'`

---

### Priority 2: On-Chain Workers

#### 2.3 Helius Enhanced Webhooks Receiver
**File:** `/app/backend/routers/webhooks.py` **[NEW]**

**Spec:**
- Endpoint: `POST /api/webhooks/helius`
- Process: Enhanced webhook events → Redis queue
- Filter: Drift Protocol program IDs only
- Retry: Exponential backoff per Helius docs
- Deduplication: Track event IDs in Redis SET
- Output: `{event_type, account, signature, data, timestamp}`

**Publish:** Redis Stream `onchain:drift:events`
**Persist:** Parquet `/app/storage/parquet/helius/drift/YYYYMMDD.parquet`

**Drift Program IDs:**
- Drift V2: `dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH`

**Implementation:**
```python
@router.post("/webhooks/helius")
async def helius_webhook(payload: dict):
    # Validate signature
    # Filter for Drift program
    # Check deduplication
    # Publish to Redis Stream
    # Persist to Parquet
    return {"status": "ok"}
```

**Helius Webhook Setup:**
- Create Enhanced Webhook via Helius Dashboard
- Program Address: `dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH`
- Webhook URL: `https://<your-domain>/api/webhooks/helius`
- Event Types: All transaction types

**Docs:** https://www.helius.dev/docs/webhooks

**DoD:**
- [ ] Webhook endpoint receives and acks Drift events ≤1s
- [ ] Zero duplicates across restarts (Redis SET tracking)
- [ ] Events persisted to Parquet
- [ ] Smoke test: `curl -X POST http://localhost:8001/api/webhooks/helius -d '{...}'`

---

#### 2.4 Drift Liquidation Map Scanner
**File:** `/app/workers/onchain/drift_liq_map.py` **[NEW]**

**Spec:**
- Method: `getProgramAccounts` (gPA) scans + Drift SDK decode
- Frequency: Every 60 minutes (hourly refresh)
- Filter: Drift user accounts with open SOL-PERP positions
- Calculate: Liquidation price for each position
- Output: `{user_pubkey, market, position_size, entry_price, liq_price, distance_bps, collateral, leverage, timestamp}`

**Publish:** Redis Stream `onchain:drift:liq_map`
**Persist:** Parquet `/app/storage/parquet/drift/liq_map/latest.parquet` (overwrite)

**Drift Data API Integration:**
- Market metadata: `https://data.api.drift.trade/markets`
- Funding history: `https://data.api.drift.trade/fundingRates?marketIndex=0` (SOL-PERP)
- DLOB L2: `https://dlob.drift.trade/l2?marketIndex=0&marketType=perp`

**Implementation:**
```python
async def scan_drift_accounts():
    # Connect to Solana RPC (Helius)
    # gPA scan for Drift user accounts
    # Decode with Drift SDK
    # Filter for SOL-PERP positions
    # Calculate liquidation price per position
    # Enrich with funding rates from Data API
    # Publish to Redis Stream
    # Save to Parquet
```

**Liquidation Price Calculation:**
- Use Drift SDK's built-in liquidation price calculation
- Factor in: collateral, leverage, oracle price, maintenance margin
- Estimate distance to liquidation in bps

**Docs:**
- Drift SDK: https://drift-labs.github.io/v2-teacher/
- Funding: https://docs.drift.trade/trading/funding-rates

**DoD:**
- [ ] Parquet has ≥N entries with `{account, est_liq_px, updated_at}`
- [ ] Refresh completes ≤65 min
- [ ] Error rate <0.1% with retry logic
- [ ] Smoke test: `curl http://localhost:8001/api/onchain/liq-map | jq '.[0:3]'`

---

### Priority 3: UI Telemetry Dashboard

#### 2.5 Telemetry Cards Component
**File:** `/app/frontend/src/components/TelemetryCards.jsx` **[NEW]**

**Cards:**
1. **Spread** (bps, color-coded: green <5, yellow 5-10, red >10)
2. **Depth** (10bps bucket USD, bid + ask)
3. **Funding APR** (with 8h rate sparkline)
4. **Basis** (bps, USDT vs USDC)
5. **OI Notional** (formatted with M/B suffix)
6. **Liquidations** (5-min count)

**Data Source:** Poll `GET /api/engine/guards` every 5s

**Design:**
- Use Shadcn Card component
- Lime green (#84CC16) for positive/passing values
- Red (#F43F5E) for warning/breach values
- Monospace font (IBM Plex Mono) for numbers
- Icons from lucide-react

**Implementation:**
```jsx
export const TelemetryCards = () => {
  const [guards, setGuards] = useState(null);
  
  useEffect(() => {
    const fetchGuards = async () => {
      const data = await getGuards();
      setGuards(data);
    };
    
    fetchGuards();
    const interval = setInterval(fetchGuards, 5000);
    return () => clearInterval(interval);
  }, []);
  
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {/* Card components */}
    </div>
  );
};
```

**DoD:**
- [ ] Cards update ≤2s after API data changes
- [ ] Color coding matches thresholds
- [ ] Responsive layout (mobile + desktop)

---

#### 2.6 OI Chart Component
**File:** `/app/frontend/src/components/OIChart.jsx` **[NEW]**

**Spec:**
- Chart type: Area chart (Recharts)
- Data: Last 24 hours of OI notional (1-hour intervals)
- X-axis: Time (formatted HH:MM)
- Y-axis: OI notional (formatted with M/B)
- Color: Lime green (#84CC16) gradient

**Data Source:** New endpoint `GET /api/market/oi_history?hours=24`

**Backend Implementation:**
**File:** `/app/backend/routers/market.py` **[NEW]**

```python
@router.get("/market/oi_history")
async def get_oi_history(hours: int = 24):
    # Read from Redis Stream market:solusdt:funding
    # Aggregate to hourly buckets
    # Return [{timestamp, oi_notional}, ...]
```

**Frontend Implementation:**
```jsx
<ResponsiveContainer width="100%" height={300}>
  <AreaChart data={oiData}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="timestamp" />
    <YAxis />
    <Tooltip />
    <Area type="monotone" dataKey="oi_notional" stroke="#84CC16" fill="#84CC16" />
  </AreaChart>
</ResponsiveContainer>
```

**DoD:**
- [ ] Chart displays last 24 hours of data
- [ ] Updates every minute with new data
- [ ] Responsive and performant

---

#### 2.7 Funding APR Sparkline Component
**File:** `/app/frontend/src/components/FundingSparkline.jsx` **[NEW]**

**Spec:**
- Visualization: Small sparkline chart (Recharts)
- Data: Last 24 8-hour funding rates (3 per day × 24h = 72 samples)
- Display: Inline with Funding APR card
- Color: Lime green for positive, red for negative

**Data Source:** `GET /api/market/funding_history?hours=24`

**Backend Implementation:**
```python
@router.get("/market/funding_history")
async def get_funding_history(hours: int = 24):
    # Read from Redis Stream market:solusdt:funding
    # Return last N funding rate samples
    # [{timestamp, funding_rate_8h, funding_apr}, ...]
```

**DoD:**
- [ ] Sparkline shows 24h trend
- [ ] Color indicates positive/negative funding
- [ ] Updates every 8 hours (funding cycle)

---

#### 2.8 Liquidation Heatmap Component
**File:** `/app/frontend/src/components/LiqHeatmap.jsx` **[NEW]**

**Spec:**
- Visualization: D3.js heatmap
- Data: Liquidation clusters (price bins × time bins)
- Bins: 50 price levels × 12 time intervals (5-min each)
- Color scale: Green (low) → Yellow → Red (high)
- Tooltip: Show count + total size on hover
- Real-time: New liquidations add cells within 2s

**Data Source:** `GET /api/market/liq_heatmap?hours=1`

**Backend Implementation:**
```python
@router.get("/market/liq_heatmap")
async def get_liq_heatmap(hours: int = 1):
    # Read from Redis Stream market:solusdt:liquidations
    # Get current price from market:solusdt:trades
    # Create price bins: current_price ± 5% (50 bins)
    # Create time bins: last 60 min (12 × 5-min bins)
    # Aggregate: count + sum of sizes per bin
    # Return [{price_bin, time_bin, count, total_size}, ...]
```

**Frontend Implementation:**
```jsx
useEffect(() => {
  const svg = d3.select(svgRef.current);
  
  // Create heatmap with D3.js
  // Color scale: d3.scaleSequential(d3.interpolateRdYlGn)
  // Tooltip on hover
  
  // WebSocket listener for new liquidations
  ws.onmessage = (event) => {
    const liq = JSON.parse(event.data);
    updateHeatmap(liq);
  };
}, []);
```

**DoD:**
- [ ] Heatmap displays last 60 minutes of liquidations
- [ ] New liquidations appear within 2s
- [ ] Tooltip shows detailed info on hover
- [ ] Color scale is intuitive (green = safe, red = high liq activity)

---

## Redis Streams Schema

### Stream Keys:
- `market:solusdt:trades` - 1-minute trade bars (Binance)
- `market:solusdc:trades` - USDC price feed (OKX) **[NEW]**
- `market:solusdt:book` - Order book snapshots (100ms)
- `market:solusdt:liquidations` - Liquidation events (multi-venue)
- `market:solusdt:funding` - OI + funding rates (Bybit)
- `onchain:drift:events` - Helius webhook events **[NEW]**
- `onchain:drift:liq_map` - Drift liquidation map **[NEW]**

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

### Consumer Groups:
- `guards-consumer` - Reads for /api/engine/guards
- `telemetry-consumer` - Reads for UI updates
- `signals-consumer` - Reads for trading signals (Phase 4)

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
├── okx/                      [NEW]
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
├── helius/                   [NEW]
│   └── drift/
│       └── 20251108.parquet
└── drift/                    [NEW]
    └── liq_map/
        └── latest.parquet    (overwrite hourly)
```

**Rollup Schedule:**
- Hourly: Aggregate 1-minute bars into hourly bars
- Daily: Archive hourly bars to daily Parquet files
- Retention: 30 days (configurable)

---

## Acceptance Tests

### Sprint 1 Tests: ✅ PASSING

- [x] **AT-P3-1.1:** Binance trades CVD worker writes 1m bars to Redis Stream
- [x] **AT-P3-1.2:** Binance book worker reports TOB every second
- [x] **AT-P3-1.3:** Liquidations worker captures events from all 3 venues
- [x] **AT-P3-1.4:** Bybit poller returns OI + funding every 60s
- [x] **AT-P3-1.5:** Guards endpoint returns live data with <5s lag
- [x] **AT-P3-1.6:** Workers reconnect gracefully on connection loss

### Sprint 2 Tests: IN PROGRESS

- [ ] **AT-P3-2.1:** OKX worker streams SOL-USDC-SWAP trades to Redis
- [ ] **AT-P3-2.2:** Basis calculation returns non-zero value during divergence
- [ ] **AT-P3-2.3:** Guards endpoint includes live `basis_bps` field
- [ ] **AT-P3-2.4:** Helius webhook receives and acks Drift events ≤1s
- [ ] **AT-P3-2.5:** Drift liq-map parquet has ≥N entries, refreshes ≤65min
- [ ] **AT-P3-2.6:** Telemetry cards update ≤2s after data changes
- [ ] **AT-P3-2.7:** OI chart displays last 24 hours
- [ ] **AT-P3-2.8:** Liquidation heatmap shows new prints within 2s

### Sprint 3 Tests: PENDING

- [ ] **AT-P3-3.1:** Performance: Workers handle 1000 msgs/s without lag
- [ ] **AT-P3-3.2:** Resilience: System recovers from Redis outage
- [ ] **AT-P3-3.3:** Data integrity: Parquet files written without loss
- [ ] **AT-P3-3.4:** UI responsiveness: All components render <100ms

---

## Implementation Checklist

### Sprint 1: ✅ COMPLETE
- [x] Create `/app/workers/market_data/` directory
- [x] Implement `binance_trades_cvd.py`
- [x] Implement `binance_book_top.py`
- [x] Implement `liquidations_multi.py`
- [x] Implement `bybit_oi_funding.py`
- [x] Set up Redis Streams (install redis-py, configure streams)
- [x] Enhance `/app/backend/routers/engine.py` with live guards
- [x] Wire guards endpoint to Redis Streams with 5s cache
- [x] Test: All workers → Redis → Guards endpoint
- [x] Update `requirements.txt` (redis, aioredis, pyarrow, fastparquet)
- [x] Create startup script `/app/workers/start_market_data_workers.sh`

### Sprint 2: IN PROGRESS
- [ ] Implement `okx_usdc_price.py` (OKX SOL-USDC-SWAP trades)
- [ ] Create `/app/backend/services/basis.py` (USDT vs USDC calculation)
- [ ] Wire basis into `/api/engine/guards` response
- [ ] Create `/app/workers/onchain/` directory
- [ ] Implement `helius_receiver.py` (webhook endpoint)
- [ ] Add webhook route to FastAPI server
- [ ] Configure Helius webhook (Drift program IDs)
- [ ] Implement `drift_liq_map.py` (gPA scanner + SDK decode)
- [ ] Create `/app/backend/routers/market.py` (new endpoints)
- [ ] Implement `/api/market/oi_history`
- [ ] Implement `/api/market/funding_history`
- [ ] Implement `/api/market/liq_heatmap`
- [ ] Create `TelemetryCards.jsx`
- [ ] Create `OIChart.jsx`
- [ ] Create `FundingSparkline.jsx`
- [ ] Create `LiqHeatmap.jsx`
- [ ] Add D3.js to package.json
- [ ] Wire telemetry components to App.js
- [ ] Test: UI updates with live data

### Sprint 3: PENDING
- [ ] Performance testing and optimization
- [ ] Error handling and edge cases
- [ ] Responsive design polish
- [ ] Loading states and skeleton loaders
- [ ] Comprehensive E2E testing
- [ ] Documentation and runbook

---

## Dependencies

### Backend (requirements.txt): ✅ INSTALLED
```
redis==5.0.1
aioredis==2.0.1
pyarrow==14.0.1
fastparquet==2023.10.1
websockets==12.0
aiohttp==3.9.1
```

### Frontend (package.json): TO ADD
```json
{
  "d3": "^7.8.5",
  "d3-scale": "^4.0.2",
  "d3-array": "^3.2.4",
  "recharts": "^2.10.0"
}
```

---

## Monitoring & Observability

### Worker Health:
- Structured JSON logs with timestamps
- Redis Stream lengths: `redis-cli XLEN market:solusdt:trades`
- Worker process monitoring via startup script PIDs
- Log files: `/var/log/{binance_trades,binance_book,liquidations,bybit_oi_funding}.log`

### Redis Monitoring:
- Stream lengths (XLEN)
- Memory usage: `redis-cli INFO memory`
- Connection count: `redis-cli INFO clients`

### API Metrics:
- Guards endpoint response time (<5s target)
- Cache hit rate (5s TTL)
- Fallback activation count

---

## Smoke Tests

### Sprint 1 Smoke Tests: ✅ PASSING
```bash
# Verify Redis streams are populating
redis-cli XLEN market:solusdt:trades    # Should be > 0
redis-cli XLEN market:solusdt:book      # Should be > 0
redis-cli XLEN market:solusdt:funding   # Should be > 0

# Test live guards endpoint
curl http://localhost:8001/api/engine/guards | jq
# Should return non-null values for spread_bps, depth_10bps, funding_apr
```

### Sprint 2 Smoke Tests: TO RUN
```bash
# Test basis calculation
curl http://localhost:8001/api/engine/guards | jq '.basis_bps'
# Should return non-zero value

# Test Helius webhook
curl -X POST http://localhost:8001/api/webhooks/helius -d '{...}'
# Should return {"status": "ok"}

# Test liq-map endpoint
curl http://localhost:8001/api/onchain/liq-map | jq '.[0:3]'
# Should return array of liquidation estimates

# Test telemetry endpoints
curl http://localhost:8001/api/market/oi_history?hours=24 | jq
curl http://localhost:8001/api/market/liq_heatmap?hours=1 | jq
```

---

## Timeline

- **Sprint 1:** ✅ Complete (5 days)
- **Sprint 2:** In Progress (7 days estimated)
  - Days 1-2: Basis calculation + OKX worker
  - Days 3-4: On-chain workers (Helius + Drift)
  - Days 5-7: UI telemetry dashboard
- **Sprint 3:** Pending (3-5 days)
  - Testing, optimization, polish

**Total Estimated:** 15-17 days (2.5 weeks)

**Critical Path:** OKX worker → Basis → UI Telemetry → Testing

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

**Phase 3 Sprint 2:** 🟡 In Progress (0% → targeting 100%)
- Next: OKX USDC worker + basis calculation
- Then: On-chain workers (Helius + Drift liq-map)
- Finally: UI telemetry dashboard

**Overall Phase 3 Progress:** ~33% Complete (Sprint 1 done, Sprint 2 in progress, Sprint 3 pending)
