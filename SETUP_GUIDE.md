# Solana Auto-Trader - Complete Setup Guide

This guide will get the full automated trading system operational with live market data and real order execution.

## Prerequisites

### 1. Install Redis
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install redis-server

# macOS
brew install redis

# Start Redis
redis-server --daemonize yes

# Verify
redis-cli ping  # Should return "PONG"
```

### 2. Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Install Node/TypeScript Dependencies
```bash
cd workers
yarn install

cd ../frontend
yarn install
```

## Environment Configuration

### 1. Backend Environment Variables
Create or update `/app/backend/.env`:

```bash
# MongoDB (already configured)
MONGO_URL=mongodb://localhost:27017/autotrader

# Redis (NEW - required for live data)
REDIS_URL=redis://localhost:6379

# JWT Secret (already configured)
JWT_SECRET=your-secret-key-here

# Helius RPC (already configured)
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=625e29ab-4bea-4694-b7d8-9fdda5871969

# Helius Webhook Secret (NEW - for webhook auth)
HELIUS_WEBHOOK_SECRET=your-webhook-secret-here

# Delegate Keypair (NEW - required for automated trading)
# Generate: solana-keygen new --no-outfile
# Copy the base58 private key (first array in output)
DELEGATE_PRIVATE_KEY=your-base58-private-key-here

# CORS
CORS_ORIGINS=http://localhost:3000,https://solana-autotrader-3.preview.emergentagent.com

# Allowed trading symbols
ALLOWED_SYMBOLS=SOL-PERP,BTC-PERP,ETH-PERP

# Frontend origin
FRONTEND_ORIGIN=http://localhost:3000
```

### 2. Generate Delegate Keypair

```bash
# Install Solana CLI if needed
sh -c "$(curl -sSfL https://release.solana.com/stable/install)"

# Generate new keypair
solana-keygen new --no-outfile

# Output will show:
# pubkey: <PUBLIC_KEY>
# Save this base58 seed phrase:
# [1,2,3,4,5,...]  <- This is your DELEGATE_PRIVATE_KEY

# Convert array to base58 (if needed)
# Use the solana-keygen tool or a converter
```

## Starting the System

### Step 1: Start Backend Services

```bash
# Start FastAPI backend
cd backend
supervisorctl restart backend

# Verify backend is running
curl http://localhost:8001/api/engine/ping
```

### Step 2: Start Market Data Workers

```bash
# These workers stream live data to Redis
cd workers

# Start Binance trades worker (CVD + VWAP)
python3 market_data/binance_trades_cvd.py > /var/log/binance_trades.log 2>&1 &

# Start Binance book worker (TOB + depth)
python3 market_data/binance_book_top.py > /var/log/binance_book.log 2>&1 &

# Start Bybit OI + Funding worker
python3 market_data/bybit_oi_funding.py > /var/log/bybit_funding.log 2>&1 &

# Start OKX USDC price worker
python3 market_data/okx_usdc_price.py > /var/log/okx_usdc.log 2>&1 &

# Start liquidations worker
python3 market_data/liquidations_multi.py > /var/log/liquidations.log 2>&1 &

# Verify workers are streaming
redis-cli XLEN market:solusdt:trades     # Should grow over time
redis-cli XLEN market:solusdt:book
redis-cli XLEN market:solusdt:funding
```

### Step 3: Start Drift Workers (On-Chain)

```bash
cd workers

# Start Drift worker service (delegation endpoints)
ts-node drift_worker_service.ts > /var/log/drift_worker.log 2>&1 &

# Verify service
curl http://localhost:8002/health

# Start Drift liq-map scanner (optional - for liquidation map)
ts-node onchain/drift_liq_map.ts > /var/log/drift_liqmap.log 2>&1 &
```

### Step 4: Start Execution Engine

```bash
cd workers

# This consumes trading signals and executes orders
ts-node execution/engine.ts > /var/log/execution_engine.log 2>&1 &

# Verify it's listening
tail -f /var/log/execution_engine.log
```

### Step 5: Start Signal Worker (Generates Trading Signals)

```bash
cd workers

# This generates CVD+VWAP signals and publishes to Redis
ts-node signals/binance_cvd_vwap.ts > /var/log/signals.log 2>&1 &

# Verify signals are being generated
tail -f /var/log/signals.log
redis-cli XLEN engine:intents  # Should show incoming intents
```

### Step 6: Start Frontend

```bash
cd frontend
supervisorctl restart frontend

# Access at: http://localhost:3000
```

## Verifying Live Data

### 1. Check Redis Streams
```bash
# Trades stream (should have data after 1-2 minutes)
redis-cli XREVRANGE market:solusdt:trades + - COUNT 1

# Book stream (updates every second)
redis-cli XREVRANGE market:solusdt:book + - COUNT 1

# Funding stream (updates every minute)
redis-cli XREVRANGE market:solusdt:funding + - COUNT 1

# Intents stream (trading signals)
redis-cli XREVRANGE engine:intents + - COUNT 5
```

### 2. Check Backend APIs
```bash
# Live guards (should show real data)
curl http://localhost:8001/api/engine/guards | jq

# Market bars (price + CVD)
curl http://localhost:8001/api/market/bars?limit=5 | jq

# OI history
curl http://localhost:8001/api/history/oi?lookback=1h | jq

# Liquidation heatmap
curl http://localhost:8001/api/history/liqs?window=6h | jq
```

### 3. Frontend Live Data Checklist

Open http://localhost:3000 and verify:

- [ ] PriceCVDPanel shows real SOL price (not $20-25 mock)
- [ ] CVD values are realistic (thousands, not hundreds)
- [ ] TelemetryCards show live metrics (not static)
- [ ] Guards status updates every 5 seconds
- [ ] OI Chart has real data
- [ ] Wallet balance shows actual SOL

## Automated Trading Flow

### Prerequisites
1. Devnet wallet with SOL (for testing)
2. DELEGATE_PRIVATE_KEY configured in backend/.env
3. All workers running (see above)

### Enable Automated Trading

1. **Connect Wallet**
   - Click "Select Wallet" button
   - Choose Phantom
   - Approve connection

2. **Sign In with Solana (SIWS)**
   - Click "Sign In" after wallet connected
   - Approve signature in Phantom
   - JWT token stored in localStorage

3. **Enable Delegation**
   - Click "Enable Delegation" in TopBar
   - Approve setDelegate transaction in Phantom
   - Badge should show "Active" (green)

4. **Enable Strategy**
   - Toggle "Automation" switch in StrategyControls
   - Set leverage (default: 5x)
   - Set risk per trade (default: 0.75%)

5. **Monitor Activity**
   - Watch ActivityLog for trading events
   - Check console for WebSocket events
   - Orders appear when signals are generated

## Troubleshooting

### No Live Data in Frontend
```bash
# Check if workers are running
ps aux | grep python3.*market_data

# Check Redis streams
redis-cli XLEN market:solusdt:trades

# Check worker logs
tail -f /var/log/binance_trades.log
tail -f /var/log/binance_book.log
```

### No Orders Being Placed
```bash
# Check if signal worker is running
ps aux | grep binance_cvd_vwap

# Check if execution engine is running
ps aux | grep engine.ts

# Check Redis intents stream
redis-cli XLEN engine:intents

# Check execution engine logs
tail -f /var/log/execution_engine.log
```

### Workers Keep Crashing
```bash
# Check Redis is running
redis-cli ping

# Check environment variables are set
env | grep REDIS_URL
env | grep DELEGATE_PRIVATE_KEY

# Check logs for errors
tail -f /var/log/*.log
```

## Architecture Summary

```
┌─────────────────┐
│ Exchange APIs   │ (Binance, Bybit, OKX)
└────────┬────────┘
         │ WebSocket/HTTP
         ↓
┌─────────────────┐
│ Market Workers  │ (Python asyncio)
└────────┬────────┘
         │ Publish
         ↓
┌─────────────────┐
│ Redis Streams   │ (Message Bus)
└────────┬────────┘
         │ Consume
         ├──────→ Guards API (FastAPI)
         │              ↓
         │         Frontend (React)
         │
         └──────→ Signal Worker (TS)
                       ↓
                  engine:intents
                       ↓
                  Execution Engine (TS)
                       ↓ preflight guards
                  DriftAdapter
                       ↓
                  Drift Protocol (Solana)
```

## Next Steps

1. Install Redis on your local machine
2. Set all environment variables in backend/.env
3. Start all workers in sequence
4. Verify live data is flowing via curl commands
5. Connect wallet and enable delegation
6. Enable strategy automation
7. Monitor ActivityLog for orders

**Full setup time:** ~30 minutes
**Prerequisites:** Redis, Solana CLI, Devnet wallet with SOL
