from fastapi import APIRouter, Depends, HTTPException, status
from src.auth import get_current_user
from src.database import users_collection
from src.models import User
from bson import ObjectId

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Retourne les informations de l'utilisateur connecté.
    """
    user = await users_collection.find_one({"_id": ObjectId(current_user["_id"])})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    user["_id"] = str(user["_id"])
    return user


@router.put("/update", response_model=User)
async def update_user(data: dict, current_user: dict = Depends(get_current_user)):
    """
    Permet de modifier certaines informations utilisateur (ex : username).
    """
    new_username = data.get("username")

    if not new_username or len(new_username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur invalide")

    result = await users_collection.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {"username": new_username.strip()}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Aucune modification apportée")

    user = await users_collection.find_one({"_id": ObjectId(current_user["_id"])})
    user["_id"] = str(user["_id"])
    return user
