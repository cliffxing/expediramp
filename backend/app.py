"""
Expediramp — Flask API server.

Run with:
    python app.py
or
    gunicorn -k eventlet -w 1 app:app
"""

import logging
from flask import Flask
from flask_cors import CORS
from config import Config
from routes.chat import chat_bp
from routes.auth import auth_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = Flask(__name__)
app.config.from_object(Config)

CORS(app, origins=[Config.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000", "http://localhost:5001"])

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
