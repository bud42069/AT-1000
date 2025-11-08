from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import json
import uuid
import redis.asyncio as aioredis
import os
import logging
from backend.services.basis import get_basis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engine", tags=["engine"])

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
STREAM_BOOK = "market:solusdt:book"
STREAM_FUNDING = "market:solusdt:funding"
STREAM_LIQUIDATIONS = "market:solusdt:liquidations"

# Cache
guards_cache = {}
guards_cache_time = None
CACHE_TTL = 5  # seconds

# In-memory storage for POC (replace with Redis/MongoDB later)
orders = {}
activity_log = []
active_clients = []

# Models
class OrderIntent(BaseModel):
    side: str  # "long" | "short"
    type: str = "post_only_limit"
    px: float
    size: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    leverage: int
    venue: str = "drift"
    notes: Optional[str] = None

class CancelRequest(BaseModel):
    orderId: str

class KillRequest(BaseModel):
    reason: str

class OrderResponse(BaseModel):
    orderId: str
    status: str
    timestamp: str

# Helper: Broadcast WS event
async def broadcast_event(event: dict):
    for client in active_clients:
        try:
            await client.send_text(json.dumps(event))
        except:
            pass

# Redis Stream for intents
INTENT_STREAM = "engine:intents"

# Endpoints
@router.post("/orders", response_model=OrderResponse)
async def place_order(intent: OrderIntent):
    """
    Place new order via execution engine
    Publishes intent to Redis Stream for consumption by TypeScript execution worker
    """
    order_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    order = {
        "orderId": order_id,
        "status": "submitted",
        "intent": intent.dict(),
        "timestamp": timestamp,
        "attempts": 0
    }
    
    orders[order_id] = order
    activity_log.append({
        "time": timestamp,
        "type": "order_submitted",
        "details": f"{intent.side.upper()} {intent.size} @ {intent.px}",
        "status": "pending",
        "statusBg": "#67E8F9"
    })
    
    # Publish intent to Redis Stream for execution engine
    try:
        redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        
        await redis.xadd(
            INTENT_STREAM,
            {
                'order_id': order_id,
                'venue': intent.venue,
                'side': intent.side,
                'type': intent.type,
                'px': str(intent.px),
                'size': str(intent.size),
                'sl': str(intent.sl),
                'tp1': str(intent.tp1),
                'tp2': str(intent.tp2),
                'tp3': str(intent.tp3),
                'leverage': str(intent.leverage),
                'sub_account_id': '0'
            },
            maxlen=1000
        )
        
        await redis.close()
        
        logger.info(f"Published intent to Redis Stream: {order_id}")
        
    except Exception as e:
        logger.error(f"Failed to publish intent to Redis: {e}")
        # Continue anyway - order is still tracked locally
    
    # Broadcast event
    await broadcast_event({
        "type": "order_submitted",
        "orderId": order_id,
        "data": intent.dict()
    })
    
    return OrderResponse(
        orderId=order_id,
        status="submitted",
        timestamp=timestamp
    )

@router.post("/cancel")
async def cancel_order(req: CancelRequest):
    """Cancel an existing order"""
    if req.orderId not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    
    orders[req.orderId]["status"] = "cancelled"
    timestamp = datetime.now(timezone.utc).isoformat()
    
    activity_log.append({
        "time": timestamp,
        "type": "order_cancelled",
        "details": f"Order {req.orderId[:8]}...",
        "status": "cancelled",
        "statusBg": "#6B7280"
    })
    
    await broadcast_event({
        "type": "order_cancelled",
        "orderId": req.orderId
    })
    
    return {"message": "Order cancelled", "orderId": req.orderId}

@router.post("/kill")
async def kill_switch(req: KillRequest):
    """Emergency stop: cancel all orders and disable automation"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Cancel all active orders
    cancelled_count = 0
    for order_id, order in orders.items():
        if order["status"] in ["submitted", "open"]:
            order["status"] = "cancelled"
            cancelled_count += 1
    
    activity_log.append({
        "time": timestamp,
        "type": "kill_switch",
        "details": f"Emergency stop: {req.reason}. Cancelled {cancelled_count} orders.",
        "status": "stopped",
        "statusBg": "#F43F5E"
    })
    
    await broadcast_event({
        "type": "kill_switch",
        "reason": req.reason,
        "cancelled": cancelled_count
    })
    
    return {
        "message": "Kill switch activated",
        "reason": req.reason,
        "cancelled": cancelled_count
    }

@router.get("/ping")
async def ping():
    """Health check with version"""
    from pathlib import Path
    version_file = Path(__file__).parent.parent.parent / 'VERSION.txt'
    version = version_file.read_text().strip() if version_file.exists() else "unknown"
    return {
        "status": "ok",
        "version": version,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get("/guards")
async def get_guards():
    """Get current risk guard metrics (LIVE DATA from Redis Streams)"""
    global guards_cache, guards_cache_time
    
    # Check cache
    if guards_cache_time and (datetime.now(timezone.utc) - guards_cache_time).total_seconds() < CACHE_TTL:
        return guards_cache
    
    try:
        # Connect to Redis
        redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        
        # Read latest data from streams
        book_result = await redis.xrevrange(STREAM_BOOK, count=1)
        funding_result = await redis.xrevrange(STREAM_FUNDING, count=1)
        
        # Count recent liquidations (last 5 minutes)
        cutoff_time = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp() * 1000)
        liq_result = await redis.xrange(STREAM_LIQUIDATIONS, min=f"{cutoff_time}-0")
        liq_count = len(liq_result)
        
        await redis.close()
        
        # Parse book data
        spread_bps = 0.0
        depth_bid_usd = 0.0
        depth_ask_usd = 0.0
        
        if book_result:
            book_data = book_result[0][1]
            spread_bps = float(book_data.get('spread_bps', 0))
            depth_bid_usd = float(book_data.get('depth_10bps_bid_usd', 0))
            depth_ask_usd = float(book_data.get('depth_10bps_ask_usd', 0))
        
        # Parse funding data
        funding_apr = 0.0
        oi_notional = 0.0
        
        if funding_result:
            funding_data = funding_result[0][1]
            funding_apr = float(funding_data.get('funding_apr', 0))
            oi_notional = float(funding_data.get('oi_notional', 0))
        
        # Calculate basis (USDT vs USDC)
        basis_bps = await get_basis(use_cache=True)
        
        # Determine status
        status = "passing"
        warnings = []
        
        if spread_bps > 10:
            status = "warning"
            warnings.append(f"Spread: {spread_bps:.2f}bps")
        
        if depth_bid_usd < 50000 or depth_ask_usd < 50000:
            status = "warning"
            warnings.append(f"Low depth: ${min(depth_bid_usd, depth_ask_usd):,.0f}")
        
        if abs(funding_apr) > 300:
            status = "warning"
            warnings.append(f"High funding: {funding_apr:.1f}%")
        
        if liq_count > 10:
            status = "breach"
            warnings.append(f"{liq_count} liquidations in 5min")
        
        result = {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "spread_bps": round(spread_bps, 2),
            "depth_10bps": {
                "bid_usd": round(depth_bid_usd, 2),
                "ask_usd": round(depth_ask_usd, 2)
            },
            "funding_apr": round(funding_apr, 2),
            "basis_bps": round(basis_bps, 2),
            "oi_notional": round(oi_notional, 2),
            "liq_events_5m": liq_count,
            "status": status,
            "warnings": warnings,
            "data_source": "live"
        }
        
        # Update cache
        guards_cache = result
        guards_cache_time = datetime.now(timezone.utc)
        
        return result
    
    except Exception as e:
        logger.error(f"Error fetching live guards data: {e}")
        
        # Fallback to mock data
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "spread_bps": 6.2,
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
            "data_source": "fallback",
            "error": str(e)
        }

@router.get("/activity")
async def get_activity():
    """Get activity log"""
    return {"logs": activity_log[-100:]}  # Last 100 entries

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time engine events"""
    await websocket.accept()
    active_clients.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or handle client messages if needed
    except WebSocketDisconnect:
        active_clients.remove(websocket)