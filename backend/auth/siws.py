"""Sign-In With Solana (SIWS) Authentication"""
import time
import os
import jwt
import base58
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

JWT_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
JWT_AUDIENCE = "at-1000"
JWT_ISSUER = "at-1000-backend"
SESSION_TTL = 60 * 60 * 12  # 12 hours

class ChallengeOut(BaseModel):
    message: str
    nonce: str
    exp: int

class VerifyIn(BaseModel):
    publicKey: str  # base58
    message: str
    signature: str  # base58
    nonce: str

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.get("/siws/challenge", response_model=ChallengeOut)
async def siws_challenge():
    """Generate SIWS challenge message"""
    nonce = base58.b58encode(os.urandom(16)).decode()
    exp = int(time.time()) + 300  # 5 min
    message = f"AT-1000 wants you to sign in.\nnonce={nonce}\nexp={exp}\naud={JWT_AUDIENCE}"
    return {"message": message, "nonce": nonce, "exp": exp}

@router.post("/siws/verify")
async def siws_verify(body: VerifyIn, request: Request):
    """Verify SIWS signature and issue JWT"""
    try:
        # Basic anti-replay: exp & aud must be present in signed message
        if f"nonce={body.nonce}" not in body.message:
            raise HTTPException(400, "nonce missing")
        
        lines = dict([l.split("=", 1) for l in body.message.split("\n") if "=" in l])
        
        if "exp" not in lines or "aud" not in lines:
            raise HTTPException(400, "bad message")
        
        if lines["aud"] != JWT_AUDIENCE:
            raise HTTPException(400, "aud mismatch")
        
        if int(lines["exp"]) < int(time.time()):
            raise HTTPException(400, "challenge expired")

        # Verify signature
        pk_bytes = base58.b58decode(body.publicKey)
        sig_bytes = base58.b58decode(body.signature)
        VerifyKey(pk_bytes).verify(body.message.encode("utf-8"), sig_bytes)
        
    except BadSignatureError:
        raise HTTPException(401, "signature invalid")
    except Exception as e:
        raise HTTPException(400, f"verification failed: {str(e)}")

    # Issue JWT (header-only auth; no cookies ⇒ CSRF minimized)
    token = jwt.encode(
        {
            "sub": body.publicKey,
            "aud": JWT_AUDIENCE,
            "iss": JWT_ISSUER,
            "iat": int(time.time()),
            "exp": int(time.time()) + SESSION_TTL,
            "ip": request.client.host,
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    
    return {"token": token, "wallet": body.publicKey}

# Auth dependency for protected routes
from fastapi import Depends, Header

def get_current_wallet(authorization: str = Header(None)) -> str:
    """Extract wallet from JWT token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid authorization header")
    
    token = authorization.split(" ")[1]
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], audience=JWT_AUDIENCE)
        return payload["sub"]  # wallet public key
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")