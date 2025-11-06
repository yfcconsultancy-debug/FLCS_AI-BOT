# app/chatbot/core.py
import os, traceback
from dotenv import load_dotenv
from pinecone import Pinecone
import cohere
from groq import Groq
# We keep the sheets util for Book Appointment and Give Feedback
from app.utils import sheets 

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

def _call_groq(prompt: str) -> str:
    if not groq: return "Groq client not configured."
    chat = groq.chat.completions.create(
        model=GROQ_MODEL, 
        messages=[{"role": "user", "content": prompt}], 
        temperature=0.3, 
        max_tokens=200 # <-- We kept the 200 token limit
    )
    return chat.choices[0].message.content.strip()

def get_rag_answer(query: str) -> dict:
    """The main AI (RAG) function."""
    try:
        # <-- THIS IS THE CORRECT LOCATION FOR THE ANALYTICS LINE -->
        sheets.write_query(query)
        
        qvec = _embed_query(query)
        contexts = _query_index(qvec, top_k=TOP_K)
        
        if not contexts and len(query.split()) > 5:
             return {
                "markdown": "Based on the provided FLCS documents, I don't have specific information about that topic.",
                "buttons": MAIN_MENU_BUTTONS
            }

        prompt = _build_prompt(query, contexts)
        answer = _call_groq(prompt)
        
        sources = list(set(f"{c.get('source')} (Page {c.get('page')})" for c in contexts if c.get('source') and c.get('page')))
        if sources:
             answer += f"\n\n---\n*Sources: {', '.join(sources)}*"

        return {"markdown": answer, "buttons": MAIN_MENU_BUTTONS}
    except Exception as e:
        traceback.print_exc()
        return {"markdown": "Sorry, an internal error occurred while processing your AI request.", "error": str(e), "buttons": MAIN_MENU_BUTTONS}

# --- Main Menu Button Definitions ---
MAIN_MENU_BUTTONS = ["Services", "Packages", "Destinations", "About Us", "Book Appointment", "Give Feedback"]
CANCEL_BUTTONS = ["Cancel"]

# --- Main Conversational "State Machine" ---
def process_message(query: str, session: dict) -> dict:
    """
    Processes a user's message, managing state and deciding whether to use
    RAG AI or a pre-saved conversational flow.
    """
    query_lower = query.lower().strip()
    
    state = session.get("chat_state")
    form_data = session.get("form_data", {})

    # --- 1. Global "Cancel" Keyword ---
    if query_lower in ["cancel", "main menu", "stop", "exit", "quit", "⬅ menu"]:
        session.pop("chat_state", None)
        session.pop("form_data", None)
        return {
            "markdown": "Welcome to FLCS! How can I help you today?", # Use your welcome text
            "buttons": MAIN_MENU_BUTTONS
        }

    # --- 2. Handle State-Based Flows (Data Collection) ---
    if state == "AWAITING_APPOINTMENT_NAME":
        form_data["name"] = query
        session["chat_state"] = "AWAITING_APPOINTMENT_EMAIL"
        session["form_data"] = form_data
        return {"markdown": f"Thanks, {query}. What is your email address?", "buttons": CANCEL_BUTTONS}
    
    elif state == "AWAITING_APPOINTMENT_EMAIL":
        form_data["email"] = query
        session["chat_state"] = "AWAITING_APPOINTMENT_MOBILE"
        session["form_data"] = form_data
        return {"markdown": "Great. What is your mobile number?", "buttons": CANCEL_BUTTONS}
        
    elif state == "AWAITING_APPOINTMENT_MOBILE":
        form_data["mobile"] = query
        session["chat_state"] = "AWAITING_APPOINTMENT_REASON"
        session["form_data"] = form_data
        return {"markdown": "Perfect. And briefly, what is the reason for your appointment?", "buttons": CANCEL_BUTTONS}

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
    elif state == "AWAITING_FEEDBACK_NAME":
        form_data["name"] = query
        session["chat_state"] = "AWAITING_FEEDBACK_EMAIL"
        session["form_data"] = form_data
        return {"markdown": f"Thanks, {query}. What is your email address?", "buttons": CANCEL_BUTTONS}

    elif state == "AWAITING_FEEDBACK_EMAIL":
        form_data["email"] = query
        session["chat_state"] = "AWAITING_FEEDBACK_MOBILE"
        session["form_data"] = form_data
        return {"markdown": "Got it. What is your mobile number?", "buttons": CANCEL_BUTTONS}
        
    elif state == "AWAITING_FEEDBACK_MOBILE":
        form_data["mobile"] = query
        session["chat_state"] = "AWAITING_FEEDBACK_SUGGESTION"
        session["form_data"] = form_data
        return {"markdown": "Finally, what is your feedback or suggestion?", "buttons": CANCEL_BUTTONS}

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
        if query_lower in ["hi", "hello", "hey"]:
            return {
                "markdown": "Welcome to FLCS! How can I help you today?",
                "buttons": MAIN_MENU_BUTTONS
            }
        
        # --- Data Collection Triggers ---
        if query_lower == "book appointment":
            session["chat_state"] = "AWAITING_APPOINTMENT_NAME"
            session["form_data"] = {}
            return {"markdown": "I can help you book an appointment. What is your full name?", "buttons": CANCEL_BUTTONS}
        
        if query_lower == "give feedback":
            session["chat_state"] = "AWAITING_FEEDBACK_NAME"
            session["form_data"] = {}
            return {"markdown": "We'd love your feedback. What is your name?", "buttons": CANCEL_BUTTONS}

        # --- Rule-Based Menu Logic ---
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

        # --- Branch 2: Packages & Pricing ---
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
        
        # --- Branch 3: Study Destinations ---
        elif query_lower == "destinations":
            return {
                "markdown": "We specialize in ITALY, but also guide students to GERMANY, USA, UK, CANADA, AUSTRALIA, and more.",
                "buttons": ["About Us", "Packages", "⬅ Menu"]
            }

        # --- Branch 4: Why Choose FLCS? ---
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

        # --- Contact & Fallback ---
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