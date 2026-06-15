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
  const workspacePanel = document.getElementById("workspace-panel");
  const workspacePanelTitle = document.getElementById("workspace-panel-title");
  const workspacePanelSubtitle = document.getElementById("workspace-panel-subtitle");
  const workspacePanelContent = document.getElementById("workspace-panel-content");
  const suggestionsBar = document.getElementById("suggestions-bar");
  const workspaceStatus = document.getElementById("workspace-status");
  const attachImageButton = document.getElementById("attach-image-btn");
  const attachDocButton = document.getElementById("attach-doc-btn");
  const attachImageInput = document.getElementById("attach-image-input");
  const attachDocInput = document.getElementById("attach-doc-input");
  const attachmentList = document.getElementById("attachment-list");
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
  let pendingAttachments = [];

  const WORKSPACE_CONFIG = {
    current: {
      label: "Live Thread",
      prompt: "",
      subtitle: "Real-time assistant conversation",
      placeholder: "Ask about a DLP case, defect issue, or notice draft...",
      suggestions: [
        "Create a clean defect-liability case summary structure I can reuse.",
        "What should be in a defect report before escalation?",
        "Give me a short handover note for an unresolved defect case.",
      ],
    },
    guidelines: {
      label: "Workflow Playbook",
      subtitle: "User instructions and safety commitments",
      placeholder: "Ask for workflow clarifications or policy explanations...",
      suggestions: [
        "List 8 practical DLP communication rules for project teams.",
        "Show bad vs good examples of DLP case updates.",
        "Create a one-minute DLP checklist for non-technical staff.",
      ],
      panelHtml: `
        <article class="workspace-card">
          <h4>How to use this assistant</h4>
          <ol>
            <li>Describe your defect issue using neutral case facts.</li>
            <li>Ask for triage, clause mapping, or notice drafting support.</li>
            <li>Review response, then copy formal output for your submission.</li>
          </ol>
        </article>
        <article class="workspace-card">
          <h4>Your personal information protection</h4>
          <ul>
            <li>Direct identifiers are masked before model dispatch.</li>
            <li>Administrative evidence views are sanitized and read-only.</li>
            <li>Session-level controls reduce accidental data exposure.</li>
          </ul>
          <p class="workspace-note">You can still avoid typing full IDs or account numbers unless absolutely required for your case.</p>
        </article>
      `,
    },
    assessment: {
      label: "Exposure Triage",
      subtitle: "Classify urgency and recommend next move",
      placeholder: "Paste a case summary to assess urgency and liability risk...",
      suggestions: [
        "Evaluate this case using low/medium/high legal urgency levels.",
        "What facts increase liability risk in this defect report?",
        "How can I rewrite this report to be clearer for legal review?",
      ],
      panelHtml: `
        <article class="workspace-card">
          <h4>Triage frame</h4>
          <div class="workspace-kpis">
            <span class="workspace-pill">Urgency</span>
            <span class="workspace-pill">Liability exposure</span>
            <span class="workspace-pill">Escalation path</span>
          </div>
          <p>Ask for a structured answer in this format: <em>Issue summary -> Risk tier -> Responsible party -> Recommended action within timeline.</em></p>
        </article>
      `,
    },
    scanner: {
      label: "Clause Mapper",
      subtitle: "Map facts to contractual and legal checkpoints",
      placeholder: "Paste defect text to extract timeline, parties, and clause cues...",
      suggestions: [
        "Identify key incident facts and missing details in this report.",
        "Turn this raw message into a structured case note.",
        "Summarize clauses I should check for this defect type.",
      ],
      panelHtml: `
        <article class="workspace-card">
          <h4>Case extraction checklist</h4>
          <ul>
            <li>Date and place of incident</li>
            <li>Type of defect and severity</li>
            <li>Evidence collected (photo, report, invoice)</li>
            <li>Developer or contractor response status</li>
          </ul>
        </article>
      `,
    },
    notice: {
      label: "Response Drafting",
      subtitle: "Generate formal communication drafts",
      placeholder: "Request a notice template, reminder, or escalation letter...",
      suggestions: [
        "Draft a notice with issue summary, expected remedy, and deadline.",
        "Write a reminder notice for delayed defect rectification.",
        "Create a concise final warning notice before escalation.",
      ],
      panelHtml: `
        <article class="workspace-card">
          <h4>Notice output template</h4>
          <p>Recommended structure:</p>
          <ol>
            <li>Reference and defect description</li>
            <li>Legal/contract basis and DLP window context</li>
            <li>Required remedial action and response deadline</li>
            <li>Escalation statement if unresolved</li>
          </ol>
        </article>
      `,
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
    return `Hi ${displayName}, I am your defect-liability support assistant. I can help with case analysis, notices, and action planning.`;
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
        chatTitle.textContent = `Defect Liability Workspace · ${active.textContent?.trim() || "Workspace"}`;
      } else {
        chatTitle.textContent = "Defect Liability Workspace";
      }
    }
    const label = WORKSPACE_CONFIG[activeWorkspace]?.label || "Live Thread";
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

  function renderWorkspacePanel(key) {
    if (!workspacePanel || !workspacePanelTitle || !workspacePanelSubtitle || !workspacePanelContent) return;
    const config = WORKSPACE_CONFIG[key];
    if (!config || key === "current") {
      workspacePanel.hidden = true;
      workspacePanelContent.innerHTML = "";
      return;
    }
    workspacePanelTitle.textContent = config.label || "Workspace";
    workspacePanelSubtitle.textContent = config.subtitle || "";
    workspacePanelContent.innerHTML = config.panelHtml || "<p class=\"workspace-empty\">No panel content available.</p>";
    workspacePanel.hidden = false;
  }

  function setWorkspaceView(key) {
    const isCurrent = key === "current";
    if (messages) messages.hidden = !isCurrent;
    if (welcomePanel) {
      welcomePanel.hidden = !isCurrent || turns > 0;
    }
    if (!isCurrent && reportNode) {
      reportNode.hidden = true;
    }
    renderWorkspacePanel(key);
  }

  function renderAttachmentList() {
    if (!attachmentList) return;
    if (!pendingAttachments.length) {
      attachmentList.hidden = true;
      attachmentList.innerHTML = "";
      return;
    }
    attachmentList.hidden = false;
    attachmentList.innerHTML = "";
    pendingAttachments.forEach((item, index) => {
      const chip = document.createElement("div");
      chip.className = "attachment-chip";

      const label = document.createElement("span");
      label.textContent = `${item.kind}: ${item.name}`;

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "attachment-remove";
      remove.textContent = "Remove";
      remove.dataset.index = String(index);

      chip.appendChild(label);
      chip.appendChild(remove);
      attachmentList.appendChild(chip);
    });
  }

  function clearAttachments() {
    pendingAttachments = [];
    if (attachImageInput) attachImageInput.value = "";
    if (attachDocInput) attachDocInput.value = "";
    renderAttachmentList();
  }

  function addAttachments(fileList, kind) {
    const files = Array.from(fileList || []).slice(0, 4);
    if (!files.length) return;
    const next = files.map((file) => ({
      name: file.name,
      type: file.type || "application/octet-stream",
      size: Number(file.size || 0),
      kind,
      file,
    }));
    pendingAttachments = [...pendingAttachments, ...next].slice(0, 6);
    renderAttachmentList();
  }

  function applyWorkspace(workspace, { includeDraft = true } = {}) {
    const key = workspace in WORKSPACE_CONFIG ? workspace : "current";
    const config = WORKSPACE_CONFIG[key];
    activateWorkspace(key);
    setWorkspaceView(key);
    renderSuggestionButtons(config.suggestions || []);
    if (input) {
      input.placeholder = config.placeholder || "Ask a question...";
    }
    if (includeDraft && config.prompt && key === "current") {
      setPromptDraft(config.prompt);
    }
    if (suggestionsBar) {
      suggestionsBar.hidden = false;
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
    clearAttachments();
  }

  function renderHistoryList() {
    if (!historyList) return;
    historyList.innerHTML = "";
    for (const session of sessions) {
      const li = document.createElement("li");
      li.className = "history-row";
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
      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "history-item-delete";
      deleteBtn.dataset.sessionId = session.id;
      deleteBtn.setAttribute("aria-label", `Delete ${session.title || "session"}`);
      deleteBtn.textContent = "Delete";
      li.appendChild(btn);
      li.appendChild(deleteBtn);
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

  async function deleteSession(sessionId) {
    const selectedSession = sessions.find((session) => session.id === sessionId);
    if (!selectedSession) return;
    const confirmed = window.confirm(`Delete this chat session?\n\n"${selectedSession.title || "Untitled session"}"`);
    if (!confirmed) return;

    try {
      const response = await fetch(`/client/sessions/${encodeURIComponent(sessionId)}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({ message: "Unable to delete session." }));
        throw new Error(payload?.message || "Unable to delete session.");
      }
    } catch (error) {
      appendMessage("system", `Could not delete session from server evidence log: ${String(error)}`, "system");
      setIndicator("denied");
      return;
    }

    sessions = sessions.filter((session) => session.id !== sessionId);
    if (!sessions.length) {
      const starter = createSession();
      sessions = [starter];
      activeSessionId = starter.id;
    } else if (activeSessionId === sessionId) {
      activeSessionId = sessions[0].id;
    }
    safeSaveSessions();
    renderHistoryList();
    renderActiveSession();
    setIndicator("ok");
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
      applyWorkspace(workspace, { includeDraft: false });
      if (workspace === "current") {
        input?.focus();
      }
    });
  });

  attachImageButton?.addEventListener("click", () => attachImageInput?.click());
  attachDocButton?.addEventListener("click", () => attachDocInput?.click());
  attachImageInput?.addEventListener("change", (event) => {
    addAttachments(event.target?.files, "Picture");
  });
  attachDocInput?.addEventListener("change", (event) => {
    addAttachments(event.target?.files, "Document");
  });
  attachmentList?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest(".attachment-remove") : null;
    if (!target) return;
    const idx = Number(target.dataset.index || -1);
    if (idx < 0 || idx >= pendingAttachments.length) return;
    pendingAttachments.splice(idx, 1);
    renderAttachmentList();
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
    const deleteBtn = event.target instanceof Element ? event.target.closest(".history-item-delete") : null;
    if (deleteBtn) {
      const sessionId = String(deleteBtn.getAttribute("data-session-id") || "");
      if (sessionId) {
        deleteSession(sessionId).catch(() => {});
      }
      return;
    }
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
    if (!prompt && !pendingAttachments.length) return;
    const attachmentNames = pendingAttachments.map((item) => item.name);
    const renderedPrompt = prompt || "Please review the attached materials for this defect-liability case.";
    const attachmentLine = attachmentNames.length ? `\n\nAttachments: ${attachmentNames.join(", ")}` : "";
    const modelPrompt = `${renderedPrompt}${attachmentLine}`;
    if (activeWorkspace !== "current") {
      applyWorkspace("current", { includeDraft: false });
    }

    appendMessage("user", `${renderedPrompt}${attachmentLine}`, "you");
    appendEntry("user", `${renderedPrompt}${attachmentLine}`, "you");
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
      const hasAttachments = pendingAttachments.length > 0;
      const headers = {
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      };
      let body;
      if (hasAttachments) {
        const formData = new FormData();
        formData.append("prompt", modelPrompt);
        formData.append("session_id", activeSessionId);
        formData.append("provider", (providerInput?.value || "ollama").trim());
        const chosenModel = (modelInput?.value || "").trim();
        if (chosenModel) {
          formData.append("model", chosenModel);
        }
        pendingAttachments.forEach((item) => {
          if (item?.file) {
            formData.append("attachments", item.file, item.name);
          }
        });
        body = formData;
      } else {
        headers["Content-Type"] = "application/json";
        body = JSON.stringify({
          prompt: modelPrompt,
          session_id: activeSessionId,
          provider: (providerInput?.value || "ollama").trim(),
          model: (modelInput?.value || "").trim() || undefined,
        });
      }
      const response = await fetch("/client/chat", {
        method: "POST",
        headers,
        signal: controller.signal,
        body,
      });
      const payload = await response.json();
      if (response.status === 401) {
        window.location.href = "/";
        return;
      }

      if (payload.status === "ok") {
        const attachmentWarnings = Array.isArray(payload.attachment_warnings) ? payload.attachment_warnings : [];
        if (attachmentWarnings.length) {
          const warningText = `Attachment notes: ${attachmentWarnings.join(" ")}`;
          appendMessage("system", warningText, "system");
          appendEntry("system", warningText, "system");
        }
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
          `assistant · ${payload.provider || "unknown"}${payload.model ? ` (${payload.model})` : ""}`
        );
        lastAssistantText = streamed.finalText || "";
        turns += 1;
        updateTurns();
        updatePrivacyReport(payload);
        setIndicator("ok");
        clearAttachments();
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
        clearAttachments();
        return;
      }
      const deniedText = payload.reply || payload.message || "Request denied by policy.";
      await streamAssistantText(deniedText, "policy denied");
      lastAssistantText = deniedText;
      turns += 1;
      updateTurns();
      updatePrivacyReport(payload);
      setIndicator("denied");
      clearAttachments();
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
