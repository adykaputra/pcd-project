(function () {
  const loginTab = document.getElementById("tab-login");
  const signupTab = document.getElementById("tab-signup");
  const loginForm = document.getElementById("login-form");
  const signupForm = document.getElementById("signup-form");
  const loginError = document.getElementById("login-error");
  const signupError = document.getElementById("signup-error");
  const googleMessage = document.getElementById("google-message");
  const googleButton = document.getElementById("google-signin");

  if (!loginTab || !signupTab || !loginForm || !signupForm) {
    return;
  }

  function toggleTab(mode) {
    const loginActive = mode === "login";
    loginTab.classList.toggle("active", loginActive);
    signupTab.classList.toggle("active", !loginActive);
    loginForm.classList.toggle("active", loginActive);
    signupForm.classList.toggle("active", !loginActive);
    if (loginError) loginError.textContent = "";
    if (signupError) signupError.textContent = "";
  }

  async function requestJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.message || "Request failed");
    }
    return body;
  }

  loginTab.addEventListener("click", () => toggleTab("login"));
  signupTab.addEventListener("click", () => toggleTab("signup"));

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (loginError) loginError.textContent = "";
    const email = document.getElementById("login-email")?.value?.trim() || "";
    const password = document.getElementById("login-password")?.value || "";

    try {
      const payload = await requestJson("/login", { email, password });
      window.location.href = payload.redirect_url || "/";
    } catch (err) {
      if (loginError) loginError.textContent = err instanceof Error ? err.message : String(err);
    }
  });

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (signupError) signupError.textContent = "";
    const name = document.getElementById("signup-name")?.value?.trim() || "";
    const email = document.getElementById("signup-email")?.value?.trim() || "";
    const password = document.getElementById("signup-password")?.value || "";

    try {
      await requestJson("/signup", { name, email, password });
      toggleTab("login");
      const loginEmail = document.getElementById("login-email");
      const loginPassword = document.getElementById("login-password");
      if (loginEmail) loginEmail.value = email;
      if (loginPassword) loginPassword.value = password;
      if (loginError) loginError.textContent = "Account created. Sign in to continue.";
    } catch (err) {
      if (signupError) signupError.textContent = err instanceof Error ? err.message : String(err);
    }
  });

  googleButton?.addEventListener("click", async () => {
    if (googleMessage) googleMessage.textContent = "";
    try {
      const response = await fetch("/auth/google/start");
      const payload = await response.json();
      const msg = payload?.message || "Google Sign-In is not configured yet.";
      if (googleMessage) googleMessage.textContent = msg;
    } catch (err) {
      if (googleMessage) googleMessage.textContent = String(err);
    }
  });
})();
