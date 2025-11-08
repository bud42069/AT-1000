"""
Delegation Router
Handles Drift Protocol delegation (set/revoke) via backend
Calls TypeScript worker service for Drift SDK operations
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import aiohttp
import logging
from datetime import datetime, timezone

from auth.siws import get_current_wallet

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/delegate", tags=["delegation"])

# Worker service configuration
DRIFT_WORKER_URL = "http://localhost:8002"


class DelegateRequest(BaseModel):
    """Request to set delegate authority"""
    delegate_pubkey: str
    sub_account_id: int = 0


class DelegateResponse(BaseModel):
    """Delegation response"""
    tx_signature: str
    delegate_pubkey: str
    status: str
    timestamp: int


@router.post("/set", response_model=DelegateResponse)
async def set_delegate(
    request: DelegateRequest,
    wallet: str = Depends(get_current_wallet)
):
    """
    Set delegate authority for automated trading
    Requires: Valid JWT from SIWS authentication
    
    Delegation allows a limited authority to:
    - Place orders
    - Cancel orders
    
    Delegate CANNOT:
    - Withdraw funds
    - Modify account settings
    - Close the account
    
    Reference: https://docs.drift.trade/getting-started/delegated-accounts
    """
    try:
        logger.info(f"Setting delegate for wallet {wallet} → {request.delegate_pubkey}")
        
        # Call Drift worker service to execute delegation
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{DRIFT_WORKER_URL}/delegate/set",
                json={
                    "wallet": wallet,
                    "delegate_pubkey": request.delegate_pubkey,
                    "sub_account_id": request.sub_account_id
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Worker error: {error_text}")
                    raise HTTPException(status_code=500, detail=f"Delegation failed: {error_text}")
                
                result = await resp.json()
                
                return DelegateResponse(
                    tx_signature=result['tx_signature'],
                    delegate_pubkey=request.delegate_pubkey,
                    status="active",
                    timestamp=int(datetime.now(timezone.utc).timestamp() * 1000)
                )
    
    except aiohttp.ClientError as e:
        logger.error(f"Failed to connect to worker service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Delegation service unavailable. Please try again."
        )
    except Exception as e:
        logger.error(f"Delegation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/revoke", response_model=DelegateResponse)
async def revoke_delegate(
    sub_account_id: int = 0,
    wallet: str = Depends(get_current_wallet)
):
    """
    Revoke delegate authority
    Requires: Valid JWT from SIWS authentication
    
    Sets delegate to null address (Solana SystemProgram)
    """
    try:
        logger.info(f"Revoking delegate for wallet {wallet}")
        
        # Call Drift worker service to revoke delegation
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{DRIFT_WORKER_URL}/delegate/revoke",
                json={
                    "wallet": wallet,
                    "sub_account_id": sub_account_id
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Worker error: {error_text}")
                    raise HTTPException(status_code=500, detail=f"Revoke failed: {error_text}")
                
                result = await resp.json()
                
                return DelegateResponse(
                    tx_signature=result['tx_signature'],
                    delegate_pubkey="11111111111111111111111111111111",  # SystemProgram (null)
                    status="inactive",
                    timestamp=int(datetime.now(timezone.utc).timestamp() * 1000)
                )
    
    except aiohttp.ClientError as e:
        logger.error(f"Failed to connect to worker service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Delegation service unavailable. Please try again."
        )
    except Exception as e:
        logger.error(f"Revoke error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_delegate_status(wallet: str = Depends(get_current_wallet)):
    """
    Get current delegation status for user
    Returns delegate pubkey and status
    """
    try:
        # Call Drift worker service to check delegation status
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{DRIFT_WORKER_URL}/delegate/status",
                params={"wallet": wallet},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return {
                        "wallet": wallet,
                        "delegate_pubkey": None,
                        "status": "unknown",
                        "error": "Failed to fetch status"
                    }
                
                result = await resp.json()
                
                return {
                    "wallet": wallet,
                    "delegate_pubkey": result.get('delegate_pubkey'),
                    "status": result.get('status', 'unknown'),
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
                }
    
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return {
            "wallet": wallet,
            "delegate_pubkey": None,
            "status": "error",
            "error": str(e)
        }
