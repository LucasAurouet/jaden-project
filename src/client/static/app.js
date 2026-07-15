const SESSION_ID = 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 11);
const API_URL = "/v1/compute";
const MAIA_KEY = "maia"; 

const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");

userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    userInput.value = "";

    const currentLoaderId = appendMessage("CONNEXION_AU_NEURAL_NET...", "assistant");

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "maia-token": MAIA_KEY
            },
            body: JSON.stringify({
                prompt: text,
                session_id: SESSION_ID
            })
        });

        if (!response.ok) throw new Error(`Status: ${response.status}`);
        
        const data = await response.json();
        console.log("Contrat respecté :", data); 

        const loaderElement = document.getElementById(currentLoaderId);
        if (loaderElement) {
            loaderElement.remove();
        }

        if (data.status === "success") {
            appendMessage(data.content, "assistant");
        } else {
            appendMessage(`ERREUR_SERVEUR//: ${data.content}`, "assistant");
        }

    } catch (error) {
        const loaderElement = document.getElementById(currentLoaderId);
        if (loaderElement) {
            loaderElement.remove();
        }
        appendMessage(`SYSTEM_ERR//: IMPOSSIBLE_DE_CONTACTER_LE_SERVEUR (${error.message})`, "assistant");
    }
}

function appendMessage(text, sender) {
    const msgDiv = document.createElement("div");
    const uniqueId = "msg-" + Date.now() + "-" + Math.random().toString(36).substr(2, 9);
    
    msgDiv.id = uniqueId;
    msgDiv.classList.add("message", sender);
    msgDiv.textContent = text;
    
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    return uniqueId;
}