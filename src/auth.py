# backend/src/auth.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from bson import ObjectId

from .database import users_collection

# -------------------------
# Configuration (env vars)
# -------------------------
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", "dev-refresh-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))     # ex: 60 min
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))       # ex: 30 days

# -------------------------
# Password hashing
# -------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---- helpers for bcrypt 72-bytes limit ----
def _normalize_password_for_bcrypt(password) -> str:
    """
    Ensure we pass an UTF-8 string truncated to 72 bytes for bcrypt.
    Accepts str or other types (coerces to str).
    """
    if password is None:
        raise ValueError("Password is required")
    # coerce to str (covers accidental objects)
    if not isinstance(password, str):
        password = str(password)
    # encode -> take first 72 bytes -> decode while ignoring partial char
    b = password.encode("utf-8")
    if len(b) > 72:
        truncated = b[:72].decode("utf-8", "ignore")
        return truncated
    return password

def hash_password(password: str) -> str:
    """
    Hash password safely with bcrypt truncation rule handled.
    """
    try:
        normalized = _normalize_password_for_bcrypt(password)
        return pwd_context.hash(normalized)
    except Exception as e:
        # raise a HTTPException so the endpoint can give a readable 400/500
        raise HTTPException(status_code=500, detail=f"Error hashing password: {e}")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        normalized = _normalize_password_for_bcrypt(plain_password)
        return pwd_context.verify(normalized, hashed_password)
    except Exception:
        return False

# -------------------------
# OAuth2 scheme (docs)
# -------------------------
# tokenUrl is used for the OpenAPI docs. Your login endpoint is '/login/' in main.py
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/")

# -------------------------
# JWT helpers
# -------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create an access JWT containing user_id and exp. Type set to 'access'."""
    expire = _now_utc() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"user_id": str(user_id), "exp": int(expire.timestamp()), "type": "access"}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a refresh JWT containing user_id and exp. Type set to 'refresh'."""
    expire = _now_utc() + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    payload = {"user_id": str(user_id), "exp": int(expire.timestamp()), "type": "refresh"}
    token = jwt.encode(payload, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return token

def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate an access token; raise HTTPException on error."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise JWTError("Wrong token type")
        return payload
    except JWTError as e:
        # unify error for FastAPI
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide ou expiré") from e

def verify_refresh_token(token: str) -> Dict[str, Any]:
    """Decode and validate a refresh token; raise HTTPException on error."""
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise JWTError("Wrong token type")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalide ou expiré") from e

# -------------------------
# User lookup helpers
# -------------------------
async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Return user document dict with stringified _id or None."""
    if not user_id:
        return None
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return None
    user = await users_collection.find_one({"_id": obj_id})
    if not user:
        return None
    user["_id"] = str(user["_id"])
    return user

async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    user = await users_collection.find_one({"username": username})
    if not user:
        return None
    user["_id"] = str(user["_id"])
    return user

async def authenticate_user(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
    """Find user by username or email and verify password. Returns user dict or None."""
    query = {"$or": [{"username": username_or_email}, {"email": username_or_email}]}
    user = await users_collection.find_one(query)
    if not user:
        return None
    if not verify_password(password, user["password"]):
        return None
    user["_id"] = str(user["_id"])
    return user

# -------------------------
# FastAPI dependencies
# -------------------------
async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Dependency that returns the full user document (dict) for the token.
    Use this when your endpoint needs the user object (e.g. current_user["_id"]).
    """
    payload = decode_access_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide : user_id manquant")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    return user

async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependency that returns just the user_id (string).
    Use this when your endpoint signature expects user_id: str = Depends(get_current_user_id).
    """
    payload = decode_access_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")
    return str(user_id)
