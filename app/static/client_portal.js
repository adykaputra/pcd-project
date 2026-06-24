(function () {
  const form = document.getElementById("admin-login-form");
  const errorNode = document.getElementById("admin-error");
  const submitButton = form?.querySelector("button[type='submit']");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (errorNode) errorNode.textContent = "";
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Signing in...";
    }
    const password = document.getElementById("admin-password")?.value || "";
    try {
      const response = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.token) {
        throw new Error(payload?.message || "Login failed");
      }
      window.location.href = `/audit/dashboard?token=${encodeURIComponent(payload.token)}`;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (errorNode) errorNode.textContent = message;
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = "Open Admin Dashboard";
      }
    }
  });
})();
