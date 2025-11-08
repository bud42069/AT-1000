"""
OKX SOL-USDC Price Worker
WebSocket: wss://ws.okx.com:8443/ws/v5/public
Channel: trades (SOL-USDC-SWAP)
Output: Real-time USDC price feed for basis calculation
Publish: Redis Stream market:solusdc:trades
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import aioredis
import websockets
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
REDIS_STREAM = "market:solusdc:trades"
INST_ID = "SOL-USDC-SWAP"

# Reconnection config
RECONNECT_DELAY_MIN = 1
RECONNECT_DELAY_MAX = 60


@dataclass
class Trade:
    """Trade from OKX"""
    inst_id: str
    trade_id: str
    price: float
    size: float
    side: str  # buy or sell
    timestamp: int
    
    def to_dict(self) -> dict:
        return asdict(self)


class OKXUSDCPrice:
    """OKX SOL-USDC-SWAP price worker"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.running = False
        self.reconnect_delay = RECONNECT_DELAY_MIN
        self.last_price = None
        self.last_publish_time = 0
        self.publish_interval = 1.0  # Publish every 1 second (throttle)
    
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
    
    async def publish_trade(self, trade: Trade):
        """Publish trade to Redis Stream"""
        if not self.redis:
            logger.warning("Redis not connected, skipping publish")
            return
        
        try:
            # Throttle publishing to 1/second
            now = datetime.now(timezone.utc).timestamp()
            if now - self.last_publish_time < self.publish_interval:
                self.last_price = trade.price
                return
            
            await self.redis.xadd(
                REDIS_STREAM,
                trade.to_dict(),
                maxlen=1000  # Keep last 1k trades (~15 minutes)
            )
            
            self.last_price = trade.price
            self.last_publish_time = now
            
            logger.debug(f"Published trade: {trade.inst_id} @ ${trade.price:.2f} | {trade.side.upper()} {trade.size:.2f}")
        except Exception as e:
            logger.error(f"Failed to publish trade to Redis: {e}")
    
    async def process_trade(self, data: dict):
        """Process incoming trade"""
        try:
            # OKX trades data structure
            for trade_data in data.get('data', []):
                trade = Trade(
                    inst_id=trade_data.get('instId'),
                    trade_id=trade_data.get('tradeId'),
                    price=float(trade_data.get('px', 0)),
                    size=float(trade_data.get('sz', 0)),
                    side=trade_data.get('side', 'unknown'),
                    timestamp=int(trade_data.get('ts', datetime.now(timezone.utc).timestamp() * 1000))
                )
                
                await self.publish_trade(trade)
        
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
    
    async def run(self):
        """Main worker loop with reconnection"""
        self.running = True
        
        # Connect to Redis
        await self.connect_redis()
        
        while self.running:
            try:
                logger.info(f"Connecting to OKX WebSocket: {OKX_WS_URL}")
                
                async with websockets.connect(
                    OKX_WS_URL,
                    ping_interval=20,
                    ping_timeout=10
                ) as ws:
                    logger.info("Connected to OKX WebSocket")
                    
                    # Subscribe to trades channel
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [
                            {
                                "channel": "trades",
                                "instId": INST_ID
                            }
                        ]
                    }
                    
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(f"Subscribed to {INST_ID} trades")
                    
                    self.reconnect_delay = RECONNECT_DELAY_MIN
                    
                    async for message in ws:
                        if not self.running:
                            break
                        
                        try:
                            data = json.loads(message)
                            
                            # Handle subscription confirmation
                            if data.get('event') == 'subscribe':
                                logger.info(f"Subscription confirmed: {data}")
                                continue
                            
                            # Process trade data
                            if data.get('arg', {}).get('channel') == 'trades':
                                await self.process_trade(data)
                        
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse message: {e}")
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
            
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            if self.running:
                logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, RECONNECT_DELAY_MAX)
    
    async def stop(self):
        """Stop worker"""
        logger.info("Stopping worker...")
        self.running = False
        
        # Close Redis
        if self.redis:
            await self.redis.close()
        
        logger.info("Worker stopped")


async def main():
    """Entry point"""
    worker = OKXUSDCPrice()
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
