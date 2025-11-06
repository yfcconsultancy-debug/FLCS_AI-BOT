# app/routes/chat.py
from flask import Blueprint, request, jsonify, session
from app.chatbot.core import process_message

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    if not q:
        return jsonify({"error": "query is required"}), 400
    
    # Pass query and session to the core logic
    result = process_message(q, session)
    
    return jsonify(result), 200