from supabase import create_client, Client
from config import Config

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
    return _client


# ── Conversation persistence ───────────────────────────────────────────

def create_conversation(user_id: str, title: str = "New Trip") -> dict:
    sb = get_supabase()
    result = (
        sb.table("conversations")
        .insert({"user_id": user_id, "title": title})
        .execute()
    )
    return result.data[0]


def get_conversations(user_id: str) -> list[dict]:
    sb = get_supabase()
    result = (
        sb.table("conversations")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data


def save_message(conversation_id: str, role: str, content: str, metadata: dict | None = None):
    sb = get_supabase()
    row = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
    }
    if metadata:
        row["metadata"] = metadata
    sb.table("messages").insert(row).execute()


def get_messages(conversation_id: str) -> list[dict]:
    sb = get_supabase()
    result = (
        sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return result.data


# ── Trip itinerary persistence ─────────────────────────────────────────

def save_itinerary(conversation_id: str, user_id: str, itinerary_data: dict) -> dict:
    sb = get_supabase()
    result = (
        sb.table("itineraries")
        .upsert({
            "conversation_id": conversation_id,
            "user_id": user_id,
            "data": itinerary_data,
        })
        .execute()
    )
    return result.data[0]


def get_itinerary(conversation_id: str) -> dict | None:
    sb = get_supabase()
    result = (
        sb.table("itineraries")
        .select("*")
        .eq("conversation_id", conversation_id)
        .maybe_single()
        .execute()
    )
    return result.data


# ── Auth helpers ───────────────────────────────────────────────────────

def verify_token(access_token: str) -> dict | None:
    """Verify a Supabase JWT and return the user object."""
    sb = get_supabase()
    try:
        user_resp = sb.auth.get_user(access_token)
        return {"id": user_resp.user.id, "email": user_resp.user.email}
    except Exception:
        return None
