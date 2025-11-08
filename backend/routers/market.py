"""
Market Data History & On-Chain Data Endpoints
Serves historical market data and Drift liquidation map
"""

from fastapi import APIRouter, Query
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import redis.asyncio as aioredis
import pyarrow.parquet as pq
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["market"])

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
STREAM_FUNDING = "market:solusdt:funding"
STREAM_LIQUIDATIONS = "market:solusdt:liquidations"
STREAM_LIQ_MAP = "onchain:drift:liq_map"

# Parquet paths
PARQUET_LIQ_MAP = "/app/storage/parquet/drift/liq_map/latest.parquet"


async def connect_redis():
    """Connect to Redis"""
    return await aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )


@router.get("/market/bars")
async def get_market_bars(
    symbol: str = Query(default="SOLUSDT"),
    limit: int = Query(default=60, le=1000)
):
    """
    Get recent 1-minute bars (OHLC, volume, CVD, VWAP)
    Data source: Binance trades worker → Redis Stream
    """
    try:
        # Read from Redis Stream
        redis = await connect_redis()
        
        result = await redis.xrevrange(
            "market:solusdt:trades",
            count=limit
        )
        
        await redis.close()
        
        # Parse results (newest first, so reverse)
        bars = []
        for entry_id, data in reversed(result):
            try:
                bars.append({
                    'timestamp': int(data.get('timestamp', 0)),
                    'open': float(data.get('open', 0)),
                    'high': float(data.get('high', 0)),
                    'low': float(data.get('low', 0)),
                    'close': float(data.get('close', 0)),
                    'volume': float(data.get('volume', 0)),
                    'buy_volume': float(data.get('buy_volume', 0)),
                    'sell_volume': float(data.get('sell_volume', 0)),
                    'cvd': float(data.get('cvd', 0)),
                    'vwap': float(data.get('vwap', 0))
                })
            except Exception as e:
                logger.error(f"Error parsing bar: {e}")
        
        return bars
    
    except Exception as e:
        logger.error(f"Error fetching market bars: {e}")
        return []


@router.get("/onchain/liq-map")
async def get_liq_map(
    limit: int = Query(default=100, le=1000),
    v: int = Query(default=1, ge=1, le=2)
):
    """
    Get Drift liquidation map (oracle-based estimates)
    Returns top N positions by distance to liquidation
    
    Query params:
    - limit: Max number of results (default: 100, max: 1000)
    - v: Version (1 = Python placeholder, 2 = TypeScript SDK)
    """
    try:
        # Select stream based on version
        stream_key = "onchain:drift:liq_map" if v == 1 else "onchain:drift:liq_map_v2"
        parquet_path = PARQUET_LIQ_MAP if v == 1 else PARQUET_LIQ_MAP.replace("liq_map", "liq_map_v2")
        
        # Try reading from Redis Stream first (latest data)
        redis = await connect_redis()
        
        result = await redis.xrevrange(stream_key, count=limit)
        await redis.close()
        
        if result:
            estimates = []
            for entry_id, data in result:
                estimates.append({
                    'account': data.get('account'),
                    'market_index': int(data.get('market_index', 0)),
                    'position_size': float(data.get('position_size', 0)),
                    'avg_entry_price': float(data.get('avg_entry_price', 0)),
                    'est_liq_px': float(data.get('est_liq_px', 0)),
                    'collateral_usd': float(data.get('collateral_usd', 0)),
                    'leverage': float(data.get('leverage', 0)),
                    'health': float(data.get('health', 0)),
                    'distance_bps': float(data.get('distance_bps', 0)),
                    'updated_at': int(data.get('updated_at', 0)),
                    'version': v
                })
            
            # Sort by distance_bps (closest to liquidation first)
            estimates.sort(key=lambda x: abs(x['distance_bps']))
            
            return estimates[:limit]
        
        # Fallback to Parquet if Redis empty
        if os.path.exists(parquet_path):
            # Try JSON fallback first (TS scanner saves as JSON temporarily)
            json_path = parquet_path.replace('.parquet', '.json')
            if os.path.exists(json_path):
                import json
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    return sorted(data, key=lambda x: abs(x.get('distanceBps', 0)))[:limit]
            
            # Try Parquet
            table = pq.read_table(parquet_path)
            df = table.to_pandas()
            
            # Sort by distance_bps
            df = df.sort_values('distance_bps', key=abs)
            
            result = df.head(limit).to_dict(orient='records')
            for item in result:
                item['version'] = v
            
            return result
        
        # Return empty if no data available
        return []
    
    except Exception as e:
        logger.error(f"Error fetching liq-map (v{v}): {e}")
        return []


@router.get("/history/oi")
async def get_oi_history(
    symbol: str = Query(default="SOLUSDT"),
    tf: str = Query(default="1m"),
    lookback: str = Query(default="24h")
):
    """
    Get Open Interest history
    Returns time series of OI notional values
    """
    try:
        # Parse lookback duration
        hours = int(lookback.rstrip('h'))
        cutoff_time = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000)
        
        # Read from Redis Stream
        redis = await connect_redis()
        
        result = await redis.xrange(
            STREAM_FUNDING,
            min=f"{cutoff_time}-0",
            count=hours * 60  # 1 per minute
        )
        
        await redis.close()
        
        # Parse results
        history = []
        for entry_id, data in result:
            try:
                ts = int(data.get('timestamp', 0))
                oi_notional = float(data.get('oi_notional', 0))
                
                history.append({
                    'ts': ts,
                    'notional': oi_notional
                })
            except Exception as e:
                logger.error(f"Error parsing OI entry: {e}")
        
        return history
    
    except Exception as e:
        logger.error(f"Error fetching OI history: {e}")
        return []


@router.get("/history/liqs")
async def get_liq_heatmap(
    symbol: str = Query(default="SOLUSDT"),
    window: str = Query(default="6h"),
    bucket_bps: int = Query(default=25)
):
    """
    Get liquidations heatmap data
    Returns price-bucketed liquidation counts and notional
    """
    try:
        # Parse window duration
        hours = int(window.rstrip('h'))
        cutoff_time = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000)
        
        # Get current price for bucketing
        redis = await connect_redis()
        
        # Get latest price
        trades_result = await redis.xrevrange("market:solusdt:trades", count=1)
        current_price = 0.0
        
        if trades_result:
            trade_data = trades_result[0][1]
            current_price = float(trade_data.get('close', 0))
        
        # Read liquidations from stream
        liq_result = await redis.xrange(
            STREAM_LIQUIDATIONS,
            min=f"{cutoff_time}-0"
        )
        
        await redis.close()
        
        if not current_price or not liq_result:
            return []
        
        # Create price buckets
        bucket_size = (bucket_bps / 10000) * current_price  # Convert bps to price range
        buckets = {}
        
        for entry_id, data in liq_result:
            try:
                price = float(data.get('price', 0))
                quantity = float(data.get('quantity', 0))
                
                # Determine bucket
                bucket_mid = round(price / bucket_size) * bucket_size
                
                if bucket_mid not in buckets:
                    buckets[bucket_mid] = {'count': 0, 'notional': 0.0}
                
                buckets[bucket_mid]['count'] += 1
                buckets[bucket_mid]['notional'] += price * quantity
            
            except Exception as e:
                logger.error(f"Error processing liq: {e}")
        
        # Convert to list
        heatmap = [
            {
                'px_mid': px,
                'count': data['count'],
                'notional': data['notional']
            }
            for px, data in sorted(buckets.items())
        ]
        
        return heatmap
    
    except Exception as e:
        logger.error(f"Error generating liq heatmap: {e}")
        return []
