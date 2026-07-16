const SESSION_ID = 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 11);
const API_URL = "/v1/compute";
const UPLOAD_URL = "/v1/workspace/upload";
const MAIA_KEY = "maia"; 

const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");

userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

document.getElementById('file-input').addEventListener('change', handleFileChange);


async function handleFileChange(event) {
    const file = event.target.files[0];
    if (!file) return;

    await uploadFile(file);
    
    event.target.value = '';
}

async function uploadFile(file) {
    const statusLabel = document.getElementById('upload-status');
    statusLabel.textContent = "Téléversement en cours...";
    statusLabel.style.color = "#ffa500";

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", SESSION_ID);
    
    try {
        const response = await fetch(UPLOAD_URL, {
            method: "POST",
            headers: { "maia-token": MAIA_KEY },
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            statusLabel.textContent = `✔ ${result.filename} prêt !`;
            statusLabel.style.color = "#4caf50";
            injectSystemMessageInChat(result.filename);
        } else {
            statusLabel.textContent = `❌ Erreur : ${result.detail || 'Impossible de charger'}`;
            statusLabel.style.color = "#f44336";
        }
    } catch (error) {
        statusLabel.textContent = "❌ Serveur backend hors ligne.";
        statusLabel.style.color = "#f44336";
        console.error("Erreur d'upload:", error);
    }
}

function injectSystemMessageInChat(filename) {
    // Note : Actuellement ton JS n'envoie que "prompt" au backend, et le backend va chercher
    // l'historique dans SQLite. Le JS n'a pas de variable locale "messages".
    // Idéalement, c'est ton backend qui doit écrire un message système dans SQLite
    // lors de l'upload pour que le LLM sache que le fichier existe.
    console.log(`[Système local] Notification d'ajout pour : ${filename}`);
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    userInput.value = "";

    const currentLoaderId = showLoader();

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

function showLoader() {
    const loaderId = "loader-" + Date.now();
    
    const msgDiv = document.createElement("div");
    msgDiv.id = loaderId;
    msgDiv.classList.add("message", "assistant");

    msgDiv.innerHTML = `
        <div class="loader-container">
            <div class="loader"></div>
        </div>
    `;

    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;

    return loaderId;
}