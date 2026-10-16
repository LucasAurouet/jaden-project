const SESSION_ID = 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 11);
const API_URL = "/api/compute";
const METRICS_URL = "/api/metrics";
const DOCUMENTS_URL = "/api/documents";

const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const promptForm = document.getElementById("prompt-form");
const sendBtn = document.getElementById("send-btn");
const documentList = document.getElementById("document-list");
const fileInput = document.getElementById("file-input");
const refreshDocumentsBtn = document.getElementById("refresh-documents-btn");

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
    fetchDocuments();
    userInput.focus();
});


promptForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage();
});

fileInput.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    await uploadDocument(file);

    event.target.value = '';
});

refreshDocumentsBtn.addEventListener("click", async () => {
    refreshDocumentsBtn.disabled = true;
    await fetchDocuments();
    refreshDocumentsBtn.disabled = false;
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


const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();


// ─── DOCUMENTS ──────────────────────────────────────────────────────────────
// Les erreurs FastAPI arrivent sous la forme {"detail": "..."}.
async function errorMessage(response) {
    const data = await response.json().catch(() => null);
    return data?.detail || `Erreur HTTP ${response.status}`;
}

async function uploadDocument(file) {
    const statusLabel = document.getElementById('upload-status');
    const setStatus = (state, text) => {
        statusLabel.dataset.state = state;
        statusLabel.textContent = text;
    };
    setStatus("busy", "▸ Indexation en cours…");
    fileInput.disabled = true;

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch(DOCUMENTS_URL, { method: "POST", body: formData });

        if (response.ok) {
            const result = await response.json();
            setStatus("ok", `✔ ${result.source} indexé (${result.chunks} passage${result.chunks > 1 ? 's' : ''})`);
            await fetchDocuments();
        } else {
            setStatus("error", `✖ ${await errorMessage(response)}`);
        }
    } catch (error) {
        setStatus("error", "✖ Client local hors ligne");
        console.error("Erreur d'upload :", error);
    } finally {
        fileInput.disabled = false;
    }
}


async function fetchDocuments() {
    try {
        const response = await fetch(DOCUMENTS_URL);
        if (!response.ok) throw new Error(await errorMessage(response));
        renderDocuments(await response.json());
    } catch (error) {
        console.error("Impossible de récupérer la liste des documents :", error);
        const li = document.createElement("li");
        li.className = "documents-error";
        li.textContent = `✖ ${error.message}`;
        li.title = error.message;
        documentList.replaceChildren(li);
    }
}


async function deleteDocument(doc, button) {
    if (!confirm(`Retirer « ${doc.source} » de la base de connaissances ?`)) return;

    button.disabled = true;
    try {
        const response = await fetch(`${DOCUMENTS_URL}/${doc.id}`, { method: "DELETE" });
        if (!response.ok && response.status !== 404) throw new Error(await errorMessage(response));
    } catch (error) {
        alert(`Suppression impossible : ${error.message}`);
    }
    await fetchDocuments();
}


function renderDocuments(documents) {
    if (!documents || documents.length === 0) {
        const li = document.createElement("li");
        li.className = "documents-empty";
        li.textContent = "Aucun document indexé";
        documentList.replaceChildren(li);
        return;
    }

    documentList.replaceChildren(...documents.map(doc => {
        const li = document.createElement("li");
        li.className = "document-item";

        const name = document.createElement("span");
        name.className = "document-name";
        name.title = doc.source;
        name.textContent = doc.source;

        const chunks = document.createElement("span");
        chunks.className = "document-chunks";
        chunks.textContent = `${doc.chunks} pass.`;
        chunks.title = `${doc.chunks} passage${doc.chunks > 1 ? 's' : ''} indexé${doc.chunks > 1 ? 's' : ''}`;

        const remove = document.createElement("button");
        remove.className = "document-delete";
        remove.textContent = "✕";
        remove.title = "Retirer ce document";
        remove.setAttribute("aria-label", `Retirer ${doc.source}`);
        remove.addEventListener("click", () => deleteDocument(doc, remove));

        li.append(name, chunks, remove);
        return li;
    }));
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


const SENDER_LABEL = { user: "OPÉRATEUR", assistant: "HOMN", error: "SYSTÈME // ERREUR" };

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
