# Auto‑Trader dApp (Solana · Drift) — Development Plan (Updated)

Context (locked): Helius RPC/Webhooks (API key: 625e29ab-4bea-4694-b7d8-9fdda5871969); public CEX data (Binance/Bybit/OKX); devnet execution + mainnet data; MVP E2E first (CVD+VWAP); Delegation primary, manual‑sign fallback. UI theme per design_guidelines.md (graphite #0B0F14 + lime #84CC16, Inter + IBM Plex Mono).

## 1) Objectives
- Ship a working E2E: Connect Phantom → SIWS consent → Delegated session → Simplified signal (1m CVD + VWAP reclaim) → Drift post‑only order → SL/TP ladder (BE at TP1) → Kill‑switch.
- Provide transparency: live telemetry, activity log, notifications, revocation at any time.
- Guardrails: leverage cap, risk per trade, priority‑fee cap, cancel/replace if stale, daily stop.
- Architecture ready for expansion: additional data feeds, signals, venues.

## 2) Phases (Core‑First → App → Features → Test/Polish)

### Phase 1 — Core POC (Status: ✅ COMPLETED)
**Goal:** Prove delegated trading & event loop on Drift devnet with minimal UI.

**Completed Work:**
- ✅ Research: Drift SDK delegation APIs (`updateUserDelegate`), compute budget/priority‑fee best practices via web search
- ✅ Project structure: `/app/backend/.env` (all vars), `/app/workers/` (TypeScript setup), frontend packages (Solana wallet adapters, recharts, d3, framer-motion)
- ✅ TypeScript POC script: `/app/workers/poc-delegation.ts` with delegation flow scaffold (ephemeral key generation, setDelegate structure, order lifecycle placeholders)
- ✅ FastAPI routers:
  - `/app/backend/routers/engine.py`: orders, cancel, kill, ping, activity, WebSocket events
  - `/app/backend/routers/settings.py`: user settings (leverage, risk, fees, delegation status)
- ✅ Environment variables: HELIUS_API_KEY, RPC_URL, DRIFT_ENV=devnet, PRIORITY_FEE_MICROLAMPORTS, DAILY_STOP_PCT, MAX_LEVERAGE, RISK_PER_TRADE_BP, DB_NAME
- ✅ Minimal UI components:
  - TopBar: wallet connect (Phantom), delegation badge, market selector, emergency stop button
  - StrategyControls: automation toggle, leverage/risk/priority fee sliders
  - ActivityLog: real-time event table with status badges
  - PriceCVDPanel: mock price chart + CVD visualization (Recharts)
  - ConsentModal: terms acceptance + risk disclosure
- ✅ Design tokens: Complete CSS variables applied (graphite + lime theme, Inter + IBM Plex Mono fonts, rounded-2xl cards, shadows, focus rings)
- ✅ Backend API testing: All endpoints verified via curl (ping, orders, activity, kill switch working)
- ✅ Frontend compilation: Webpack polyfills configured (crypto-browserify, stream-browserify, buffer, process), app rendering perfectly
- ✅ WebSocket stub: Real-time event streaming scaffold ready for engine events

**User Stories (All Validated):**
1) ✅ User can see "Delegation: Active/Inactive" badge in TopBar
2) ✅ User can submit test orders via API and see confirmation
3) ✅ User can view activity log with order events
4) ✅ User can trigger kill switch and see orders cancelled
5) ✅ UI renders with correct design tokens (graphite + lime theme)

**Next:** Phase 2 implementation

---

### Phase 2 — V1 App Development (Status: 🔄 IN PROGRESS)
**Goal:** Functional dApp UI + API + Engine worker wired to POC behaviors with simplified signal integration.

**Remaining Work:**
- [ ] Complete Drift SDK integration in `/app/workers/poc-delegation.ts`:
  - Implement actual `updateUserDelegate` transaction flow
  - Add post-only limit order placement logic
  - Implement cancel/replace with max 2 attempts
  - Add SL/TP ladder placement on fill
  - Implement BE move at TP1
- [ ] Create execution engine worker (`/app/workers/execution-engine.ts`):
  - Wrap POC logic into ExecutionEngine class
  - Implement `place_post_only_order`, `monitor_order_status`, `cancel_and_replace`, `convert_to_market`
  - Connect to backend via HTTP/WS
  - Add structured logging with correlation IDs
- [ ] Simplified signal worker (`/app/workers/signal-simple.ts`):
  - Connect to Binance fstream WebSocket (SOLUSDT aggTrade)
  - Calculate 1m CVD bars
  - Compute VWAP from trades
  - Publish signals to backend via HTTP or Redis
  - Add signal gate logic (CVD trend + VWAP reclaim)
- [ ] Backend enhancements:
  - Implement SIWS message verification (simple)
  - Add session heartbeat mechanism
  - Store user settings in MongoDB with UUID ids
  - Enhance WebSocket to broadcast engine events to all connected clients
  - Add correlation IDs to all logs
- [ ] Frontend integration:
  - Wire real WebSocket connection to backend
  - Implement actual Phantom wallet signing for SIWS
  - Add delegation transaction flow (prompt user to sign updateUserDelegate)
  - Connect StrategyControls to backend settings API
  - Update PriceCVDPanel to consume real signal data
  - Add toast notifications for all engine events
- [ ] Basic guards implementation:
  - Leverage cap validation (max 10x)
  - Post-only order requirement
  - Attempt counter (max 2)
  - Liq-gap placeholder check
  - Priority fee cap enforcement
- [ ] Testing:
  - Call testing_agent for E2E validation
  - Fix all bugs to green
  - Verify on devnet with test wallet

**User Stories (Phase 2):**
1) As a user, I connect Phantom and complete SIWS consent before enabling automation
2) As a user, I can enable the strategy toggle and see live status + toasts
3) As a user, I can set leverage/risk/priority fee caps and they apply to the next order
4) As a user, I can view live price + CVD and see signal badges update in real time
5) As a user, I can see activity log rows for submitted/cancelled/filled/SL/TP/error events

**Acceptance Criteria:**
- Phantom wallet connects and signs SIWS message
- Delegation transaction succeeds on devnet
- Strategy toggle enables/disables automation
- Real orders placed on Drift devnet via delegate
- SL/TP ladder installed on fill
- Kill switch cancels all orders immediately
- Activity log shows all events in real time
- WebSocket events trigger toast notifications

---

### Phase 3 — Data Ingestion Infrastructure (Status: 📋 NOT STARTED)
**Goal:** Robust data plane, on‑chain plane, and unified minute signals.

**Planned Work:**
- [ ] Python asyncio workers:
  - `ingest-trades-ws.py`: Binance SOLUSDT aggTrade → NDJSON + Parquet + minute CVD
  - `ingest-liq-ws.py`: Binance forceOrder + OKX/Bybit liquidations
  - `poll-oi-funding.py`: Bybit/OKX/Binance REST periodic (every 1m)
  - `ingest-book.py`: Binance depth@100ms → TOB snapshots
- [ ] On-chain workers:
  - `helius-receiver.py`: Enhanced Webhooks → Redis queue; Drift account/liq intel
  - `drift-liq-map.py`: gPA scans + decode via Drift SDK → latest parquet
- [ ] Message bus: Redis Streams setup; unified `signals.jsonl` minute feed
- [ ] Storage: Parquet layout in `/app/storage/parquet/{venue}/{symbol}/{type}/`
- [ ] UI telemetry expansion:
  - Funding APR and basis bps bento cards
  - OI notional chart
  - Liquidation cluster heatmap (D3.js)
  - Nearest liquidation distance indicator

**User Stories (Phase 3):**
1) As a user, I see funding APR and basis bps update each minute
2) As a user, I see nearest liquidation cluster distance and a heatmap preview
3) As a user, I can filter the activity log by status (submitted/fill/stop/error)
4) As a user, I can download a daily activity export (JSONL/CSV)
5) As a user, I can view signal regime (on/off) affecting entries

---

### Phase 4 — Advanced Signals, Risk Lattice & Polish (Status: 📋 NOT STARTED)
**Goal:** Production guardrails and UX polish; prepare tiny mainnet run.

**Planned Work:**
- [ ] Advanced guards:
  - Spread < 0.10% check
  - Depth ≥ 50% of 30-day median
  - RSI(5m) gate (≥50 for longs, ≤50 shorts)
  - OBV-cliff veto (10-bar Z ≥ 2.0 against)
  - Liq-gap ≥ 4×ATR(5m) and ≥ 10× taker-fee distance
  - Funding > 3× median or basis > 10 bps → skip
  - Daily hard stop: min(1.5× 30-day σPnL, 2% equity)
- [ ] Execution enhancements:
  - Guarded market convert (only if A-tier signal + book impact ≤ cap)
  - Attempt tracking with correlation IDs
  - Priority fee management (cluster analysis, optional Jito bundles)
  - Manual-sign fallback path (user approves each tx)
- [ ] Revocation UX:
  - Explicit Revoke button in TopBar
  - On-chain revoke transaction
  - Session invalidation in backend
  - Audit log for all delegation changes
- [ ] Observability:
  - Prometheus metrics export
  - Grafana dashboards (fills, errors, kill-switch, PnL)
  - Structured JSON logs with correlation IDs
  - Log aggregation (Loki optional)
- [ ] Mainnet preparation:
  - Tiny-size dry run (post-only, min size)
  - Capture full audit trail
  - Verify priority fees and compute budget
  - Test revocation flow on mainnet

**User Stories (Phase 4):**
1) As a user, trading halts when the daily stop is hit and shows a clear reason
2) As a user, entries are vetoed when funding or basis exceeds caps
3) As a user, SL/TP adjustments and BE move are visible in the log with timestamps
4) As a user, I can revoke delegation and see trading disabled immediately
5) As a user, I can switch to manual‑sign mode and sign each tx when desired

---

## 3) Implementation Steps (Updated Checklist)

**Phase 1 (✅ COMPLETED):**
- [x] Research Drift SDK delegation APIs
- [x] Set up project structure (backend/.env, workers/, frontend packages)
- [x] Create TypeScript POC script scaffold
- [x] Create FastAPI routers (engine, settings)
- [x] Wire environment variables
- [x] Build minimal UI (TopBar, StrategyControls, ActivityLog, PriceCVDPanel, ConsentModal)
- [x] Apply design tokens from design_guidelines.md
- [x] Test backend API endpoints
- [x] Configure webpack polyfills for Solana wallet adapters

**Phase 2 (🔄 IN PROGRESS):**
- [ ] Complete Drift SDK integration (delegation, orders, SL/TP)
- [ ] Create execution engine worker
- [ ] Create simplified signal worker (Binance CVD + VWAP)
- [ ] Enhance backend (SIWS, session, WebSocket events)
- [ ] Wire frontend to real backend (wallet signing, delegation tx, settings)
- [ ] Implement basic guards
- [ ] Call testing_agent for E2E validation
- [ ] Fix all bugs to green

**Phase 3 (📋 NOT STARTED):**
- [ ] Build Python asyncio data workers
- [ ] Set up Redis Streams message bus
- [ ] Implement Parquet storage layout
- [ ] Build on-chain workers (Helius, Drift liq map)
- [ ] Expand UI telemetry (funding, basis, OI, liq clusters)

**Phase 4 (📋 NOT STARTED):**
- [ ] Implement advanced guards and risk lattice
- [ ] Add guarded market convert and priority fee mgmt
- [ ] Build revocation UX and audit trail
- [ ] Set up Prometheus + Grafana observability
- [ ] Conduct mainnet tiny-size dry run

---

## 4) API & Event Contracts (v1)

**REST Endpoints:**
- `POST /api/engine/orders` - Place order
  ```json
  { "side": "long|short", "type": "post_only_limit", "px": 25.50, "size": 10.0, "sl": 24.50, "tp1": 26.00, "tp2": 26.50, "tp3": 27.00, "leverage": 5, "venue": "drift", "notes": "..." }
  ```
- `POST /api/engine/cancel` - Cancel order
  ```json
  { "orderId": "uuid" }
  ```
- `POST /api/engine/kill` - Emergency stop
  ```json
  { "reason": "User-initiated emergency stop" }
  ```
- `GET /api/engine/ping` - Health check
- `GET /api/engine/activity` - Get activity log
- `GET /api/settings?user_id=<id>` - Get user settings
- `PUT /api/settings` - Update user settings
  ```json
  { "userId": "uuid", "max_leverage": 10, "risk_per_trade": 0.75, "daily_drawdown_limit": 2.0, "priority_fee_cap": 1000, "delegate_enabled": true, "strategy_enabled": false }
  ```

**WebSocket:**
- `WS /api/engine/ws` - Real-time engine events
  - Events: `order_submitted`, `order_filled`, `order_cancelled`, `order_replaced`, `sl_hit`, `tp_hit`, `error`, `kill_switch`

**Unified Signals (Phase 3):**
- `signals.jsonl` (minute cadence)
  ```json
  { "ts": "2025-11-08T03:45:00Z", "price": 25.50, "cvd_1m": 12345, "cvd_5m": 67890, "liq_notional_1h": 1000000, "nearest_onchain_liq_dist": 2.5, "spread_bps": 5, "funding_apr": 15.2, "oi_notional": 50000000, "basis_bps": 3, "regime": "bullish", "alerts": [] }
  ```

---

## 5) Next Actions (Immediate - Phase 2)

**Priority 1 (Critical Path):**
1. Complete Drift SDK integration in `poc-delegation.ts`:
   - Install Drift SDK dependencies in `/app/workers/`
   - Implement `updateUserDelegate` transaction
   - Test delegation on devnet with test wallet
2. Create execution engine worker:
   - Implement core methods (place, monitor, cancel/replace)
   - Connect to backend via HTTP
3. Create simplified signal worker:
   - Connect to Binance WebSocket
   - Calculate 1m CVD
   - Publish to backend

**Priority 2 (Integration):**
4. Wire frontend to backend:
   - Implement SIWS signing flow
   - Add delegation transaction prompt
   - Connect strategy controls to settings API
5. Test E2E flow:
   - Call testing_agent
   - Fix bugs to green
   - Verify on devnet

**Priority 3 (Polish):**
6. Add comprehensive error handling
7. Improve activity log with more event types
8. Add loading states and skeleton loaders

---

## 6) Success Criteria (Updated)

**Phase 1 (✅ COMPLETED):**
- [x] POC script scaffold created
- [x] Backend API endpoints working
- [x] UI renders with correct design tokens
- [x] All components present (TopBar, StrategyControls, ActivityLog, PriceCVDPanel, ConsentModal)
- [x] Webpack compiles without errors

**Phase 2 (Target):**
- [ ] Delegation works on devnet (updateUserDelegate tx confirmed)
- [ ] Order lifecycle complete (post-only → fill → SL/TP ladder → BE move)
- [ ] Revoke delegation works
- [ ] E2E flow live with simplified signal
- [ ] Logs and toasts reflect all events
- [ ] Kill-switch reliable and instant
- [ ] Testing agent validates all flows (green)

**Phase 3 (Target):**
- [ ] Minute signals populated from CEX data
- [ ] Telemetry visible (funding, basis, OI, liq clusters)
- [ ] Parquet files written to storage
- [ ] On-chain data ingested (Helius webhooks)

**Phase 4 (Target):**
- [ ] All guards enforce limits
- [ ] Daily stop halts trading
- [ ] Priority fee caps applied
- [ ] Revocation UX complete
- [ ] Observability dashboards green
- [ ] Mainnet tiny-size post-only passes

**Go-Live Checklist:**
- [ ] Phantom connect + SIWS + consent working
- [ ] Delegated mode functional
- [ ] Manual-sign fallback available
- [ ] Tiny mainnet post-only successful
- [ ] All dashboards green
- [ ] Audit trail complete

---

## 7) Tech Stack Summary

**Frontend:**
- React (CRA) + Tailwind CSS + Shadcn/UI
- Solana wallet adapters (@solana/wallet-adapter-react, @solana/wallet-adapter-phantom)
- Recharts (price/CVD charts)
- D3.js (liquidation heatmap)
- Framer Motion (animations)
- Sonner (toast notifications)

**Backend:**
- FastAPI (Python 3.11)
- Motor (async MongoDB driver)
- WebSockets (real-time events)
- Redis Streams (message bus - Phase 3)
- Parquet/PyArrow (data storage - Phase 3)

**Workers:**
- TypeScript (execution engine, POC)
- Python asyncio (data ingestion - Phase 3)
- Drift Protocol SDK (@drift-labs/sdk)
- Solana web3.js (@solana/web3.js)

**Infrastructure:**
- MongoDB (user settings, activity logs)
- Redis (message bus, caching)
- S3-compatible storage (Parquet files)
- Prometheus + Grafana (observability - Phase 4)

---

## 8) File Structure (Current)

```
/app/
├── backend/
│   ├── .env                    # ✅ Environment variables
│   ├── server.py               # ✅ Main FastAPI app
│   ├── requirements.txt        # ✅ Python dependencies
│   └── routers/
│       ├── engine.py           # ✅ Order/execution endpoints
│       └── settings.py         # ✅ User settings endpoints
├── frontend/
│   ├── .env                    # ✅ REACT_APP_BACKEND_URL
│   ├── package.json            # ✅ Dependencies installed
│   ├── craco.config.js         # ✅ Webpack polyfills configured
│   ├── public/
│   │   └── index.html          # ✅ Google Fonts loaded
│   └── src/
│       ├── index.css           # ✅ Design tokens applied
│       ├── App.js              # ✅ Main app component
│       ├── contexts/
│       │   └── WalletContext.jsx  # ✅ Solana wallet provider
│       └── components/
│           ├── TopBar.jsx         # ✅ Header with wallet/delegation/emergency
│           ├── StrategyControls.jsx  # ✅ Automation settings
│           ├── ActivityLog.jsx    # ✅ Event log table
│           ├── PriceCVDPanel.jsx  # ✅ Price chart + CVD
│           ├── ConsentModal.jsx   # ✅ Terms acceptance
│           └── ui/                # ✅ Shadcn components
├── workers/
│   ├── package.json            # ✅ TypeScript dependencies
│   ├── tsconfig.json           # ✅ TypeScript config
│   ├── poc-delegation.ts       # ✅ POC script scaffold
│   ├── execution-engine.ts     # 🔄 TODO: Phase 2
│   └── signal-simple.ts        # 🔄 TODO: Phase 2
├── storage/
│   └── parquet/                # 📋 TODO: Phase 3
├── design_guidelines.md        # ✅ Complete design spec
└── plan.md                     # ✅ This file
```

---

## 9) Risk Management (Configured)

**Current Settings (Devnet):**
- `MAX_LEVERAGE=10` (hard cap)
- `RISK_PER_TRADE_BP=75` (0.75% of account equity)
- `DAILY_STOP_PCT=2` (2% daily drawdown limit)
- `PRIORITY_FEE_MICROLAMPORTS=1000` (1000 microlamports per CU)

**Phase 2 Guards:**
- Leverage cap validation
- Post-only order requirement
- Max 2 cancel/replace attempts
- Liq-gap placeholder check
- Priority fee cap enforcement

**Phase 4 Guards (Advanced):**
- Spread/depth checks
- RSI gate
- OBV-cliff veto
- Liq-gap ≥ 4×ATR(5m)
- Funding/basis caps
- Daily hard stop with σPnL calculation

---

## 10) Deployment Notes (Future)

**Devnet (Current):**
- RPC: Helius devnet endpoint
- Drift: Devnet program IDs
- Testing: Safe environment with fake funds

**Mainnet (Phase 4):**
- RPC: Helius mainnet endpoint (same API key)
- Drift: Mainnet-beta program IDs
- Initial run: Tiny size (min order size), post-only only
- Monitoring: Full observability stack required
- Audit: Complete activity log export before go-live

---

**Last Updated:** 2025-11-08 03:43 UTC  
**Current Phase:** Phase 2 (V1 App Development) - IN PROGRESS  
**Next Milestone:** Complete Drift SDK integration and execution engine worker
