const SESSION_ID = crypto.randomUUID();
const API_URL = "/v1/compute";
const MAIA_KEY = "mon-super-token-maia"; 

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

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-MAIA-Token": MAIA_KEY
            },
            body: JSON.stringify({
                prompt: text,
                session_id: SESSION_ID
            })
        });

        if (!response.ok) throw new Error(`Status: ${response.status}`);
        
        const data = await response.json();
        console.log("Contrat respecté :", data); 

        document.getElementById(loaderId).remove();

        if (data.status === "success") {
            appendMessage(data.response, "assistant");
        } else {
            appendMessage(`ERREUR_SERVEUR//: ${data.response}`, "assistant");
        }

    } catch (error) {
        appendMessage(`SYSTEM_ERR//: IMPOSSIBLE_DE_CONTACTER_LE_SERVEUR (${error.message})`, "assistant");
    }
}

function appendMessage(text, sender) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", sender);
    msgDiv.textContent = text;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}