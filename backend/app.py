"""
Expediramp — Flask API server.

Run with:
    python app.py
or
    gunicorn -k eventlet -w 1 app:app
"""

import logging
from flask import Flask, request
from config import Config
from routes.chat import chat_bp
from routes.auth import auth_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = Flask(__name__)
app.config.from_object(Config)


def _is_allowed_origin(origin: str | None) -> bool:
    if not origin:
        return False

    allowed = {
        Config.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:5001",
    }
    return origin in allowed or origin.endswith(".vercel.app")


@app.before_request
def handle_preflight():
    if request.method == "OPTIONS" and request.path.startswith("/api/"):
        return ("", 204)


@app.after_request
def add_cors_headers(response):
    if request.path.startswith("/api/"):
        origin = request.headers.get("Origin")
        if _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

app.register_blueprint(chat_bp)
app.register_blueprint(auth_bp)


@app.route("/api/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "Expediramp API"}


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=Config.FLASK_PORT,
        debug=Config.FLASK_ENV == "development",
    )
