const SESSION_ID = 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 11);
const API_URL = "/api/compute";
const UPLOAD_URL = "/api/workspace/upload";
const WORKSPACE_URL = "/api/workspace/inspect";
const METRICS_URL = "/api/metrics";

const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const promptForm = document.getElementById("prompt-form");
const sendBtn = document.getElementById("send-btn");
const fileListContainer = document.getElementById("workspace-files");
const fileInput = document.getElementById("file-input");
const refreshWorkspaceBtn = document.getElementById("refresh-workspace-btn");

const HISTORY_SIZE = 40;
const history = {
    cpu:    new Array(HISTORY_SIZE).fill(null),
    ram:    new Array(HISTORY_SIZE).fill(null),
    gpu:    new Array(HISTORY_SIZE).fill(null),
    tokens: new Array(HISTORY_SIZE).fill(null),
};

let exchangeCount = 0;

marked.setOptions({ breaks: true });

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    updateMetrics();
    setInterval(updateMetrics, 2000);
    tickClock();
    setInterval(tickClock, 1000);
    fetchWorkspaceFiles();
    userInput.focus();
});

// Un <form> gère nativement la touche Entrée et le bouton "submit".
promptForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage();
});

fileInput.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    await uploadFile(file);

    event.target.value = '';
});

refreshWorkspaceBtn.addEventListener("click", async () => {
    refreshWorkspaceBtn.disabled = true;
    await fetchWorkspaceFiles();
    refreshWorkspaceBtn.disabled = false;
});


// ─── UTILITAIRES ────────────────────────────────────────────────────────────
const pad = (n) => String(n).padStart(2, '0');
const timestamp = () => {
    const d = new Date();
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

function tickClock() {
    document.getElementById("clock").textContent = timestamp();
}

// Les couleurs viennent des variables CSS : une seule source de vérité.
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();


// ─── WORKSPACE ──────────────────────────────────────────────────────────────
async function uploadFile(file) {
    const statusLabel = document.getElementById('upload-status');
    const setStatus = (state, text) => {
        statusLabel.dataset.state = state;
        statusLabel.textContent = text;
    };
    setStatus("busy", "▸ Injection en cours…");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", SESSION_ID);

    try {
        const response = await fetch(UPLOAD_URL, {
            method: "POST",
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            setStatus("ok", `✔ ${result.filename} injecté dans le contexte`);
        } else {
            setStatus("error", `✖ ${result.detail || 'Impossible de charger'}`);
        }
    } catch (error) {
        setStatus("error", "✖ Client local hors ligne");
        console.error("Erreur d'upload:", error);
    }
}


async function fetchWorkspaceFiles() {
    try {
        const response = await fetch(WORKSPACE_URL);

        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);

        const files = await response.json();
        renderWorkspaceFiles(files);

    } catch (error) {
        console.error("Impossible de récupérer la liste des fichiers du workspace :", error);
        fileListContainer.innerHTML = `<li class="workspace-error">✖ Workspace inaccessible</li>`;
    }
}


function renderWorkspaceFiles(files) {
    fileListContainer.innerHTML = "";

    if (!files || files.length === 0) {
        fileListContainer.innerHTML = `<li class="workspace-empty-message">Workspace vide</li>`;
        return;
    }

    files.forEach(file => {
        const li = document.createElement("li");

        li.classList.add("workspace-file-item");
        
        const name = document.createElement("span");
        name.className = "workspace-file-name";
        name.title = file.name;
        name.textContent = file.name;

        const size = document.createElement("span");
        size.className = "workspace-file-size";
        size.textContent = `${(file.size / 1024).toFixed(1)} Ko`;

        li.append(name, size);
        fileListContainer.appendChild(li);
    });
}


// ─── DIALOGUE ───────────────────────────────────────────────────────────────
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    userInput.value = "";
    sendBtn.disabled = true;

    const loader = showLoader();

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompt: text,
                session_id: SESSION_ID
            })
        });

        if (!response.ok) throw new Error(`Status: ${response.status}`);

        const data = await response.json();
        loader.remove();

        if (data.status === "success") {
            appendMessage(data.content, "assistant");
            exchangeCount++;
            document.getElementById("msg-counter").textContent =
                `${pad(exchangeCount)} ÉCHANGE${exchangeCount > 1 ? 'S' : ''}`;
        } else {
            appendMessage(data.content, "error");
        }

    } catch (error) {
        loader.remove();
        appendMessage(`Client local injoignable (${error.message}).`, "error");
    } finally {
        sendBtn.disabled = false;
        userInput.focus();
    }
}


const SENDER_LABEL = { user: "OPÉRATEUR", assistant: "MAIA", error: "SYSTÈME // ERREUR" };

function createMessage(sender) {
    document.getElementById("boot")?.remove();

    const msg = document.createElement("article");
    msg.className = `msg msg--${sender}`;

    const meta = document.createElement("header");
    meta.className = "msg__meta";
    const who = document.createElement("span");
    who.className = "msg__who";
    who.textContent = SENDER_LABEL[sender];
    const time = document.createElement("span");
    time.className = "msg__time";
    time.textContent = timestamp();
    meta.append(who, time);

    const body = document.createElement("div");
    body.className = "msg__body";

    msg.append(meta, body);
    chatBox.appendChild(msg);
    return { msg, body };
}

function appendMessage(text, sender) {
    const { msg, body } = createMessage(sender);

    if (sender === "assistant") {
        // La sortie du LLM n'est pas fiable (elle peut reprendre du contenu
        // injecté via un fichier) : on nettoie le HTML avant de l'insérer.
        body.innerHTML = DOMPurify.sanitize(marked.parse(text));
        body.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
    } else {
        body.textContent = text;
    }
    chatBox.scrollTop = chatBox.scrollHeight;
    return msg;
}

function showLoader() {
    const { msg, body } = createMessage("assistant");
    body.innerHTML = `<span class="thinking">TRAITEMENT EN COURS</span>`;
    chatBox.scrollTop = chatBox.scrollHeight;
    return msg;
}


// ─── MONITEUR ───────────────────────────────────────────────────────────────
const charts = {};

function initCharts() {
    const make = (id, series, color, max) => {
        charts[id] = new Chart(document.getElementById(id), {
            type: 'line',
            data: {
                labels: new Array(HISTORY_SIZE).fill(''),
                datasets: [{
                    data: series,
                    borderColor: color,
                    backgroundColor: color + '1a',   // hex + alpha ≈ 10 %
                    fill: true,
                    spanGaps: true,
                }]
            },
            options: {
                animation: false,
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { display: false },
                    // max fixe pour les %, échelle automatique pour les tokens/s
                    y: { display: false, min: 0, max, suggestedMax: max ?? 40 }
                },
                elements: {
                    point: { radius: 0 },
                    line:  { borderWidth: 1.5, tension: 0.25 }
                }
            }
        });
    };

    make('chart-cpu',    history.cpu,    cssVar('--accent'), 100);
    make('chart-ram',    history.ram,    cssVar('--cyan'),  100);
    make('chart-gpu',    history.gpu,    cssVar('--red'),   100);
    make('chart-tokens', history.tokens, cssVar('--green'));
}

function pushMetric(series, value) {
    series.push(value ?? null);
    if (series.length > HISTORY_SIZE) series.shift();
}

function updateChart(id, series) {
    charts[id].data.datasets[0].data = [...series];
    charts[id].update('none');
}

function setLinkState(state, label) {
    const link = document.getElementById("link-status");
    link.dataset.state = state;
    document.getElementById("link-text").textContent = label;

    const boot = document.getElementById("boot-link");
    if (boot) {
        boot.className = { ok: "ok", error: "err" }[state] ?? "wait";
        boot.textContent = { ok: "ÉTABLIE", error: "ÉCHEC" }[state] ?? "EN ATTENTE";
    }
}

function formatUptime(seconds) {
    const s = Math.floor(seconds);
    const d = Math.floor(s / 86400);
    const hms = `${pad(Math.floor(s % 86400 / 3600))}:${pad(Math.floor(s % 3600 / 60))}:${pad(s % 60)}`;
    return d > 0 ? `${d}j ${hms}` : hms;
}

async function updateMetrics() {
    let data;
    try {
        const response = await fetch(METRICS_URL);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        data = await response.json();
    } catch (error) {
        setLinkState("error", "CLIENT HORS LIGNE");
        return;
    }

    // Le client renvoie {} quand le serveur d'inférence ne répond pas.
    const sys = data.system;
    const inf = data.inference;
    if (!sys) {
        setLinkState("error", "SERVEUR INJOIGNABLE");
    } else {
        setLinkState("ok", "LIAISON ÉTABLIE");
    }

    pushMetric(history.cpu,    sys?.cpu_percent);
    pushMetric(history.ram,    sys?.ram_percent);
    pushMetric(history.gpu,    sys?.gpu_percent);
    pushMetric(history.tokens, inf?.tg_tokens_per_sec);

    const set = (id, val, format) => {
        document.getElementById(id).textContent = val != null ? format(val) : '—';
    };

    set('stat-cpu',    sys?.cpu_percent,       v => `${v.toFixed(0)}%`);
    set('stat-ram',    sys?.ram_percent,       v => `${v.toFixed(0)}%`);
    set('stat-gpu',    sys?.gpu_percent,       v => `${v.toFixed(0)}%`);
    set('stat-tokens', inf?.tg_tokens_per_sec, v => `${v.toFixed(1)} t/s`);

    const vramUsed = sys?.gpu_vram_used_mb, vramTotal = sys?.gpu_vram_total_mb;
    set('read-vram', vramUsed != null && vramTotal ? vramUsed : null,
        v => `${(v / 1024).toFixed(1)}/${(vramTotal / 1024).toFixed(0)} Go`);
    set('read-temp',   sys?.gpu_temp_c,        v => `${v.toFixed(0)} °C`);
    set('read-pp',     inf?.pp_tokens_per_sec, v => `${v.toFixed(0)} t/s`);
    set('read-uptime', sys?.uptime_seconds,    formatUptime);
    document.getElementById('read-temp').classList.toggle('hot', (sys?.gpu_temp_c ?? 0) >= 80);

    updateChart('chart-cpu',    history.cpu);
    updateChart('chart-ram',    history.ram);
    updateChart('chart-gpu',    history.gpu);
    updateChart('chart-tokens', history.tokens);
}
