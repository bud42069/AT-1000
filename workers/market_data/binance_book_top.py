"""
Binance Order Book Worker
WebSocket: wss://fstream.binance.com/ws/solusdt@depth@100ms
Output: TOB (top of book) + 10bps depth snapshot
Publish: Redis Stream market:solusdt:book
Update frequency: 100ms
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

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
BINANCE_WS_URL = "wss://fstream.binance.com/ws/solusdt@depth@100ms"
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
REDIS_STREAM = "market:solusdt:book"
SYMBOL = "SOLUSDT"
DEPTH_BPS_THRESHOLD = 10  # 10 basis points

# Reconnection config
RECONNECT_DELAY_MIN = 1
RECONNECT_DELAY_MAX = 60


@dataclass
class BookSnapshot:
    """Order book snapshot"""
    symbol: str
    timestamp: int
    bid_px: float
    bid_qty: float
    ask_px: float
    ask_qty: float
    mid_px: float
    spread_bps: float
    depth_10bps_bid_usd: float
    depth_10bps_ask_usd: float
    
    def to_dict(self) -> dict:
        return asdict(self)


class OrderBook:
    """Maintains order book state"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[float, float] = {}  # price -> quantity
        self.asks: Dict[float, float] = {}  # price -> quantity
        self.last_update_id = 0
    
    def update(self, data: dict):
        """Update order book from diff data"""
        # Update bids
        for bid in data.get('b', []):
            price = float(bid[0])
            qty = float(bid[1])
            
            if qty == 0:
                self.bids.pop(price, None)
            else:
                self.bids[price] = qty
        
        # Update asks
        for ask in data.get('a', []):
            price = float(ask[0])
            qty = float(ask[1])
            
            if qty == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = qty
        
        self.last_update_id = data.get('u', self.last_update_id)
    
    def get_tob(self) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        """Get top of book (best bid, best ask)"""
        if not self.bids or not self.asks:
            return None, None
        
        best_bid = max(self.bids.keys())
        best_ask = min(self.asks.keys())
        
        return (best_bid, self.bids[best_bid]), (best_ask, self.asks[best_ask])
    
    def get_depth_10bps(self, mid_px: float) -> Tuple[float, float]:
        """Calculate depth within 10 bps of mid price"""
        threshold_bps = DEPTH_BPS_THRESHOLD / 10000  # Convert to decimal
        
        # Bid depth (within 10bps below mid)
        bid_threshold = mid_px * (1 - threshold_bps)
        bid_depth_usd = sum(
            price * qty 
            for price, qty in self.bids.items() 
            if price >= bid_threshold
        )
        
        # Ask depth (within 10bps above mid)
        ask_threshold = mid_px * (1 + threshold_bps)
        ask_depth_usd = sum(
            price * qty 
            for price, qty in self.asks.items() 
            if price <= ask_threshold
        )
        
        return bid_depth_usd, ask_depth_usd
    
    def get_snapshot(self) -> Optional[BookSnapshot]:
        """Get current book snapshot"""
        bid, ask = self.get_tob()
        
        if not bid or not ask:
            return None
        
        bid_px, bid_qty = bid
        ask_px, ask_qty = ask
        mid_px = (bid_px + ask_px) / 2
        spread_bps = ((ask_px - bid_px) / mid_px) * 10000
        
        # Calculate 10bps depth
        bid_depth_usd, ask_depth_usd = self.get_depth_10bps(mid_px)
        
        return BookSnapshot(
            symbol=self.symbol,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            bid_px=bid_px,
            bid_qty=bid_qty,
            ask_px=ask_px,
            ask_qty=ask_qty,
            mid_px=mid_px,
            spread_bps=spread_bps,
            depth_10bps_bid_usd=bid_depth_usd,
            depth_10bps_ask_usd=ask_depth_usd
        )


class BinanceBookTop:
    """Binance Order Book Worker"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.order_book = OrderBook(SYMBOL)
        self.running = False
        self.reconnect_delay = RECONNECT_DELAY_MIN
        self.last_publish_time = 0
        self.publish_interval = 1.0  # Publish every 1 second (not every 100ms to reduce load)
    
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
    
    async def publish_snapshot(self, snapshot: BookSnapshot):
        """Publish snapshot to Redis Stream"""
        if not self.redis:
            logger.warning("Redis not connected, skipping publish")
            return
        
        try:
            # Publish to Redis Stream
            await self.redis.xadd(
                REDIS_STREAM,
                snapshot.to_dict(),
                maxlen=1000  # Keep last 1k snapshots (~15 minutes at 1/sec)
            )
            logger.debug(f"Published book: {snapshot.symbol} | Bid:{snapshot.bid_px:.2f} Ask:{snapshot.ask_px:.2f} | Spread:{snapshot.spread_bps:.2f}bps | Depth: ${snapshot.depth_10bps_bid_usd:.0f}/${snapshot.depth_10bps_ask_usd:.0f}")
        except Exception as e:
            logger.error(f"Failed to publish snapshot to Redis: {e}")
    
    async def process_update(self, data: dict):
        """Process order book update"""
        try:
            # Update order book
            self.order_book.update(data)
            
            # Throttle publishing to 1/second
            now = datetime.now(timezone.utc).timestamp()
            if now - self.last_publish_time >= self.publish_interval:
                snapshot = self.order_book.get_snapshot()
                if snapshot:
                    await self.publish_snapshot(snapshot)
                    self.last_publish_time = now
            
        except Exception as e:
            logger.error(f"Error processing update: {e}")
    
    async def run(self):
        """Main worker loop with reconnection"""
        self.running = True
        
        # Connect to Redis
        await self.connect_redis()
        
        while self.running:
            try:
                logger.info(f"Connecting to Binance WebSocket: {BINANCE_WS_URL}")
                
                async with websockets.connect(
                    BINANCE_WS_URL,
                    ping_interval=20,
                    ping_timeout=10
                ) as ws:
                    logger.info("Connected to Binance WebSocket")
                    self.reconnect_delay = RECONNECT_DELAY_MIN
                    
                    async for message in ws:
                        if not self.running:
                            break
                        
                        try:
                            data = json.loads(message)
                            
                            # Process depth update
                            if data.get('e') == 'depthUpdate':
                                await self.process_update(data)
                        
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
    worker = BinanceBookTop()
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
