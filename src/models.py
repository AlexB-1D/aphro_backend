from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# ✅ Modèle utilisateur de base
class User(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    username: Optional[str]
    email: EmailStr

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {}


# ✅ Modèle pour la création de compte
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


# ✅ Modèle pour la connexion
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ✅ Modèle pour le token JWT
class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


# ✅ Réponse utilisateur après connexion
class UserResponse(BaseModel):
    id: str
    username: str
    email: str
