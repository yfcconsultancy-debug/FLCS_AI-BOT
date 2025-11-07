# app/chatbot/core.py
import os, traceback, re
from dotenv import load_dotenv
from pinecone import Pinecone
import cohere
from groq import Groq
from app.utils import sheets 
from ddgs import DDGS # <-- NEW: For internet fallback

# --- Load Env ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"))
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX", "flcs-chatbot")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
EMBED_MODEL = os.getenv("COHERE_EMBED_MODEL", "embed-english-v3.0")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
TOP_K = int(os.getenv("TOP_K", "4"))

# --- Clients ---
pc = Pinecone(api_key=PINECONE_API_KEY) if PINECONE_API_KEY else None
co = cohere.Client(COHERE_API_KEY) if COHERE_API_KEY else None
groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# --- NEW: Phone number validation regex ---
# This checks for a +, a non-zero digit, and 7-14 more digits.
PHONE_REGEX = re.compile(r"^\+[1-9]\d{7,14}$")

# --- AI RAG Functions ---
def _embed_query(text: str):
    resp = co.embed(model=EMBED_MODEL, input_type="search_query", texts=[text])
    return resp.embeddings[0]

def _query_index(qvec, top_k=TOP_K):
    if not pc: return []
    try:
        index = pc.Index(INDEX_NAME)
        res = index.query(vector=qvec, top_k=top_k, include_metadata=True)
        return [m["metadata"] for m in res["matches"]]
    except Exception as e:
        print(f"[RAG Error] Pinecone query failed: {e}")
        return []

def _build_prompt(question: str, contexts: list) -> str:
    context_block = "\n\n---\n".join([c.get("text", "") for c in contexts if c.get("text")])
    if not context_block:
        context_block = "No relevant context found."
        
    return f"""You are an expert student counselor AI assistant for FLCS Consultancy. 
Answer ONLY using the information in the Context. If the Context does not contain the answer, say:
"Based on the provided FLCS documents, I don't have specific information about that topic."

Format your answer in Markdown with short paragraphs and bullet points where helpful.

Context:
{context_block}

Question: {question}

Answer:"""

# --- UPDATED: _call_groq now takes a max_tokens argument ---
def _call_groq(prompt: str, max_tokens: int = 200) -> str:
    if not groq: return "Groq client not configured."
    chat = groq.chat.completions.create(
        model=GROQ_MODEL, 
        messages=[{"role": "user", "content": prompt}], 
        temperature=0.3, 
        max_tokens=max_tokens # Use the max_tokens argument
    )
    return chat.choices[0].message.content.strip()

# --- NEW: Internet Fallback Function ---
def _get_internet_answer(query: str) -> dict:
    print(f"[Core] RAG failed. Falling back to internet search for: '{query}'")
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=3)
            if not results:
                return {
                    "markdown": "Sorry, I couldn't find any information on that topic from my documents or the web.",
                    "buttons": MAIN_MENU_BUTTONS
                }

        web_context = "\n\n---\n".join([r['body'] for r in results])
        
        web_prompt = f"""You are a helpful AI assistant. Answer the user's question based *only* on the provided Web Search Context. 
Keep your answer very short and concise (under 150 words).

Web Search Context:
{web_context}

Question: {query}

Short Answer:"""
        
        # Use a short token limit for a concise answer
        answer = _call_groq(web_prompt, max_tokens=100)
        answer += "\n\n*(This information was found on the web and is not from FLCS documents.)*"
        
        return {"markdown": answer, "buttons": MAIN_MENU_BUTTONS}
        
    except Exception as e:
        print(f"[Internet Fallback Error] {e}")
        return {
            "markdown": "Sorry, I ran into an error trying to search the internet for that topic.",
            "buttons": MAIN_MENU_BUTTONS
        }

# --- UPDATED: get_rag_answer now includes the fallback logic ---
def get_rag_answer(query: str) -> dict:
    """The main AI (RAG) function with web fallback."""
    try:
        # Log the query to analytics *before* any search
        sheets.write_query(query)
        
        qvec = _embed_query(query)
        contexts = _query_index(qvec, top_k=TOP_K)
        
        # --- Fallback Check 1: No Context ---
        if not contexts:
            print(f"[Core] No PDF context found for '{query}'.")
            return _get_internet_answer(query)

        prompt = _build_prompt(query, contexts)
        answer = _call_groq(prompt) # Uses default 200-token limit
        
        # --- Fallback Check 2: RAG answer wasn't helpful ---
        if "I don't have specific information" in answer:
            print(f"[Core] RAG answer was not helpful.")
            return _get_internet_answer(query)
        
        # Success! Return the RAG answer
        sources = list(set(f"{c.get('source')} (Page {c.get('page')})" for c in contexts if c.get('source') and c.get('page')))
        if sources:
             answer += f"\n\n---\n*Sources: {', '.join(sources)}*"

        return {"markdown": answer, "buttons": MAIN_MENU_BUTTONS}
    except Exception as e:
        traceback.print_exc()
        return {"markdown": "Sorry, an internal error occurred while processing your AI request.", "error": str(e), "buttons": MAIN_MENU_BUTTONS}

# --- Main Menu Button Definitions (Unchanged) ---
MAIN_MENU_BUTTONS = ["Services", "Packages", "Destinations", "About Us", "Book Appointment", "Give Feedback"]
CANCEL_BUTTONS = ["Cancel"]

# --- Main Conversational "State Machine" ---
def process_message(query: str, session: dict) -> dict:
    query_lower = query.lower().strip()
    state = session.get("chat_state")
    form_data = session.get("form_data", {})

    # --- 1. Global "Cancel" Keyword (Unchanged) ---
    if query_lower in ["cancel", "main menu", "stop", "exit", "quit", "⬅ menu"]:
        session.pop("chat_state", None)
        session.pop("form_data", None)
        return {
            "markdown": "Welcome to FLCS! How can I help you today?",
            "buttons": MAIN_MENU_BUTTONS
        }

    # --- 2. Handle State-Based Flows (Data Collection) ---
    
    # ... (Appointment Name & Email states are unchanged) ...
    if state == "AWAITING_APPOINTMENT_NAME":
        form_data["name"] = query
        session["chat_state"] = "AWAITING_APPOINTMENT_EMAIL"
        session["form_data"] = form_data
        return {"markdown": f"Thanks, {query}. What is your email address?", "buttons": CANCEL_BUTTONS}
    
    elif state == "AWAITING_APPOINTMENT_EMAIL":
        form_data["email"] = query # We could add email regex here too, but let's keep it simple
        session["chat_state"] = "AWAITING_APPOINTMENT_MOBILE"
        session["form_data"] = form_data
        return {"markdown": "Great. What is your mobile number? (e.g., +919876543210)", "buttons": CANCEL_BUTTONS}
        
    # --- UPDATED: Appointment Mobile State ---
    elif state == "AWAITING_APPOINTMENT_MOBILE":
        if PHONE_REGEX.match(query):
            form_data["mobile"] = query
            session["chat_state"] = "AWAITING_APPOINTMENT_REASON"
            session["form_data"] = form_data
            return {"markdown": "Perfect. And briefly, what is the reason for your appointment?", "buttons": CANCEL_BUTTONS}
        else:
            # Stay in the same state and ask again
            return {"markdown": "That doesn't look like a valid phone number. Please enter it in the full international format (e.g., +919876543210).", "buttons": CANCEL_BUTTONS}

    elif state == "AWAITING_APPOINTMENT_REASON":
        form_data["reason"] = query
        ok, msg = sheets.write_appointment(form_data)
        session.pop("chat_state", None)
        session.pop("form_data", None)
        if ok:
            return {"markdown": "Thank you! Your appointment request is submitted. We will contact you soon.", "buttons": MAIN_MENU_BUTTONS}
        else:
            print(f"[Core Error] Appointment write failed: {msg}")
            return {"markdown": f"Sorry, there was an error submitting your request. Admins notified.", "buttons": MAIN_MENU_BUTTONS}

    # --- Feedback Flow ---
    # ... (Feedback Name & Email states are unchanged) ...
    elif state == "AWAITING_FEEDBACK_NAME":
        form_data["name"] = query
        session["chat_state"] = "AWAITING_FEEDBACK_EMAIL"
        session["form_data"] = form_data
        return {"markdown": f"Thanks, {query}. What is your email address?", "buttons": CANCEL_BUTTONS}

    elif state == "AWAITING_FEEDBACK_EMAIL":
        form_data["email"] = query
        session["chat_state"] = "AWAITING_FEEDBACK_MOBILE"
        session["form_data"] = form_data
        return {"markdown": "Got it. What is your mobile number? (e.g., +919876543210)", "buttons": CANCEL_BUTTONS}
        
    # --- UPDATED: Feedback Mobile State ---
    elif state == "AWAITING_FEEDBACK_MOBILE":
        if PHONE_REGEX.match(query):
            form_data["mobile"] = query
            session["chat_state"] = "AWAITING_FEEDBACK_SUGGESTION"
            session["form_data"] = form_data
            return {"markdown": "Finally, what is your feedback or suggestion?", "buttons": CANCEL_BUTTONS}
        else:
            # Stay in the same state and ask again
            return {"markdown": "That doesn't look like a valid phone number. Please enter it in the full international format (e.g., +919876543210).", "buttons": CANCEL_BUTTONS}

    elif state == "AWAITING_FEEDBACK_SUGGESTION":
        form_data["suggestion"] = query
        ok, msg = sheets.write_feedback(form_data)
        session.pop("chat_state", None)
        session.pop("form_data", None)
        if ok:
            return {"markdown": "Thank you! Your feedback has been received.", "buttons": MAIN_MENU_BUTTONS}
        else:
            print(f"[Core Error] Feedback write failed: {msg}")
            return {"markdown": f"Sorry, there was an error submitting your feedback. Admins notified.", "buttons": MAIN_MENU_BUTTONS}
            
    # --- 3. Handle Menu Keywords (when in no state) ---
    if not state:
        # ... (All menu logic is unchanged) ...
        if query_lower in ["hi", "hello", "hey"]:
            return {
                "markdown": "Welcome to FLCS! How can I help you today?",
                "buttons": MAIN_MENU_BUTTONS
            }
        
        if query_lower == "book appointment":
            session["chat_state"] = "AWAITING_APPOINTMENT_NAME"
            session["form_data"] = {}
            return {"markdown": "I can help you book an appointment. What is your full name?", "buttons": CANCEL_BUTTONS}
        
        if query_lower == "give feedback":
            session["chat_state"] = "AWAITING_FEEDBACK_NAME"
            session["form_data"] = {}
            return {"markdown": "We'd love your feedback. What is your name?", "buttons": CANCEL_BUTTONS}

        elif query_lower == "services":
            return {
                "markdown": "We offer end-to-end support for your study abroad journey. What would you like to know more about?",
                "buttons": ["Admission", "Visa", "Scholarships", "Post-Arrival", "⬅ Menu"]
            }
        elif query_lower == "admission":
            return {
                "markdown": "We help you choose the right career, select top universities, and draft key documents like SOPs, LORs, and CVs.",
                "buttons": ["Visa", "Scholarships", "⬅ Services"]
            }
        elif query_lower == "visa":
            return {
                "markdown": "We provide full visa and immigration support, including documentation, mock interviews, and appointment booking. We have a 99% visa success rate!",
                "buttons": ["Admission", "Scholarships", "⬅ Services"]
            }
        elif query_lower == "scholarships":
            return {
                "markdown": "We assist with scholarship applications, document translation, and legalization. We've helped students secure over ₹20 Crore in scholarships.",
                "buttons": ["Admission", "Visa", "⬅ Services"]
            }
        elif query_lower == "post-arrival":
            return {
                "markdown": "Our support continues after you land in Italy! We assist with airport pickup, accommodation, residence permits, and opening a bank account.",
                "buttons": ["Admission", "Scholarships", "⬅ Services"]
            }
        elif query_lower == "⬅ services":
            return {
                "markdown": "What service would you like to know more about?",
                "buttons": ["Admission", "Visa", "Scholarships", "Post-Arrival", "⬅ Menu"]
            }

        elif query_lower in ["packages", "⬅ packages"]:
            return {
                "markdown": "We offer three packages to fit your needs. Which one would you like to see?",
                "buttons": ["Silver", "Gold", "Platinum", "Compare", "Add-ons", "⬅ Menu"]
            }
        elif query_lower == "silver":
            return {
                "markdown": "🪙 Silver: Best for self-starters. Includes guidance, document templates, and one mock visa interview.",
                "buttons": ["Gold", "Platinum", "⬅ Packages"]
            }
        elif query_lower == "gold":
            return {
                "markdown": "🥇 Gold: Our most popular option. We draft your documents, file up to 7 applications with you, and provide 3 mock interviews.",
                "buttons": ["Silver", "Platinum", "⬅ Packages"]
            }
        elif query_lower == "platinum":
            return {
                "markdown": "💎 Platinum: Our 'done-for-you' solution. We handle everything, from applications to post-arrival support, with many fees included.",
                "buttons": ["Silver", "Gold", "⬅ Packages"]
            }
        elif query_lower == "compare":
            return {
                "markdown": "Here's a quick comparison:\n\n*🪙 Silver:* Guidance-focused.\n*🥇 Gold:* 'Done-with-you' service.\n*💎 Platinum:* 'Done-for-you' comprehensive solution.",
                "buttons": ["Silver", "Gold", "Platinum", "⬅ Packages"]
            }
        elif query_lower == "add-ons":
            return {
                "markdown": "We also offer individual services like Italian Translation (₹1500), Mock Interviews (₹5000), and an Accommodation Hunt in Italy (₹15,000).",
                "buttons": ["⬅ Packages"]
            }
        
        elif query_lower == "destinations":
            return {
                "markdown": "We specialize in ITALY, but also guide students to GERMANY, USA, UK, CANADA, AUSTRALIA, and more.",
                "buttons": ["About Us", "Packages", "⬅ Menu"]
            }

        elif query_lower == "about us":
            return {
                "markdown": "Why choose FLCS?\n\n*Proven Success:* 99% visa success rate.\n*Expert Team:* Personalized guidance.\n*Transparency:* You get real-time updates.\n*Dual Offices:* Support in both India and Italy.",
                "buttons": ["📞 Contact", "Reviews", "⬅ Menu"]
            }
        elif query_lower == "reviews":
            return {
                "markdown": "Our students love us! Abhigyan Sharma said we 'genuinely help,' and Ayman Durrani said we 'guided me through the entire process.'",
                "buttons": ["About Us", "📞 Contact", "⬅ Menu"]
            }

        elif query_lower == "📞 contact":
            return {
                "markdown": "Let's connect!\n\n*Phone:* +91 906 888 7041\n*WhatsApp:* +91 963 903 6869\n*Website:* www.flcs.in",
                "buttons": ["Services", "Packages", "⬅ Menu"]
            }
        elif query_lower in ["bye", "exit"]:
            return {"markdown": "Goodbye! Have a great day!", "buttons": []}
            
    # --- 4. Fallback to AI (RAG) ---
    # If no state and no menu keyword, assume it's an AI question.
    print(f"[Core] No state or menu keyword found. Passing to RAG AI: '{query}'")
    return get_rag_answer(query)

# --- Health Check Function (Unchanged) ---
def get_status():
    ok = True
    reasons = []
    if not pc: ok=False; reasons.append("Pinecone not configured")
    if not co: ok=False; reasons.append("Cohere not configured")
    if not groq: ok=False; reasons.append("Groq not configured")
    
    if pc:
        try:
            if INDEX_NAME not in pc.list_indexes().names(): # Fixed ()
                ok=False; reasons.append(f"Pinecone index '{INDEX_NAME}' not found")
        except Exception as e:
            ok=False; reasons.append(f"Pinecone error: {e}")
    return ok, reasons