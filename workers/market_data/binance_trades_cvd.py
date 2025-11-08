"""
Binance Trades + CVD Worker
WebSocket: wss://fstream.binance.com/ws/solusdt@aggTrade
Output: 1-minute bars with OHLC, volume, CVD, VWAP
Publish: Redis Stream market:solusdt:trades
Persist: Parquet files (hourly rollups)
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aioredis
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
BINANCE_WS_URL = "wss://fstream.binance.com/ws/solusdt@aggTrade"
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
REDIS_STREAM = "market:solusdt:trades"
PARQUET_DIR = "/app/storage/parquet/binance/SOLUSDT/trades"
SYMBOL = "SOLUSDT"

# Reconnection config
RECONNECT_DELAY_MIN = 1
RECONNECT_DELAY_MAX = 60
MAX_MSGS_PER_SEC = 10


@dataclass
class Trade:
    """Aggregated trade from Binance"""
    event_time: int
    symbol: str
    agg_trade_id: int
    price: float
    quantity: float
    first_trade_id: int
    last_trade_id: int
    timestamp: int
    is_buyer_maker: bool
    
    @classmethod
    def from_json(cls, data: dict) -> 'Trade':
        return cls(
            event_time=data['E'],
            symbol=data['s'],
            agg_trade_id=data['a'],
            price=float(data['p']),
            quantity=float(data['q']),
            first_trade_id=data['f'],
            last_trade_id=data['l'],
            timestamp=data['T'],
            is_buyer_maker=data['m']
        )


@dataclass
class Bar:
    """1-minute OHLCV bar with CVD and VWAP"""
    symbol: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: float
    sell_volume: float
    cvd: float
    vwap: float
    trade_count: int
    
    def to_dict(self) -> dict:
        return asdict(self)


class BarAggregator:
    """Aggregates trades into 1-minute bars"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.reset()
    
    def reset(self):
        """Reset aggregator for new bar"""
        self.open: Optional[float] = None
        self.high: Optional[float] = None
        self.low: Optional[float] = None
        self.close: Optional[float] = None
        self.volume = 0.0
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.value_sum = 0.0  # For VWAP calculation
        self.trade_count = 0
        self.current_minute = None
    
    def add_trade(self, trade: Trade):
        """Add trade to current bar"""
        price = trade.price
        qty = trade.quantity
        
        # Update OHLC
        if self.open is None:
            self.open = price
        self.high = max(self.high or price, price)
        self.low = min(self.low or price, price)
        self.close = price
        
        # Update volumes
        self.volume += qty
        if trade.is_buyer_maker:
            # Buyer is maker = sell order (taker sold)
            self.sell_volume += qty
        else:
            # Buyer is taker = buy order
            self.buy_volume += qty
        
        # VWAP calculation
        self.value_sum += price * qty
        self.trade_count += 1
    
    def finalize_bar(self, timestamp: int) -> Optional[Bar]:
        """Finalize current bar and return it"""
        if self.open is None:
            return None
        
        cvd = self.buy_volume - self.sell_volume
        vwap = self.value_sum / self.volume if self.volume > 0 else self.close
        
        bar = Bar(
            symbol=self.symbol,
            timestamp=timestamp,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            buy_volume=self.buy_volume,
            sell_volume=self.sell_volume,
            cvd=cvd,
            vwap=vwap,
            trade_count=self.trade_count
        )
        
        self.reset()
        return bar


class BinanceTradesCVD:
    """Binance Trades + CVD Worker"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.aggregator = BarAggregator(SYMBOL)
        self.bars_buffer: List[Bar] = []
        self.running = False
        self.reconnect_delay = RECONNECT_DELAY_MIN
    
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
    
    async def publish_bar(self, bar: Bar):
        """Publish bar to Redis Stream"""
        if not self.redis:
            logger.warning("Redis not connected, skipping publish")
            return
        
        try:
            # Publish to Redis Stream
            await self.redis.xadd(
                REDIS_STREAM,
                bar.to_dict(),
                maxlen=10000  # Keep last 10k bars (~1 week)
            )
            logger.info(f"Published bar: {bar.symbol} @ {bar.timestamp} | O:{bar.open:.2f} H:{bar.high:.2f} L:{bar.low:.2f} C:{bar.close:.2f} | CVD:{bar.cvd:.0f}")
        except Exception as e:
            logger.error(f"Failed to publish bar to Redis: {e}")
    
    async def save_parquet(self, bars: List[Bar]):
        """Save bars to Parquet file (hourly rollup)"""
        if not bars:
            return
        
        try:
            # Group by date
            date_str = datetime.fromtimestamp(bars[0].timestamp / 1000, tz=timezone.utc).strftime('%Y%m%d')
            filepath = f"{PARQUET_DIR}/{date_str}.parquet"
            
            # Convert to Arrow Table
            data = {
                'symbol': [b.symbol for b in bars],
                'timestamp': [b.timestamp for b in bars],
                'open': [b.open for b in bars],
                'high': [b.high for b in bars],
                'low': [b.low for b in bars],
                'close': [b.close for b in bars],
                'volume': [b.volume for b in bars],
                'buy_volume': [b.buy_volume for b in bars],
                'sell_volume': [b.sell_volume for b in bars],
                'cvd': [b.cvd for b in bars],
                'vwap': [b.vwap for b in bars],
                'trade_count': [b.trade_count for b in bars],
            }
            
            table = pa.table(data)
            
            # Append to existing file or create new
            if os.path.exists(filepath):
                existing_table = pq.read_table(filepath)
                table = pa.concat_tables([existing_table, table])
            
            pq.write_table(table, filepath, compression='snappy')
            logger.info(f"Saved {len(bars)} bars to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save Parquet: {e}")
    
    async def process_trade(self, trade_data: dict):
        """Process incoming trade"""
        try:
            trade = Trade.from_json(trade_data)
            
            # Get current minute timestamp
            trade_time = datetime.fromtimestamp(trade.timestamp / 1000, tz=timezone.utc)
            current_minute = trade_time.replace(second=0, microsecond=0)
            minute_ts = int(current_minute.timestamp() * 1000)
            
            # Check if we need to finalize previous bar
            if self.aggregator.current_minute is None:
                self.aggregator.current_minute = minute_ts
            elif minute_ts > self.aggregator.current_minute:
                # New minute started, finalize previous bar
                bar = self.aggregator.finalize_bar(self.aggregator.current_minute)
                if bar:
                    await self.publish_bar(bar)
                    self.bars_buffer.append(bar)
                    
                    # Save to Parquet every hour
                    if len(self.bars_buffer) >= 60:
                        await self.save_parquet(self.bars_buffer)
                        self.bars_buffer.clear()
                
                self.aggregator.current_minute = minute_ts
            
            # Add trade to current bar
            self.aggregator.add_trade(trade)
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
    
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
                            
                            # Process trade
                            if data.get('e') == 'aggTrade':
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
        
        # Finalize any pending bar
        if self.aggregator.open is not None:
            bar = self.aggregator.finalize_bar(self.aggregator.current_minute)
            if bar:
                await self.publish_bar(bar)
                self.bars_buffer.append(bar)
        
        # Save remaining bars
        if self.bars_buffer:
            await self.save_parquet(self.bars_buffer)
        
        # Close Redis
        if self.redis:
            await self.redis.close()
        
        logger.info("Worker stopped")


async def main():
    """Entry point"""
    worker = BinanceTradesCVD()
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
