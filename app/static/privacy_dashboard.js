(function () {
  const resultSummary = document.getElementById("result-summary");
  const tokenInput = document.getElementById("admin-token");
  const datasetSelect = document.getElementById("benchmark-dataset");
  const qualityCards = document.getElementById("quality-cards");
  const policyBars = document.getElementById("policy-bars");
  const trendChart = document.getElementById("trend-chart");
  const toastNode = document.getElementById("toast");
  const viewButtons = Array.from(document.querySelectorAll(".menu-item[data-view]"));
  const viewSections = Array.from(document.querySelectorAll(".view-section"));
  const bootstrap = window.__DASHBOARD_BOOTSTRAP__ || {};
  const logoutButton = document.getElementById("dashboard-logout");

  function setViewer(title, payload) {
    if (!resultSummary) return;
    if (typeof payload === "string") {
      resultSummary.textContent = `${title}: ${payload}`;
      return;
    }
    if (!payload || typeof payload !== "object") {
      resultSummary.textContent = `${title}: completed.`;
      return;
    }
    const status = payload.status ? `Status: ${payload.status}. ` : "";
    const message = payload.message ? `${payload.message}. ` : "";
    const details = [];
    if (payload.summary?.total_blocked_last_24h !== undefined) {
      details.push(`blocked_last_24h=${payload.summary.total_blocked_last_24h}`);
    }
    if (payload.benchmark?.metrics?.core_pii_leak_rate !== undefined) {
      details.push(`leak_rate=${payload.benchmark.metrics.core_pii_leak_rate}`);
    }
    if (payload.calibration?.recommended_challenge_threshold !== undefined) {
      details.push(`challenge_threshold=${payload.calibration.recommended_challenge_threshold}`);
    }
    resultSummary.textContent = `${title}: ${status}${message}${details.length ? `(${details.join(", ")})` : ""}`.trim();
  }

  function showToast(message, type = "success") {
    if (!toastNode) return;
    toastNode.textContent = message;
    toastNode.className = `toast show ${type}`;
    window.clearTimeout(showToast._timer);
    showToast._timer = window.setTimeout(() => {
      toastNode.className = "toast";
    }, 2000);
  }

  function setActiveView(nextView) {
    viewButtons.forEach((button) => {
      button.classList.toggle("active", button.dataset.view === nextView);
    });
    viewSections.forEach((section) => {
      const views = String(section.dataset.view || "dashboard")
        .split(",")
        .map((item) => item.trim());
      section.hidden = !(views.includes(nextView) || views.includes("all"));
    });
  }

  function getToken() {
    return (tokenInput?.value || "").trim();
  }

  async function callApi(path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (options.auth) {
      const token = getToken();
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
    }

    const response = await fetch(path, {
      method: options.method || "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch (err) {
      payload = { status: "error", message: `Failed to parse JSON: ${err}` };
    }
    if (!response.ok) {
      const message = payload?.message || `Request failed (${response.status})`;
      throw new Error(message);
    }
    return payload;
  }

  function updateMetricsFromBenchmark(benchmarkPayload) {
    const metrics = benchmarkPayload?.benchmark?.metrics || benchmarkPayload?.metrics || benchmarkPayload?.overall?.metrics;
    if (!metrics) return;
    const datasetNode = document.getElementById("metric-dataset");
    const leakNode = document.getElementById("metric-leak");
    const detectionNode = document.getElementById("metric-detection");
    if (datasetNode) datasetNode.textContent = metrics.dataset_version || "n/a";
    if (leakNode) leakNode.textContent = String(metrics.core_pii_leak_rate ?? "n/a");
    if (detectionNode) detectionNode.textContent = String(metrics.pii_detection_rate ?? "n/a");
  }

  function asNumber(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function extractMetrics(payload) {
    return payload?.benchmark?.metrics || payload?.metrics || payload?.overall?.metrics || null;
  }

  function renderQualityCards(metrics) {
    if (!qualityCards || !metrics) return;
    const leakPct = (asNumber(metrics.core_pii_leak_rate) * 100).toFixed(1);
    const utilityPct = (asNumber(metrics.avg_utility_score, 1) * 100).toFixed(1);
    const detectionPct = (asNumber(metrics.pii_detection_rate) * 100).toFixed(1);
    const accuracyPct = (asNumber(metrics.expected_action_accuracy) * 100).toFixed(1);
    const cards = [
      { label: "Leak Rate", value: `${leakPct}%` },
      { label: "Detection", value: `${detectionPct}%` },
      { label: "Utility", value: `${utilityPct}%` },
      { label: "Policy Accuracy", value: `${accuracyPct}%` },
    ];
    qualityCards.innerHTML = cards
      .map(
        (entry) => `
          <div class="quality-item">
            <span class="label">${entry.label}</span>
            <span class="value">${entry.value}</span>
          </div>
        `
      )
      .join("");
  }

  function renderPolicyBars(metrics) {
    if (!policyBars || !metrics) return;
    const counts = metrics.policy_action_counts || {};
    const allow = asNumber(counts.allow);
    const challenge = asNumber(counts.challenge);
    const block = asNumber(counts.block);
    const total = Math.max(allow + challenge + block, 1);
    const rows = [
      { key: "allow", label: "allow", value: allow },
      { key: "challenge", label: "challenge", value: challenge },
      { key: "block", label: "block", value: block },
    ];
    policyBars.innerHTML = rows
      .map((row) => {
        const width = ((row.value / total) * 100).toFixed(1);
        return `
          <div class="bar-row">
            <span class="bar-label">${row.label}</span>
            <div class="bar-track"><div class="bar-fill ${row.key}" style="width:${width}%"></div></div>
            <span class="bar-value">${row.value}</span>
          </div>
        `;
      })
      .join("");
  }

  function renderTrendChart(history) {
    if (!trendChart || !Array.isArray(history) || history.length === 0) {
      if (trendChart) {
        trendChart.innerHTML = `<text x="20" y="28" fill="#9cadcf" font-size="13">No benchmark history yet. Run Benchmark to generate trend data.</text>`;
      }
      return;
    }

    const points = [...history].reverse();
    const width = 760;
    const height = 210;
    const padX = 45;
    const padY = 26;
    const innerW = width - padX * 2;
    const innerH = height - padY * 2;

    const maxLeak = Math.max(...points.map((p) => asNumber(p.leak_rate)));
    const maxLatency = Math.max(...points.map((p) => asNumber(p.latency_ms)));
    const leakDenom = Math.max(maxLeak, 0.001);
    const latencyDenom = Math.max(maxLatency, 1);

    const projectX = (idx) => (points.length === 1 ? width / 2 : padX + (idx / (points.length - 1)) * innerW);
    const projectLeakY = (value) => padY + (1 - asNumber(value) / leakDenom) * innerH;
    const projectLatencyY = (value) => padY + (1 - asNumber(value) / latencyDenom) * innerH;

    const leakPath = points
      .map((point, idx) => `${idx === 0 ? "M" : "L"} ${projectX(idx).toFixed(2)} ${projectLeakY(point.leak_rate).toFixed(2)}`)
      .join(" ");
    const latencyPath = points
      .map((point, idx) => `${idx === 0 ? "M" : "L"} ${projectX(idx).toFixed(2)} ${projectLatencyY(point.latency_ms).toFixed(2)}`)
      .join(" ");

    const dots = points
      .map((point, idx) => {
        const x = projectX(idx);
        const yLeak = projectLeakY(point.leak_rate);
        const yLatency = projectLatencyY(point.latency_ms);
        return `
          <circle cx="${x.toFixed(2)}" cy="${yLeak.toFixed(2)}" r="3" fill="#22d3ee">
            <title>${point.ts}: leak ${asNumber(point.leak_rate).toFixed(3)}</title>
          </circle>
          <circle cx="${x.toFixed(2)}" cy="${yLatency.toFixed(2)}" r="2.8" fill="#a78bfa">
            <title>${point.ts}: latency ${asNumber(point.latency_ms).toFixed(1)} ms</title>
          </circle>
        `;
      })
      .join("");

    trendChart.innerHTML = `
      <rect x="0" y="0" width="${width}" height="${height}" fill="#0a1126"></rect>
      <line x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}" stroke="#2d3b63" stroke-width="1"></line>
      <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" stroke="#2d3b63" stroke-width="1"></line>
      <path d="${leakPath}" fill="none" stroke="#22d3ee" stroke-width="2.2"></path>
      <path d="${latencyPath}" fill="none" stroke="#a78bfa" stroke-width="2.2"></path>
      ${dots}
      <text x="${padX}" y="${padY - 8}" fill="#9cadcf" font-size="12">Leak rate</text>
      <text x="${padX + 90}" y="${padY - 8}" fill="#9cadcf" font-size="12">Latency (ms)</text>
    `;
  }

  function renderChartCenter(payload, historyOverride) {
    const metrics = extractMetrics(payload);
    if (metrics) {
      renderQualityCards(metrics);
      renderPolicyBars(metrics);
    }
    const history = Array.isArray(historyOverride)
      ? historyOverride
      : Array.isArray(payload?.history)
        ? payload.history
        : Array.isArray(bootstrap.benchmarkHistory)
          ? bootstrap.benchmarkHistory
          : [];
    renderTrendChart(history);
  }

  async function refreshHistory() {
    try {
      const payload = await callApi("/privacy/benchmark/history?limit=20", { auth: true });
      renderTrendChart(payload.history || []);
      return payload;
    } catch (err) {
      return null;
    }
  }

  async function refreshDatasetVersions() {
    try {
      const payload = await callApi("/privacy/benchmark/datasets", { auth: true });
      const versions = payload.versions || [];
      if (!datasetSelect) return;
      const current = datasetSelect.value;
      datasetSelect.innerHTML = "";
      versions.forEach((version) => {
        const option = document.createElement("option");
        option.value = version;
        option.textContent = version;
        datasetSelect.appendChild(option);
      });
      if (versions.includes(current)) datasetSelect.value = current;
    } catch (err) {
      // Silent if no token yet; shown explicitly when user triggers action.
    }
  }

  document.getElementById("login-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = document.getElementById("login-password").value;
    try {
      const payload = await callApi("/login", {
        method: "POST",
        body: { password },
      });
      if (tokenInput) tokenInput.value = payload.token || "";
      setViewer("Login Success", payload);
      showToast("Admin token acquired.", "success");
      await refreshDatasetVersions();
    } catch (err) {
      setViewer("Login Error", { status: "error", message: String(err) });
      showToast("Login failed.", "error");
    }
  });

  document.getElementById("generate-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      prompt: document.getElementById("generate-prompt").value,
      provider: document.getElementById("generate-provider").value || "mock",
    };
    const model = document.getElementById("generate-model").value;
    if (model) payload.model = model;
    const challengeThreshold = document.getElementById("generate-challenge").value;
    const blockThreshold = document.getElementById("generate-block").value;
    if (challengeThreshold) payload.policy_challenge_threshold = Number(challengeThreshold);
    if (blockThreshold) payload.policy_block_threshold = Number(blockThreshold);

    try {
      const response = await callApi("/generate", { method: "POST", body: payload });
      setViewer("Generate Result", response);
      renderChartCenter(response);
      showToast("Generate request completed.", "success");
    } catch (err) {
      setViewer("Generate Error", { status: "error", message: String(err) });
      showToast("Generate request failed.", "error");
    }
  });

  document.getElementById("btn-benchmark")?.addEventListener("click", async () => {
    try {
      const version = datasetSelect?.value || "v1";
      const response = await callApi(`/privacy/benchmark?dataset_version=${encodeURIComponent(version)}&split=all&persist=1`, { auth: true });
      updateMetricsFromBenchmark(response.benchmark);
      setViewer("Benchmark Result", response);
      renderChartCenter(response.benchmark);
      await refreshHistory();
      showToast("Benchmark run finished.", "success");
    } catch (err) {
      setViewer("Benchmark Error", { status: "error", message: String(err) });
      showToast("Benchmark failed.", "error");
    }
  });

  document.getElementById("btn-summary")?.addEventListener("click", async () => {
    try {
      const response = await callApi("/audit/summary?hours=24", { auth: true });
      setViewer("Audit Summary", response);
      renderChartCenter(response);
      showToast("Audit summary refreshed.", "success");
    } catch (err) {
      setViewer("Audit Summary Error", { status: "error", message: String(err) });
      showToast("Audit summary failed.", "error");
    }
  });

  viewButtons.forEach((button) => {
    button.addEventListener("click", () => setActiveView(button.dataset.view || "dashboard"));
  });

  logoutButton?.addEventListener("click", async (event) => {
    event.preventDefault();
    try {
      await fetch("/logout", { method: "POST", headers: { "Content-Type": "application/json" } });
    } catch {
      // ignore logout transport errors
    }
    window.location.replace("/");
  });

  setActiveView("dashboard");
  renderChartCenter(bootstrap.benchmark || {});
  if (window.location.search.includes("token=")) {
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  if (getToken()) {
    refreshDatasetVersions();
  }
})();
