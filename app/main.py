# app/main.py
import os, sys
from flask import Flask, render_template
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env")) 

from app.routes.chat import chat_bp
from app.routes.health import health_bp
from app.routes.analytics import analytics_bp # <-- IMPORT NEW BLUEPRINT

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "app", "templates"),
            static_folder=os.path.join(BASE_DIR, "app", "static"),
            static_url_path="/static")

# --- Set Secret Key for Sessions ---
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    print("CRITICAL: FLASK_SECRET_KEY is not set. Using unsafe default.")
    app.secret_key = "default_unsafe_key_for_dev"

# Blueprints
app.register_blueprint(chat_bp, url_prefix="/api")
app.register_blueprint(health_bp, url_prefix="/api")
app.register_blueprint(analytics_bp, url_prefix="/api") # <-- REGISTER NEW BLUEPRINT
print("✅ Chat, Health, & Analytics blueprints registered.") # <-- UPDATED PRINT

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    print("🚀 Starting FLCS Chatbot (development server)...")
    app.run(debug=True, host="127.0.0.1", port=5000)