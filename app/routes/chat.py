# # app/routes/chat.py
# from flask import Blueprint, request, jsonify, session
# from app.chatbot.core import process_message

# chat_bp = Blueprint("chat", __name__)

# @chat_bp.route("/chat", methods=["POST"])
# def chat():
#     data = request.get_json(silent=True) or {}
#     q = (data.get("query") or "").strip()
#     if not q:
#         return jsonify({"error": "query is required"}), 400
    
#     # Pass query and session to the core logic
#     result = process_message(q, session)
    
#     return jsonify(result), 200
# app/routes/chat.py
from flask import Blueprint, request, jsonify, session
from app.chatbot.core import process_message
from app.utils import sheets # Import sheets for query logging
import traceback

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        q = (data.get("query") or "").strip()
        if not q:
            return jsonify({"error": "query is required"}), 400
        
        # Log the raw query *before* processing
        # We can move this inside core.py as well, but here is fine
        if q.lower() not in ["hi", "hello", "hey"]: # Don't log simple hellos
             sheets.write_query(q)
        
        # Pass query and the user's session to the core logic
        result_dict = process_message(q, session)
        
        # The core.py file returns a dictionary, which we send as JSON
        return jsonify(result_dict), 200
        
    except Exception as e:
        print(f"--- UNEXPECTED ERROR in /api/chat ---")
        traceback.print_exc()
        print(f"--- END ERROR ---")
        return jsonify({
            "markdown": "Sorry, a critical error occurred on the server.",
            "buttons": []
        }), 500