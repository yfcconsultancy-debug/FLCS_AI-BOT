# wsgi.py
import os
import sys

# Add the project's root directory to the Python path
# This allows the server to find the 'app' module
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import the Flask app instance from app/main.py
# and rename it to 'application' so Gunicorn can find it.
try:
    from app.main import app as application
except ImportError:
    print("CRITICAL: Could not import 'app' from 'app.main'.")
    print("Ensure app/main.py exists and has no import errors.")
    raise
