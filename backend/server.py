from fastapi import FastAPI, APIRouter, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import from_url as redis_from_url
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'autotrader')]

# Create the main app without a prefix
app = FastAPI(title="AT-1000 Auto-Trader Backend", version="1.0.0-phase2")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.get("/version")
async def get_version():
    """Get application version"""
    version_file = Path(__file__).parent.parent / 'VERSION.txt'
    if version_file.exists():
        version = version_file.read_text().strip()
    else:
        version = "1.0.0-phase2"
    return {"version": version, "env": os.environ.get('DRIFT_ENV', 'devnet')}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

# Import and include additional routers
from routers import engine, settings
from auth import siws
from ws import manager

# Startup: Initialize Redis for rate limiting
@app.on_event("startup")
async def startup_event():
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    try:
        r = await redis_from_url(redis_url, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(r)
        logger.info(f"✅ FastAPILimiter initialized with Redis: {redis_url}")
    except Exception as e:
        logger.warning(f"⚠️  Redis not available, rate limiting disabled: {e}")

# Include routers
app.include_router(api_router)
app.include_router(engine.router)
app.include_router(settings.router)
app.include_router(siws.router)
app.include_router(manager.router)

# CORS Configuration (strict)
allowed_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,  # No cookies, JWT in headers only
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()