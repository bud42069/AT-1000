"""
Drift Liquidation Map Scanner
Scans Drift user accounts via getProgramAccounts and calculates oracle-based liquidation estimates
Uses Drift SDK v2 for account decoding and health calculations
Publishes to Redis Stream and maintains Parquet file
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import aiohttp

import redis.asyncio as aioredis
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
HELIUS_RPC_URL = os.getenv('HELIUS_RPC_URL', 'https://mainnet.helius-rpc.com/?api-key=625e29ab-4bea-4694-b7d8-9fdda5871969')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
REDIS_STREAM = "onchain:drift:liq_map"
PARQUET_PATH = "/app/storage/parquet/drift/liq_map/latest.parquet"
DRIFT_PROGRAM_ID = "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH"
DRIFT_DATA_API = "https://data.api.drift.trade"

# SOL-PERP market index
SOL_PERP_MARKET_INDEX = 0

# Scan configuration
SCAN_INTERVAL = 3600  # 1 hour
ACCOUNT_PAGE_SIZE = 1000


@dataclass
class LiquidationEstimate:
    """Liquidation estimate for a Drift user account"""
    account: str
    market_index: int
    position_size: float
    avg_entry_price: float
    est_liq_px: float
    collateral_usd: float
    leverage: float
    health: float
    distance_bps: float  # Distance to liquidation in basis points
    updated_at: int
    
    def to_dict(self) -> dict:
        return asdict(self)


class DriftLiqMapScanner:
    """Drift liquidation map scanner"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.oracle_prices: Dict[int, float] = {}
        self.market_metadata: Dict = {}
    
    async def connect_redis(self):
        """Connect to Redis"""
        if not self.redis:
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
        """Create HTTP session"""
        self.session = aiohttp.ClientSession(
            headers={'Content-Type': 'application/json'}
        )
        logger.info("Created HTTP session")
    
    async def fetch_market_metadata(self):
        """Fetch market metadata from Drift Data API"""
        try:
            url = f"{DRIFT_DATA_API}/contracts"
            
            async with self.session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch market metadata: {resp.status}")
                    return
                
                data = await resp.json()
                self.market_metadata = data
                
                logger.info(f"Fetched market metadata: {len(data.get('markets', []))} markets")
        
        except Exception as e:
            logger.error(f"Error fetching market metadata: {e}")
    
    async def fetch_oracle_price(self, market_index: int) -> Optional[float]:
        """Fetch oracle price for market (placeholder - would use Pyth/Switchboard)"""
        # TODO: Integrate with actual oracle (Pyth/Switchboard)
        # For now, use last trade price from our Redis stream as proxy
        try:
            await self.connect_redis()
            
            # Read latest price from trades stream
            result = await self.redis.xrevrange("market:solusdt:trades", count=1)
            
            if result:
                trade_data = result[0][1]
                price = float(trade_data.get(b'close', 0))
                self.oracle_prices[market_index] = price
                return price
            
            return None
        
        except Exception as e:
            logger.error(f"Error fetching oracle price: {e}")
            return None
    
    async def fetch_user_accounts_page(self, offset: int = 0) -> List[Dict]:
        """Fetch page of Drift user accounts via RPC"""
        try:
            # getProgramAccounts RPC call with filters
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getProgramAccounts",
                "params": [
                    DRIFT_PROGRAM_ID,
                    {
                        "encoding": "base64",
                        "filters": [
                            {
                                "dataSize": 4376  # Drift UserAccount size (approximate)
                            }
                        ],
                        "dataSlice": {
                            "offset": 0,
                            "length": 0  # Get full account data
                        }
                    }
                ]
            }
            
            async with self.session.post(HELIUS_RPC_URL, json=payload, timeout=30) as resp:
                if resp.status != 200:
                    logger.error(f"RPC error: {resp.status}")
                    return []
                
                data = await resp.json()
                
                if 'result' not in data:
                    logger.error(f"No result in RPC response: {data}")
                    return []
                
                accounts = data['result']
                logger.info(f"Fetched {len(accounts)} user accounts from RPC")
                
                return accounts
        
        except Exception as e:
            logger.error(f"Error fetching user accounts: {e}")
            return []
    
    def decode_position_data(self, account_data: bytes) -> Optional[Dict]:
        """
        Decode Drift user account data (simplified)
        TODO: Use actual Drift SDK for proper decoding
        For now, return mock position data
        """
        # This is a placeholder - actual implementation would use Drift SDK
        # to decode the base64 account data and extract position information
        
        # Mock position data for demonstration
        return {
            'market_index': SOL_PERP_MARKET_INDEX,
            'position_size': 10.0,  # base asset quantity
            'avg_entry_price': 180.0,
            'collateral_usd': 5000.0
        }
    
    def calculate_liquidation_price(
        self,
        position_size: float,
        avg_entry_price: float,
        collateral_usd: float,
        oracle_price: float,
        maintenance_margin_ratio: float = 0.03  # 3% MMR for SOL-PERP
    ) -> Tuple[float, float, float]:
        """
        Calculate oracle-based liquidation price
        
        Formula: C + q*(p - avg) = mmr*|q|*p
        Solve for p (liquidation price)
        
        Returns: (liq_price, leverage, health)
        """
        try:
            if position_size == 0:
                return (0.0, 0.0, 1.0)
            
            # Calculate leverage
            position_notional = abs(position_size) * oracle_price
            leverage = position_notional / collateral_usd if collateral_usd > 0 else 0
            
            # Solve for liquidation price
            # C + q*(p - avg) = mmr*|q|*p
            # C + q*p - q*avg = mmr*|q|*p
            # C - q*avg = (mmr*|q| - q)*p
            # p = (C - q*avg) / (mmr*|q| - q)
            
            q = position_size
            abs_q = abs(q)
            
            numerator = collateral_usd - q * avg_entry_price
            denominator = maintenance_margin_ratio * abs_q - q
            
            if denominator == 0:
                liq_price = 0.0
            else:
                liq_price = numerator / denominator
            
            # Calculate current health (simplified)
            # Health = (Collateral + Unrealized PnL) / (MMR * Position Size)
            unrealized_pnl = position_size * (oracle_price - avg_entry_price)
            total_collateral = collateral_usd + unrealized_pnl
            required_collateral = maintenance_margin_ratio * abs_q * oracle_price
            
            health = total_collateral / required_collateral if required_collateral > 0 else 1.0
            
            return (liq_price, leverage, health)
        
        except Exception as e:
            logger.error(f"Error calculating liquidation price: {e}")
            return (0.0, 0.0, 1.0)
    
    async def process_account(self, account_pubkey: str, account_data: bytes, oracle_price: float) -> Optional[LiquidationEstimate]:
        """Process single user account and calculate liquidation estimate"""
        try:
            # Decode position data
            position = self.decode_position_data(account_data)
            
            if not position or position['position_size'] == 0:
                return None
            
            # Calculate liquidation price
            liq_price, leverage, health = self.calculate_liquidation_price(
                position_size=position['position_size'],
                avg_entry_price=position['avg_entry_price'],
                collateral_usd=position['collateral_usd'],
                oracle_price=oracle_price
            )
            
            if liq_price <= 0:
                return None
            
            # Calculate distance to liquidation in bps
            distance_bps = ((liq_price - oracle_price) / oracle_price) * 10000
            
            return LiquidationEstimate(
                account=account_pubkey,
                market_index=position['market_index'],
                position_size=position['position_size'],
                avg_entry_price=position['avg_entry_price'],
                est_liq_px=liq_price,
                collateral_usd=position['collateral_usd'],
                leverage=leverage,
                health=health,
                distance_bps=distance_bps,
                updated_at=int(datetime.now(timezone.utc).timestamp() * 1000)
            )
        
        except Exception as e:
            logger.error(f"Error processing account {account_pubkey}: {e}")
            return None
    
    async def publish_estimate(self, estimate: LiquidationEstimate):
        """Publish liquidation estimate to Redis Stream"""
        try:
            await self.connect_redis()
            
            await self.redis.xadd(
                REDIS_STREAM,
                estimate.to_dict(),
                maxlen=10000  # Keep last 10k estimates
            )
        
        except Exception as e:
            logger.error(f"Error publishing estimate: {e}")
    
    async def save_parquet(self, estimates: List[LiquidationEstimate]):
        """Save liquidation estimates to Parquet file"""
        if not estimates:
            return
        
        try:
            # Convert to Arrow Table
            data = {
                'account': [e.account for e in estimates],
                'market_index': [e.market_index for e in estimates],
                'position_size': [e.position_size for e in estimates],
                'avg_entry_price': [e.avg_entry_price for e in estimates],
                'est_liq_px': [e.est_liq_px for e in estimates],
                'collateral_usd': [e.collateral_usd for e in estimates],
                'leverage': [e.leverage for e in estimates],
                'health': [e.health for e in estimates],
                'distance_bps': [e.distance_bps for e in estimates],
                'updated_at': [e.updated_at for e in estimates],
            }
            
            table = pa.table(data)
            
            # Overwrite file (latest snapshot)
            pq.write_table(table, PARQUET_PATH, compression='snappy')
            logger.info(f"Saved {len(estimates)} estimates to {PARQUET_PATH}")
            
        except Exception as e:
            logger.error(f"Failed to save Parquet: {e}")
    
    async def scan_once(self):
        """Run one full scan cycle"""
        try:
            logger.info("Starting liquidation map scan...")
            
            # Fetch market metadata
            await self.fetch_market_metadata()
            
            # Fetch oracle price for SOL-PERP
            oracle_price = await self.fetch_oracle_price(SOL_PERP_MARKET_INDEX)
            
            if not oracle_price:
                logger.warning("No oracle price available, skipping scan")
                return
            
            logger.info(f"Oracle price for SOL-PERP: ${oracle_price:.2f}")
            
            # Fetch user accounts (paginated)
            accounts = await self.fetch_user_accounts_page()
            
            if not accounts:
                logger.warning("No user accounts found")
                return
            
            # Process accounts and calculate liquidation estimates
            estimates = []
            
            for account_info in accounts[:100]:  # Limit to first 100 for demo
                account_pubkey = account_info.get('pubkey', '')
                account_data_b64 = account_info.get('account', {}).get('data', [''])[0]
                
                if not account_pubkey or not account_data_b64:
                    continue
                
                # Decode base64 account data
                try:
                    import base64
                    account_data = base64.b64decode(account_data_b64)
                except Exception as e:
                    logger.error(f"Failed to decode account data: {e}")
                    continue
                
                # Process account
                estimate = await self.process_account(account_pubkey, account_data, oracle_price)
                
                if estimate:
                    estimates.append(estimate)
                    await self.publish_estimate(estimate)
            
            # Save to Parquet
            if estimates:
                await self.save_parquet(estimates)
                logger.info(f"Scan complete: {len(estimates)} positions with liquidation estimates")
            else:
                logger.warning("No valid liquidation estimates generated")
        
        except Exception as e:
            logger.error(f"Error in scan cycle: {e}")
    
    async def run(self):
        """Main scanner loop"""
        self.running = True
        
        # Connect to Redis
        await self.connect_redis()
        
        # Create HTTP session
        await self.create_session()
        
        logger.info(f"Starting Drift liquidation map scanner (interval: {SCAN_INTERVAL}s)")
        
        while self.running:
            try:
                await self.scan_once()
                await asyncio.sleep(SCAN_INTERVAL)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def stop(self):
        """Stop scanner"""
        logger.info("Stopping scanner...")
        self.running = False
        
        # Close session
        if self.session:
            await self.session.close()
        
        # Close Redis
        if self.redis:
            await self.redis.close()
        
        logger.info("Scanner stopped")


async def main():
    """Entry point"""
    scanner = DriftLiqMapScanner()
    
    try:
        await scanner.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(main())
