"""
Multi-Venue Liquidations Worker
Sources: Binance, OKX, Bybit liquidation feeds
Output: Liquidation events with venue, side, price, quantity
Publish: Redis Stream market:solusdt:liquidations
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
import websockets
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
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
REDIS_STREAM = "market:solusdt:liquidations"
PARQUET_DIR = "/app/storage/parquet/liquidations/SOLUSDT"
SYMBOL = "SOLUSDT"

# WebSocket URLs
BINANCE_WS_URL = "wss://fstream.binance.com/ws/!forceOrder@arr"
OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"

# Reconnection config
RECONNECT_DELAY_MIN = 1
RECONNECT_DELAY_MAX = 60


@dataclass
class Liquidation:
    """Liquidation event"""
    venue: str
    symbol: str
    side: str
    price: float
    quantity: float
    timestamp: int
    
    def to_dict(self) -> dict:
        return asdict(self)


class LiquidationsWorker:
    """Multi-venue liquidations aggregator"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.liq_buffer: List[Liquidation] = []
        self.running = False
        self.reconnect_delays = {
            'binance': RECONNECT_DELAY_MIN,
            'okx': RECONNECT_DELAY_MIN,
            'bybit': RECONNECT_DELAY_MIN
        }
    
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
    
    async def publish_liquidation(self, liq: Liquidation):
        """Publish liquidation to Redis Stream"""
        if not self.redis:
            logger.warning("Redis not connected, skipping publish")
            return
        
        try:
            await self.redis.xadd(
                REDIS_STREAM,
                liq.to_dict(),
                maxlen=10000  # Keep last 10k liquidations
            )
            logger.info(f"Liquidation [{liq.venue}]: {liq.side.upper()} {liq.quantity:.2f} @ ${liq.price:.2f}")
        except Exception as e:
            logger.error(f"Failed to publish liquidation to Redis: {e}")
    
    async def save_parquet(self, liquidations: List[Liquidation]):
        """Save liquidations to Parquet file"""
        if not liquidations:
            return
        
        try:
            date_str = datetime.fromtimestamp(liquidations[0].timestamp / 1000, tz=timezone.utc).strftime('%Y%m%d')
            filepath = f"{PARQUET_DIR}/{date_str}.parquet"
            
            # Convert to Arrow Table
            data = {
                'venue': [l.venue for l in liquidations],
                'symbol': [l.symbol for l in liquidations],
                'side': [l.side for l in liquidations],
                'price': [l.price for l in liquidations],
                'quantity': [l.quantity for l in liquidations],
                'timestamp': [l.timestamp for l in liquidations],
            }
            
            table = pa.table(data)
            
            # Append to existing file or create new
            if os.path.exists(filepath):
                existing_table = pq.read_table(filepath)
                table = pa.concat_tables([existing_table, table])
            
            pq.write_table(table, filepath, compression='snappy')
            logger.info(f"Saved {len(liquidations)} liquidations to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save Parquet: {e}")
    
    async def process_binance_liquidation(self, data: dict):
        """Process Binance liquidation"""
        try:
            order = data.get('o', {})
            symbol = order.get('s')
            
            # Filter for SOLUSDT
            if symbol != SYMBOL:
                return
            
            liq = Liquidation(
                venue='binance',
                symbol=symbol,
                side='long' if order.get('S') == 'SELL' else 'short',  # Liquidation side opposite
                price=float(order.get('p', 0)),
                quantity=float(order.get('q', 0)),
                timestamp=data.get('E', int(datetime.now(timezone.utc).timestamp() * 1000))
            )
            
            await self.publish_liquidation(liq)
            self.liq_buffer.append(liq)
            
            # Save to Parquet hourly
            if len(self.liq_buffer) >= 100:
                await self.save_parquet(self.liq_buffer)
                self.liq_buffer.clear()
        
        except Exception as e:
            logger.error(f"Error processing Binance liquidation: {e}")
    
    async def process_okx_liquidation(self, data: dict):
        """Process OKX liquidation"""
        try:
            for item in data.get('data', []):
                inst_id = item.get('instId')
                
                # Filter for SOL-USDT-SWAP
                if 'SOL' not in inst_id or 'USDT' not in inst_id:
                    continue
                
                liq = Liquidation(
                    venue='okx',
                    symbol='SOLUSDT',
                    side=item.get('side', 'unknown'),
                    price=float(item.get('bkPx', 0)),
                    quantity=float(item.get('sz', 0)),
                    timestamp=int(item.get('ts', datetime.now(timezone.utc).timestamp() * 1000))
                )
                
                await self.publish_liquidation(liq)
                self.liq_buffer.append(liq)
        
        except Exception as e:
            logger.error(f"Error processing OKX liquidation: {e}")
    
    async def process_bybit_liquidation(self, data: dict):
        """Process Bybit liquidation"""
        try:
            for item in data.get('data', []):
                symbol = item.get('symbol')
                
                # Filter for SOLUSDT
                if symbol != 'SOLUSDT':
                    continue
                
                liq = Liquidation(
                    venue='bybit',
                    symbol=symbol,
                    side=item.get('side', 'unknown').lower(),
                    price=float(item.get('price', 0)),
                    quantity=float(item.get('size', 0)),
                    timestamp=int(item.get('updatedTime', datetime.now(timezone.utc).timestamp() * 1000))
                )
                
                await self.publish_liquidation(liq)
                self.liq_buffer.append(liq)
        
        except Exception as e:
            logger.error(f"Error processing Bybit liquidation: {e}")
    
    async def run_binance(self):
        """Binance liquidations feed"""
        while self.running:
            try:
                logger.info("Connecting to Binance liquidations WebSocket")
                
                async with websockets.connect(BINANCE_WS_URL, ping_interval=20) as ws:
                    logger.info("Connected to Binance liquidations")
                    self.reconnect_delays['binance'] = RECONNECT_DELAY_MIN
                    
                    async for message in ws:
                        if not self.running:
                            break
                        
                        try:
                            data = json.loads(message)
                            if data.get('e') == 'forceOrder':
                                await self.process_binance_liquidation(data)
                        except Exception as e:
                            logger.error(f"Error processing Binance message: {e}")
            
            except Exception as e:
                logger.error(f"Binance WebSocket error: {e}")
            
            if self.running:
                delay = self.reconnect_delays['binance']
                logger.info(f"Reconnecting to Binance in {delay}s...")
                await asyncio.sleep(delay)
                self.reconnect_delays['binance'] = min(delay * 2, RECONNECT_DELAY_MAX)
    
    async def run_okx(self):
        """OKX liquidations feed"""
        while self.running:
            try:
                logger.info("Connecting to OKX liquidations WebSocket")
                
                async with websockets.connect(OKX_WS_URL, ping_interval=20) as ws:
                    # Subscribe to liquidation orders
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [
                            {
                                "channel": "liquidation-orders",
                                "instType": "SWAP"
                            }
                        ]
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info("Connected to OKX liquidations")
                    self.reconnect_delays['okx'] = RECONNECT_DELAY_MIN
                    
                    async for message in ws:
                        if not self.running:
                            break
                        
                        try:
                            data = json.loads(message)
                            if data.get('arg', {}).get('channel') == 'liquidation-orders':
                                await self.process_okx_liquidation(data)
                        except Exception as e:
                            logger.error(f"Error processing OKX message: {e}")
            
            except Exception as e:
                logger.error(f"OKX WebSocket error: {e}")
            
            if self.running:
                delay = self.reconnect_delays['okx']
                logger.info(f"Reconnecting to OKX in {delay}s...")
                await asyncio.sleep(delay)
                self.reconnect_delays['okx'] = min(delay * 2, RECONNECT_DELAY_MAX)
    
    async def run_bybit(self):
        """Bybit liquidations feed"""
        while self.running:
            try:
                logger.info("Connecting to Bybit liquidations WebSocket")
                
                async with websockets.connect(BYBIT_WS_URL, ping_interval=20) as ws:
                    # Subscribe to liquidation channel
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": ["liquidation.SOLUSDT"]
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info("Connected to Bybit liquidations")
                    self.reconnect_delays['bybit'] = RECONNECT_DELAY_MIN
                    
                    async for message in ws:
                        if not self.running:
                            break
                        
                        try:
                            data = json.loads(message)
                            if data.get('topic') == 'liquidation.SOLUSDT':
                                await self.process_bybit_liquidation(data)
                        except Exception as e:
                            logger.error(f"Error processing Bybit message: {e}")
            
            except Exception as e:
                logger.error(f"Bybit WebSocket error: {e}")
            
            if self.running:
                delay = self.reconnect_delays['bybit']
                logger.info(f"Reconnecting to Bybit in {delay}s...")
                await asyncio.sleep(delay)
                self.reconnect_delays['bybit'] = min(delay * 2, RECONNECT_DELAY_MAX)
    
    async def run(self):
        """Main worker - runs all venue feeds concurrently"""
        self.running = True
        
        # Connect to Redis
        await self.connect_redis()
        
        # Run all venue feeds concurrently
        await asyncio.gather(
            self.run_binance(),
            self.run_okx(),
            self.run_bybit()
        )
    
    async def stop(self):
        """Stop worker"""
        logger.info("Stopping worker...")
        self.running = False
        
        # Save remaining liquidations
        if self.liq_buffer:
            await self.save_parquet(self.liq_buffer)
        
        # Close Redis
        if self.redis:
            await self.redis.close()
        
        logger.info("Worker stopped")


async def main():
    """Entry point"""
    worker = LiquidationsWorker()
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
