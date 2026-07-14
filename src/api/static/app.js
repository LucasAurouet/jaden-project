const SESSION_ID = crypto.randomUUID();
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

    // 1. On affiche le message utilisateur
    appendMessage(text, "user");
    userInput.value = "";

    // 2. On affiche l'indicateur de chargement et on récupère son ID unique
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

        // 3. On supprime l'indicateur de chargement
        const loaderElement = document.getElementById(currentLoaderId);
        if (loaderElement) {
            loaderElement.remove();
        }

        // 4. On affiche la réponse avec le bon champ (.content)
        if (data.status === "success") {
            appendMessage(data.content, "assistant");
        } else {
            appendMessage(`ERREUR_SERVEUR//: ${data.content}`, "assistant");
        }

    } catch (error) {
        // En cas d'erreur, on nettoie quand même le loader s'il existe
        const loaderElement = document.getElementById(currentLoaderId);
        if (loaderElement) {
            loaderElement.remove();
        }
        appendMessage(`SYSTEM_ERR//: IMPOSSIBLE_DE_CONTACTER_LE_SERVEUR (${error.message})`, "assistant");
    }
}

// 🟢 Fonction améliorée pour générer des IDs uniques
function appendMessage(text, sender) {
    const msgDiv = document.createElement("div");
    const uniqueId = "msg-" + Date.now() + "-" + Math.random().toString(36).substr(2, 9);
    
    msgDiv.id = uniqueId;
    msgDiv.classList.add("message", sender);
    msgDiv.textContent = text;
    
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    return uniqueId; // 🟢 Permet de récupérer l'ID pour pouvoir le supprimer plus tard
}