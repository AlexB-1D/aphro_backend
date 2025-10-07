from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# -------------------
# Utilisateur
# -------------------
class UserCreate(BaseModel):
    username: str
    password: str
    gender: str

class UserResponse(BaseModel):
    id: str
    username: str
    gender: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserProfile(BaseModel):
    username: str
    gender: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Tu peux ajouter d'autres champs : age, bio, photos, etc.

# -------------------
# Location
# -------------------
class LocationCreate(BaseModel):
    user_id: str
    latitude: float
    longitude: float

# -------------------
# Likes & Matches
# -------------------
class LikeCreate(BaseModel):
    liker_id: str
    liked_id: str

class LikeResponse(BaseModel):
    liker_id: str
    liked_id: str
    created_at: datetime
    match: bool = False

class MatchesResponse(BaseModel):
    matches: List[str]  # liste des user_id

# -------------------
# Tokens
# -------------------
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# -------------------
# Device token
# -------------------
class DeviceToken(BaseModel):
    device_token: str
    platform: str = "android"

# -------------------
# Message
# -------------------
class Message(BaseModel):
    from_user: str
    to_user: str
    content: str
    timestamp: datetime

class MessagesResponse(BaseModel):
    messages: List[Message]
