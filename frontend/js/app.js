/* ==========================================================================
   Live — Assistant IA vérifié
   Client SSE pour /api/chat/stream (backend Flask)
   ========================================================================== */

// -----------------------------------------------------------------------
// Config — change cette valeur si ton backend tourne sur un autre port/host
// -----------------------------------------------------------------------
const API_BASE = "http://localhost:5001";

// -----------------------------------------------------------------------
// State
// -----------------------------------------------------------------------
let sessionId = null;
let isStreaming = false;

// -----------------------------------------------------------------------
// DOM refs
// -----------------------------------------------------------------------
const $hero = document.getElementById("hero");
const $chat = document.getElementById("chat");
const $stage = document.getElementById("stage");
const $form = document.getElementById("composerForm");
const $input = document.getElementById("messageInput");
const $sendBtn = document.getElementById("sendBtn");
const $orbWrap = document.querySelector(".orb-wrap");
const $brandOrb = document.getElementById("brandOrb");
const $statusDot = document.getElementById("statusDot");
const $statusLabel = document.getElementById("statusLabel");
const $resetBtn = document.getElementById("resetBtn");
const $chips = document.getElementById("chips");

// -----------------------------------------------------------------------
// Boot: check backend health
// -----------------------------------------------------------------------
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { method: "GET" });
    if (res.ok) {
      setConnectionStatus(true);
    } else {
      setConnectionStatus(false);
    }
  } catch (err) {
    setConnectionStatus(false);
  }
}

function setConnectionStatus(online) {
  $statusDot.classList.toggle("online", online);
  $statusDot.classList.toggle("offline", !online);
  $statusLabel.textContent = online ? "En ligne" : "Serveur hors ligne";
}

checkHealth();

// -----------------------------------------------------------------------
// Orb state helper
// -----------------------------------------------------------------------
function setOrbState(state) {
  $orbWrap.setAttribute("data-state", state);
}

// -----------------------------------------------------------------------
// Utilities
// -----------------------------------------------------------------------
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function getHostname(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Nettoie le texte final: retire les balises [Source: ...] et [Confiance: ...]
 *  déjà représentées visuellement par les chips de sources et le badge. */
function cleanFinalText(text) {
  return text
    .replace(/\[Source[^\]]*\]/gi, "")
    .replace(/\[Confiance\s*:\s*[^\]]*\]/gi, "")
    .replace(/[ \t]+\n/g, "\n")
    .trim();
}

function renderParagraphs(container, text) {
  const clean = cleanFinalText(text);
  const parts = clean.split(/\n{2,}/).filter(Boolean);
  container.innerHTML = "";
  if (parts.length === 0) return;
  parts.forEach((part) => {
    const p = document.createElement("p");
    p.innerHTML = escapeHtml(part).replace(/\n/g, "<br>");
    container.appendChild(p);
  });
}

function confidenceMeta(confidence) {
  const map = {
    haute:   { label: "Vérifiée · sources croisées", cls: "haute" },
    moyenne: { label: "Probable · une seule source",  cls: "moyenne" },
    faible:  { label: "Confiance faible",              cls: "faible" },
    low:     { label: "Confiance faible",               cls: "low" },
    "n/a":   { label: "Connaissance générale",          cls: "na" },
    unknown: { label: "Non vérifiée",                    cls: "unknown" },
  };
  return map[confidence] || map["n/a"];
}

function formatTime() {
  const d = new Date();
  return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function scrollToBottom() {
  $stage.scrollTop = $stage.scrollHeight;
}

// -----------------------------------------------------------------------
// Message rendering
// -----------------------------------------------------------------------
function showChatView() {
  if ($hero.hidden) return;
  $hero.hidden = true;
  $chat.hidden = false;
}

function addUserMessage(text) {
  showChatView();
  const msg = document.createElement("div");
  msg.className = "msg msg-user";
  msg.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  $chat.appendChild(msg);
  scrollToBottom();
}

function addAssistantMessage() {
  showChatView();
  const msg = document.createElement("div");
  msg.className = "msg msg-assistant";
  msg.innerHTML = `
    <div class="avatar-mini"><div class="orb"></div></div>
    <div class="bubble">
      <div class="status-line" hidden><span class="pulse"></span><span class="status-text"></span></div>
      <div class="content"></div>
      <div class="sources" hidden></div>
      <div class="meta" hidden>
        <span class="confidence-badge"><span class="dot"></span><span class="label"></span></span>
        <span class="timestamp"></span>
      </div>
    </div>
  `;
  $chat.appendChild(msg);
  scrollToBottom();

  return {
    root: msg,
    statusLine: msg.querySelector(".status-line"),
    statusText: msg.querySelector(".status-text"),
    content: msg.querySelector(".content"),
    sources: msg.querySelector(".sources"),
    meta: msg.querySelector(".meta"),
    badge: msg.querySelector(".confidence-badge"),
    timestamp: msg.querySelector(".timestamp"),
  };
}

function renderSources(el, sources) {
  if (!sources || sources.length === 0) return;
  el.hidden = false;
  el.innerHTML = "";
  sources.slice(0, 6).forEach((src) => {
    const a = document.createElement("a");
    a.className = "source-chip";
    a.href = src.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.innerHTML = `
      <span class="src-domain">${escapeHtml(getHostname(src.url))}</span>
      <span class="src-title">${escapeHtml(src.title || "Source")}</span>
    `;
    el.appendChild(a);
  });
}

function finalizeMessage(refs, data) {
  refs.statusLine.hidden = true;
  renderParagraphs(refs.content, data.response || "");
  renderSources(refs.sources, data.sources);

  const meta = confidenceMeta(data.confidence);
  refs.badge.className = `confidence-badge ${meta.cls}`;
  refs.badge.querySelector(".label").textContent = meta.label;
  refs.timestamp.textContent = formatTime();
  refs.meta.hidden = false;

  scrollToBottom();
}

function showErrorMessage(refs, text) {
  refs.statusLine.hidden = true;
  refs.content.innerHTML = `<p class="error-line">⚠️ ${escapeHtml(text)}</p>`;
  scrollToBottom();
}

// -----------------------------------------------------------------------
// Streaming: POST + parse text/event-stream manually
// -----------------------------------------------------------------------
async function streamChat(userMessage) {
  isStreaming = true;
  $sendBtn.disabled = true;
  setOrbState("searching");

  const refs = addAssistantMessage();
  let rawContent = "";
  let gotFirstToken = false;

  try {
    const res = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: userMessage,
        session_id: sessionId,
      }),
    });

    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop(); // dernier morceau potentiellement incomplet

      for (const chunk of chunks) {
        const line = chunk.trim();
        if (!line.startsWith("data:")) continue;

        const jsonStr = line.slice(5).trim();
        if (!jsonStr) continue;

        let evt;
        try {
          evt = JSON.parse(jsonStr);
        } catch {
          continue;
        }

        handleEvent(evt);
      }
    }

    setOrbState("idle");
  } catch (err) {
    setOrbState("error");
    showErrorMessage(refs, "Connexion au serveur perdue. Vérifie que le backend tourne bien, puis réessaie.");
    setConnectionStatus(false);
  } finally {
    isStreaming = false;
    $sendBtn.disabled = false;
  }

  // ---- handlers ----
  function handleEvent(evt) {
    switch (evt.type) {
      case "session":
        sessionId = evt.data;
        break;

      case "status":
        setOrbState(evt.data.includes("Recherche") ? "searching" : "thinking");
        refs.statusLine.hidden = false;
        refs.statusText.textContent = evt.data;
        break;

      case "sources":
        renderSources(refs.sources, evt.data);
        break;

      case "token":
        if (!gotFirstToken) {
          gotFirstToken = true;
          refs.statusLine.hidden = true;
        }
        rawContent += evt.data;
        refs.content.innerHTML = escapeHtml(rawContent).replace(/\n/g, "<br>") + '<span class="cursor"></span>';
        scrollToBottom();
        break;

      case "done":
        finalizeMessage(refs, evt.data);
        break;

      case "error":
        setOrbState("error");
        showErrorMessage(refs, evt.data || "Une erreur est survenue.");
        break;
    }
  }
}

// -----------------------------------------------------------------------
// Form submit
// -----------------------------------------------------------------------
$form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $input.value.trim();
  if (!text || isStreaming) return;

  addUserMessage(text);
  $input.value = "";
  streamChat(text);
});

// -----------------------------------------------------------------------
// Suggestion chips
// -----------------------------------------------------------------------
$chips.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const q = chip.getAttribute("data-q");
  addUserMessage(q);
  streamChat(q);
});

// -----------------------------------------------------------------------
// Reset conversation
// -----------------------------------------------------------------------
$resetBtn.addEventListener("click", async () => {
  if (isStreaming) return;

  if (sessionId) {
    try {
      await fetch(`${API_BASE}/api/session/${sessionId}`, { method: "DELETE" });
    } catch {
      /* pas grave si ça échoue, on repart quand même côté client */
    }
  }

  sessionId = null;
  $chat.innerHTML = "";
  $chat.hidden = true;
  $hero.hidden = false;
  $input.value = "";
  setOrbState("idle");
});
