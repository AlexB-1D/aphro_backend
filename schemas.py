from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    password: str
    gender: str

class LocationCreate(BaseModel):
    user_id: str
    latitude: float
    longitude: float

class LikeCreate(BaseModel):
    liker_id: str
    liked_id: str
