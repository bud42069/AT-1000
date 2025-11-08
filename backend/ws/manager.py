"""WebSocket Manager for Real-time Event Broadcasting"""
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
clients: Set[WebSocket] = set()

@router.websocket("/api/ws/engine.events")
async def ws_events(ws: WebSocket):
    """WebSocket endpoint for engine events"""
    await ws.accept()
    clients.add(ws)
    logger.info(f"Client connected. Total clients: {len(clients)}")
    
    try:
        while True:
            # Keep connection alive (ignore incoming messages)
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
        logger.info(f"Client disconnected. Total clients: {len(clients)}")

async def broadcast(event: dict):
    """Broadcast event to all connected clients"""
    if not clients:
        return
    
    dead = []
    for ws in clients:
        try:
            await ws.send_json(event)
        except Exception as e:
            logger.error(f"Failed to send to client: {e}")
            dead.append(ws)
    
    for ws in dead:
        clients.discard(ws)
    
    logger.debug(f"Broadcasted event to {len(clients) - len(dead)} clients")