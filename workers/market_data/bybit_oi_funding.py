"""
Bybit Open Interest + Funding Rate Poller
Endpoints: 
  - /v5/market/open-interest (5-min intervals)
  - /v5/market/history-fund-rate (funding history)
Poll frequency: Every 60 seconds
Output: OI notional, funding rate (8h), funding APR
Publish: Redis Stream market:solusdt:funding
Persist: Parquet files
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aioredis
import aiohttp
import pyarrow as pa
import pyarrow.parquet as pq
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BYBIT_API_BASE = "https://api.bybit.com"
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
REDIS_STREAM = "market:solusdt:funding"
PARQUET_DIR = "/app/storage/parquet/bybit/SOLUSDT/funding"
SYMBOL = "SOLUSDT"
POLL_INTERVAL = 60  # seconds


@dataclass
class FundingSnapshot:
    """Funding + OI snapshot"""
    symbol: str
    timestamp: int
    oi_notional: float
    oi_value: float
    funding_rate_8h: float
    funding_apr: float
    next_funding_time: int
    
    def to_dict(self) -> dict:
        return asdict(self)


class BybitOIFunding:
    """Bybit OI + Funding Rate Poller"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.snapshots_buffer: List[FundingSnapshot] = []
        self.running = False
        self.funding_interval_hours: int = 8  # Default, will be fetched from API
    
    async def connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis = await aioredis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=False
            )
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def create_session(self):
        """Create aiohttp session"""
        self.session = aiohttp.ClientSession(
            headers={'Content-Type': 'application/json'}
        )
        logger.info("Created HTTP session")
    
    async def fetch_open_interest(self) -> Optional[Dict]:
        """Fetch open interest from Bybit"""
        try:
            url = f"{BYBIT_API_BASE}/v5/market/open-interest"
            params = {
                'category': 'linear',
                'symbol': SYMBOL,
                'intervalTime': '5min'
            }
            
            async with self.session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch OI: {resp.status}")
                    return None
                
                data = await resp.json()
                
                if data.get('retCode') != 0:
                    logger.error(f"API error: {data.get('retMsg')}")
                    return None
                
                result = data.get('result', {})
                list_data = result.get('list', [])
                
                if not list_data:
                    return None
                
                # Get latest OI data
                oi_data = list_data[0]
                return {
                    'oi_value': float(oi_data.get('openInterest', 0)),
                    'timestamp': int(oi_data.get('timestamp', 0))
                }
        
        except asyncio.TimeoutError:
            logger.error("Timeout fetching OI")
            return None
        except Exception as e:
            logger.error(f"Error fetching OI: {e}")
            return None
    
    async def fetch_funding_rate(self) -> Optional[Dict]:
        """Fetch funding rate from Bybit"""
        try:
            url = f"{BYBIT_API_BASE}/v5/market/funding/history"
            params = {
                'category': 'linear',
                'symbol': SYMBOL,
                'limit': 1
            }
            
            async with self.session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch funding: {resp.status}")
                    return None
                
                data = await resp.json()
                
                if data.get('retCode') != 0:
                    logger.error(f"API error: {data.get('retMsg')}")
                    return None
                
                result = data.get('result', {})
                list_data = result.get('list', [])
                
                if not list_data:
                    return None
                
                # Get latest funding rate
                funding_data = list_data[0]
                funding_rate_8h = float(funding_data.get('fundingRate', 0))
                
                # Calculate annualized funding rate
                # 8h rate * 3 (per day) * 365 (per year)
                funding_apr = funding_rate_8h * 3 * 365 * 100  # Convert to percentage
                
                return {
                    'funding_rate_8h': funding_rate_8h,
                    'funding_apr': funding_apr,
                    'funding_rate_timestamp': int(funding_data.get('fundingRateTimestamp', 0))
                }
        
        except asyncio.TimeoutError:
            logger.error("Timeout fetching funding rate")
            return None
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")
            return None
    
    async def fetch_tickers(self) -> Optional[Dict]:
        """Fetch ticker data for price (used for OI notional calculation)"""
        try:
            url = f"{BYBIT_API_BASE}/v5/market/tickers"
            params = {
                'category': 'linear',
                'symbol': SYMBOL
            }
            
            async with self.session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch ticker: {resp.status}")
                    return None
                
                data = await resp.json()
                
                if data.get('retCode') != 0:
                    logger.error(f"API error: {data.get('retMsg')}")
                    return None
                
                result = data.get('result', {})
                list_data = result.get('list', [])
                
                if not list_data:
                    return None
                
                ticker = list_data[0]
                return {
                    'price': float(ticker.get('lastPrice', 0)),
                    'next_funding_time': int(ticker.get('nextFundingTime', 0))
                }
        
        except asyncio.TimeoutError:
            logger.error("Timeout fetching ticker")
            return None
        except Exception as e:
            logger.error(f"Error fetching ticker: {e}")
            return None
    
    async def publish_snapshot(self, snapshot: FundingSnapshot):
        """Publish snapshot to Redis Stream"""
        if not self.redis:
            logger.warning("Redis not connected, skipping publish")
            return
        
        try:
            await self.redis.xadd(
                REDIS_STREAM,
                snapshot.to_dict(),
                maxlen=10000  # Keep last 10k snapshots (~1 week at 1/min)
            )
            logger.info(f"Funding: {snapshot.symbol} | OI: ${snapshot.oi_notional:,.0f} | Funding: {snapshot.funding_rate_8h:.6f} ({snapshot.funding_apr:.2f}% APR)")
        except Exception as e:
            logger.error(f"Failed to publish snapshot to Redis: {e}")
    
    async def save_parquet(self, snapshots: List[FundingSnapshot]):
        """Save snapshots to Parquet file"""
        if not snapshots:
            return
        
        try:
            date_str = datetime.fromtimestamp(snapshots[0].timestamp / 1000, tz=timezone.utc).strftime('%Y%m%d')
            filepath = f"{PARQUET_DIR}/{date_str}.parquet"
            
            # Convert to Arrow Table
            data = {
                'symbol': [s.symbol for s in snapshots],
                'timestamp': [s.timestamp for s in snapshots],
                'oi_notional': [s.oi_notional for s in snapshots],
                'oi_value': [s.oi_value for s in snapshots],
                'funding_rate_8h': [s.funding_rate_8h for s in snapshots],
                'funding_apr': [s.funding_apr for s in snapshots],
                'next_funding_time': [s.next_funding_time for s in snapshots],
            }
            
            table = pa.table(data)
            
            # Append to existing file or create new
            if os.path.exists(filepath):
                existing_table = pq.read_table(filepath)
                table = pa.concat_tables([existing_table, table])
            
            pq.write_table(table, filepath, compression='snappy')
            logger.info(f"Saved {len(snapshots)} snapshots to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save Parquet: {e}")
    
    async def poll_once(self):
        """Poll OI and funding once"""
        try:
            # Fetch all data concurrently
            oi_data, funding_data, ticker_data = await asyncio.gather(
                self.fetch_open_interest(),
                self.fetch_funding_rate(),
                self.fetch_tickers(),
                return_exceptions=True
            )
            
            # Check for errors
            if isinstance(oi_data, Exception):
                logger.error(f"OI fetch error: {oi_data}")
                return
            if isinstance(funding_data, Exception):
                logger.error(f"Funding fetch error: {funding_data}")
                return
            if isinstance(ticker_data, Exception):
                logger.error(f"Ticker fetch error: {ticker_data}")
                return
            
            if not oi_data or not funding_data or not ticker_data:
                logger.warning("Missing data from API")
                return
            
            # Calculate OI notional (OI value * current price)
            oi_notional = oi_data['oi_value'] * ticker_data['price']
            
            # Create snapshot
            snapshot = FundingSnapshot(
                symbol=SYMBOL,
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
                oi_notional=oi_notional,
                oi_value=oi_data['oi_value'],
                funding_rate_8h=funding_data['funding_rate_8h'],
                funding_apr=funding_data['funding_apr'],
                next_funding_time=ticker_data['next_funding_time']
            )
            
            await self.publish_snapshot(snapshot)
            self.snapshots_buffer.append(snapshot)
            
            # Save to Parquet hourly
            if len(self.snapshots_buffer) >= 60:
                await self.save_parquet(self.snapshots_buffer)
                self.snapshots_buffer.clear()
        
        except Exception as e:
            logger.error(f"Error in poll_once: {e}")
    
    async def run(self):
        """Main polling loop"""
        self.running = True
        
        # Connect to Redis
        await self.connect_redis()
        
        # Create HTTP session
        await self.create_session()
        
        logger.info(f"Starting OI + Funding poller (interval: {POLL_INTERVAL}s)")
        
        while self.running:
            try:
                await self.poll_once()
                await asyncio.sleep(POLL_INTERVAL)
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(POLL_INTERVAL)
    
    async def stop(self):
        """Stop worker"""
        logger.info("Stopping worker...")
        self.running = False
        
        # Save remaining snapshots
        if self.snapshots_buffer:
            await self.save_parquet(self.snapshots_buffer)
        
        # Close session
        if self.session:
            await self.session.close()
        
        # Close Redis
        if self.redis:
            await self.redis.close()
        
        logger.info("Worker stopped")


async def main():
    """Entry point"""
    worker = BybitOIFunding()
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
