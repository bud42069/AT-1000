#!/bin/bash
# GitHub CLI Batch Setup for Phase 2 Close-Out
# Creates labels, project, and 18 issues with auto-linking

set -e

REPO="bud42069/AT-1000"

echo "🏗️  Setting up Phase 2 GitHub Infrastructure..."

# Step 1: Create labels
echo "📋 Creating labels..."
gh label create "frontend" --description "Frontend React components" --color "0E8A16" --repo $REPO || true
gh label create "backend" --description "Backend FastAPI/Python" --color "1D76DB" --repo $REPO || true
gh label create "workers" --description "Workers (signals, execution)" --color "FBCA04" --repo $REPO || true
gh label create "auth" --description "Authentication (SIWS, JWT)" --color "5319E7" --repo $REPO || true
gh label create "drift" --description "Drift Protocol integration" --color "B60205" --repo $REPO || true
gh label create "blockchain" --description "Blockchain transactions" --color "D93F0B" --repo $REPO || true
gh label create "security" --description "Security & hardening" --color "D4C5F9" --repo $REPO || true
gh label create "testing" --description "Testing & validation" --color "C2E0C6" --repo $REPO || true
gh label create "acceptance" --description "Acceptance tests" --color "C5DEF5" --repo $REPO || true
gh label create "websocket" --description "WebSocket real-time" --color "F9D0C4" --repo $REPO || true
gh label create "api" --description "API endpoints" --color "0052CC" --repo $REPO || true
gh label create "ui" --description "UI/UX components" --color "FEF2C0" --repo $REPO || true
gh label create "risk" --description "Risk management & guards" --color "E99695" --repo $REPO || true
gh label create "observability" --description "Logging & monitoring" --color "BFD4F2" --repo $REPO || true
gh label create "rate-limiting" --description "Rate limiting" --color "FFC274" --repo $REPO || true
gh label create "signals" --description "Signal generation" --color "006B75" --repo $REPO || true
gh label create "execution" --description "Order execution" --color "CC317C" --repo $REPO || true
gh label create "risk-management" --description "SL/TP management" --color "84B6EB" --repo $REPO || true
gh label create "kill-switch" --description "Kill switch & emergency" --color "D93F0B" --repo $REPO || true
gh label create "persistence" --description "Data persistence" --color "5319E7" --repo $REPO || true
gh label create "realtime" --description "Real-time updates" --color "D876E3" --repo $REPO || true

# Step 2: Create Project
echo "📊 Creating Phase 2 Project board..."
PROJECT_ID=$(gh project create --owner bud42069 --title "Phase 2: DoD-6 + Acceptance Tests" --format json | jq -r '.id') || true

# Step 3: Create DoD-6 Issues (Tasks 1-11)
echo "🎯 Creating DoD-6 task issues..."

ISSUE1=$(gh issue create --repo $REPO \
  --title "feat(auth): Wire SIWS login on wallet connect" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-1

**Tasks**:
- [ ] Import siwsLogin from ./lib/siws.js
- [ ] Add authenticated state to App component
- [ ] Call siwsLogin(wallet) after Phantom connection
- [ ] Store JWT in localStorage
- [ ] Add auth error handling with Sonner toast
- [ ] Handle hardware wallet fallback (Ledger via Phantom doesn't support signMessage)

**Estimate**: 2-3 hours

**DoD**: JWT stored, API calls include Authorization header, passes AT-1

**Gotcha**: Add graceful fallback for Ledger users who can't use signMessage" \
  --label "frontend,auth" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE2=$(gh issue create --repo $REPO \
  --title "feat(delegate): Implement Drift delegation transaction flow" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-2

**Tasks**:
- [ ] Add Enable Delegation button in ConsentModal
- [ ] Build updateUserDelegate instruction (client-side Drift SDK)
- [ ] Prompt Phantom to sign transaction
- [ ] Wait for confirmation (show loading spinner)
- [ ] Update delegationActive state on success
- [ ] Wire Revoke button in TopBar with confirmation dialog
- [ ] Mirror Drift delegate semantics in UX copy

**Estimate**: 3-4 hours

**DoD**: Delegation tx confirms on devnet, badge shows Active/Inactive, passes AT-2" \
  --label "frontend,drift,blockchain" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE3=$(gh issue create --repo $REPO \
  --title "feat(strategy): Connect strategy toggle to backend API" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-3

**Tasks**:
- [ ] Import updateSettings from ./lib/api.js
- [ ] Wire onToggle prop to API call with loading state
- [ ] Handle success/error with Sonner toasts
- [ ] Disable toggle when delegation inactive
- [ ] Add tooltip: 'Enable delegation first' when disabled

**Estimate**: 1-2 hours

**DoD**: Toggle calls PUT /api/settings, backend stores setting, disabled when inactive" \
  --label "frontend,api" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE4=$(gh issue create --repo $REPO \
  --title "feat(ws): Integrate WebSocket for real-time events" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-4

**Tasks**:
- [ ] Add WebSocket connection on component mount
- [ ] Connect to wss://.../api/ws/engine.events
- [ ] Implement JWT auth: pass short-TTL token in query string OR use Sec-WebSocket-Protocol
- [ ] Listen for all event types (order_submitted, filled, cancelled, etc.)
- [ ] Update activityLogs state on each event
- [ ] Trigger Sonner toasts with correct colors per event type
- [ ] Handle reconnection on disconnect (exponential backoff)

**Estimate**: 2-3 hours

**DoD**: Events appear in ActivityLog real-time, toasts display, reconnection works

**Gotcha**: Browsers can't set custom headers on WebSocket - use query string JWT or Sec-WebSocket-Protocol" \
  --label "frontend,websocket,realtime" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE5=$(gh issue create --repo $REPO \
  --title "feat(ui): Add guards display panel" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-5

**Tasks**:
- [ ] Poll /api/engine/guards every 10 seconds
- [ ] Display: spread_bps, depth_ok, liq_gap_atr_ok, funding_apr, basis_bps
- [ ] Color code based on thresholds (green < threshold, red >= threshold)
- [ ] Add tooltips explaining each guard
- [ ] Show last update timestamp

**Estimate**: 1 hour

**DoD**: Guards visible in UI panel, colors update dynamically, tooltips present" \
  --label "frontend,ui,risk" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE6=$(gh issue create --repo $REPO \
  --title "feat(auth): Enforce JWT on protected routes" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-6

**Tasks**:
- [ ] Import get_current_wallet from auth.siws
- [ ] Add wallet: str = Depends(get_current_wallet) to:
  - POST /api/engine/orders
  - POST /api/engine/cancel
  - POST /api/engine/kill
- [ ] Test: Call without JWT → 401 Unauthorized
- [ ] Test: Call with expired JWT → 401 Token expired
- [ ] Test: Call with valid JWT → Success with wallet extracted

**Estimate**: 30 min

**DoD**: All protected routes require valid JWT, 401 for unauthorized, wallet in logs" \
  --label "backend,security,auth" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE7=$(gh issue create --repo $REPO \
  --title "feat(security): Add rate limiting to API endpoints" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-7

**Tasks**:
- [ ] Add RateLimiter(times=5, seconds=60) to POST /api/engine/orders
- [ ] Add RateLimiter(times=10, seconds=60) to POST /api/auth/siws/verify (per IP)
- [ ] Test: Send 6 requests in 60s → 6th returns 429
- [ ] Test: Send 11 SIWS verify in 60s → 11th returns 429
- [ ] Log rate limit violations with wallet/IP

**Estimate**: 30 min

**DoD**: Orders limited 5/min per JWT, SIWS verify limited 10/min per IP, 429 responses" \
  --label "backend,security,rate-limiting" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE8=$(gh issue create --repo $REPO \
  --title "chore(version): Verify VERSION endpoint returns correctly" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-8

**Tasks**:
- [x] Already implemented in /api/engine/ping
- [ ] Verify: curl http://localhost:8001/api/engine/ping | jq .version
- [ ] Expected output: '1.0.0-phase2'
- [ ] Document in README

**Estimate**: 5 min

**DoD**: /api/engine/ping returns version from VERSION.txt, documented" \
  --label "backend,testing" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE9=$(gh issue create --repo $REPO \
  --title "feat(security): Security hardening checklist" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-9

**Tasks**:
- [ ] Add per-IP rate limit on /api/auth/siws/verify (already in Task 7)
- [ ] Add wallet pubkey logging to all engine actions (from JWT sub claim)
- [ ] Add request ID (req_id) to all logs (use uuid4 or middleware)
- [ ] Create market allow-list: ALLOWED_SYMBOLS=SOL-PERP in .env
- [ ] Enforce allow-list in POST /api/engine/orders (403 if symbol not in list)
- [ ] Test: Attempt BTC-PERP order → 403 Forbidden

**Estimate**: 1 hour

**DoD**: IP limiting active, logs include wallet+req_id, only SOL-PERP orders allowed" \
  --label "backend,security,observability" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE10=$(gh issue create --repo $REPO \
  --title "feat(observability): Add structured JSON logging" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-10

**Tasks**:
- [ ] Add correlation ID (req_id) to all logs
- [ ] Use JSON log format: {timestamp, level, req_id, wallet, message, ...}
- [ ] Add metrics logging: order_placement_rate, fill_rate, kill_switch_count, guard_failures
- [ ] Create /app/logs/engine.log for centralized logging
- [ ] Configure log rotation (size-based or time-based)
- [ ] Test: Place order → verify JSON log entry with all fields

**Estimate**: 1 hour

**DoD**: All logs structured JSON, correlation IDs present, metrics logged, log file exists" \
  --label "backend,observability" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

ISSUE11=$(gh issue create --repo $REPO \
  --title "test(e2e): Comprehensive testing agent validation" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#task-11

**Tasks**:
- [ ] Run AT-1 through AT-7 manually first
- [ ] Fix any obvious bugs found during manual testing
- [ ] Call testing_agent_v3 with full context from PHASE2_CLOSEOUT.md
- [ ] Read test report: /app/test_reports/iteration_X.json
- [ ] Fix all HIGH priority bugs
- [ ] Fix all MEDIUM priority bugs
- [ ] Fix all LOW priority bugs (do not skip)
- [ ] Re-run testing agent if major fixes applied
- [ ] Verify all tests GREEN
- [ ] Review git diff from testing agent

**Estimate**: 2-3 hours

**DoD**: All tests GREEN, no open HIGH/MEDIUM/LOW bugs, git diff reviewed and approved

**Dependencies**: Requires AT-1 through AT-7 issues completed" \
  --label "testing,e2e" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

# Step 4: Create Acceptance Test Issues (AT-1 through AT-7)
echo "✅ Creating Acceptance Test issues..."

AT1=$(gh issue create --repo $REPO \
  --title "test(at-1): Authentication flow validation" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#at-1

**Test Steps**:
1. Open preview URL in browser
2. Click Connect Wallet (Phantom)
3. Approve Phantom connection
4. Observe SIWS challenge fetch (Network tab)
5. Sign message in Phantom
6. Verify JWT stored in localStorage (at_token key)
7. Open DevTools → Network → Check subsequent API calls include Authorization: Bearer <JWT>
8. Call GET /api/engine/ping with JWT in Postman/curl
9. Verify response: {status: ok, version: 1.0.0-phase2, timestamp}

**Pass Criteria**:
- ✅ JWT stored in localStorage
- ✅ Authorization header present in all /api/engine/* calls
- ✅ Ping returns 200 with version

**Depends on**: Issue #${ISSUE1}" \
  --label "testing,acceptance,auth" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

AT2=$(gh issue create --repo $REPO \
  --title "test(at-2): Delegation flow on devnet" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#at-2

**Test Steps**:
1. Connect wallet (authenticated via AT-1)
2. Open consent modal and accept terms
3. Click Enable Delegation button
4. Approve updateUserDelegate transaction in Phantom
5. Wait for confirmation (~5-10s on devnet)
6. Verify badge shows 'Delegation: Active'
7. Verify strategy toggle becomes enabled
8. Click Revoke button in TopBar
9. Confirm revocation dialog
10. Approve revocation transaction in Phantom
11. Verify badge shows 'Delegation: Inactive'
12. Verify strategy toggle becomes disabled

**Pass Criteria**:
- ✅ Delegation tx confirms on devnet (check Solana Explorer)
- ✅ Badge updates to Active after setDelegate
- ✅ Revocation tx confirms
- ✅ Badge updates to Inactive after revoke
- ✅ Strategy toggle disabled when inactive

**Depends on**: Issue #${ISSUE2}" \
  --label "testing,acceptance,delegation" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

AT3=$(gh issue create --repo $REPO \
  --title "test(at-3): Signal to order execution on Drift" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#at-3

**Setup**:
\`\`\`bash
# Terminal 1: Start Binance signal worker
cd /app/workers
yarn ts-node signals/binance_cvd_vwap.ts

# Terminal 2: Monitor signal output
tail -f /app/data/signals/solusdt-1m.jsonl
\`\`\`

**Test Steps**:
1. Enable delegation (AT-2)
2. Enable strategy toggle in UI
3. Wait for VWAP reclaim signal (or manually append signal to jsonl file)
4. Observe signal worker emit OrderIntent
5. Observe engine receive intent (check worker logs)
6. Verify post-only order placed on Drift devnet
7. Query Drift UI or SDK for order confirmation
8. Verify ActivityLog shows 'order_submitted' event
9. Verify Sonner toast notification appears (cyan bg, info)

**Mock Signal** (if needed):
\`\`\`bash
echo '{\"ts\":1699999999999,\"symbol\":\"SOLUSDT\",\"signal\":\"longB\",\"confirm\":{\"vwap_reclaim\":true,\"cvd_trend\":\"up\"},\"intent\":{\"side\":\"long\",\"limitPx\":25.50,\"size\":0,\"slPx\":24.00,\"tpPx\":{\"p1\":27.50,\"p2\":29.00,\"p3\":30.50},\"leverage\":5}}' >> /app/data/signals/solusdt-1m.jsonl
\`\`\`

**Pass Criteria**:
- ✅ Signal emitted to /app/data/signals/solusdt-1m.jsonl
- ✅ Order appears on Drift devnet (visible in Drift UI or SDK query)
- ✅ ActivityLog shows event with correct details
- ✅ Toast notification displayed

**Depends on**: Issue #${ISSUE3}, #${ISSUE4}" \
  --label "testing,acceptance,signals" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

AT4=$(gh issue create --repo $REPO \
  --title "test(at-4): Cancel and replace with max 2 attempts" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#at-4

**Setup**:
Place order via engine, then simulate price drift

**Test Steps**:
1. Place post-only order (limitPx = 25.00) via engine
2. Simulate price drift to 26.00 (modify market price or wait)
3. Verify engine cancels original order
4. Verify engine places new order (limitPx = 26.00)
5. Check attempt count = 1 in logs
6. Simulate second drift to 27.00
7. Verify second cancel/replace executes
8. Check attempt count = 2 in logs
9. Simulate third drift to 28.00
10. Verify order abandoned (engine does NOT place 3rd attempt)
11. Check ActivityLog for:
    - 'order_replaced' event (2 times)
    - 'order_abandoned' event with reason: 'max_attempts'

**Pass Criteria**:
- ✅ Cancel/replace executes on first price drift
- ✅ Cancel/replace executes on second price drift
- ✅ Attempt count increments correctly (1 → 2)
- ✅ Order abandoned after 2 attempts (no 3rd attempt)
- ✅ All events logged in ActivityLog with correct details

**Depends on**: Issue #${ISSUE11}" \
  --label "testing,acceptance,execution" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

AT5=$(gh issue create --repo $REPO \
  --title "test(at-5): Stop-loss and take-profit ladder with BE move" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#at-5

**Test Steps**:
1. Place small order (0.1 SOL) via engine
2. Force fill (market order on devnet or wait for fill)
3. Query open orders via Drift SDK or UI
4. Verify 4 orders exist:
   - 1× stop-loss (trigger_market, reduce-only, 100% size)
   - 3× take-profits (trigger_limit, reduce-only, sizes: 50%/30%/20%)
5. Verify TP trigger prices: tp1 < tp2 < tp3 for long (reverse for short)
6. Simulate TP1 hit (price reaches tp1 level)
7. Verify engine moves SL to breakeven + fees
8. Query orders again via SDK
9. Verify SL trigger price = entry_price + estimated_fees (for long)
10. Check ActivityLog for events:
    - 'stops_installed'
    - 'tp_hit' (TP1)
    - 'sl_moved_to_be'
11. Verify toasts displayed for each event

**Pass Criteria**:
- ✅ SL + TP ladder visible on-chain (4 orders total)
- ✅ TP sizes correct: 50%, 30%, 20% of original position
- ✅ SL moves to BE+fees after TP1 hit
- ✅ All events logged in ActivityLog
- ✅ Toasts displayed for each state change

**Depends on**: Issue #${ISSUE11}" \
  --label "testing,acceptance,risk-management" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

AT6=$(gh issue create --repo $REPO \
  --title "test(at-6): Kill-switch triggers on guard breach" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#at-6

**Setup**:
Modify /api/engine/guards endpoint to return failing condition

**Test Steps**:
1. Place 2-3 orders via engine (all post-only on devnet)
2. Modify guards endpoint to return: {spread_bps: 30, ...} (exceeds 25 bps threshold)
3. Attempt to place new order
4. Verify engine detects guard breach BEFORE placing order
5. Verify engine calls kill-switch (cancels all open orders)
6. Check ActivityLog for 'kill_switch' event with reason: 'spread'
7. Verify toast notification: 'Kill Switch Activated: spread' (rose bg, error)
8. Verify strategy toggle automatically disabled
9. Verify no new orders can be placed until guards pass

**Pass Criteria**:
- ✅ All open orders cancelled on guard breach
- ✅ Kill-switch event logged with correct reason
- ✅ Strategy toggle disabled automatically
- ✅ Toast notification displayed
- ✅ New orders blocked until guards pass

**Depends on**: Issue #${ISSUE5}, #${ISSUE11}" \
  --label "testing,acceptance,kill-switch" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

AT7=$(gh issue create --repo $REPO \
  --title "test(at-7): Event persistence and UI display" \
  --body "**Ref**: PHASE2_CLOSEOUT.md#at-7

**Test Steps**:
1. Run AT-1 through AT-6 (generates diverse events)
2. Call GET /api/engine/activity
3. Verify response contains all events from previous tests:
   - order_submitted (multiple)
   - order_filled (if any fills occurred)
   - order_cancelled (from kill-switch in AT-6)
   - order_replaced (from AT-4, 2 times)
   - order_abandoned (from AT-4)
   - stops_installed (from AT-5)
   - tp_hit (from AT-5)
   - sl_moved_to_be (from AT-5)
   - kill_switch (from AT-6)
4. Check ActivityLog panel in UI
5. Verify all events displayed with:
   - Correct timestamps (ISO 8601 format)
   - Correct types (capitalized, underscores → spaces)
   - Correct details (order IDs, prices, reasons)
   - Correct status badges (colored per event type)
6. Verify events sorted by timestamp (newest first)
7. Verify no duplicate events
8. Verify no missing events

**Pass Criteria**:
- ✅ All events in GET /api/engine/activity response
- ✅ All events visible in UI ActivityLog panel
- ✅ Timestamps and details correct and complete
- ✅ Status badges colored correctly
- ✅ No duplicates or missing events
- ✅ Events sorted newest-first

**Depends on**: AT-1 through AT-6 completion" \
  --label "testing,acceptance,persistence" \
  --assignee "@me" | grep -oP '(?<=/issues/)\d+')

echo "✨ Phase 2 GitHub setup complete!"
echo ""
echo "📊 Summary:"
echo "  - 20 labels created"
echo "  - 1 project board created"
echo "  - 11 DoD-6 task issues created (#${ISSUE1}-#${ISSUE11})"
echo "  - 7 acceptance test issues created (#${AT1}-#${AT7})"
echo ""
echo "🔗 Next steps:"
echo "  1. Review issues: https://github.com/$REPO/issues"
echo "  2. Start with Issue #${ISSUE1} (SIWS integration)"
echo "  3. Use: gh issue develop <#> to auto-create feature branch"
echo "  4. Follow conventional commits format"
echo ""
