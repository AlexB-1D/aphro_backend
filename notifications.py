# notifications.py
import os
import json
from firebase_admin import messaging, credentials, initialize_app

# Charger le JSON du service account depuis la variable d'environnement
firebase_json = os.getenv("FCM_SERVICE_ACCOUNT")

if firebase_json:
    service_account_info = json.loads(firebase_json)
    cred = credentials.Certificate(service_account_info)
    initialize_app(cred)
else:
    print("⚠️  Aucun compte de service FCM trouvé, les notifications push ne fonctionneront pas.")

async def send_push_notification(device_token: str, title: str, body: str, data: dict = None):
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=device_token,
        data=data or {}
    )
    response = messaging.send(message)
    return response
