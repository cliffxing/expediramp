"""Auth routes for Firebase-backed sessions."""

from flask import Blueprint, jsonify, request

from services.firebase_client import verify_token

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    return jsonify({"ok": True})


@auth_bp.route("/api/auth/me", methods=["GET"])
def me():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "No token"}), 401

    user = verify_token(auth_header[7:])
    if not user:
        return jsonify({"error": "Invalid token"}), 401

    return jsonify({"user": user})
