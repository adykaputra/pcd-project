(function () {
  const form = document.getElementById("chat-form");
  const messages = document.getElementById("messages");
  const input = document.getElementById("chat-input");
  const providerInput = document.getElementById("provider");
  const modelInput = document.getElementById("model");
  const indicator = document.getElementById("policy-indicator");
  const turnCounter = document.getElementById("turn-counter");
  const typingIndicator = document.getElementById("typing-indicator");
  const reportNode = document.getElementById("privacy-report");
  const reportPolicy = document.getElementById("report-policy");
  const reportScore = document.getElementById("report-score");
  const reportLevel = document.getElementById("report-level");
  const reportTokens = document.getElementById("report-tokens");
  const reportReasons = document.getElementById("report-reasons");
  const reportProof = document.getElementById("report-proof");
  const clearButton = document.getElementById("clear-chat");
  const copyButton = document.getElementById("copy-last");
  const logoutButton = document.getElementById("logout-btn");
  const historyList = document.getElementById("history-list");
  const welcomePanel = document.getElementById("chat-welcome");
  const suggestionsBar = document.getElementById("suggestions-bar");
  const workspaceStatus = document.getElementById("workspace-status");
  const workspaceButtons = Array.from(document.querySelectorAll(".workspace-btn"));
  const chatTitle = document.querySelector(".chat-topbar h2");
  const bootstrap = window.__CLIENT_BOOTSTRAP__ || {};
  const displayName = String(bootstrap.displayName || "Client");
  const userIdentity = String(bootstrap.userIdentity || displayName || "anonymous").toLowerCase();
  const authToken = String(bootstrap.authToken || "");
  const REQUEST_TIMEOUT_MS = 120000;
  const HISTORY_KEY = `dlp_chat_sessions_v3:${userIdentity}`;
  const MAX_HISTORY = 20;
  let lastAssistantText = "";
  let turns = 0;
  let sessions = [];
  let activeSessionId = "";
  let activeWorkspace = "current";

  const WORKSPACE_CONFIG = {
    current: {
      label: "Current Case",
      prompt: "",
      suggestions: [
        "Create a clean DLP case summary structure I can reuse.",
        "What should be in a defect report before escalation?",
        "Give me a short handover note for an unresolved defect case.",
      ],
    },
    guidelines: {
      label: "DLP Guidelines",
      prompt: "Give me a practical checklist for managing Defect Liability Period communication with clients and contractors.",
      suggestions: [
        "List 8 practical DLP communication rules for project teams.",
        "Show bad vs good examples of DLP case updates.",
        "Create a one-minute DLP checklist for non-technical staff.",
      ],
    },
    assessment: {
      label: "Liability Assessment",
      prompt: "Assess this defect case and explain urgency, liability risk, and recommended next action.",
      suggestions: [
        "Evaluate this case using low/medium/high legal urgency levels.",
        "What facts increase liability risk in this defect report?",
        "How can I rewrite this report to be clearer for legal review?",
      ],
    },
    scanner: {
      label: "Clause Scanner",
      prompt: "Scan this defect report and extract key timeline facts, parties involved, and required actions.",
      suggestions: [
        "Identify key incident facts and missing details in this report.",
        "Turn this raw message into a structured case note.",
        "Summarize clauses I should check for this defect type.",
      ],
    },
    notice: {
      label: "Notice Letter",
      prompt: "Draft a formal DLP notice letter for contractor response within a defined timeline.",
      suggestions: [
        "Draft a notice with issue summary, expected remedy, and deadline.",
        "Write a reminder notice for delayed defect rectification.",
        "Create a concise final warning notice before escalation.",
      ],
    },
  };

  function autoResizeInput() {
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  }

  function nowTs() {
    return Date.now();
  }

  function defaultSystemMessage() {
    return `Hi ${displayName}, I am your DLP legal support assistant. I can help with defect case analysis, notices, and action planning.`;
  }

  function createSession() {
    const ts = nowTs();
    return {
      id: `chat-${ts}-${Math.random().toString(36).slice(2, 7)}`,
      title: "New case",
      updatedAt: ts,
      entries: [{ role: "system", text: defaultSystemMessage(), meta: "system", ts }],
    };
  }

  function safeLoadSessions() {
    try {
      const raw = window.localStorage.getItem(HISTORY_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter((session) => session && typeof session === "object")
        .map((session) => ({
          id: String(session.id || ""),
          title: String(session.title || "New case"),
          updatedAt: Number(session.updatedAt || nowTs()),
          entries: Array.isArray(session.entries) ? session.entries : [],
        }))
        .filter((session) => session.id && session.entries.length > 0)
        .slice(0, MAX_HISTORY);
    } catch {
      return [];
    }
  }

  function safeSaveSessions() {
    try {
      window.localStorage.setItem(HISTORY_KEY, JSON.stringify(sessions.slice(0, MAX_HISTORY)));
    } catch {
      // Ignore storage failures gracefully.
    }
  }

  function getActiveSession() {
    return sessions.find((session) => session.id === activeSessionId) || null;
  }

  function getSessionTitle(entries) {
    const firstUser = (entries || []).find((entry) => entry.role === "user" && entry.text);
    if (!firstUser) return "New case";
    const compact = String(firstUser.text).replace(/\s+/g, " ").trim();
    return compact.length > 44 ? `${compact.slice(0, 44)}...` : compact;
  }

  function formatTime(ts) {
    try {
      return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "--:--";
    }
  }

  function updateTurns() {
    if (!turnCounter) return;
    turnCounter.textContent = `${turns} turns`;
  }

  function setIndicator(status) {
    const safe = String(status || "neutral").toLowerCase();
    const labelMap = {
      neutral: "ready",
      ok: "clear",
      challenge: "review",
      denied: "blocked",
    };
    indicator.className = `badge ${safe}`;
    indicator.textContent = labelMap[safe] || safe;
  }

  function setTyping(visible) {
    if (!typingIndicator) return;
    typingIndicator.hidden = !visible;
  }

  function activateWorkspace(workspace) {
    const current = String(workspace || "current");
    activeWorkspace = current in WORKSPACE_CONFIG ? current : "current";
    workspaceButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.workspace === activeWorkspace);
    });
    if (chatTitle) {
      const active = workspaceButtons.find((btn) => btn.dataset.workspace === activeWorkspace);
      if (active && activeWorkspace !== "current") {
        chatTitle.textContent = `DLP Legal Assistant · ${active.textContent?.trim() || "Workspace"}`;
      } else {
        chatTitle.textContent = "DLP Legal Assistant";
      }
    }
    const label = WORKSPACE_CONFIG[activeWorkspace]?.label || "Current Case";
    if (workspaceStatus) {
      workspaceStatus.textContent = `Mode: ${label.toLowerCase()}`;
    }
  }

  function setPromptDraft(text, focus = true) {
    if (!input) return;
    input.value = String(text || "");
    autoResizeInput();
    if (focus) input.focus();
  }

  function renderSuggestionButtons(items) {
    if (!suggestionsBar) return;
    const values = Array.isArray(items) ? items : [];
    suggestionsBar.innerHTML = values
      .map(
        (item) =>
          `<button class="suggestion-btn" type="button" data-prompt="${String(item)
            .replaceAll("&", "&amp;")
            .replaceAll("\"", "&quot;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")}">${String(item)}</button>`
      )
      .join("");
  }

  function applyWorkspace(workspace, { includeDraft = true } = {}) {
    const key = workspace in WORKSPACE_CONFIG ? workspace : "current";
    const config = WORKSPACE_CONFIG[key];
    activateWorkspace(key);
    renderSuggestionButtons(config.suggestions || []);
    if (includeDraft && config.prompt) {
      setPromptDraft(config.prompt);
    }
    if (suggestionsBar) {
      suggestionsBar.hidden = false;
    }
    if (key !== "current" && welcomePanel) {
      welcomePanel.hidden = false;
    }
  }

  function createMessageNode(role, text, meta = "", ts = nowTs()) {
    if (!messages) return;
    const node = document.createElement("div");
    node.className = `message ${role}`;

    const stamp = formatTime(ts);

    const metaNode = document.createElement("div");
    metaNode.className = "meta";
    metaNode.textContent = `${meta || role} · ${stamp}`;

    const textNode = document.createElement("p");
    textNode.textContent = String(text || "");

    node.appendChild(metaNode);
    node.appendChild(textNode);
    return { node, textNode };
  }

  function appendMessage(role, text, meta = "", ts = nowTs()) {
    if (!messages) return null;
    const built = createMessageNode(role, text, meta, ts);
    if (!built) return null;
    const { node, textNode } = built;
    messages.appendChild(node);
    messages.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
    return { node, textNode };
  }

  function updatePrivacyReport(payload) {
    if (!reportNode) return;
    const risk = payload?.risk_assessment || {};
    const reasons = Array.isArray(risk.reasons) ? risk.reasons : [];
    const tokenCounts = payload?.tokenization?.token_counts || {};
    const dispatchProof = payload?.dispatch_proof || {};
    const totalTokens = Object.values(tokenCounts).reduce((sum, value) => sum + (Number(value) || 0), 0);
    reportPolicy.textContent = String(risk.policy_action || payload.status || "n/a");
    reportScore.textContent = String(risk.risk_score ?? "n/a");
    reportLevel.textContent = String(risk.risk_level || "n/a");
    const caseFlags = Math.max(reasons.length, totalTokens);
    reportTokens.textContent = String(caseFlags);
    reportReasons.textContent = reasons.length ? `Case signals: ${reasons.join(", ")}` : "Case signals: none";
    if (reportProof) {
      const secureRelay = dispatchProof.model_input_is_tokenized ? "active" : "standby";
      reportProof.textContent = `Background compliance guard: ${secureRelay}.`;
    }
    reportNode.hidden = false;
  }

  function appendEntry(role, text, meta, ts = nowTs()) {
    const active = getActiveSession();
    if (!active) return;
    active.entries.push({ role, text, meta, ts });
    active.updatedAt = ts;
    active.title = getSessionTitle(active.entries);
    sessions = [active, ...sessions.filter((session) => session.id !== active.id)].slice(0, MAX_HISTORY);
    safeSaveSessions();
    renderHistoryList();
    if (role === "user" && welcomePanel) {
      welcomePanel.hidden = true;
    }
  }

  function renderActiveSession() {
    if (!messages) return;
    const active = getActiveSession();
    if (!active) return;
    messages.innerHTML = "";
    for (const entry of active.entries) {
      appendMessage(entry.role, entry.text, entry.meta || entry.role, entry.ts || nowTs());
    }
    turns = active.entries.filter((entry) => entry.role === "user").length;
    updateTurns();
    if (welcomePanel) {
      welcomePanel.hidden = turns > 0;
    }
    applyWorkspace("current", { includeDraft: false });
    const lastAssistant = [...active.entries].reverse().find((entry) => entry.role === "assistant");
    lastAssistantText = lastAssistant?.text || "";
    setIndicator("neutral");
    if (reportNode) reportNode.hidden = true;
  }

  function renderHistoryList() {
    if (!historyList) return;
    historyList.innerHTML = "";
    for (const session of sessions) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `history-item${session.id === activeSessionId ? " active" : ""}`;
      btn.dataset.sessionId = session.id;

      const titleNode = document.createElement("span");
      titleNode.className = "history-item-title";
      titleNode.textContent = session.title || "New case";

      const timeNode = document.createElement("span");
      timeNode.className = "history-item-time";
      timeNode.textContent = formatTime(session.updatedAt);

      btn.appendChild(titleNode);
      btn.appendChild(timeNode);
      li.appendChild(btn);
      historyList.appendChild(li);
    }
  }

  function startNewSession() {
    const session = createSession();
    sessions = [session, ...sessions].slice(0, MAX_HISTORY);
    activeSessionId = session.id;
    safeSaveSessions();
    renderHistoryList();
    renderActiveSession();
  }

  async function streamAssistantText(text, meta) {
    const entryTs = nowTs();
    const built = appendMessage("assistant", "", meta, entryTs);
    if (!built) return { finalText: text, ts: entryTs };
    const textNode = built.textNode;
    const finalText = String(text || "");
    const prefersReduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced || finalText.length < 60) {
      textNode.textContent = finalText;
      appendEntry("assistant", finalText, meta, entryTs);
      return { finalText, ts: entryTs };
    }

    const words = finalText.split(" ");
    let current = "";
    for (let i = 0; i < words.length; i += 1) {
      current = current ? `${current} ${words[i]}` : words[i];
      textNode.textContent = current;
      if (messages) {
        messages.scrollTo({ top: messages.scrollHeight, behavior: "auto" });
      }
      if (i % 3 === 0) {
        await new Promise((resolve) => window.setTimeout(resolve, 16));
      }
    }
    appendEntry("assistant", finalText, meta, entryTs);
    return { finalText, ts: entryTs };
  }

  function ensureSessionState() {
    sessions = safeLoadSessions();
    if (sessions.length === 0) {
      const starter = createSession();
      sessions = [starter];
      activeSessionId = starter.id;
      safeSaveSessions();
    } else {
      activeSessionId = sessions[0].id;
    }
    renderHistoryList();
    renderActiveSession();
  }

  function handleSessionSelection(target) {
    const button = target.closest(".history-item");
    if (!button) return;
    const sessionId = String(button.dataset.sessionId || "");
    if (!sessionId || sessionId === activeSessionId) return;
    activeSessionId = sessionId;
    renderHistoryList();
    renderActiveSession();
  }

  if (!form) return;
  if (window.location.search.includes("token=")) {
    window.history.replaceState({}, document.title, window.location.pathname);
  }
  ensureSessionState();

  suggestionsBar?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest(".suggestion-btn") : null;
    if (!target) return;
    const text = target.getAttribute("data-prompt") || "";
    setPromptDraft(text);
  });

  welcomePanel?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest(".welcome-action") : null;
    if (!target) return;
    const text = target.getAttribute("data-prompt") || "";
    setPromptDraft(text);
  });

  workspaceButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const workspace = btn.dataset.workspace || "current";
      if (workspace === "current") {
        applyWorkspace("current", { includeDraft: false });
        input?.focus();
        return;
      }
      applyWorkspace(workspace, { includeDraft: true });
    });
  });

  input?.addEventListener("input", autoResizeInput);
  input?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  clearButton?.addEventListener("click", startNewSession);
  historyList?.addEventListener("click", (event) => {
    handleSessionSelection(event.target);
  });
  logoutButton?.addEventListener("click", async (event) => {
    event.preventDefault();
    try {
      await fetch("/logout", { method: "POST", headers: { "Content-Type": "application/json" } });
    } catch {
      // ignore network errors during logout
    }
    window.location.replace("/");
  });
  copyButton?.addEventListener("click", async () => {
    if (!lastAssistantText) return;
    try {
      await navigator.clipboard.writeText(lastAssistantText);
      setIndicator("ok");
    } catch (err) {
      setIndicator("denied");
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const prompt = (input?.value || "").trim();
    if (!prompt) return;

    appendMessage("user", prompt, "you");
    appendEntry("user", prompt, "you");
    input.value = "";
    autoResizeInput();
    setTyping(true);
    const submitButton = form.querySelector("button[type='submit']");
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Sending...";
    }
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch("/client/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        signal: controller.signal,
        body: JSON.stringify({
          prompt,
          provider: (providerInput?.value || "ollama").trim(),
          model: (modelInput?.value || "").trim() || undefined,
        }),
      });
      const payload = await response.json();
      if (response.status === 401) {
        window.location.href = "/";
        return;
      }

      if (payload.status === "ok") {
        if (payload.fallback_reason === "ollama_unavailable") {
          appendMessage(
            "system",
            "Local Ollama model is temporarily unavailable. Please retry in a moment.",
            "system"
          );
          appendEntry(
            "system",
            "Local Ollama model is temporarily unavailable. Please retry in a moment.",
            "system"
          );
        }
        const streamed = await streamAssistantText(
          payload.reply || "No response text returned.",
          `assistant · ${payload.provider || "unknown"}`
        );
        lastAssistantText = streamed.finalText || "";
        turns += 1;
        updateTurns();
        updatePrivacyReport(payload);
        setIndicator("ok");
        return;
      }
      if (payload.status === "challenge") {
        const challengeText = payload.reply || "Prompt needs revision.";
        await streamAssistantText(challengeText, "policy challenge");
        lastAssistantText = challengeText;
        turns += 1;
        updateTurns();
        updatePrivacyReport(payload);
        setIndicator("challenge");
        return;
      }
      const deniedText = payload.reply || payload.message || "Request denied by policy.";
      await streamAssistantText(deniedText, "policy denied");
      lastAssistantText = deniedText;
      turns += 1;
      updateTurns();
      updatePrivacyReport(payload);
      setIndicator("denied");
    } catch (err) {
      if (err && err.name === "AbortError") {
        appendMessage(
          "assistant",
          "I did not get a response from Ollama in time. First reply can take longer if the model is cold. Ensure Ollama is running and model llama3.2:3b is available.",
          "timeout"
        );
        appendEntry(
          "assistant",
          "I did not get a response from Ollama in time. First reply can take longer if the model is cold. Ensure Ollama is running and model llama3.2:3b is available.",
          "timeout"
        );
      } else {
        const errorText = `Connection error: ${err}`;
        appendMessage("assistant", errorText, "error");
        appendEntry("assistant", errorText, "error");
      }
      setIndicator("denied");
    } finally {
      window.clearTimeout(timeoutId);
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = "Send";
      }
      setTyping(false);
    }
  });

  autoResizeInput();
})();
