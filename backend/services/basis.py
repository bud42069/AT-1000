"""
Basis Calculation Service
Calculates USDT vs USDC basis for SOL perpetuals
Formula: basis_bps = ((px_usdc - px_usdt) / px_usdt) * 10000
"""

import redis.asyncio as aioredis
import os
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
STREAM_USDT = "market:solusdt:trades"
STREAM_USDC = "market:solusdc:trades"

# Cache
_basis_cache = None
_basis_cache_time = None
CACHE_TTL = 5  # seconds


class BasisCalculator:
    """Calculates and caches basis (USDT vs USDC)"""
    
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
                logger.info("BasisCalculator connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    async def get_latest_price(self, stream_key: str) -> Optional[float]:
        """Get latest price from stream"""
        try:
            await self.connect()
            
            # Read last entry from stream
            result = await self.redis.xrevrange(stream_key, count=1)
            
            if not result:
                return None
            
            # Parse result: [(id, {field: value, ...})]
            entry_id, data = result[0]
            
            # Extract price (different field names for different streams)
            if 'price' in data:
                # OKX format
                return float(data['price'])
            elif 'close' in data:
                # Binance 1m bar format
                return float(data['close'])
            else:
                logger.warning(f"No price field found in stream {stream_key}: {data}")
                return None
        
        except Exception as e:
            logger.error(f"Error reading price from {stream_key}: {e}")
            return None
    
    async def calculate_basis(self) -> Optional[float]:
        """Calculate basis (USDT vs USDC)"""
        try:
            # Get latest prices
            usdt_price = await self.get_latest_price(STREAM_USDT)
            usdc_price = await self.get_latest_price(STREAM_USDC)
            
            if not usdt_price or not usdc_price:
                logger.warning(f"Missing price data: USDT={usdt_price}, USDC={usdc_price}")
                return None
            
            # Calculate basis in basis points
            # basis_bps = ((px_usdc - px_usdt) / px_usdt) * 10000
            basis_bps = ((usdc_price - usdt_price) / usdt_price) * 10000
            
            logger.debug(f"Basis: USDT=${usdt_price:.2f}, USDC=${usdc_price:.2f}, Basis={basis_bps:.2f}bps")
            
            return basis_bps
        
        except Exception as e:
            logger.error(f"Error calculating basis: {e}")
            return None
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()


# Global instance
_calculator = BasisCalculator()


async def get_basis(use_cache: bool = True) -> float:
    """
    Get current basis (USDT vs USDC)
    Returns basis in basis points (bps)
    
    Args:
        use_cache: Whether to use cached value (5s TTL)
    
    Returns:
        basis_bps (float): Basis in basis points, or 0.0 if unavailable
    """
    global _basis_cache, _basis_cache_time
    
    # Check cache
    if use_cache and _basis_cache is not None and _basis_cache_time:
        age = (datetime.now(timezone.utc) - _basis_cache_time).total_seconds()
        if age < CACHE_TTL:
            return _basis_cache
    
    # Calculate fresh value
    basis_bps = await _calculator.calculate_basis()
    
    if basis_bps is not None:
        # Update cache
        _basis_cache = basis_bps
        _basis_cache_time = datetime.now(timezone.utc)
        return basis_bps
    
    # Return cached value if available, otherwise 0.0
    if _basis_cache is not None:
        logger.warning("Using stale cached basis value")
        return _basis_cache
    
    return 0.0
