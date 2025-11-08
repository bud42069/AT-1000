"""
Helius Enhanced Webhooks Receiver
Receives Drift Protocol events from Helius Enhanced Webhooks
Filters, deduplicates, and persists events
Publishes to Redis Stream for consumption
"""

from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json
import hashlib
import logging
import redis.asyncio as aioredis
import pyarrow as pa
import pyarrow.parquet as pq
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
REDIS_STREAM = "onchain:drift:events"
REDIS_DEDUP_SET = "onchain:drift:event_ids"
PARQUET_DIR = "/app/storage/parquet/helius/drift"

# Drift Program IDs
DRIFT_PROGRAM_ID = "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH"

# Helius webhook secret (for signature verification)
HELIUS_WEBHOOK_SECRET = os.getenv('HELIUS_WEBHOOK_SECRET', '')


class HeliusWebhookHandler:
    """Handles Helius webhook events"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.event_buffer: List[Dict] = []
    
    async def connect_redis(self):
        """Connect to Redis"""
        if not self.redis:
            try:
                self.redis = await aioredis.from_url(
                    REDIS_URL,
                    encoding="utf-8",
                    decode_responses=False
                )
                logger.info("HeliusWebhookHandler connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Helius webhook signature
        Reference: https://www.helius.dev/docs/api-reference/webhooks
        """
        if not HELIUS_WEBHOOK_SECRET:
            # Production: MUST have secret configured
            logger.error("⚠️ HELIUS_WEBHOOK_SECRET not set - webhook auth disabled (INSECURE)")
            logger.error("Set HELIUS_WEBHOOK_SECRET environment variable for production")
            # In dev mode, allow but log warning
            return True
        
        try:
            # Calculate expected signature (Helius uses HMAC-SHA256)
            import hmac
            expected = hmac.new(
                HELIUS_WEBHOOK_SECRET.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(expected, signature)
            
            if not is_valid:
                logger.warning(f"Invalid webhook signature. Expected: {expected[:16]}..., Got: {signature[:16]}...")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    async def is_duplicate(self, event_id: str) -> bool:
        """Check if event ID already processed"""
        try:
            await self.connect_redis()
            
            # Check if event ID exists in dedup set
            exists = await self.redis.sismember(REDIS_DEDUP_SET, event_id)
            
            if not exists:
                # Add to dedup set with 24h expiry
                await self.redis.sadd(REDIS_DEDUP_SET, event_id)
                await self.redis.expire(REDIS_DEDUP_SET, 86400)  # 24 hours
            
            return bool(exists)
        
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return False
    
    def filter_drift_events(self, events: List[Dict]) -> List[Dict]:
        """Filter events for Drift protocol only"""
        filtered = []
        
        for event in events:
            # Check if event involves Drift program
            account_data = event.get('accountData', [])
            
            for account in account_data:
                if account.get('account') == DRIFT_PROGRAM_ID:
                    filtered.append(event)
                    break
        
        return filtered
    
    async def publish_event(self, event: Dict):
        """Publish event to Redis Stream"""
        try:
            await self.connect_redis()
            
            # Flatten event for Redis Stream
            stream_data = {
                'signature': event.get('signature', ''),
                'type': event.get('type', ''),
                'timestamp': event.get('timestamp', int(datetime.now(timezone.utc).timestamp() * 1000)),
                'slot': event.get('slot', 0),
                'event_json': json.dumps(event)  # Store full event as JSON
            }
            
            await self.redis.xadd(
                REDIS_STREAM,
                stream_data,
                maxlen=10000  # Keep last 10k events
            )
            
            logger.info(f"Published Drift event: {event.get('signature', 'unknown')}")
        
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
    
    async def save_parquet(self, events: List[Dict]):
        """Save events to Parquet file"""
        if not events:
            return
        
        try:
            date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
            filepath = f"{PARQUET_DIR}/{date_str}.parquet"
            
            # Convert to Arrow Table
            data = {
                'signature': [e.get('signature', '') for e in events],
                'type': [e.get('type', '') for e in events],
                'timestamp': [e.get('timestamp', 0) for e in events],
                'slot': [e.get('slot', 0) for e in events],
                'event_json': [json.dumps(e) for e in events],
            }
            
            table = pa.table(data)
            
            # Append to existing file or create new
            if os.path.exists(filepath):
                existing_table = pq.read_table(filepath)
                table = pa.concat_tables([existing_table, table])
            
            pq.write_table(table, filepath, compression='snappy')
            logger.info(f"Saved {len(events)} events to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save Parquet: {e}")
    
    async def process_events(self, events: List[Dict]) -> int:
        """Process incoming webhook events"""
        processed_count = 0
        
        for event in events:
            try:
                # Generate event ID from signature
                event_id = event.get('signature', '')
                
                if not event_id:
                    logger.warning("Event missing signature, skipping")
                    continue
                
                # Check for duplicates
                if await self.is_duplicate(event_id):
                    logger.debug(f"Duplicate event: {event_id}")
                    continue
                
                # Publish to Redis Stream
                await self.publish_event(event)
                
                # Add to buffer for batch Parquet write
                self.event_buffer.append(event)
                
                processed_count += 1
                
                # Flush buffer every 100 events
                if len(self.event_buffer) >= 100:
                    await self.save_parquet(self.event_buffer)
                    self.event_buffer.clear()
            
            except Exception as e:
                logger.error(f"Error processing event: {e}")
        
        return processed_count


# Global handler instance
handler = HeliusWebhookHandler()


@router.post("/helius")
async def helius_webhook(
    request: Request,
    x_helius_signature: Optional[str] = Header(None)
):
    """
    Helius Enhanced Webhook Endpoint
    Receives Drift Protocol events from Helius
    
    Webhook Configuration:
    - Program Address: dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH
    - Webhook URL: https://<your-domain>/api/webhooks/helius
    - Event Types: All transaction types
    """
    try:
        # Read request body
        body_bytes = await request.body()
        
        # Verify signature (if configured)
        if x_helius_signature:
            if not handler.verify_signature(body_bytes, x_helius_signature):
                logger.warning("Invalid webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse payload
        payload = json.loads(body_bytes)
        
        # Extract events
        events = payload if isinstance(payload, list) else [payload]
        
        # Filter for Drift events only
        drift_events = handler.filter_drift_events(events)
        
        if not drift_events:
            logger.debug("No Drift events in webhook payload")
            return {
                "status": "ok",
                "processed": 0,
                "message": "No Drift events"
            }
        
        # Process events
        processed_count = await handler.process_events(drift_events)
        
        logger.info(f"Processed {processed_count}/{len(drift_events)} Drift events")
        
        return {
            "status": "ok",
            "processed": processed_count,
            "total": len(events),
            "drift_events": len(drift_events)
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/helius/health")
async def webhook_health():
    """Health check for webhook endpoint"""
    try:
        await handler.connect_redis()
        
        # Get event count from stream
        event_count = await handler.redis.xlen(REDIS_STREAM)
        
        # Get dedup set size
        dedup_count = await handler.redis.scard(REDIS_DEDUP_SET)
        
        return {
            "status": "healthy",
            "redis_connected": True,
            "events_in_stream": event_count,
            "deduplicated_ids": dedup_count,
            "drift_program_id": DRIFT_PROGRAM_ID
        }
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "redis_connected": False,
            "error": str(e)
        }
