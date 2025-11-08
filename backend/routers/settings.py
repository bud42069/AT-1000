from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
import os

router = APIRouter(prefix="/api/settings", tags=["settings"])

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://mongodb:27017/')
client = AsyncIOMotorClient(MONGO_URL)
db = client['autotrader']
settings_collection = db['settings']

class UserSettings(BaseModel):
    userId: str
    max_leverage: int = 10
    risk_per_trade: float = 0.75  # 75 bps
    daily_drawdown_limit: float = 2.0  # 2%
    priority_fee_cap: int = 1000  # microlamports
    delegate_enabled: bool = False
    strategy_enabled: bool = False

@router.get("/")
async def get_settings(user_id: str):
    """Get user settings"""
    settings = await settings_collection.find_one({"userId": user_id})
    if not settings:
        # Return defaults
        return UserSettings(userId=user_id).dict()
    return settings

@router.put("/")
async def update_settings(settings: UserSettings):
    """Update user settings"""
    result = await settings_collection.update_one(
        {"userId": settings.userId},
        {"$set": settings.dict()},
        upsert=True
    )
    return {"message": "Settings updated", "userId": settings.userId}