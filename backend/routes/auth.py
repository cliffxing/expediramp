"""
Auth routes — thin proxies around Supabase Auth.

The frontend can also call Supabase Auth directly via the JS client;
these routes exist for convenience and to keep the API key server-side.
"""

from flask import Blueprint, request, jsonify
from services.supabase_client import get_supabase

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    body = request.get_json(force=True)
    email = body.get("email", "")
    password = body.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    sb = get_supabase()
    try:
        result = sb.auth.sign_up({"email": email, "password": password})
        return jsonify({
            "user": {"id": result.user.id, "email": result.user.email},
            "session": {
                "access_token": result.session.access_token,
                "refresh_token": result.session.refresh_token,
            } if result.session else None,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    body = request.get_json(force=True)
    email = body.get("email", "")
    password = body.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    sb = get_supabase()
    try:
        result = sb.auth.sign_in_with_password({"email": email, "password": password})
        return jsonify({
            "user": {"id": result.user.id, "email": result.user.email},
            "session": {
                "access_token": result.session.access_token,
                "refresh_token": result.session.refresh_token,
            },
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    # Client-side token invalidation is sufficient for Supabase JWTs;
    # optionally call sb.auth.sign_out() with the user's token.
    return jsonify({"ok": True})


@auth_bp.route("/api/auth/me", methods=["GET"])
def me():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "No token"}), 401
    token = auth_header[7:]
    sb = get_supabase()
    try:
        user_resp = sb.auth.get_user(token)
        return jsonify({"user": {"id": user_resp.user.id, "email": user_resp.user.email}})
    except Exception:
        return jsonify({"error": "Invalid token"}), 401
