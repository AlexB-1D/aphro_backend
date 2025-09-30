# chat.py
import asyncio, datetime
from fastapi import WebSocket, WebSocketDisconnect
from backend.database import messages_collection, device_tokens_collection
from backend import crud
from backend.notifications import send_push_notification

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}  # user_id -> websocket

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_json(message)

manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            to_user = data.get("to_user")
            content = data.get("content")

            # Vérifie que les deux utilisateurs sont matchés
            matches = await crud.get_matches(user_id)
            if to_user not in matches:
                await websocket.send_json({"error": "Vous ne pouvez envoyer des messages qu'à vos matchs."})
                continue

            # Stocke le message
            message_doc = {
                "from_user": user_id,
                "to_user": to_user,
                "content": content,
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
                "read": False
            }
            await messages_collection.insert_one(message_doc)

            # Envoie en temps réel via WebSocket
            await manager.send_personal_message(message_doc, to_user)

            # Notifications push via FCM
            tokens = await device_tokens_collection.find({"user_id": to_user}).to_list(None)
            for t in tokens:
                await send_push_notification(
                    t["device_token"],
                    title="Nouveau message",
                    body=f"Vous avez un nouveau message de {user_id}",
                    data={"from_user": user_id, "type": "message"}
                )

    except WebSocketDisconnect:
        manager.disconnect(user_id)
