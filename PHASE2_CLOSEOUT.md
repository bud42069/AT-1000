# Phase 2 Close-Out Checklist

## Context
- **Status**: 85% Complete (DoD 1-5 ✅, DoD-6 pending)
- **Repo**: https://github.com/bud42069/AT-1000
- **Preview**: https://solana-autotrader-3.preview.emergentagent.com
- **Target**: 100% Phase 2 completion with all 6 acceptance tests passing

---

## DoD-6: Frontend Integration (9-13 hours)

### Task 1: SIWS Integration (2-3 hours)
**File**: `/app/frontend/src/App.js`

- [ ] Import `siwsLogin` from `./lib/siws.js`
- [ ] Add `authenticated` state to App component
- [ ] Call `siwsLogin(wallet)` after Phantom connection established
- [ ] Add loading state during auth ("Authenticating...")
- [ ] Store JWT in localStorage via `siwsLogin` response
- [ ] Update UI state to show authenticated status
- [ ] Handle auth errors with Sonner toast
- [ ] Test: Connect Phantom → SIWS challenge → Sign message → Receive JWT

**API Flow**:
```javascript
// 1. User clicks Connect Wallet
// 2. Phantom connects
// 3. Call siwsLogin(wallet):
//    - GET /api/auth/siws/challenge
//    - wallet.signMessage(challenge)
//    - POST /api/auth/siws/verify
//    - Store JWT in localStorage
// 4. All subsequent API calls include: Authorization: Bearer <JWT>
```

**Acceptance**: 
- JWT stored in localStorage after successful SIWS
- API calls include Authorization header
- Auth errors show toast notification

---

### Task 2: Delegate Flow (3-4 hours)
**Files**: 
- `/app/frontend/src/components/ConsentModal.jsx`
- `/app/frontend/src/components/TopBar.jsx`

**Delegate Button (ConsentModal):**
- [ ] Add "Enable Delegation" button after terms acceptance
- [ ] **Option A (Recommended)**: Client-side Drift SDK
  - [ ] Install `@drift-labs/sdk` in frontend (already done)
  - [ ] Create ephemeral delegate keypair client-side
  - [ ] Build `updateUserDelegate` instruction
  - [ ] Prompt Phantom to sign transaction
  - [ ] Wait for confirmation
- [ ] **Option B**: Server-built transaction
  - [ ] Create `/api/drift/delegate/build` endpoint
  - [ ] Return base64-encoded transaction
  - [ ] Prompt Phantom to sign
  - [ ] Submit via `sendAndConfirmTransaction`
- [ ] Show loading spinner during tx
- [ ] Update `delegationActive` state on success
- [ ] Show success toast: "Delegation enabled"
- [ ] Handle errors:
  - Insufficient SOL for tx fees → "Add SOL to wallet"
  - User rejects tx → "Delegation cancelled"
  - Transaction fails → "Transaction failed: {reason}"
- [ ] Test on devnet with real wallet

**Revoke Button (TopBar):**
- [ ] Wire "Revoke" button click handler
- [ ] Show confirmation dialog: "Revoke trading authority?"
- [ ] Call revoke flow (similar to delegate):
  - Option A: Client-side `updateUserDelegate(PublicKey.default)`
  - Option B: POST `/api/drift/delegate/revoke`
- [ ] Show loading spinner
- [ ] Update `delegationActive` state to false on success
- [ ] Show success toast: "Delegation revoked"
- [ ] Disable strategy toggle when delegation inactive
- [ ] Test revocation on devnet

**Acceptance**:
- Delegation tx confirms on devnet
- Badge shows "Active" after delegation
- Badge shows "Inactive" after revocation
- Strategy toggle disabled when inactive

---

### Task 3: Strategy Toggle Wiring (1-2 hours)
**File**: `/app/frontend/src/components/StrategyControls.jsx`

- [ ] Import `updateSettings` from `./lib/api.js`
- [ ] Wire `onToggle` prop to API call
- [ ] Show loading spinner during update
- [ ] Call `updateSettings({ userId: wallet.publicKey, strategy_enabled: enabled })`
- [ ] Handle success:
  - Update local state
  - Show toast: "Strategy enabled" / "Strategy disabled"
- [ ] Handle errors:
  - Show toast: "Failed to update settings: {error}"
- [ ] Disable toggle if delegation inactive
- [ ] Add tooltip: "Enable delegation first" when disabled
- [ ] Test toggle on/off

**Acceptance**:
- Toggle sends PUT `/api/settings` with strategy_enabled
- Backend receives and stores setting
- Toggle disabled when delegation inactive
- Success/error toasts display

---

### Task 4: WebSocket Integration (2-3 hours)
**File**: `/app/frontend/src/App.js`

- [ ] Add WebSocket connection on component mount
- [ ] Connect to: `wss://phantom-trader-4.preview.emergentagent.com/api/ws/engine.events`
- [ ] Use `useEffect` with cleanup on unmount
- [ ] Listen for events:
  - `order_submitted`
  - `order_filled`
  - `order_cancelled`
  - `order_replaced`
  - `sl_hit`
  - `tp_hit`
  - `sl_moved_to_be`
  - `kill_switch`
  - `error`
- [ ] Update `activityLogs` state on each event
- [ ] Trigger Sonner toasts:
  - `order_submitted` → Info (cyan bg)
  - `order_filled` → Success (lime bg)
  - `order_cancelled` → Warning (amber bg)
  - `sl_hit` / `tp_hit` → Info (cyan bg)
  - `sl_moved_to_be` → Success (lime bg)
  - `kill_switch` → Error (rose bg)
- [ ] Handle reconnection on disconnect (exponential backoff)
- [ ] Log connection status to console
- [ ] Test with mock events from backend

**WebSocket Flow**:
```javascript
useEffect(() => {
  if (!connected) return;
  
  const wsUrl = `wss://phantom-trader-4.preview.emergentagent.com/api/ws/engine.events`;
  const ws = new WebSocket(wsUrl);
  
  ws.onopen = () => console.log('✅ WS connected');
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleEngineEvent(data);
  };
  ws.onerror = (err) => console.error('WS error:', err);
  ws.onclose = () => {
    console.log('WS closed, reconnecting...');
    setTimeout(() => { /* reconnect */ }, 5000);
  };
  
  return () => ws.close();
}, [connected]);
```

**Acceptance**:
- WebSocket connects successfully
- Events appear in ActivityLog in real-time
- Toasts display for each event type
- Reconnection works after disconnect

---

### Task 5: Guards UI Display (1 hour)
**File**: `/app/frontend/src/components/PriceCVDPanel.jsx` or new component

- [ ] Poll `/api/engine/guards` every 10 seconds
- [ ] Display guard metrics in sidebar or panel:
  - Spread: `{spread_bps} bps` (green if < 10, red if >= 10)
  - Depth: `{depth_ok ? '✅' : '❌'}` OK
  - Liq Gap: `{liq_gap_atr_ok ? '✅' : '❌'}` OK
  - Funding APR: `{funding_apr}%` (green if < 500, red if >= 500)
  - Basis: `{basis_bps} bps` (green if < 10, red if >= 10)
- [ ] Add tooltips explaining each guard
- [ ] Update colors based on thresholds
- [ ] Test with mock data

**Acceptance**:
- Guards display in UI
- Colors update based on values
- Tooltips explain each guard

---

## Backend Polish (DoD-5 Quick Hits)

### Task 6: Enforce JWT on Protected Routes (30 min)
**File**: `/app/backend/routers/engine.py`

- [ ] Import `get_current_wallet` from `auth.siws`
- [ ] Add `wallet: str = Depends(get_current_wallet)` to:
  - `POST /api/engine/orders`
  - `POST /api/engine/cancel`
  - `POST /api/engine/kill`
- [ ] Test: Call without JWT → 401 Unauthorized
- [ ] Test: Call with expired JWT → 401 Token expired
- [ ] Test: Call with valid JWT → Success

**Acceptance**:
- All protected routes require valid JWT
- Unauthorized requests return 401
- Wallet address extracted from JWT claims

---

### Task 7: Rate Limiting (30 min)
**File**: `/app/backend/routers/engine.py`

- [ ] Add `@router.post("/orders", dependencies=[Depends(RateLimiter(times=5, seconds=60))])`
- [ ] Test: Send 6 requests in 60s → 6th returns 429
- [ ] Add rate limit to `/api/auth/siws/verify`: 10/min/IP
- [ ] Log rate limit violations

**Acceptance**:
- Orders endpoint limited to 5/min per JWT
- SIWS verify limited to 10/min per IP
- 429 status returned when exceeded

---

### Task 8: VERSION Verification (5 min)
**File**: `/app/backend/routers/engine.py`

- [x] Already implemented: `GET /api/engine/ping` returns version
- [ ] Verify: `curl http://localhost:8001/api/engine/ping | jq .version`
- [ ] Expected output: `"1.0.0-phase2"`

**Acceptance**:
- Ping returns version from VERSION.txt
- Version matches file content

---

## E2E Acceptance Tests (4-6 hours)

### AT-1: Authentication Flow (1 hour)
**Goal**: Verify SIWS authentication end-to-end

**Steps**:
1. Open preview URL in browser
2. Click "Connect Wallet"
3. Approve Phantom connection
4. Observe SIWS challenge fetch
5. Sign message in Phantom
6. Verify JWT stored in localStorage
7. Open DevTools → Network → Check subsequent API calls include `Authorization: Bearer <JWT>`
8. Call `GET /api/engine/ping` with JWT
9. Verify response includes version

**Pass Criteria**:
- JWT stored in localStorage: `at_token`
- Authorization header present in API calls
- Ping returns 200 with version

---

### AT-2: Delegation Flow (1 hour)
**Goal**: Enable and revoke delegation on devnet

**Steps**:
1. Connect wallet (authenticated)
2. Open consent modal
3. Accept terms
4. Click "Enable Delegation"
5. Approve transaction in Phantom
6. Wait for confirmation (~5-10s)
7. Verify badge shows "Delegation: Active"
8. Click "Revoke" in TopBar
9. Confirm revocation dialog
10. Approve transaction in Phantom
11. Verify badge shows "Delegation: Inactive"

**Pass Criteria**:
- Delegation tx confirms on devnet (check Solana Explorer)
- Badge updates to "Active"
- Revocation tx confirms
- Badge updates to "Inactive"
- Strategy toggle disabled when inactive

---

### AT-3: Signal→Order (1-2 hours)
**Goal**: Verify signal generates and engine places order

**Setup**:
```bash
# Terminal 1: Start Binance signal worker
cd /app/workers
yarn ts-node signals/binance_cvd_vwap.ts

# Terminal 2: Monitor signal output
tail -f /app/data/signals/solusdt-1m.jsonl
```

**Steps**:
1. Enable delegation (AT-2)
2. Enable strategy toggle
3. Wait for VWAP reclaim signal (or simulate)
4. Observe signal worker emit OrderIntent
5. Observe engine receive intent (check logs)
6. Verify post-only order placed on Drift devnet
7. Check Drift UI or query via SDK for order
8. Verify ActivityLog shows "order_submitted" event
9. Verify toast notification appears

**Pass Criteria**:
- Signal emitted to `/app/data/signals/solusdt-1m.jsonl`
- Order appears on Drift devnet
- ActivityLog shows event
- Toast notification displayed

**Mock Signal (if needed)**:
```bash
# Manually append signal to trigger engine
echo '{"ts":1699999999999,"symbol":"SOLUSDT","signal":"longB","confirm":{"vwap_reclaim":true,"cvd_trend":"up"},"intent":{"side":"long","limitPx":25.50,"size":0,"slPx":24.00,"tpPx":{"p1":27.50,"p2":29.00,"p3":30.50},"leverage":5}}' >> /app/data/signals/solusdt-1m.jsonl
```

---

### AT-4: Modify/Replace (1 hour)
**Goal**: Verify cancel/replace logic with attempt tracking

**Setup**:
- Place order via engine
- Simulate price drift (modify market price in guards mock)

**Steps**:
1. Place post-only order (limitPx = 25.00)
2. Simulate price drift to 26.00 (beyond tolerance)
3. Verify engine cancels original order
4. Verify engine places new order (limitPx = 26.00)
5. Check attempt count = 1
6. Simulate second drift to 27.00
7. Verify second cancel/replace
8. Check attempt count = 2
9. Simulate third drift to 28.00
10. Verify order abandoned (max 2 attempts reached)
11. Check ActivityLog for "order_replaced" (2x) and "order_abandoned" events

**Pass Criteria**:
- Cancel/replace executes on price drift
- Attempt count increments correctly
- Order abandoned after 2 attempts
- All events logged in ActivityLog

---

### AT-5: Stops/Targets (1-2 hours)
**Goal**: Verify SL/TP ladder and breakeven move

**Steps**:
1. Place small order (0.1 SOL) via engine
2. Force fill (market order or wait for devnet fill)
3. Query open orders via Drift SDK
4. Verify 4 orders exist:
   - 1 stop-loss (trigger_market, reduce-only)
   - 3 take-profits (trigger_limit, reduce-only, sizes: 50%/30%/20%)
5. Simulate TP1 hit (price reaches tp1)
6. Verify engine moves SL to BE+fees
7. Query orders again
8. Verify SL trigger price = entry + estimated fees
9. Check ActivityLog for:
   - "stops_installed"
   - "tp_hit"
   - "sl_moved_to_be"
10. Verify toasts displayed

**Pass Criteria**:
- SL + TP ladder visible on-chain
- TP sizes correct (50%/30%/20%)
- SL moves to BE after TP1
- All events logged and toasted

---

### AT-6: Kill-Switch (30 min)
**Goal**: Verify kill-switch on guard breach

**Setup**:
- Modify `/api/engine/guards` to return failing condition

**Steps**:
1. Place 2-3 orders via engine
2. Modify guards endpoint to return: `{ "spread_bps": 30, ... }` (over 25 bps threshold)
3. Attempt to place new order
4. Verify engine calls kill-switch
5. Verify all open orders cancelled
6. Check ActivityLog for "kill_switch" event with reason "spread"
7. Verify toast: "Kill Switch Activated: spread"
8. Verify strategy toggle disabled

**Pass Criteria**:
- Orders cancelled on guard breach
- Kill-switch event logged
- Reason included in event
- Strategy disabled after kill-switch

---

### AT-7: Persistence (30 min)
**Goal**: Verify all events persisted and displayed

**Steps**:
1. Run AT-1 through AT-6
2. Call `GET /api/engine/activity`
3. Verify response contains all events from previous tests:
   - order_submitted (multiple)
   - order_filled (if any)
   - order_cancelled (from kill-switch)
   - order_replaced (from AT-4)
   - order_abandoned (from AT-4)
   - stops_installed (from AT-5)
   - tp_hit (from AT-5)
   - sl_moved_to_be (from AT-5)
   - kill_switch (from AT-6)
4. Check ActivityLog panel in UI
5. Verify all events displayed with:
   - Correct timestamps
   - Correct types
   - Correct details
   - Correct status badges
6. Verify events sorted by timestamp (newest first)

**Pass Criteria**:
- All events in API response
- All events in UI ActivityLog
- Timestamps and details correct
- No duplicate or missing events

---

## Security & Ops Quick Wins (1 hour)

### Task 9: Security Hardening
**Files**: `/app/backend/server.py`, `/app/backend/.env`

- [x] CORS locked to preview domain (already done)
- [x] JWT-only auth (no cookies) (already done)
- [ ] Add per-IP rate limit on `/api/auth/siws/verify`: 10/min
- [ ] Add wallet pubkey logging on all engine actions
- [ ] Add request ID (`req_id`) to all logs
- [ ] Create market allow-list: `ALLOWED_SYMBOLS=SOL-PERP`
- [ ] Enforce allow-list in `/api/engine/orders`
- [ ] Test: Attempt to place order for non-allowed symbol → 403 Forbidden

**Acceptance**:
- IP rate limiting active
- All logs include wallet + req_id
- Only SOL-PERP orders allowed

---

### Task 10: Observability
**Files**: `/app/backend/server.py`, `/app/workers/execution/engine.ts`

- [ ] Add correlation ID to all logs
- [ ] Log format: `{"timestamp": "...", "level": "INFO", "req_id": "...", "wallet": "...", "message": "..."}`
- [ ] Add metrics logging:
  - Order placement rate
  - Fill rate
  - Kill-switch triggers
  - Guard failures
- [ ] Create log aggregation file: `/app/logs/engine.log`
- [ ] Test: Place order → verify log entry with all fields

**Acceptance**:
- All logs structured JSON
- Correlation IDs present
- Metrics logged
- Log file created

---

## Testing Agent Validation (2-3 hours)

### Task 11: Comprehensive E2E Testing
**Goal**: Run testing agent on full application

**Preparation**:
1. Ensure all AT-1 through AT-7 pass manually
2. Fix any bugs found during manual testing
3. Document all fixed issues

**Testing Agent Call**:
```json
{
  "original_problem_statement_and_user_choices_inputs": "Production-grade dApp for automated trading on Solana DEX perps (Drift). Connects to Phantom wallet, ingests real-time market data from CEX (Binance/Bybit/OKX), generates trading signals (CVD, liquidation clusters, basis/funding), and executes trades automatically with delegation/revocation controls. Features live telemetry, risk controls, emergency stop, and activity logs. User choices: Helius API key provided, public exchange APIs, devnet execution + mainnet data, E2E with simplified signal (CVD+VWAP), delegation primary with manual-sign fallback.",
  
  "features_or_bugs_to_test": [
    "SIWS authentication flow (challenge → sign → verify → JWT)",
    "Delegation flow (setDelegate tx → Active badge → revoke → Inactive)",
    "Strategy toggle (enable/disable automation)",
    "WebSocket event streaming (order_submitted, order_filled, etc.)",
    "Order placement via Drift SDK (post-only limit orders)",
    "SL/TP ladder installation on fill",
    "Cancel/replace logic with max 2 attempts",
    "Kill-switch on guard breach",
    "Activity log persistence and display",
    "Risk guards enforcement (spread, depth, liq-gap, funding, basis)",
    "Toast notifications for all events",
    "UI responsiveness and error handling"
  ],
  
  "files_of_reference": [
    "/app/backend/server.py",
    "/app/backend/auth/siws.py",
    "/app/backend/routers/engine.py",
    "/app/workers/execution/driftAdapter.ts",
    "/app/workers/execution/engine.ts",
    "/app/workers/signals/binance_cvd_vwap.ts",
    "/app/frontend/src/App.js",
    "/app/frontend/src/lib/siws.js",
    "/app/frontend/src/lib/api.js",
    "/app/frontend/src/components/TopBar.jsx",
    "/app/frontend/src/components/ConsentModal.jsx",
    "/app/frontend/src/components/StrategyControls.jsx",
    "/app/frontend/src/components/ActivityLog.jsx"
  ],
  
  "required_credentials": [
    "HELIUS_API_KEY (already in .env)",
    "Test wallet keypair for devnet (user must provide)",
    "Phantom wallet extension installed"
  ],
  
  "testing_type": "both",
  
  "agent_to_agent_context_note": {
    "description": "Phase 2 completion testing. All backend infrastructure (SIWS, WS, Drift adapter, signal worker, guards) complete and tested. Frontend wiring (DoD-6) completed. Running comprehensive E2E validation before sign-off."
  },
  
  "mocked_api": {
    "description": "Guards endpoint returns mock passing values (needs live data in Phase 3)",
    "value": {
      "has_mocked_apis": true,
      "mocked_apis_list": [
        "/api/engine/guards (returns mock spread/depth/liq-gap/funding/basis)"
      ]
    }
  }
}
```

**Post-Testing**:
- [ ] Read test report: `/app/test_reports/iteration_X.json`
- [ ] Fix all HIGH priority bugs
- [ ] Fix all MEDIUM priority bugs
- [ ] Fix all LOW priority bugs (do not skip)
- [ ] Re-run testing agent if major fixes
- [ ] Verify all tests GREEN

**Acceptance**:
- Testing agent report shows all tests passing
- No HIGH or MEDIUM priority bugs remain
- All LOW priority bugs fixed
- Git diff reviewed and approved

---

## Final Checklist (Sign-Off)

### Pre-Deployment Verification
- [ ] All 7 acceptance tests (AT-1 through AT-7) pass manually
- [ ] Testing agent validation complete (all tests GREEN)
- [ ] No open bugs in test report
- [ ] Frontend compiles without errors: `cd /app/frontend && yarn build`
- [ ] Backend starts without errors: `cd /app/backend && python server.py`
- [ ] Binance signal worker runs: `cd /app/workers && yarn ts-node signals/binance_cvd_vwap.ts`
- [ ] All API endpoints respond correctly:
  - `GET /api/engine/ping` → 200 with version
  - `GET /api/engine/guards` → 200 with metrics
  - `GET /api/auth/siws/challenge` → 200 with challenge
  - `POST /api/auth/siws/verify` → 200 with JWT (with valid signature)
  - `POST /api/engine/orders` → 200 with orderId (with valid JWT)
  - `WS /api/ws/engine.events` → connects successfully
- [ ] Logs structured JSON with correlation IDs
- [ ] VERSION.txt matches `/api/engine/ping` response
- [ ] All secrets in .env (no hardcoded keys)
- [ ] CORS restricted to preview domain
- [ ] Rate limiting active
- [ ] UI renders correctly (no console errors)
- [ ] All design tokens applied (graphite + lime theme)
- [ ] Responsive on desktop, tablet, mobile

### Documentation
- [ ] README updated with:
  - Setup instructions
  - Environment variables
  - Running workers
  - Testing instructions
  - API documentation
- [ ] PHASE2_CLOSEOUT.md reviewed
- [ ] plan.md updated to 100% complete

### Git & Deployment
- [ ] All changes committed
- [ ] Commit message: "feat: Phase 2 complete - DoD 1-6 + all acceptance tests passing"
- [ ] Push to GitHub
- [ ] Tag release: `v1.0.0-phase2`
- [ ] Update preview URL (if needed)
- [ ] Verify preview URL loads correctly

---

## Estimated Time Breakdown

| Task | Estimated Time |
|------|----------------|
| Frontend Integration (Tasks 1-5) | 9-13 hours |
| Backend Polish (Tasks 6-8) | 1 hour |
| Acceptance Tests (AT-1 through AT-7) | 4-6 hours |
| Security & Ops (Tasks 9-10) | 1 hour |
| Testing Agent Validation (Task 11) | 2-3 hours |
| **TOTAL** | **17-24 hours** |

---

## Success Criteria

**Phase 2 COMPLETE when:**
1. ✅ DoD-1 through DoD-6 all complete
2. ✅ All 7 acceptance tests pass
3. ✅ Testing agent report: all tests GREEN
4. ✅ No open HIGH/MEDIUM/LOW priority bugs
5. ✅ Documentation complete
6. ✅ Code committed and tagged
7. ✅ Preview URL functional

**Ready for Phase 3:** Data ingestion infrastructure (CEX streams, on-chain workers, Parquet storage)

---

## Notes

- **Devnet only**: All testing on Solana devnet with fake funds
- **Tiny size**: Use minimum order sizes (e.g., 0.1 SOL) for safety
- **Mocked guards**: Guards endpoint returns passing values (real data in Phase 3)
- **Manual signal**: Can manually append signal to trigger engine if needed
- **Helius rate limits**: 625 RPS on Developer plan (sufficient for testing)

---

**Last Updated**: 2025-11-08 04:45 UTC  
**Status**: Phase 2 - 85% → Target 100%  
**Next**: Complete Tasks 1-11 → Phase 2 COMPLETE ✅
