# main.py
from fastapi import FastAPI, HTTPException, Depends, WebSocket, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import asyncio, time

from backend import crud, schemas, auth
from backend.database import users_collection, likes_collection, tokens_collection, messages_collection, device_tokens_collection
from backend.chat import websocket_endpoint, manager
from backend.notifications import send_push_notification

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# -------------------
# Rate limiting middleware
# -------------------
class RateLimiterMiddleware:
    def __init__(self, app, max_requests: int = 30, window: int = 60):
        self.app = app
        self.max_requests = max_requests
        self.window = window
        self.requests = {}  # user_id -> [timestamps]

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            user_id = headers.get(b"x-user-id", b"anonymous").decode()
            now = time.time()
            timestamps = self.requests.get(user_id, [])
            timestamps = [t for t in timestamps if now - t < self.window]
            if len(timestamps) >= self.max_requests:
                response = JSONResponse({"detail": "Too many requests"}, status_code=429)
                await response(scope, receive, send)
                return
            timestamps.append(now)
            self.requests[user_id] = timestamps
        await self.app(scope, receive, send)

# -------------------
# Dépendance JWT
# -------------------
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = auth.decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide")
    return payload.get("user_id")

# -------------------
# Lifespan avec scheduler
# -------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await crud.create_location_index()

    # Scheduler des croisements
    async def crossing_scheduler():
        while True:
            try:
                detected = await crud.detect_crossings()
                if detected:
                    print(f"[Crossing Scheduler] {len(detected)} nouveaux croisements détectés")
            except Exception as e:
                print(f"[Crossing Scheduler] Erreur : {e}")
            await asyncio.sleep(60)

    # Scheduler cleanup tokens expirés
    async def cleanup_scheduler():
        while True:
            now = datetime.now(timezone.utc)
            await tokens_collection.delete_many({"expires_at": {"$lt": now}})
            await asyncio.sleep(3600)  # toutes les heures

    task_crossing = asyncio.create_task(crossing_scheduler())
    task_cleanup = asyncio.create_task(cleanup_scheduler())
    print("Schedulers démarrés...")

    yield

    task_crossing.cancel()
    task_cleanup.cancel()
    try:
        await task_crossing
    except asyncio.CancelledError:
        print("Scheduler crossing arrêté")
    try:
        await task_cleanup
    except asyncio.CancelledError:
        print("Scheduler cleanup arrêté")

# -------------------
# Application
# -------------------
app = FastAPI(lifespan=lifespan)
app.add_middleware(RateLimiterMiddleware)

origins = [
    "http://localhost:5173",  # ton frontend en dev
    "https://ton-frontend-distant.com",  # ajoute ton frontend deployé ici
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,   # les domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],     # autorise GET, POST, PUT, DELETE…
    allow_headers=["*"],     # autorise tous les headers
)


@app.get("/")
async def root():
    return {"message": "Hello, Aphro!"}

# -------------------
# Endpoints utilisateurs
# -------------------
@app.post("/users/")
async def create_user_endpoint(user: schemas.UserCreate):
    existing = await crud.get_user_by_username(user.username)
    if existing:
        raise HTTPException(status_code=400, detail="Utilisateur déjà existant")
    user_dict = user.model_dump()
    user_dict["password"] = auth.hash_password(user.password)
    new_user = await crud.create_user(user_dict)
    return {"id": str(new_user["_id"]), "username": new_user["username"], "gender": new_user["gender"]}

@app.post("/login/")
async def login(username: str, password: str):
    user = await crud.get_user_by_username(username)
    if not user or not auth.verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    access_token = auth.create_access_token({"user_id": str(user["_id"])})
    refresh_token = auth.create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=auth.REFRESH_TOKEN_EXPIRE_DAYS)

    await tokens_collection.insert_one({
        "user_id": str(user["_id"]),
        "refresh_token": refresh_token,
        "expires_at": expires_at
    })

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

# -------------------
# Refresh / Logout
# -------------------
@app.post("/refresh/")
async def refresh_token(old_refresh_token: str):
    token_doc = await tokens_collection.find_one({"refresh_token": old_refresh_token})
    if not token_doc or token_doc["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré")
    user_id = token_doc["user_id"]
    await tokens_collection.delete_one({"refresh_token": old_refresh_token})

    new_refresh_token = auth.create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=auth.REFRESH_TOKEN_EXPIRE_DAYS)
    await tokens_collection.insert_one({"user_id": user_id, "refresh_token": new_refresh_token, "expires_at": expires_at})
    access_token = auth.create_access_token({"user_id": user_id})
    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

@app.post("/logout/")
async def logout(refresh_token: str):
    result = await tokens_collection.delete_one({"refresh_token": refresh_token})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token non trouvé")
    return {"message": "Refresh token révoqué"}

# -------------------
# Device token
# -------------------
@app.post("/register-device/")
async def register_device(user_id: str = Depends(get_current_user), device_token: str = None, platform: str = "android"):
    if not device_token:
        raise HTTPException(status_code=400, detail="Device token requis")
    await device_tokens_collection.update_one(
        {"user_id": user_id, "device_token": device_token},
        {"$set": {"platform": platform}},
        upsert=True
    )
    return {"message": "Device token enregistré"}

# -------------------
# Localisation
# -------------------
@app.post("/update-location/")
async def update_location_endpoint(loc: schemas.LocationCreate, user_id: str = Depends(get_current_user)):
    if user_id != loc.user_id:
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas modifier la position d'un autre utilisateur")
    await crud.update_location(loc.user_id, loc.latitude, loc.longitude)
    return {"message": "Position mise à jour"}

# -------------------
# Likes & Matches
# -------------------
@app.post("/like/")
async def like_endpoint(like: schemas.LikeCreate, user_id: str = Depends(get_current_user)):
    if user_id != like.liker_id:
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas liker pour un autre utilisateur")
    result = await crud.create_like(like.liker_id, like.liked_id)
    if result.get("match"):
        for uid in [like.liker_id, like.liked_id]:
            tokens = await device_tokens_collection.find({"user_id": uid}).to_list(None)
            for t in tokens:
                await send_push_notification(
                    t["device_token"],
                    title="Nouveau match !",
                    body="Vous avez un nouveau match 🎉",
                    data={"type": "match"}
                )
    return result

@app.get("/matches/")
async def matches_endpoint(user_id: str = Depends(get_current_user)):
    return await crud.get_matches(user_id)

@app.get("/likes-history/")
async def likes_history(user_id: str = Depends(get_current_user)):
    given = await likes_collection.find({"liker_id": user_id}).to_list(None)
    received = await likes_collection.find({"liked_id": user_id}).to_list(None)
    matches = [l["liked_id"] for l in given if await likes_collection.find_one({"liker_id": l["liked_id"], "liked_id": user_id})]
    return {
        "likes_given": [{"liked_id": l["liked_id"], "created_at": l["created_at"], "match": l["liked_id"] in matches} for l in given],
        "likes_received": [{"liker_id": l["liker_id"], "created_at": l["created_at"], "match": l["liker_id"] in matches} for l in received]
    }

@app.get("/matches-history/")
async def matches_history(user_id: str = Depends(get_current_user)):
    matches = await crud.get_matches(user_id)
    return {"matches": matches}

# -------------------
# Nearby users avec pagination
# -------------------
@app.get("/nearby-users/")
async def nearby_users_endpoint(user_id: str = Depends(get_current_user), skip: int = 0, limit: int = 20):
    users = await crud.get_nearby_users(user_id, skip=skip, limit=limit)
    return {"nearby_users": users}

# -------------------
# Détection manuelle des croisements
# -------------------
@app.get("/detect-crossings/")
async def detect_crossings_endpoint():
    detected = await crud.detect_crossings()
    return detected

# -------------------
# WebSocket Messagerie
# -------------------
@app.websocket("/ws/{user_id}")
async def websocket_route(websocket: WebSocket, user_id: str):
    await websocket_endpoint(websocket, user_id)

# -------------------
# Historique des messages avec pagination
# -------------------
@app.get("/messages/{other_user_id}")
async def get_messages(other_user_id: str, skip: int = 0, limit: int = 20, user_id: str = Depends(get_current_user)):
    messages = await messages_collection.find({
        "$or": [
            {"from_user": user_id, "to_user": other_user_id},
            {"from_user": other_user_id, "to_user": user_id}
        ]
    }).sort("timestamp", 1).skip(skip).limit(limit).to_list(None)
    return {"messages": messages}
