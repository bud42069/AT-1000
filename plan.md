# Auto‑Trader dApp (Solana · Drift) — Development Plan

Context (locked): Helius RPC/Webhooks; public CEX data (Binance/Bybit/OKX); devnet execution + mainnet data; MVP E2E first (CVD+VWAP); Delegation primary, manual‑sign fallback. UI theme per design_guidelines.md (graphite + lime, Inter + IBM Plex Mono).

## 1) Objectives
- Ship a working E2E: Connect Phantom → SIWS consent → Delegated session → Simplified signal (1m CVD + VWAP reclaim) → Drift post‑only order → SL/TP ladder (BE at TP1) → Kill‑switch.
- Provide transparency: live telemetry, activity log, notifications, revocation at any time.
- Guardrails: leverage cap, risk per trade, priority‑fee cap, cancel/replace if stale, daily stop.
- Architecture ready for expansion: additional data feeds, signals, venues.

## 2) Phases (Core‑First → App → Features → Test/Polish)

### Phase 1 — Core POC (Isolation; do not proceed until green)
Goal: Prove delegated trading & event loop on Drift devnet with minimal UI.
- Websearch: latest Drift SDK delegate permissions (devnet), setDelegate, compute budget/priority‑fee best practices; Helius Enhanced Webhooks filters for delegate authority.
- Isolated script (TypeScript):
  - Generate ephemeral keypair; prompt Phantom to setDelegate (scoped: place/cancel orders; no withdrawals); TTL 24h.
  - Place post‑only limit on SOL‑PERP (devnet), confirm; if partial + price drifts beyond tol → cancel_and_replace (max 2 attempts).
  - On fill: immediately place SL + TP ladder; move SL → BE+fees at TP1.
  - Kill‑switch function: cancel open orders, disable loop.
- Backend stub (FastAPI): `/api/engine/kill`, `/api/engine/ping` to drive POC and emit structured logs.
- Success checks: confirmed signatures, order lifecycle events observed, revoke works.

User Stories (≥5):
1) As a user, I can delegate trading to an ephemeral key and see "Delegation: Active".
2) As a user, I can submit a post‑only test order on devnet and see confirmation.
3) As a user, I can watch an order be cancel/replaced when price moves past tolerance.
4) As a user, I see SL/TP ladder placed on fill and SL moves to BE at TP1.
5) As a user, I can hit Emergency Stop to cancel orders and disable automation instantly.

### Phase 2 — V1 App Development (E2E path)
Goal: Functional dApp UI + API + Engine worker wired to POC behaviors.
- Frontend (React+Tailwind+Shadcn): TopBar (Connect, DelegationBadge, EmergencyStop), Consent/SIWS modal, StrategyControls (toggle, leverage, risk, priority fee), Price+CVD panel, ActivityLog, Sonner toasts. All elems have data‑testids.
- Backend (FastAPI @ 0.0.0.0:8001; prefix /api):
  - REST: `POST /api/engine/orders`, `POST /api/engine/cancel`, `POST /api/engine/kill`, `GET /api/settings`, `PUT /api/settings`.
  - WS: `GET /api/ws/engine.events` to stream engine/order events to UI.
  - Session: SIWS message verify (simple), session heartbeat, store user settings (Mongo) with UUID ids.
- Engine Worker (TypeScript): wraps POC logic; implements ExecutionEngine v1.0 methods; connects to backend via HTTP/WS; devnet only in V1.
- Simplified signal: Binance fstream trades WS → 1m CVD + VWAP (client or small worker) → publish to UI; trigger demo entries when gate passes.
- Basic guards: leverage cap, post‑only, attempts ≤2, liq‑gap placeholder, priority‑fee cap.
- Logs: structured JSON with correlation ids; activity stored in Mongo.
- Design: apply tokens from design_guidelines.md (lime for CTAs, panels #11161C, focus lime ring, rounded‑2xl, shadow).

User Stories (≥5):
1) As a user, I connect Phantom and complete SIWS consent before enabling automation.
2) As a user, I can enable the strategy toggle and see live status + toasts.
3) As a user, I can set leverage/risk/priority fee caps and they apply to the next order.
4) As a user, I can view live price + CVD and see signal badges update in real time.
5) As a user, I can see activity log rows for submitted/cancelled/filled/SL/TP/error events.

### Phase 3 — Data Ingestion Infrastructure (CEX + On‑Chain)
Goal: Robust data plane, on‑chain plane, and unified minute signals.
- Python asyncio workers:
  - `ingest-trades-ws`: Binance SOLUSDT aggTrade → NDJSON + Parquet + minute CVD.
  - `ingest-liq-ws`: Binance forceOrder + OKX/Bybit liqs.
  - `poll-oi-funding`: Bybit/OKX/Binance REST periodic.
  - `ingest-book`: Binance depth@100ms → TOB snapshots.
- On‑chain:
  - `helius-receiver`: Enhanced Webhooks → queue; Drift account/liq intel.
  - `drift-liq-map`: scans + decode via Drift SDK → latest parquet.
- Message bus: Redis Streams; unified `signals.jsonl` minute feed.
- UI telemetry: funding/basis/oi/liq clusters bento; liquidation heatmap preview.

User Stories (≥5):
1) As a user, I see funding APR and basis bps update each minute.
2) As a user, I see nearest liquidation cluster distance and a heatmap preview.
3) As a user, I can filter the activity log by status (submitted/fill/stop/error).
4) As a user, I can download a daily activity export (JSONL/CSV).
5) As a user, I can view signal regime (on/off) affecting entries.

### Phase 4 — Advanced Signals, Risk Lattice & Polish
Goal: Production guardrails and UX polish; prepare tiny mainnet run.
- Guards: spread/depth, RSI gate, OBV‑cliff veto, liq‑gap ≥ 4×ATR(5m), funding/basis caps, daily hard stop.
- Execution: guarded market convert; attempt tracking; priority‑fee mgmt (cluster/Jito option later); manual‑sign fallback path.
- Revocation UX: explicit Revoke button; session invalidation; audits.
- Observability: Prometheus/Grafana, structured logs; dashboards for fills, errors, kill‑switch.
- Mainnet tiny‑size dry run: post‑only min size; capture audit.

User Stories (≥5):
1) As a user, trading halts when the daily stop is hit and shows a clear reason.
2) As a user, entries are vetoed when funding or basis exceeds caps.
3) As a user, SL/TP adjustments and BE move are visible in the log with timestamps.
4) As a user, I can revoke delegation and see trading disabled immediately.
5) As a user, I can switch to manual‑sign mode and sign each tx when desired.

## 3) Implementation Steps (high‑level checklist)
- Env: HELIUS_API_KEY, RPC_URL, DRIFT_ENV (devnet→mainnet later), PRIORITY_FEE_MICROLAMPORTS, DAILY_STOP_PCT, MAX_LEVERAGE, RISK_PER_TRADE_BP.
- Phase 1 POC script + minimal FastAPI endpoints; verify delegated flow and order lifecycle on devnet.
- Phase 2 bulk implementation (frontend + backend + engine worker) with simplified signal; wire WS events.
- Phase 3 data workers + Redis Streams + parquet layout; expand UI telemetry.
- Phase 4 guards + risk lattice + observability + revoke + mainnet tiny run.
- After each phase: call testing_agent for E2E, fix to green, then proceed.

## 4) API & Event Contracts (v1)
- POST /api/engine/orders { side, type:"post_only_limit", px, size, sl, tp1, tp2, tp3, leverage, venue:"drift", notes }
- POST /api/engine/cancel { orderId }
- POST /api/engine/kill { reason }
- GET/PUT /api/settings { max_leverage, risk_per_trade, daily_drawdown_limit, priority_fee_cap, delegate_enabled, strategy_enabled }
- WS /api/ws/engine.events → order_submitted|filled|cancelled|replaced|sl_hit|tp_hit|error|kill_switch

## 5) Next Actions (immediate)
- Create Phase 1 POC TypeScript script (delegate + post‑only lifecycle on devnet) and tiny FastAPI stub for kill.
- Wire envs; verify via devnet wallet; record signatures; prepare revoke flow.
- Implement minimal UI shell per design (TopBar with Connect/Delegate/E‑Stop; StrategyControls panel; ActivityLog table).
- Run testing_agent on POC+UI shell; iterate to green.

## 6) Success Criteria
- POC: Delegation works on devnet; order lifecycle confirmed; revoke disables trading.
- V1: E2E flow live with simplified signal; logs and toasts reflect events; kill‑switch reliable.
- Data plane: minute signals populated; telemetry visible; parquet written.
- Risk lattice: guards enforce limits; daily stop halts trading; priority fee caps applied.
- Go‑live checklist met: Phantom connect+SIWS+consent; delegated + manual‑sign; tiny mainnet post‑only passes; dashboards green.
