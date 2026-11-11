const API_URL = "/api/compute";
const STATUS_URL = "/api/status";
const SESSIONS_URL = "/api/sessions";

const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const promptForm = document.getElementById("prompt-form");
const sendBtn = document.getElementById("send-btn");
const sessionList = document.getElementById("session-list");
const loginScreen = document.getElementById("login");
const loginForm = document.getElementById("login-form");

// Écran d'accueil d'une conversation vide, recopié à chaque nouvelle discussion.
const bootTemplate = document.getElementById("boot").cloneNode(true);

let currentUser = null;
// Id de la conversation affichée : généré ici, la session n'existe côté serveur
// qu'après le premier échange. Il est gardé dans l'URL (#id) pour survivre à un F5.
let sessionId = null;
let sessionSaved = false;
let exchangeCount = 0;
let statusStarted = false;

marked.setOptions({ breaks: true });

document.addEventListener('DOMContentLoaded', async () => {
    tickClock();
    setInterval(tickClock, 1000);

    const response = await fetch("/api/me").catch(() => null);
    if (response?.ok) {
        await startApp(await response.json());
    } else {
        showLogin();
    }
});


promptForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage();
});

document.getElementById("new-session-btn").addEventListener("click", () => {
    newSession();
    userInput.focus();
});

document.getElementById("logout-btn").addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST" }).catch(() => null);
    showLogin();
});

loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const error = document.getElementById("login-error");
    const button = document.getElementById("login-btn");
    error.textContent = "";
    button.disabled = true;
    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: document.getElementById("login-username").value,
                password: document.getElementById("login-password").value,
            }),
        });
        if (!response.ok) {
            error.textContent = await errorMessage(response);
            return;
        }
        document.getElementById("login-password").value = "";
        await startApp(await response.json());
    } catch (err) {
        error.textContent = "Client unreachable.";
    } finally {
        button.disabled = false;
    }
});


// ─── SESSION UTILISATEUR ────────────────────────────────────────────────────
async function startApp(user) {
    currentUser = user;
    loginScreen.hidden = true;
    document.getElementById("user-box").hidden = false;
    document.getElementById("user-name").textContent = user.username;

    if (!statusStarted) {
        statusStarted = true;
        setInterval(updateStatus, 5000);
    }
    updateStatus();
    await fetchSessions();

    const fromUrl = decodeURIComponent(location.hash.slice(1));
    if (fromUrl) {
        await openSession(fromUrl);
    } else {
        newSession();
    }
    userInput.focus();
}

function showLogin() {
    currentUser = null;
    document.getElementById("user-box").hidden = true;
    sessionList.replaceChildren();
    resetChat();
    loginScreen.hidden = false;
    document.getElementById("login-username").focus();
}

// fetch vers le client ; un 401 (session expirée ou révoquée) renvoie à la connexion.
async function apiFetch(url, options) {
    const response = await fetch(url, options);
    if (response.status === 401 && currentUser) {
        showLogin();
        throw new Error("Session expired: please log in again.");
    }
    return response;
}

// ─── UTILITAIRES ────────────────────────────────────────────────────────────
const pad = (n) => String(n).padStart(2, '0');
const timestamp = (d = new Date()) => {
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

function tickClock() {
    document.getElementById("clock").textContent = timestamp();
}



// ─── ERREURS ────────────────────────────────────────────────────────────────
// Les erreurs FastAPI arrivent sous la forme {"detail": "..."}.
async function errorMessage(response) {
    const data = await response.json().catch(() => null);
    return data?.detail || `HTTP error ${response.status}`;
}

// ─── CONVERSATIONS ──────────────────────────────────────────────────────────
// crypto.randomUUID n'existe qu'en contexte sécurisé (HTTPS ou localhost).
function newId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, "0")).join("");
}

function setExchangeCount(count) {
    exchangeCount = count;
    document.getElementById("msg-counter").textContent =
        `${pad(exchangeCount)} EXCHANGE${exchangeCount > 1 ? 'S' : ''}`;
}

function resetChat() {
    chatBox.replaceChildren(bootTemplate.cloneNode(true));
    setExchangeCount(0);
    // L'écran d'accueil recopié reprend l'état actuel de la liaison.
    setLinkState(document.getElementById("link-status").dataset.state,
                 document.getElementById("link-text").textContent);
}

function newSession() {
    sessionId = newId();
    sessionSaved = false;
    window.history.replaceState(null, "", location.pathname);
    resetChat();
    highlightSession();
}

async function openSession(id) {
    try {
        const response = await apiFetch(`${SESSIONS_URL}/${encodeURIComponent(id)}/messages`);
        if (response.status === 404) {
            newSession();
            return;
        }
        if (!response.ok) throw new Error(await errorMessage(response));
        const messages = await response.json();

        sessionId = id;
        sessionSaved = true;
        window.history.replaceState(null, "", `#${encodeURIComponent(id)}`);
        resetChat();
        for (const message of messages) {
            appendMessage(message.content, message.role, new Date(message.created_at));
        }
        setExchangeCount(messages.filter(m => m.role === "user").length);
        highlightSession();
    } catch (error) {
        appendMessage(`Cannot open the conversation: ${error.message}`, "error");
    }
}

async function fetchSessions() {
    try {
        const response = await apiFetch(SESSIONS_URL);
        if (!response.ok) throw new Error(await errorMessage(response));
        renderSessions(await response.json());
    } catch (error) {
        console.error("Cannot fetch the conversations:", error);
        const li = document.createElement("li");
        li.className = "documents-error";
        li.textContent = `✖ ${error.message}`;
        sessionList.replaceChildren(li);
    }
}

async function deleteSession(session, button) {
    if (!confirm(`Delete the conversation "${session.title}"?`)) return;

    button.disabled = true;
    try {
        const response = await apiFetch(`${SESSIONS_URL}/${encodeURIComponent(session.id)}`, { method: "DELETE" });
        if (!response.ok && response.status !== 404) throw new Error(await errorMessage(response));
        if (session.id === sessionId) newSession();
    } catch (error) {
        alert(`Cannot delete: ${error.message}`);
    }
    await fetchSessions();
}

function renderSessions(sessions) {
    if (sessions.length === 0) {
        const li = document.createElement("li");
        li.className = "documents-empty";
        li.textContent = "No conversation";
        sessionList.replaceChildren(li);
        return;
    }

    sessionList.replaceChildren(...sessions.map(session => {
        const li = document.createElement("li");
        li.className = "document-item session-item";
        li.dataset.id = session.id;
        li.addEventListener("click", () => {
            if (session.id !== sessionId) openSession(session.id);
        });

        const name = document.createElement("span");
        name.className = "document-name";
        name.title = session.title;
        name.textContent = session.title;

        const remove = document.createElement("button");
        remove.className = "document-delete";
        remove.textContent = "✕";
        remove.title = "Delete this conversation";
        remove.setAttribute("aria-label", `Delete ${session.title}`);
        remove.addEventListener("click", (e) => {
            e.stopPropagation();
            deleteSession(session, remove);
        });

        li.append(name, remove);
        return li;
    }));
    highlightSession();
}

function highlightSession() {
    for (const li of sessionList.querySelectorAll(".session-item")) {
        li.setAttribute("aria-current", li.dataset.id === sessionId ? "true" : "false");
    }
}


// ─── DIALOGUE ───────────────────────────────────────────────────────────────
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    userInput.value = "";
    sendBtn.disabled = true;

    const reply = createStreamingReply();

    try {
        const response = await apiFetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompt: text,
                session_id: sessionId
            })
        });

        if (!response.ok) {
            reply.fail(await errorMessage(response));
            return;
        }

        for await (const event of readEvents(response)) {
            if (event.type === "delta") {
                reply.append(event.content);
            } else if (event.type === "tool") {
                reply.setStatus(`TOOL // ${event.name}`);
            } else if (event.type === "status") {
                reply.setStatus(event.message);
            } else if (event.type === "error") {
                reply.fail(event.message);
                return;
            } else if (event.type === "done") {
                reply.finish();
                setExchangeCount(exchangeCount + 1);
                // Session créée par ce premier échange : elle entre dans l'URL et la liste.
                if (!sessionSaved) {
                    sessionSaved = true;
                    window.history.replaceState(null, "", `#${encodeURIComponent(sessionId)}`);
                }
                fetchSessions();
                return;
            }
        }
        // Flux terminé sans "done" ni "error" : la connexion a été coupée.
        reply.fail("Stream interrupted before the end of the answer.");

    } catch (error) {
        reply.fail(error.message);
    } finally {
        sendBtn.disabled = false;
        userInput.focus();
    }
}


// Lit un flux SSE ("data: <json>" séparés par une ligne vide) et renvoie chaque événement.
async function* readEvents(response) {
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    while (true) {
        const { value, done } = await reader.read();
        if (done) return;
        buffer += value;
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop();
        for (const block of blocks) {
            const data = block.split("\n")
                .filter(line => line.startsWith("data:"))
                .map(line => line.slice(5).trim())
                .join("\n");
            if (data) yield JSON.parse(data);
        }
    }
}


// Message assistant rempli au fil du flux, avec une ligne d'état sous le texte.
function createStreamingReply() {
    const { msg, body } = createMessage("assistant");
    const status = document.createElement("span");
    status.className = "thinking";
    msg.append(status);

    let text = "";
    let frame = null;

    const isAtBottom = () => chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight < 40;
    const render = () => {
        cancelAnimationFrame(frame);
        frame = null;
        const follow = isAtBottom();
        body.innerHTML = DOMPurify.sanitize(marked.parse(text));
        if (follow) chatBox.scrollTop = chatBox.scrollHeight;
    };
    const setStatus = (label) => {
        status.textContent = label;
        status.hidden = false;
        chatBox.scrollTop = chatBox.scrollHeight;
    };

    setStatus("PROCESSING");

    return {
        setStatus,
        append(delta) {
            text += delta;
            status.hidden = true;
            // Un seul rendu Markdown par frame, quel que soit le débit de tokens.
            frame ??= requestAnimationFrame(render);
        },
        finish() {
            status.remove();
            render();
            body.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
        },
        fail(message) {
            // Une réponse partielle reste affichée mais n'est pas enregistrée par le serveur.
            if (text) this.finish(); else msg.remove();
            appendMessage(message, "error");
        },
    };
}


const SENDER_LABEL = { user: "DUELIST", assistant: "JADEN", error: "THE CODEX FALTERS" };

function createMessage(sender, date = new Date()) {
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
    time.textContent = timestamp(date);
    meta.append(who, time);

    const body = document.createElement("div");
    body.className = "msg__body";

    msg.append(meta, body);
    chatBox.appendChild(msg);
    return { msg, body };
}

function appendMessage(text, sender, date) {
    const { msg, body } = createMessage(sender, date);

    if (sender === "assistant") {
        body.innerHTML = DOMPurify.sanitize(marked.parse(text));
        body.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
    } else {
        body.textContent = text;
    }
    chatBox.scrollTop = chatBox.scrollHeight;
    return msg;
}


// ─── LIAISON ────────────────────────────────────────────────────────────────
function setLinkState(state, label) {
    const link = document.getElementById("link-status");
    link.dataset.state = state;
    document.getElementById("link-text").textContent = label;

    const boot = document.getElementById("boot-link");
    if (boot) {
        boot.className = { ok: "ok", error: "err" }[state] ?? "wait";
        boot.textContent = { ok: "ESTABLISHED", error: "FAILED" }[state] ?? "PENDING";
    }
}

async function updateStatus() {
    if (!currentUser) return;
    let data;
    try {
        const response = await apiFetch(STATUS_URL);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        data = await response.json();
    } catch (error) {
        setLinkState("error", "CLIENT OFFLINE");
        return;
    }
    if (data.server) {
        setLinkState("ok", "LINK ESTABLISHED");
    } else {
        setLinkState("error", "SERVER UNREACHABLE");
    }
}
