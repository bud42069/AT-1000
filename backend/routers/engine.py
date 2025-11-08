from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import json
import uuid

router = APIRouter(prefix="/api/engine", tags=["engine"])

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

# Endpoints
@router.post("/orders", response_model=OrderResponse)
async def place_order(intent: OrderIntent):
    """Place new order via execution engine"""
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
    """Health check"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

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