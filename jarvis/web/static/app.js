// Jarvis front end. Plain JavaScript, no build step.
(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);

  // localStorage can be blocked (private mode); never let that break the app.
  // It only remembers which tab and chat were open; the chats themselves are
  // saved by the server in data/.
  const store = {
    get(key, fallback) {
      try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
    },
    set(key, value) {
      try {
        if (value === null) localStorage.removeItem(key);
        else localStorage.setItem(key, value);
      } catch { /* ignore */ }
    },
  };

  const el = {
    tabs: document.querySelectorAll(".tab"),
    chat: $("#chat"), form: $("#form"), input: $("#input"), send: $("#send"),
    chips: $("#chips"), newChat: $("#newChat"), chatItems: $("#chatItems"),
    cheatForm: $("#cheatForm"), requirement: $("#requirement"), cheatSend: $("#cheatSend"),
    examples: $("#examples"), results: $("#results"),
    status: $("#status"), statusText: $("#statusText"),
  };

  // chat: id of the open chat, or null for a new one that is not saved yet.
  const state = { chat: null, chatBusy: false, cheatBusy: false };

  // ---------- server calls ----------
  async function api(path, body) {
    const options = body === undefined
      ? {}
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    let response;
    try {
      response = await fetch(path, options);
    } catch {
      throw new Error("Cannot reach the Jarvis server. Is `python run.py` still running?");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
    return data;
  }

  // ---------- rendering helpers ----------
  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // Tiny, safe formatter: escape first, then allow **bold**, *italic*, `code` and line breaks.
  function format(text) {
    return escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\n/g, "<br>");
  }

  function when(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    const sameDay = date.toDateString() === new Date().toDateString();
    return sameDay
      ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : date.toLocaleDateString([], { day: "numeric", month: "short" });
  }

  const TYPING = '<span class="typing"><i></i><i></i><i></i></span>';

  // ---------- tabs ----------
  function showView(name) {
    el.tabs.forEach((tab) => {
      const active = tab.dataset.view === name;
      tab.setAttribute("aria-selected", String(active));
      $(`#view-${tab.dataset.view}`).hidden = !active;
    });
    store.set("jarvis.view", name);
    (name === "cheat" ? el.requirement : el.input).focus();
  }

  // ---------- 1. Learn with Jarvis ----------
  function scrollChat() {
    el.chat.scrollTop = el.chat.scrollHeight;
  }

  function addMessage(role, html) {
    const node = document.createElement("div");
    node.className = `msg ${role}`;
    node.innerHTML = (role === "jarvis" ? '<span class="who">JARVIS</span>' : "") + html;
    el.chat.appendChild(node);
    scrollChat();
    return node;
  }

  function welcome() {
    el.chat.innerHTML = "";
    addMessage(
      "jarvis",
      format(
        "Online. I'm Jarvis, your **Verification & Validation** tutor.\n" +
        "Ask me anything about V&V. Got a requirement to sort out? Use **Cheat on your exam**."
      )
    );
  }

  function markActive() {
    el.chatItems.querySelectorAll(".chat-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.id === state.chat);
    });
  }

  async function loadChatList() {
    const { chats } = await api("/api/chats");
    el.chatItems.innerHTML = chats.length ? "" : '<p class="muted empty">No saved chats yet.</p>';
    chats.forEach((chat) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "chat-item";
      item.dataset.id = chat.id;
      item.title = chat.title;
      item.innerHTML = `<span class="t">${escapeHtml(chat.title)}</span><span class="d">${when(chat.updated)}</span>`;
      el.chatItems.appendChild(item);
    });
    markActive();
    return chats;
  }

  async function openChat(id) {
    state.chat = id;
    store.set("jarvis.chat", id);
    markActive();
    welcome();
    try {
      const { messages } = await api(`/api/history?chat=${encodeURIComponent(id)}`);
      if (state.chat !== id) return;  // another chat was opened meanwhile
      messages.forEach((m) => addMessage(m.role === "user" ? "user" : "jarvis", format(m.content)));
    } catch (error) {
      addMessage("system", escapeHtml(error.message));
    }
  }

  function newChat() {
    state.chat = null;
    store.set("jarvis.chat", null);
    markActive();
    welcome();
    el.input.focus();
  }

  async function sendMessage(text) {
    text = text.trim();
    if (!text || state.chatBusy) return;
    addMessage("user", format(text));
    const typing = addMessage("jarvis", TYPING);
    state.chatBusy = true;
    el.send.disabled = true;
    try {
      const data = await api("/api/chat", { chat_id: state.chat, message: text });
      typing.remove();
      addMessage("jarvis", format(data.reply));
      state.chat = data.chat_id;  // a new chat gets its id with the first reply
      store.set("jarvis.chat", data.chat_id);
      loadChatList().catch(() => {});
    } catch (error) {
      typing.remove();
      addMessage("system", escapeHtml(error.message));
    } finally {
      state.chatBusy = false;
      el.send.disabled = false;
      checkHealth();
    }
  }

  // ---------- 2. Cheat on your exam ----------
  function resultCard(requirement, at) {
    const card = document.createElement("article");
    card.className = "result";
    card.innerHTML =
      `<div class="req-row"><p class="req">${escapeHtml(requirement)}</p>` +
      `<span class="d">${at ? when(at) : ""}</span></div><div class="answer">${TYPING}</div>`;
    return card;
  }

  function renderVerdict(slot, data) {
    const kind = data.verdict === "Validation" ? "val" : "ver";
    const question = kind === "val" ? "Are we building the right product?" : "Are we building the product right?";
    slot.innerHTML =
      `<div class="verdict-row"><span class="badge ${kind}">${escapeHtml(data.verdict)}</span>` +
      `<span class="muted">${question}</span></div>` +
      (data.reason ? `<p><b>Why</b> ${escapeHtml(data.reason)}</p>` : "") +
      (data.example ? `<p><b>Example</b> ${escapeHtml(data.example)}</p>` : "");
  }

  async function loadCheats() {
    try {
      const { cheats } = await api("/api/cheats");
      el.results.innerHTML = "";
      cheats.forEach((entry) => {
        const card = resultCard(entry.requirement, entry.at);
        renderVerdict(card.querySelector(".answer"), entry);
        el.results.appendChild(card);
      });
    } catch { /* nothing saved yet, or server offline */ }
  }

  async function classify(text) {
    text = text.trim();
    if (!text || state.cheatBusy) return;
    const card = resultCard(text);
    el.results.prepend(card);
    const slot = card.querySelector(".answer");
    state.cheatBusy = true;
    el.cheatSend.disabled = true;
    el.requirement.value = "";
    try {
      const entry = await api("/api/classify", { requirement: text });
      renderVerdict(slot, entry);
      card.querySelector(".d").textContent = when(entry.at);
    } catch (error) {
      slot.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
    } finally {
      state.cheatBusy = false;
      el.cheatSend.disabled = false;
      checkHealth();
    }
  }

  // ---------- status ----------
  async function checkHealth() {
    try {
      const health = await api("/api/health");
      el.status.className = `status ${health.online ? "online" : "offline"}`;
      el.statusText.textContent = health.online ? health.model : "ollama offline";
    } catch {
      el.status.className = "status offline";
      el.statusText.textContent = "server offline";
    }
  }

  // ---------- events ----------
  el.tabs.forEach((tab) => tab.addEventListener("click", () => showView(tab.dataset.view)));

  el.form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = el.input.value;
    el.input.value = "";
    sendMessage(text);
  });

  el.chips.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (chip?.dataset.message) sendMessage(chip.dataset.message);
  });

  el.newChat.addEventListener("click", () => {
    if (!state.chatBusy) newChat();
  });

  el.chatItems.addEventListener("click", (event) => {
    const item = event.target.closest(".chat-item");
    if (item && !state.chatBusy && item.dataset.id !== state.chat) openChat(item.dataset.id);
  });

  el.cheatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    classify(el.requirement.value);
  });

  el.requirement.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {  // Enter sends, Shift+Enter = new line
      event.preventDefault();
      classify(el.requirement.value);
    }
  });

  el.examples.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (chip?.dataset.example) classify(chip.dataset.example);
  });

  // ---------- start ----------
  async function start() {
    welcome();
    showView(store.get("jarvis.view", "learn") === "cheat" ? "cheat" : "learn");
    checkHealth();
    setInterval(checkHealth, 15000);
    loadCheats();
    try {
      const chats = await loadChatList();
      const remembered = store.get("jarvis.chat", null);
      const open = chats.find((c) => c.id === remembered) || chats[0];
      if (open) await openChat(open.id);
    } catch (error) {
      addMessage("system", escapeHtml(error.message));
    }
  }

  start();
})();
