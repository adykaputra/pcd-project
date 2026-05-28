(function () {
  const form = document.getElementById("chat-form");
  const messages = document.getElementById("messages");
  const input = document.getElementById("chat-input");
  const providerInput = document.getElementById("provider");
  const modelInput = document.getElementById("model");
  const indicator = document.getElementById("policy-indicator");

  function addMessage(role, text, meta = "") {
    const node = document.createElement("div");
    node.className = `message ${role}`;
    node.innerHTML = `<div class="meta">${meta || role}</div><p>${text}</p>`;
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
  }

  function setIndicator(status) {
    const safe = String(status || "neutral").toLowerCase();
    indicator.className = `badge ${safe}`;
    indicator.textContent = safe;
  }

  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const prompt = (input?.value || "").trim();
    if (!prompt) return;

    addMessage("user", prompt, "you");
    input.value = "";

    try {
      const response = await fetch("/client/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          provider: (providerInput?.value || "mock").trim(),
          model: (modelInput?.value || "").trim() || undefined,
        }),
      });
      const payload = await response.json();

      if (payload.status === "ok") {
        addMessage("assistant", payload.reply || "No response text returned.", `assistant · ${payload.provider || "unknown"}`);
        setIndicator("ok");
        return;
      }
      if (payload.status === "challenge") {
        addMessage("assistant", payload.reply || "Prompt needs revision.", "policy challenge");
        setIndicator("challenge");
        return;
      }
      addMessage("assistant", payload.reply || payload.message || "Request denied by policy.", "policy denied");
      setIndicator("denied");
    } catch (err) {
      addMessage("assistant", `Connection error: ${err}`, "error");
      setIndicator("denied");
    }
  });
})();
