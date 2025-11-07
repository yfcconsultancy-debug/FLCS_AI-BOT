# app/utils/sheets.py
import os, datetime, json # <--- ADD IMPORT JSON
import gspread
from google.oauth2.service_account import Credentials

# --- Config ---
SA_PATH = os.getenv("GOOGLE_SA_PATH", "creds/google-service-account.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_creds = None
_gc = None

# --- Helper ---
def _get_client():
    global _creds, _gc
    if _gc: return _gc
    
    # --- NEW VERCEL LOGIC ---
    # 1. Try to load from Vercel Environment Variable
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS")
    if creds_json_str:
        try:
            print("[Sheets DEBUG] Found GOOGLE_CREDENTIALS. Loading from env var.")
            creds_info = json.loads(creds_json_str)
            _creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        except Exception as e:
            print(f"[Sheets DEBUG] CRITICAL: Failed to parse GOOGLE_CREDENTIALS: {e}")
            return None
    
    # 2. Fallback to local file (for your own computer)
    elif os.path.isfile(SA_PATH):
        try:
            print("[Sheets DEBUG] Loading from local file: {SA_PATH}")
            _creds = Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
        except Exception as e:
            print(f"[Sheets DEBUG] CRITICAL: Failed to load from local file: {e}")
            return None
            
    # 3. If neither, fail
    else:
        print(f"[Sheets DEBUG] CRITICAL: No credentials found.")
        return None

    # --- Authorize gspread ---
    try:
        _gc = gspread.authorize(_creds)
        print(f"[Sheets DEBUG] gspread client authorized.")
        return _gc
    except Exception as e:
        print(f"[Sheets DEBUG] CRITICAL: Error authorizing gspread: {e}")
        return None
        
#
# ... ALL OTHER FUNCTIONS ( _write_to_sheet, write_feedback, etc.) ...
# ... ARE EXACTLY THE SAME. NO OTHER CHANGES NEEDED IN THIS FILE. ...
#

def _write_to_sheet(sheet_id, tab_name, data_row):
    try:
        gc = _get_client()
        if not gc: 
            return False, "Client not authorized"
        
        print(f"[Sheets DEBUG] Opening sheet by ID: {sheet_id}")
        sh = gc.open_by_key(sheet_id)
        print(f"[Sheets DEBUG] Sheet '{sh.title}' opened.")
        
        ws = None
        try:
            print(f"[Sheets DEBUG] Accessing tab: {tab_name}")
            ws = sh.worksheet(tab_name)
            print(f"[Sheets DEBUG] Tab '{tab_name}' found.")
        except gspread.WorksheetNotFound:
            print(f"[Sheets DEBUG] Tab '{tab_name}' not found. Creating it...")
            ws = sh.add_worksheet(title=tab_name, rows=1000, cols=10)
            print(f"[Sheets DEBUG] Tab '{tab_name}' created.")
            
        print(f"[Sheets DEBUG] Appending row: {data_row}")
        ws.append_row(data_row)
        print(f"[Sheets DEBUG] Row appended successfully.")
        return True, "Success"
        
    except Exception as e:
        print(f"[Sheets DEBUG] CRITICAL: Error writing to sheet: {e}")
        return False, str(e)

# --- Public Functions (Appointments & Feedback) ---
def write_feedback(data: dict):
    print("[Sheets DEBUG] write_feedback called.")
    if os.getenv("FEEDBACK_ENABLED", "false").lower() != "true":
        return True, "Feedback disabled"
        
    sheet_id = os.getenv("GOOGLE_SHEET_ID_FEEDBACK")
    tab_name = os.getenv("GOOGLE_SHEET_TAB_FEEDBACK", "Feedback")
    
    if not sheet_id: 
        print("[Sheets DEBUG] FEEDBACK_SHEET_ID not configured.")
        return False, "Feedback Sheet ID not configured"
    
    row = [
        datetime.datetime.utcnow().isoformat() + "Z",
        data.get("name", ""),
        data.get("email", ""),
        data.get("mobile", ""),
        data.get("suggestion", "")
    ]
    return _write_to_sheet(sheet_id, tab_name, row)

def write_appointment(data: dict):
    print("[Sheets DEBUG] write_appointment called.")
    if os.getenv("APPOINTMENT_ENABLED", "false").lower() != "true":
        return True, "Appointments disabled"
        
    sheet_id = os.getenv("GOOGLE_SHEET_ID_APPOINTMENT")
    tab_name = os.getenv("GOOGLE_SHEET_TAB_APPOINTMENT", "Appointments")

    if not sheet_id: 
        print("[Sheets DEBUG] APPOINTMENT_SHEET_ID not configured.")
        return False, "Appointment Sheet ID not configured"

    row = [
        datetime.datetime.utcnow().isoformat() + "Z",
        data.get("name", ""),
        data.get("email", ""),
        data.get("mobile", ""),
        data.get("reason", "")
    ]
    return _write_to_sheet(sheet_id, tab_name, row)

# --- NEW: Public Functions (Analytics) ---

def write_view():
    """Writes a simple timestamp to the 'Views' tab."""
    print("[Sheets DEBUG] write_view called.")
    if os.getenv("ANALYTICS_ENABLED", "false").lower() != "true":
        return True, "Analytics disabled"
    
    sheet_id = os.getenv("GOOGLE_SHEET_ID_ANALYTICS")
    tab_name = os.getenv("GOOGLE_SHEET_TAB_VIEWS", "Views")

    if not sheet_id: 
        print("[Sheets DEBUG] ANALYTICS_SHEET_ID not configured.")
        return False, "Analytics Sheet ID not configured"

    row = [datetime.datetime.utcnow().isoformat() + "Z"]
    return _write_to_sheet(sheet_id, tab_name, row)

def write_query(query: str):
    """Writes a timestamp and the user's query to the 'Queries' tab."""
    print("[Sheets DEBUG] write_query called.")
    if os.getenv("ANALYTICS_ENABLED", "false").lower() != "true":
        return True, "Analytics disabled"

    sheet_id = os.getenv("GOOGLE_SHEET_ID_ANALYTICS")
    tab_name = os.getenv("GOOGLE_SHEET_TAB_QUERIES", "Queries")

    if not sheet_id: 
        print("[Sheets DEBUG] ANALYTICS_SHEET_ID not configured.")
        return False, "Analytics Sheet ID not configured"

    row = [datetime.datetime.utcnow().isoformat() + "Z", query]
    return _write_to_sheet(sheet_id, tab_name, row)
