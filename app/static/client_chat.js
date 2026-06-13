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
  const clearButton = document.getElementById("clear-chat");
  const copyButton = document.getElementById("copy-last");
  const quickButtons = Array.from(document.querySelectorAll(".quick-btn"));
  const bootstrap = window.__CLIENT_BOOTSTRAP__ || {};
  const authToken = String(bootstrap.authToken || "");
  const REQUEST_TIMEOUT_MS = 30000;
  let lastAssistantText = "";
  let turns = 0;

  function autoResizeInput() {
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  }

  function addMessage(role, text, meta = "") {
    if (!messages) return;
    const node = document.createElement("div");
    node.className = `message ${role}`;

    const stamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    const metaNode = document.createElement("div");
    metaNode.className = "meta";
    metaNode.textContent = `${meta || role} · ${stamp}`;

    const textNode = document.createElement("p");
    textNode.textContent = String(text || "");

    node.appendChild(metaNode);
    node.appendChild(textNode);
    messages.appendChild(node);
    messages.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
  }

  function setIndicator(status) {
    const safe = String(status || "neutral").toLowerCase();
    indicator.className = `badge ${safe}`;
    indicator.textContent = safe;
  }

  function setTyping(visible) {
    if (!typingIndicator) return;
    typingIndicator.hidden = !visible;
  }

  function updateTurns() {
    if (!turnCounter) return;
    turnCounter.textContent = `${turns} turns`;
  }

  function updatePrivacyReport(payload) {
    if (!reportNode) return;
    const risk = payload?.risk_assessment || {};
    const reasons = Array.isArray(risk.reasons) ? risk.reasons : [];
    const tokenCounts = payload?.tokenization?.token_counts || {};
    const totalTokens = Object.values(tokenCounts).reduce((sum, value) => sum + (Number(value) || 0), 0);
    reportPolicy.textContent = String(risk.policy_action || payload.status || "n/a");
    reportScore.textContent = String(risk.risk_score ?? "n/a");
    reportLevel.textContent = String(risk.risk_level || "n/a");
    reportTokens.textContent = String(totalTokens);
    reportReasons.textContent = reasons.length ? `Signals: ${reasons.join(", ")}` : "Signals: none";
    reportNode.hidden = false;
  }

  function clearChat() {
    if (!messages) return;
    messages.innerHTML = "";
    addMessage(
      "system",
      "Conversation cleared. Continue safely. I will still tokenize sensitive details before model dispatch.",
      "system"
    );
    turns = 0;
    updateTurns();
    setIndicator("neutral");
    if (reportNode) reportNode.hidden = true;
    lastAssistantText = "";
  }

  if (!form) return;
  quickButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const text = btn.dataset.prompt || "";
      if (input) input.value = text;
      autoResizeInput();
      input?.focus();
    });
  });

  input?.addEventListener("input", autoResizeInput);
  input?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  clearButton?.addEventListener("click", clearChat);
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

    addMessage("user", prompt, "you");
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
          provider: (providerInput?.value || "mock").trim(),
          model: (modelInput?.value || "").trim() || undefined,
        }),
      });
      const payload = await response.json();
      if (response.status === 401) {
        window.location.href = "/";
        return;
      }

      if (payload.status === "ok") {
        addMessage("assistant", payload.reply || "No response text returned.", `assistant · ${payload.provider || "unknown"}`);
        lastAssistantText = payload.reply || "";
        turns += 1;
        updateTurns();
        updatePrivacyReport(payload);
        setIndicator("ok");
        return;
      }
      if (payload.status === "challenge") {
        addMessage("assistant", payload.reply || "Prompt needs revision.", "policy challenge");
        lastAssistantText = payload.reply || "";
        turns += 1;
        updateTurns();
        updatePrivacyReport(payload);
        setIndicator("challenge");
        return;
      }
      addMessage("assistant", payload.reply || payload.message || "Request denied by policy.", "policy denied");
      lastAssistantText = payload.reply || payload.message || "";
      turns += 1;
      updateTurns();
      updatePrivacyReport(payload);
      setIndicator("denied");
    } catch (err) {
      if (err && err.name === "AbortError") {
        addMessage(
          "assistant",
          "I did not get a response from the model in time. If you selected Ollama, make sure it is running and the model exists, or switch provider to 'mock' for instant demo replies.",
          "timeout"
        );
      } else {
        addMessage("assistant", `Connection error: ${err}`, "error");
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
  updateTurns();
})();
