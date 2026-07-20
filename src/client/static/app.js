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

const HISTORY_SIZE = 30;
const history = {
    cpu:    new Array(HISTORY_SIZE).fill(null),
    ram:    new Array(HISTORY_SIZE).fill(null),
    gpu:    new Array(HISTORY_SIZE).fill(null),
    tokens: new Array(HISTORY_SIZE).fill(null),
};

marked.setOptions({ breaks: true });

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    updateMetrics();
    setInterval(updateMetrics, 2000);
    fetchWorkspaceFiles(); 
});

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

    if (sender === "assistant") {
        msgDiv.innerHTML = marked.parse(text);
        msgDiv.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
    } else {
        msgDiv.textContent = text; 
    }
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


function pushMetric(series, value) {
    series.push(value ?? null);
    if (series.length > HISTORY_SIZE) series.shift();
}


function makeChartData(series, color) {
    return {
        labels: new Array(HISTORY_SIZE).fill(''),
        datasets: [{
            data: series,
            borderColor: color,
            backgroundColor: color.replace(')', ', 0.08)').replace('rgb', 'rgba'),
            fill: true,
            spanGaps: true,
        }]
    };
}

const C_AMBER    = 'rgb(232, 200, 74)';
const C_PHOSPHOR = 'rgb(74, 222, 128)';
const C_BLOOD    = 'rgb(192, 57, 43)';
const C_IVORY    = 'rgb(212, 206, 184)';

const charts = {};

// ─── CHART.JS CONFIG ────────────────────────────────────────────────────────
const CHART_DEFAULTS = {
    type: 'line',
    options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
            x: { display: false },
            y: {
                display: false,
                min: 0,
                max: 100,
            }
        },
        elements: {
            point: { radius: 0 },
            line:  { borderWidth: 1.5, tension: 0.3 }
        }
    }
};


function initCharts() {
    const base = (id, series, color, max = 100) => {
        const cfg = JSON.parse(JSON.stringify(CHART_DEFAULTS));
        cfg.options.scales.y.max = max;
        cfg.data = makeChartData(series, color);
        charts[id] = new Chart(document.getElementById(id), cfg);
    };

    base('chart-cpu',    history.cpu,    C_AMBER);
    base('chart-ram',    history.ram,    C_PHOSPHOR);
    base('chart-gpu',    history.gpu,    C_BLOOD);
    base('chart-tokens', history.tokens, C_IVORY,  200);    
}

function updateChart(id, series) {
    if (!charts[id]) return;
    charts[id].data.datasets[0].data = [...series];
    charts[id].update('none');  
}

// ─── METRICS POLL ───────────────────────────────────────────────────────────
async function updateMetrics() {
    try {
        const response = await fetch('/v1/metrics/all');
        if (!response.ok) return;
        const data = await response.json();

        // Push dans les séries
        pushMetric(history.cpu,    data.system?.cpu_percent ?? null);
        pushMetric(history.ram,    data.system?.ram_percent ?? null);
        pushMetric(history.gpu,    data.system?.gpu_percent ?? null);
        pushMetric(history.tokens, data.inference?.tg_tokens_per_second ?? null);

        const set = (id, val, unit = '') => {
            const el = document.getElementById(id);
            if (el) el.textContent = val != null ? val.toFixed(1) + unit : '—';
        };

        set('stat-cpu',    data.system?.cpu_percent,              ' %');
        set('stat-ram',    data.system?.ram_percent,              ' %');
        set('stat-gpu',    data.system?.gpu_percent,              ' %');
        set('stat-tokens', data.inference?.tg_tokens_per_second,  ' t/s');

        updateChart('chart-cpu',    history.cpu);
        updateChart('chart-ram',    history.ram);
        updateChart('chart-gpu',    history.gpu);
        updateChart('chart-tokens', history.tokens);

    } catch (error) {
        console.error("Erreur métriques:", error);
    }
}