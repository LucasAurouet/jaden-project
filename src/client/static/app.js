const SESSION_ID = 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 11);
const API_URL = "/v1/compute";
const UPLOAD_URL = "/v1/workspace/upload";
const WORKSPACE_URL = "/v1/workspace/inspect";
const MAIA_KEY = "maia"; 

const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const fileListContainer = document.getElementById("workspace-files"); 
const fileInput = document.getElementById("file-input");
const refreshWorkspaceBtn = document.getElementById("refresh-workspace-btn"); 

userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

fileInput.addEventListener("change", async (event) => {    
    const file = event.target.files[0];
    if (!file) return;

    await uploadFile(file);
    
    event.target.value = '';
});

if (refreshWorkspaceBtn) {
    refreshWorkspaceBtn.addEventListener("click", async () => {
        const originalText = refreshWorkspaceBtn.innerHTML;
        refreshWorkspaceBtn.disabled = true;
        refreshWorkspaceBtn.innerHTML = "Actualisation...";
        
        await fetchWorkspaceFiles();
        
        refreshWorkspaceBtn.disabled = false;
        refreshWorkspaceBtn.innerHTML = originalText;
    });
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


async function fetchWorkspaceFiles() {
    if (!fileListContainer) return;
    
    try {
        const response = await fetch(WORKSPACE_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "maia-token": MAIA_KEY
            },
            body: JSON.stringify({ session_id: SESSION_ID })
        }); 

        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        
        const files = await response.json();
        renderWorkspaceFiles(files);

    } catch (error) {
        console.error("Impossible de récupérer la liste des fichiers du workspace :", error);
        fileListContainer.innerHTML = `<li style="color: #f44336; font-size: 0.9em; padding: 8px;">Impossible de charger le workspace</li>`;
    }
}


function renderWorkspaceFiles(files) {
    fileListContainer.innerHTML = "";

    if (!files || files.length === 0) {
        fileListContainer.innerHTML = `<li class="workspace-empty-message">Le workspace est vide</li>`;
        return;
    }

    files.forEach(file => {
        const li = document.createElement("li");

        li.classList.add("workspace-file-item");

        const sizeKB = (file.size / 1024).toFixed(1);
        
        li.innerHTML = `
            <span class="workspace-file-name" title="${file.name}">
                ${file.name}
            </span>
            <span class="workspace-file-size">
                ${sizeKB} Ko
            </span>
        `;
        fileListContainer.appendChild(li);
    });
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