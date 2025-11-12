# # app/main.py
# import os, sys
# from flask import Flask, render_template
# from dotenv import load_dotenv


# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# sys.path.insert(0, BASE_DIR)
# load_dotenv(os.path.join(BASE_DIR, ".env")) 

# from app.routes.chat import chat_bp
# from app.routes.health import health_bp
# from app.routes.analytics import analytics_bp # <-- IMPORT NEW BLUEPRINT

# app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "app", "templates"),
#             static_folder=os.path.join(BASE_DIR, "app", "static"),
#             static_url_path="/static")

# # --- Set Secret Key for Sessions ---
# app.secret_key = os.getenv("FLASK_SECRET_KEY")
# if not app.secret_key:
#     print("CRITICAL: FLASK_SECRET_KEY is not set. Using unsafe default.")
#     app.secret_key = "default_unsafe_key_for_dev"

# # Blueprints
# app.register_blueprint(chat_bp, url_prefix="/api")
# app.register_blueprint(health_bp, url_prefix="/api")
# app.register_blueprint(analytics_bp, url_prefix="/api") # <-- REGISTER NEW BLUEPRINT
# print("✅ Chat, Health, & Analytics blueprints registered.") # <-- UPDATED PRINT

# @app.route("/")
# def index():
#     return render_template("index.html")

# if __name__ == "__main__":
#     print("🚀 Starting FLCS Chatbot (development server)...")
#     app.run(debug=True, host="127.0.0.1", port=5000)
# app/main.py
# app/main.py
import os
import sys
import traceback
from flask import Flask, render_template, request
from dotenv import load_dotenv
# from flask_cors import CORS  <--- REMOVED
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Add Project Root to Path ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env")) 
print(f"Added {BASE_DIR} to sys.path")

# --- Import Blueprints ---
try:
    from app.routes.chat import chat_bp
    from app.routes.health import health_bp
    from app.routes.analytics import analytics_bp
    blueprints_loaded = True
except ImportError as e:
    print(f"CRITICAL ERROR: Failed to import blueprints: {e}")
    traceback.print_exc()
    blueprints_loaded = False

# --- Flask App Initialization ---
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, "app", "templates"),
            static_folder=os.path.join(BASE_DIR, "app", "static"),
            static_url_path="/static")
print("Flask app created.")

# --- CORS Configuration ---
# (This entire block has been REMOVED)

# --- Flask Secret Key ---
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    print("CRITICAL WARNING: FLASK_SECRET_KEY is not set. Using unsafe default.")
    app.secret_key = "default_unsafe_key_for_dev_only"

# --- Rate Limiter Setup (Security) ---
def get_ipaddr():
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return get_remote_address()

limiter = Limiter(
    get_ipaddr,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
print("Flask-Limiter initialized.")

# --- Register Blueprints ---
if blueprints_loaded:
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(analytics_bp, url_prefix="/api")
    
    limiter.limit("30 per 5 minutes")(chat_bp)
    print("✅ Chat, Health, & Analytics blueprints registered.")
else:
    print("❌ FAILED to register blueprints due to import error.")

# --- Main Route ---
@app.route("/")
def index():
    """Serves the main index.html page which contains the chat widget."""
    return render_template("index.html")

# --- Run Application ---
if __name__ == "__main__":
    print("🚀 Starting FLCS Chatbot (development server)...")
    app.run(debug=True, host="127.0.0.1", port=5000)