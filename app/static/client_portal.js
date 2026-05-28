(function () {
  const form = document.getElementById("admin-login-form");
  const errorNode = document.getElementById("admin-error");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (errorNode) errorNode.textContent = "";
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
      if (errorNode) errorNode.textContent = String(err);
    }
  });
})();
