#!/bin/bash
# Phase 3 Market Data Workers - Startup Script
# Starts all market data workers in background

echo "🚀 Starting Phase 3 Market Data Workers..."
echo ""

# Check Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Starting Redis..."
    redis-server --daemonize yes
    sleep 2
fi

echo "✅ Redis is running"
echo ""

# Start workers in background
echo "Starting Binance Trades + CVD worker..."
python3 /app/workers/market_data/binance_trades_cvd.py > /var/log/binance_trades.log 2>&1 &
TRADES_PID=$!
echo "  PID: $TRADES_PID"

echo "Starting Binance Book worker..."
python3 /app/workers/market_data/binance_book_top.py > /var/log/binance_book.log 2>&1 &
BOOK_PID=$!
echo "  PID: $BOOK_PID"

echo "Starting Liquidations worker..."
python3 /app/workers/market_data/liquidations_multi.py > /var/log/liquidations.log 2>&1 &
LIQ_PID=$!
echo "  PID: $LIQ_PID"

echo "Starting Bybit OI + Funding worker..."
python3 /app/workers/market_data/bybit_oi_funding.py > /var/log/bybit_oi_funding.log 2>&1 &
FUNDING_PID=$!
echo "  PID: $FUNDING_PID"

echo ""
echo "✅ All workers started!"
echo ""
echo "Worker PIDs:"
echo "  Trades:       $TRADES_PID"
echo "  Book:         $BOOK_PID"
echo "  Liquidations: $LIQ_PID"
echo "  Funding:      $FUNDING_PID"
echo ""
echo "Logs:"
echo "  tail -f /var/log/binance_trades.log"
echo "  tail -f /var/log/binance_book.log"
echo "  tail -f /var/log/liquidations.log"
echo "  tail -f /var/log/bybit_oi_funding.log"
echo ""
echo "To stop all workers:"
echo "  kill $TRADES_PID $BOOK_PID $LIQ_PID $FUNDING_PID"
echo ""
echo "Redis Streams:"
echo "  redis-cli XLEN market:solusdt:trades"
echo "  redis-cli XLEN market:solusdt:book"
echo "  redis-cli XLEN market:solusdt:liquidations"
echo "  redis-cli XLEN market:solusdt:funding"
echo ""
echo "Test guards endpoint:"
echo "  curl http://localhost:8001/api/engine/guards"
