# app/routes/analytics.py
from flask import Blueprint, jsonify
from app.utils import sheets

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route("/track_view", methods=["POST"])
def track_view():
    """
    Called by the frontend once per session when the
    chat window is first opened.
    """
    ok, msg = sheets.write_view()
    if ok:
        return jsonify({"ok": True}), 200
    else:
        # Don't bother the user with this error, just log it
        print(f"[Analytics Error] Failed to write view: {msg}")
        return jsonify({"ok": False, "error": msg}), 500