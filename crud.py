# crud.py
from bson import ObjectId
from backend.database import users_collection, likes_collection, tokens_collection
from datetime import datetime, timezone
import math

# -------------------
# Utilisateurs
# -------------------
async def create_user(user_dict):
    result = await users_collection.insert_one(user_dict)
    return await users_collection.find_one({"_id": result.inserted_id})

async def get_user_by_username(username: str):
    return await users_collection.find_one({"username": username})

async def get_user(user_id: str):
    return await users_collection.find_one({"_id": ObjectId(user_id)})

# -------------------
# Localisation
# -------------------
async def update_location(user_id: str, lat: float, lng: float):
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"location": {"type": "Point", "coordinates": [lng, lat]}}}
    )

# Assure toi que l'index 2dsphere existe (à exécuter une fois)
async def create_location_index():
    await users_collection.create_index([("location", "2dsphere")])

# -------------------
# Nearby Users
# -------------------
async def get_nearby_users(user_id: str, max_distance_m=100):
    user = await get_user(user_id)
    if not user or "location" not in user:
        return []

    user_lng, user_lat = user["location"]["coordinates"]

    nearby = await users_collection.find({
        "location": {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [user_lng, user_lat]},
                "$maxDistance": max_distance_m
            }
        },
        "_id": {"$ne": ObjectId(user_id)}
    }).to_list(20)  # limite 20 utilisateurs

    return nearby

# -------------------
# Likes & Matches
# -------------------
async def create_like(liker_id: str, liked_id: str):
    # Evite doublons
    existing = await likes_collection.find_one({"liker_id": liker_id, "liked_id": liked_id})
    if existing:
        return {"message": "Like déjà existant"}

    await likes_collection.insert_one({"liker_id": liker_id, "liked_id": liked_id, "created_at": datetime.now(timezone.utc)})

    # Vérifie match réciproque
    reciprocal = await likes_collection.find_one({"liker_id": liked_id, "liked_id": liker_id})
    if reciprocal:
        return {"match": True}
    return {"match": False}

async def get_matches(user_id: str):
    # Likes reçus et réciproques
    likes = await likes_collection.find({"liker_id": user_id}).to_list(None)
    matches = []
    for like in likes:
        reciprocal = await likes_collection.find_one({"liker_id": like["liked_id"], "liked_id": user_id})
        if reciprocal:
            matches.append(like["liked_id"])
    return matches

# -------------------
# Détection des croisements
# -------------------
async def detect_crossings(radius_m=100):
    users = await users_collection.find({"location": {"$exists": True}}).to_list(None)
    detected = []
    for i, user_a in enumerate(users):
        lng_a, lat_a = user_a["location"]["coordinates"]
        for user_b in users[i + 1:]:
            lng_b, lat_b = user_b["location"]["coordinates"]
            distance = haversine(lat_a, lng_a, lat_b, lng_b)
            if distance <= radius_m:
                detected.append((str(user_a["_id"]), str(user_b["_id"])))
    return detected

def haversine(lat1, lon1, lat2, lon2):
    # Distance en mètres entre deux points GPS
    R = 6371000  # rayon Terre en m
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
