// app/static/js/script.js
document.addEventListener("DOMContentLoaded", () => {
    // 1. Get all the necessary HTML elements
    const launch = document.getElementById("chat-launcher");
    const win = document.getElementById("chat-window");
    const closeBtn = document.getElementById("close-chat");
    const messages = document.getElementById("chat-messages");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("message-input");
    const typing = document.getElementById("typing-indicator");
    const qbtns = document.getElementById("quick-buttons");
    
    // --- NEW: Get expand/minimize buttons ---
    const expandBtn = document.getElementById("expand-chat");
    const minimizeBtn = document.getElementById("minimize-chat");

    let openedOnce = false;

    // --- 2. Event Listeners ---
    launch?.addEventListener("click", toggleChatWindow);
    closeBtn?.addEventListener("click", toggleChatWindow);
    form?.addEventListener("submit", handleFormSubmit);
    
    // --- NEW: Listeners for size toggle ---
    expandBtn?.addEventListener("click", toggleSize);
    minimizeBtn?.addEventListener("click", toggleSize);


    /**
     * Toggles the chat window's visibility and tracks the first view.
     */
    function toggleChatWindow() {
        const opening = win.classList.contains("hidden");
        
        if (opening) {
            // Open the window
            win.classList.remove("hidden");
            win.setAttribute("aria-hidden", "false");
            input.focus();
            
            // --- First-Time Open Logic ---
            if (!openedOnce) {
                send("hello", true); 
                openedOnce = true;
                
                try {
                    fetch("/api/track_view", { 
                        method: "POST",
                        headers: {"Content-Type":"application/json"}
                    });
                } catch (e) {
                    console.warn("Could not track view", e);
                }
            }
        } else {
            // Close the window
            win.classList.add("hidden");
            win.setAttribute("aria-hidden", "true");
            
            // --- NEW: Reset to small size when closed ---
            if (win.classList.contains("expanded")) {
                toggleSize();
            }
        }
    }
    
    // --- NEW: Function to toggle window size ---
    function toggleSize() {
        win.classList.toggle("expanded");
        expandBtn.classList.toggle("hidden");
        minimizeBtn.classList.toggle("hidden");
    }

    /**
     * Handles the form submission (when user presses Send or Enter).
     */
    function handleFormSubmit(e) {
        e.preventDefault();
        const t = input.value.trim();
        if (!t) return; // Don't send empty messages
        input.value = "";
        send(t, false);
    }

    /**
     * Appends a new message bubble to the chat window.
     * @param {string} role - 'user' or 'bot'
     * @param {string} content - The text or HTML content
     * @param {boolean} isHTML - True if content is pre-rendered HTML (from Markdown)
     */
    function addMsg(role, content, isHTML = false) {
        const row = document.createElement("div");
        row.className = role === "user" ? "message user" : "message bot";
        
        const bubble = document.createElement("div");
        bubble.className = "bubble";
        
        if (isHTML) {
            bubble.innerHTML = content; // Render Markdown HTML
        } else {
            bubble.textContent = content; // Render plain text
        }
        
        row.appendChild(bubble);
        messages.appendChild(row);
        
        // Scroll to the bottom
        messages.scrollTop = messages.scrollHeight;
        return row;
    }

    /**
     * Renders a list of strings as quick-reply buttons.
     * @param {string[]} list - An array of button text strings
     */
    function setButtons(list = []) {
        qbtns.innerHTML = "";
        if (list.length > 0) {
            list.forEach(txt => {
                const b = document.createElement("button");
                b.type = "button";
                b.textContent = txt;
                // When a button is clicked, send its text as a message
                b.onclick = () => send(txt, false);
                qbtns.appendChild(b);
            });
            qbtns.style.display = "flex";
        } else {
            qbtns.style.display = "none";
        }
    }

    /**
     * Sends a message to the backend and renders the response.
     * @param {string} text - The query text to send
     * @param {boolean} isInitial - True if this is the first hidden "hello" message
     */
    async function send(text, isInitial = false) {
        if (!text?.trim()) return;

        // Add user message to UI
        if (!isInitial) {
            addMsg("user", text);
        }

        // Show typing indicator and clear old buttons
        typing.classList.remove("hidden");
        setButtons([]);
        messages.scrollTop = messages.scrollHeight;

        try {
            // --- Fetch call to our Flask API ---
            const r = await fetch("/api/chat", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ query: text })
            });

            typing.classList.add("hidden");

            if (!r.ok) {
                addMsg("bot", "Sorry, an error occurred. Please try again.");
                return;
            }

            const json = await r.json();
            
            const md = json.markdown || json.response || "Sorry, I'm not sure how to respond.";
            
            // Use marked.js (loaded in index.html) to parse Markdown
            const html = window.marked ? marked.parse(md) : md;
            
            // Add the bot's HTML-parsed response
            addMsg("bot", html, true);
            
            // Render any new buttons
            setButtons(json.buttons || []);

        } catch (e) {
            typing.classList.add("hidden");
            console.error(e);
            addMsg("bot", "Network error. Please check your connection and try again.");
        }
    }

    // --- 3. Keypress Listener for 'Enter' ---
    input?.addEventListener("keypress", e => {
        // Send message on 'Enter' key, but not if 'Shift' is pressed
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleFormSubmit(e);
        }
    });
});