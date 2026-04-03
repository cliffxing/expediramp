"""
Chat API routes.

POST /api/chat          — Send a message, get a response (non-streaming)
POST /api/chat/stream   — Send a message, get SSE stream
GET  /api/conversations — List conversations for the authenticated user
GET  /api/conversations/<id>/messages — Get messages for a conversation
"""

import json
import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context
from agents.travel_agent import run_agent, run_agent_streaming
from agents.tools import SYSTEM_PROMPT
from services.firebase_client import (
    create_conversation,
    get_conversations,
    save_message,
    get_messages,
    save_itinerary,
    verify_token,
)

logger = logging.getLogger(__name__)
chat_bp = Blueprint("chat", __name__)


def _get_user_optional():
    """Extract user from Authorization header, or return None for anonymous."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return verify_token(token)
    return None


@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    """Non-streaming chat endpoint."""
    body = request.get_json(force=True)
    user_message = body.get("message", "").strip()
    conversation_id = body.get("conversation_id")
    history = body.get("history", [])

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    user = _get_user_optional()

    # Build OpenAI messages from history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    # Persist user message
    if user and conversation_id:
        try:
            save_message(conversation_id, "user", user_message)
        except Exception as e:
            logger.warning("Failed to save user message: %s", e)

    # Run agent
    try:
        result = run_agent(messages)
    except Exception as exc:
        logger.exception("Agent error")
        return jsonify({"error": str(exc)}), 500

    # Persist assistant reply
    if user and conversation_id:
        try:
            save_message(
                conversation_id,
                "assistant",
                result["reply"],
                metadata={"itinerary": result["itinerary"]} if result["itinerary"] else None,
            )
            if result["itinerary"]:
                save_itinerary(conversation_id, user["id"], result["itinerary"])
        except Exception as e:
            logger.warning("Failed to save assistant message: %s", e)

    return jsonify({
        "reply": result["reply"],
        "itinerary": result["itinerary"],
        "tools_used": result["tool_calls_made"],
        "conversation_id": conversation_id,
    })


@chat_bp.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Streaming chat endpoint using Server-Sent Events."""
    body = request.get_json(force=True)
    user_message = body.get("message", "").strip()
    conversation_id = body.get("conversation_id")
    history = body.get("history", [])

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    user = _get_user_optional()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    if user and conversation_id:
        try:
            save_message(conversation_id, "user", user_message)
        except Exception:
            pass

    def generate():
        full_reply = ""
        itinerary = None
        try:
            for event in run_agent_streaming(messages):
                if event["type"] == "token":
                    full_reply += event["data"]
                elif event["type"] == "itinerary":
                    itinerary = event["data"]
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.exception("Streaming agent error")
            yield f"data: {json.dumps({'type': 'error', 'data': str(exc)})}\n\n"

        # Persist after stream completes
        if user and conversation_id and full_reply:
            try:
                save_message(
                    conversation_id,
                    "assistant",
                    full_reply,
                    metadata={"itinerary": itinerary} if itinerary else None,
                )
                if itinerary:
                    save_itinerary(conversation_id, user["id"], itinerary)
            except Exception:
                pass

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@chat_bp.route("/api/conversations", methods=["GET", "OPTIONS"])
def list_conversations():
    if request.method == "OPTIONS":
        return ("", 204)
    user = _get_user_optional()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    convos = get_conversations(user["id"])
    return jsonify({"conversations": convos})


@chat_bp.route("/api/conversations", methods=["POST", "OPTIONS"])
def new_conversation():
    if request.method == "OPTIONS":
        return ("", 204)
    user = _get_user_optional()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    body = request.get_json(force=True)
    title = body.get("title", "New Trip")
    convo = create_conversation(user["id"], title)
    return jsonify(convo), 201


@chat_bp.route("/api/conversations/<conversation_id>/messages", methods=["GET", "OPTIONS"])
def conversation_messages(conversation_id):
    if request.method == "OPTIONS":
        return ("", 204)
    user = _get_user_optional()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    msgs = get_messages(conversation_id)
    return jsonify({"messages": msgs})

