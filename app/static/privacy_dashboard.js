(function () {
  const viewer = document.getElementById("response-viewer");
  const tokenInput = document.getElementById("admin-token");
  const datasetSelect = document.getElementById("benchmark-dataset");
  const splitSelect = document.getElementById("benchmark-split");
  const qualityCards = document.getElementById("quality-cards");
  const policyBars = document.getElementById("policy-bars");
  const trendChart = document.getElementById("trend-chart");
  const bootstrap = window.__DASHBOARD_BOOTSTRAP__ || {};

  function setViewer(title, payload) {
    const body = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
    viewer.textContent = `${title}\n${"=".repeat(title.length)}\n${body}`;
  }

  function getToken() {
    return (tokenInput?.value || "").trim();
  }

  async function callApi(path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (options.auth) {
      const token = getToken();
      if (!token) {
        throw new Error("Admin token missing. Login first or paste token in sidebar.");
      }
      headers.Authorization = `Bearer ${token}`;
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

  function renderHistoryRows(history) {
    const tbody = document.getElementById("history-body");
    if (!tbody || !Array.isArray(history)) return;
    tbody.innerHTML = "";
    for (const row of history) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.ts || "n/a"}</td>
        <td>${row.dataset_version || "n/a"}</td>
        <td>${row.dataset_split || "n/a"}</td>
        <td>${row.leak_rate ?? "n/a"}</td>
        <td>${row.utility_score ?? "n/a"}</td>
        <td>${row.latency_ms ?? "n/a"}</td>
        <td>${row.allow_count ?? 0}/${row.challenge_count ?? 0}/${row.block_count ?? 0}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  async function refreshHistory() {
    try {
      const payload = await callApi("/privacy/benchmark/history?limit=20", { auth: true });
      renderHistoryRows(payload.history || []);
      renderTrendChart(payload.history || []);
      setViewer("Benchmark History", payload);
    } catch (err) {
      setViewer("History Error", { status: "error", message: String(err) });
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
      await refreshDatasetVersions();
    } catch (err) {
      setViewer("Login Error", { status: "error", message: String(err) });
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
    } catch (err) {
      setViewer("Generate Error", { status: "error", message: String(err) });
    }
  });

  document.getElementById("detokenize-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = document.getElementById("detokenize-text").value;
    try {
      const response = await callApi("/detokenize", {
        method: "POST",
        body: { text },
        auth: true,
      });
      setViewer("Detokenize Result", response);
    } catch (err) {
      setViewer("Detokenize Error", { status: "error", message: String(err) });
    }
  });

  document.getElementById("btn-benchmark")?.addEventListener("click", async () => {
    try {
      const version = datasetSelect?.value || "v1";
      const split = splitSelect?.value || "all";
      const response = await callApi(`/privacy/benchmark?dataset_version=${encodeURIComponent(version)}&split=${encodeURIComponent(split)}&persist=1`, { auth: true });
      updateMetricsFromBenchmark(response.benchmark);
      setViewer("Benchmark Result", response);
      renderChartCenter(response.benchmark);
      await refreshHistory();
    } catch (err) {
      setViewer("Benchmark Error", { status: "error", message: String(err) });
    }
  });

  document.getElementById("btn-cross-split")?.addEventListener("click", async () => {
    try {
      const version = datasetSelect?.value || "v1";
      const response = await callApi(`/privacy/benchmark?dataset_version=${encodeURIComponent(version)}&mode=cross_split&persist=0`, { auth: true });
      updateMetricsFromBenchmark(response.benchmark);
      setViewer("Cross-Split Benchmark", response);
      renderChartCenter(response.benchmark);
    } catch (err) {
      setViewer("Cross-Split Error", { status: "error", message: String(err) });
    }
  });

  document.getElementById("btn-calibrate")?.addEventListener("click", async () => {
    try {
      const version = datasetSelect?.value || "v1";
      const split = splitSelect?.value || "validation";
      const response = await callApi(`/privacy/calibrate?dataset_version=${encodeURIComponent(version)}&split=${encodeURIComponent(split)}`, { auth: true });
      setViewer("Calibration Result", response);
      renderChartCenter(response);
    } catch (err) {
      setViewer("Calibration Error", { status: "error", message: String(err) });
    }
  });

  document.getElementById("btn-autotune")?.addEventListener("click", async () => {
    try {
      const response = await callApi("/privacy/autotune?hours=168&min_samples=10", { auth: true });
      setViewer("Autotune Recommendation", response);
      renderChartCenter(response);
    } catch (err) {
      setViewer("Autotune Error", { status: "error", message: String(err) });
    }
  });

  document.getElementById("btn-history")?.addEventListener("click", refreshHistory);

  document.getElementById("btn-summary")?.addEventListener("click", async () => {
    try {
      const response = await callApi("/audit/summary?hours=24", { auth: true });
      setViewer("Audit Summary", response);
      renderChartCenter(response);
    } catch (err) {
      setViewer("Audit Summary Error", { status: "error", message: String(err) });
    }
  });

  renderChartCenter(bootstrap.benchmark || {});

  if (getToken()) {
    refreshDatasetVersions();
  }
})();
