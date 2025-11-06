# app/routes/health.py
from flask import Blueprint, jsonify
from app.chatbot.core import get_status

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def health():
    ok, reasons = get_status()
    return jsonify({"ok": ok, "issues": reasons}), (200 if ok else 503)