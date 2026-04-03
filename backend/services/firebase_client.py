from datetime import datetime, timedelta, timezone

import firebase_admin
from firebase_admin import auth, credentials, firestore

from config import Config

_app = None
_db = None
_token_cache = {}
_TOKEN_CACHE_TTL = timedelta(minutes=5)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_credentials():
    if Config.FIREBASE_SERVICE_ACCOUNT_KEY_PATH:
        return credentials.Certificate(Config.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)

    if Config.FIREBASE_PROJECT_ID and Config.FIREBASE_CLIENT_EMAIL and Config.FIREBASE_PRIVATE_KEY:
        return credentials.Certificate({
            "type": "service_account",
            "project_id": Config.FIREBASE_PROJECT_ID,
            "client_email": Config.FIREBASE_CLIENT_EMAIL,
            "private_key": Config.FIREBASE_PRIVATE_KEY,
            "token_uri": "https://oauth2.googleapis.com/token",
        })

    return credentials.ApplicationDefault()


def get_firebase_app():
    global _app
    if _app is None:
        options = {}
        if Config.FIREBASE_PROJECT_ID:
            options["projectId"] = Config.FIREBASE_PROJECT_ID
        _app = firebase_admin.initialize_app(_build_credentials(), options or None)
    return _app


def get_firestore():
    global _db
    if _db is None:
        _db = firestore.client(app=get_firebase_app())
    return _db


def create_conversation(user_id: str, title: str = "New Trip") -> dict:
    db = get_firestore()
    doc_ref = db.collection("conversations").document()
    now = _utc_now_iso()
    payload = {
        "id": doc_ref.id,
        "user_id": user_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(payload)
    return payload


def get_conversations(user_id: str) -> list[dict]:
    db = get_firestore()
    conversations = [
        {**(doc.to_dict() or {}), "id": doc.id}
        for doc in db.collection("conversations").where("user_id", "==", user_id).stream()
    ]
    return sorted(conversations, key=lambda convo: convo.get("updated_at", ""), reverse=True)


def save_message(conversation_id: str, role: str, content: str, metadata: dict | None = None):
    db = get_firestore()
    message_ref = db.collection("conversations").document(conversation_id).collection("messages").document()
    now = _utc_now_iso()
    payload = {
        "id": message_ref.id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "created_at": now,
    }
    if metadata:
        payload["metadata"] = metadata

    message_ref.set(payload)
    db.collection("conversations").document(conversation_id).set({"updated_at": now}, merge=True)


def get_messages(conversation_id: str) -> list[dict]:
    db = get_firestore()
    messages = [
        {**(doc.to_dict() or {}), "id": doc.id}
        for doc in db.collection("conversations").document(conversation_id).collection("messages").stream()
    ]
    return sorted(messages, key=lambda message: message.get("created_at", ""))


def save_itinerary(conversation_id: str, user_id: str, itinerary_data: dict) -> dict:
    db = get_firestore()
    doc_ref = db.collection("itineraries").document(conversation_id)
    existing = doc_ref.get()
    now = _utc_now_iso()
    payload = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "data": itinerary_data,
        "updated_at": now,
    }
    if not existing.exists:
        payload["created_at"] = now
    doc_ref.set(payload, merge=True)
    return {**payload, "id": conversation_id}


def get_itinerary(conversation_id: str) -> dict | None:
    db = get_firestore()
    snapshot = db.collection("itineraries").document(conversation_id).get()
    if not snapshot.exists:
        return None
    return {**(snapshot.to_dict() or {}), "id": snapshot.id}


def verify_token(access_token: str) -> dict | None:
    now = datetime.now(timezone.utc)
    cached = _token_cache.get(access_token)
    if cached and cached["expires_at"] > now:
        return cached["user"]

    try:
        decoded = auth.verify_id_token(access_token, app=get_firebase_app())
        user = {
            "id": decoded["uid"],
            "email": decoded.get("email"),
        }
        _token_cache[access_token] = {
            "user": user,
            "expires_at": now + _TOKEN_CACHE_TTL,
        }
        return user
    except Exception:
        _token_cache.pop(access_token, None)
        return None
