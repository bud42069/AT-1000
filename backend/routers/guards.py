"""
Enhanced Guards Router - Live Market Data
Reads from Redis Streams populated by market data workers
Replaces mock values with real-time metrics
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import redis.asyncio as aioredis
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/engine", tags=["engine"])

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# Redis Streams
STREAM_TRADES = "market:solusdt:trades"
STREAM_BOOK = "market:solusdt:book"
STREAM_LIQUIDATIONS = "market:solusdt:liquidations"
STREAM_FUNDING = "market:solusdt:funding"

# Cache configuration
CACHE_TTL = 5  # seconds
cache = {}
cache_timestamps = {}


class RedisStreamsReader:
    """Redis Streams reader for market data"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        if not self.redis:
            try:
                self.redis = await aioredis.from_url(
                    REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("Connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    async def get_latest(self, stream_key: str) -> Optional[Dict[str, Any]]:
        """Get latest entry from stream"""
        try:
            await self.connect()
            
            # Read last entry from stream
            result = await self.redis.xrevrange(stream_key, count=1)
            
            if not result:
                return None
            
            # Parse result: [(id, {field: value, ...})]
            entry_id, data = result[0]
            
            # Convert numeric strings to floats
            parsed_data = {}
            for key, value in data.items():
                try:
                    # Try to convert to float
                    if '.' in value or 'e' in value.lower():
                        parsed_data[key] = float(value)
                    else:
                        parsed_data[key] = int(value)
                except (ValueError, AttributeError):
                    parsed_data[key] = value
            
            return parsed_data
        
        except Exception as e:
            logger.error(f"Error reading from stream {stream_key}: {e}")
            return None
    
    async def count_recent(self, stream_key: str, minutes: int) -> int:
        """Count entries in stream within last N minutes"""
        try:
            await self.connect()
            
            # Calculate timestamp N minutes ago
            cutoff_time = int((datetime.now(timezone.utc) - timedelta(minutes=minutes)).timestamp() * 1000)
            cutoff_id = f"{cutoff_time}-0"
            
            # Count entries after cutoff
            result = await self.redis.xrange(stream_key, min=cutoff_id)
            
            return len(result)
        
        except Exception as e:
            logger.error(f"Error counting entries in {stream_key}: {e}")
            return 0
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()


# Global reader instance
reader = RedisStreamsReader()


def is_cache_valid(key: str) -> bool:
    """Check if cache entry is still valid"""
    if key not in cache or key not in cache_timestamps:
        return False
    
    age = (datetime.now(timezone.utc) - cache_timestamps[key]).total_seconds()
    return age < CACHE_TTL


async def get_cached_or_fetch(key: str, fetch_fn) -> Any:
    """Get from cache or fetch and cache"""
    if is_cache_valid(key):
        return cache[key]
    
    value = await fetch_fn()
    cache[key] = value
    cache_timestamps[key] = datetime.now(timezone.utc)
    return value


@router.get("/guards")
async def get_guards():
    """
    Get current risk guard metrics (LIVE DATA)
    Returns real-time market data from Redis Streams
    """
    try:
        # Fetch all data concurrently with caching
        book_data = await get_cached_or_fetch("book", lambda: reader.get_latest(STREAM_BOOK))
        funding_data = await get_cached_or_fetch("funding", lambda: reader.get_latest(STREAM_FUNDING))
        liq_count = await get_cached_or_fetch("liq_count", lambda: reader.count_recent(STREAM_LIQUIDATIONS, 5))
        
        # Determine status based on guard thresholds
        status = "passing"
        warnings = []
        
        # Extract metrics with fallbacks
        spread_bps = 0.0
        depth_bid_usd = 0.0
        depth_ask_usd = 0.0
        funding_apr = 0.0
        oi_notional = 0.0
        
        # Book metrics
        if book_data:
            spread_bps = book_data.get('spread_bps', 0.0)
            depth_bid_usd = book_data.get('depth_10bps_bid_usd', 0.0)
            depth_ask_usd = book_data.get('depth_10bps_ask_usd', 0.0)
            
            # Guard: Spread too wide
            if spread_bps > 10:
                status = "warning"
                warnings.append(f"Spread: {spread_bps:.2f}bps (>10bps)")
            
            # Guard: Insufficient depth
            if depth_bid_usd < 50000 or depth_ask_usd < 50000:
                status = "warning"
                warnings.append(f"Depth: ${min(depth_bid_usd, depth_ask_usd):,.0f} (<$50k)")
        
        # Funding metrics
        if funding_data:
            funding_apr = funding_data.get('funding_apr', 0.0)
            oi_notional = funding_data.get('oi_notional', 0.0)
            
            # Guard: Extreme funding
            if abs(funding_apr) > 300:
                status = "warning"
                warnings.append(f"Funding APR: {funding_apr:.1f}% (|x|>300%)")
        
        # Liquidation metrics
        liq_events_5m = liq_count if isinstance(liq_count, int) else 0
        
        # Guard: High liquidation activity
        if liq_events_5m > 10:
            status = "breach"
            warnings.append(f"Liquidations: {liq_events_5m} in 5min (>10)")
        
        # Calculate basis (placeholder - needs multi-venue price data)
        # TODO: Implement USDT vs USDC basis calculation
        basis_bps = 0.0
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "spread_bps": round(spread_bps, 2),
            "depth_10bps": {
                "bid_usd": round(depth_bid_usd, 2),
                "ask_usd": round(depth_ask_usd, 2)
            },
            "funding_apr": round(funding_apr, 2),
            "basis_bps": round(basis_bps, 2),
            "oi_notional": round(oi_notional, 2),
            "liq_events_5m": liq_events_5m,
            "status": status,
            "warnings": warnings,
            "data_sources": {
                "book": "live" if book_data else "unavailable",
                "funding": "live" if funding_data else "unavailable",
                "liquidations": "live" if liq_count >= 0 else "unavailable"
            }
        }
    
    except Exception as e:
        logger.error(f"Error in get_guards: {e}")
        
        # Fallback to mock data if Redis unavailable
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "spread_bps": 6.5,
            "depth_10bps": {
                "bid_usd": 125000,
                "ask_usd": 130000
            },
            "funding_apr": 112.0,
            "basis_bps": 4.0,
            "oi_notional": 45000000,
            "liq_events_5m": 0,
            "status": "passing",
            "warnings": [],
            "data_sources": {
                "book": "fallback",
                "funding": "fallback",
                "liquidations": "fallback"
            },
            "error": str(e)
        }
