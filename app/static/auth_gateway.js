(function () {
  const loginForm = document.getElementById("login-form");
  const signupForm = document.getElementById("signup-form");
  const switchModeButton = document.getElementById("switch-mode");
  const switchCopy = document.getElementById("switch-copy");
  const modeTitle = document.getElementById("auth-mode-title");
  const modeSubtitle = document.getElementById("auth-mode-subtitle");
  const loginError = document.getElementById("login-error");
  const signupError = document.getElementById("signup-error");
  const googleMessage = document.getElementById("google-message");
  const googleButton = document.getElementById("google-signin");
  const banner = document.getElementById("auth-banner");
  const bootstrap = window.__AUTH_BOOTSTRAP__ || {};
  let currentMode = "login";

  if (!loginForm || !signupForm) {
    return;
  }

  function toggleMode(mode) {
    currentMode = mode === "signup" ? "signup" : "login";
    const loginActive = currentMode === "login";
    const signupActive = !loginActive;
    loginForm.classList.toggle("active", loginActive);
    signupForm.classList.toggle("active", signupActive);
    if (loginError) loginError.textContent = "";
    if (signupError) signupError.textContent = "";

    if (modeTitle) modeTitle.textContent = loginActive ? "Welcome Back" : "Create Account";
    if (modeSubtitle) {
      modeSubtitle.textContent = loginActive
        ? "Sign in to access your privacy firewall workspace."
        : "Register once, then sign in to use your protected AI workspace.";
    }
    if (switchCopy) switchCopy.textContent = loginActive ? "Don't have an account?" : "Already have an account?";
    if (switchModeButton) switchModeButton.textContent = loginActive ? "Create Account" : "Back to Sign In";
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

  switchModeButton?.addEventListener("click", () => {
    toggleMode(currentMode === "login" ? "signup" : "login");
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (loginError) loginError.textContent = "";
    const email = document.getElementById("login-email")?.value?.trim() || "";
    const password = document.getElementById("login-password")?.value || "";

    try {
      const payload = await requestJson("/login", { email, password });
      window.location.replace(payload.redirect_url || "/");
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
      toggleMode("login");
      const loginEmail = document.getElementById("login-email");
      const loginPassword = document.getElementById("login-password");
      if (loginEmail) loginEmail.value = email;
      if (loginPassword) loginPassword.value = password;
      if (loginError) loginError.textContent = "Account created. Sign in to continue.";
    } catch (err) {
      if (signupError) signupError.textContent = err instanceof Error ? err.message : String(err);
    }
  });

  const initialError = String(bootstrap.authError || "");
  const initialMessage = String(bootstrap.authMessage || "");
  if (banner && (initialError || initialMessage)) {
    banner.hidden = false;
    banner.textContent = initialError || initialMessage;
    banner.classList.toggle("error", Boolean(initialError));
  }

  googleButton?.addEventListener("click", () => {
    if (googleMessage) {
      googleMessage.textContent = "Redirecting to Google...";
    }
    window.location.href = "/auth/google/start";
  });

  toggleMode("login");
})();
