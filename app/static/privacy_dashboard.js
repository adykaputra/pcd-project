(function () {
  const resultSummary = document.getElementById("result-summary");
  const tokenInput = document.getElementById("admin-token");
  const datasetSelect = document.getElementById("benchmark-dataset");
  const pipelineScan = document.getElementById("pipeline-scan");
  const pipelinePolicy = document.getElementById("pipeline-policy");
  const pipelineDispatch = document.getElementById("pipeline-dispatch");
  const pipelineTrace = document.getElementById("pipeline-trace");
  const pipelineDetail = document.getElementById("pipeline-detail");
  const methodLeaderboard = document.getElementById("method-leaderboard");
  const adversarialSummary = document.getElementById("adversarial-summary");
  const vaultSummary = document.getElementById("vault-summary");
  const vivaSummary = document.getElementById("viva-summary");
  const vaultRetentionInput = document.getElementById("vault-retention-hours");
  const vaultPolicyInput = document.getElementById("vault-policy-hours");
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
    if (payload.risk_assessment?.policy_action) {
      details.push(`policy=${payload.risk_assessment.policy_action}`);
    }
    if (payload.tokenization?.token_counts) {
      const counts = payload.tokenization.token_counts;
      const totalTokens = Object.values(counts).reduce((acc, n) => acc + asNumber(n), 0);
      details.push(`pii_tokens=${totalTokens}`);
    }
    if (payload.dispatch_proof?.model_input_is_tokenized !== undefined) {
      details.push(`dispatch_tokenized=${payload.dispatch_proof.model_input_is_tokenized ? "yes" : "no"}`);
    }
    if (payload.comparison?.adaptive_summary?.core_pii_leak_rate !== undefined) {
      details.push(`adaptive_leak_rate=${payload.comparison.adaptive_summary.core_pii_leak_rate}`);
    }
    if (payload.comparison?.adaptive_summary?.avg_target_recall !== undefined) {
      details.push(`adaptive_recall=${payload.comparison.adaptive_summary.avg_target_recall}`);
    }
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
      const views = String(section.dataset.view || "prompt")
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

  function updatePipeline(payload) {
    if (!payload || typeof payload !== "object") return;
    const tokenization = payload.tokenization || {};
    const risk = payload.risk_assessment || {};
    const proof = payload.dispatch_proof || {};
    const tokenCounts = tokenization.token_counts || {};
    const totalPiiTokens = Object.values(tokenCounts).reduce((acc, n) => acc + asNumber(n), 0);

    if (pipelineScan) {
      pipelineScan.textContent = tokenization.applied
        ? `PII detected (${totalPiiTokens} token${totalPiiTokens === 1 ? "" : "s"})`
        : "No PII detected";
    }
    if (pipelinePolicy) {
      const riskScore = risk.risk_score !== undefined ? Number(risk.risk_score).toFixed(2) : "n/a";
      pipelinePolicy.textContent = `${String(risk.policy_action || "allow").toUpperCase()} (risk ${riskScore})`;
    }
    if (pipelineDispatch) {
      pipelineDispatch.textContent = proof.model_input_is_tokenized ? "Tokenized payload sent" : "Dispatch proof unavailable";
    }
    if (pipelineTrace) {
      pipelineTrace.textContent = proof.original_prompt_sha256 ? "Hash + audit trail recorded" : "No trace hash yet";
    }
    if (pipelineDetail) {
      pipelineDetail.textContent = proof.tokenized_prompt_preview
        ? `Latest tokenized preview: ${proof.tokenized_prompt_preview}`
        : "Run Generate to capture tokenized payload proof.";
    }
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
        trendChart.innerHTML = `<text x="20" y="28" fill="#5f6f89" font-size="13">No benchmark history yet. Run Benchmark to generate trend data.</text>`;
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
      <rect x="0" y="0" width="${width}" height="${height}" fill="#ffffff"></rect>
      <line x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}" stroke="#c7d5ea" stroke-width="1"></line>
      <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" stroke="#c7d5ea" stroke-width="1"></line>
      <path d="${leakPath}" fill="none" stroke="#0ea5e9" stroke-width="2.2"></path>
      <path d="${latencyPath}" fill="none" stroke="#6366f1" stroke-width="2.2"></path>
      ${dots}
      <text x="${padX}" y="${padY - 8}" fill="#5f6f89" font-size="12">Leak rate</text>
      <text x="${padX + 90}" y="${padY - 8}" fill="#5f6f89" font-size="12">Latency (ms)</text>
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

  function renderMethodLeaderboard(comparison) {
    if (!methodLeaderboard) return;
    const rows = comparison?.method_metrics;
    if (!Array.isArray(rows) || rows.length === 0) {
      methodLeaderboard.className = "leaderboard muted";
      methodLeaderboard.textContent = "Run Method Comparison to populate method ranking.";
      return;
    }

    methodLeaderboard.className = "leaderboard";
    methodLeaderboard.innerHTML = rows
      .slice(0, 5)
      .map(
        (row, idx) => `
          <div class="leaderboard-row">
            <strong>${idx + 1}. ${row.method_name}</strong>
            <span>score ${Number(row.composite_score ?? 0).toFixed(3)}</span>
            <span>recall ${Number(row.avg_target_recall ?? 0).toFixed(3)}</span>
            <span>leak ${Number(row.core_pii_leak_rate ?? 0).toFixed(3)}</span>
            <span>wins ${row.wins || 0}</span>
          </div>
        `
      )
      .join("");
  }

  function renderAdversarialSummary(adversarial) {
    if (!adversarialSummary) return;
    if (!adversarial || !adversarial.summary) {
      adversarialSummary.textContent = "Run Adversarial Stress to populate robustness metrics.";
      return;
    }
    const s = adversarial.summary;
    adversarialSummary.textContent =
      `dataset=${adversarial.dataset_version}, split=${adversarial.split}, cases=${adversarial.total_cases}, variants=${adversarial.total_variants}, baseline_leak=${s.baseline_core_leak_rate}, attacked_leak=${s.attacked_core_leak_rate}, recall_degradation_events=${s.recall_degradation_events}`;
  }

  function renderVaultSummary(payload) {
    if (!vaultSummary) return;
    const vault = payload?.vault || {};
    const retentionHours = payload?.retention_hours;
    if (vaultPolicyInput && retentionHours !== undefined) {
      vaultPolicyInput.value = String(retentionHours);
    }
    if (vault.entries === undefined) {
      vaultSummary.textContent = "Vault stats not loaded yet.";
      return;
    }
    const byType = Object.entries(vault.by_type || {})
      .map(([k, v]) => `${k}:${v}`)
      .join(", ");
    vaultSummary.textContent = `entries=${vault.entries}, oldest=${vault.oldest_entry_ts || "n/a"}, newest=${vault.newest_entry_ts || "n/a"}, by_type=[${byType || "none"}]`;
  }

  function renderVivaSummary(payload) {
    if (!vivaSummary) return;
    const viva = payload?.viva;
    if (!viva) {
      vivaSummary.className = "leaderboard muted";
      vivaSummary.textContent = "No viva artifact generated in this session.";
      return;
    }
    const files = viva.artifacts || {};
    const hashes = viva.hashes || {};
    vivaSummary.className = "leaderboard";
    vivaSummary.innerHTML = `
      <div class="leaderboard-row">
        <strong>Dataset ${viva.dataset_version || "n/a"}</strong>
        <span>Leak ${viva.baseline_leak_rate ?? "n/a"}</span>
        <span>Detection ${viva.baseline_detection_rate ?? "n/a"}</span>
        <span>Top ${viva.top_method || "n/a"}</span>
        <span>Git ${viva.git_commit || "n/a"}</span>
      </div>
      <div class="leaderboard-row">
        <strong>Artifacts</strong>
        <span>${files.json || "n/a"}</span>
        <span>${files.markdown || "n/a"}</span>
        <span>${files.leaderboard_csv || "n/a"}</span>
        <span>${files.adversarial_csv || "n/a"}</span>
      </div>
      <div class="leaderboard-row">
        <strong>SHA256</strong>
        <span>${hashes.json || "n/a"}</span>
        <span>${hashes.markdown || "n/a"}</span>
        <span>${hashes.leaderboard_csv || "n/a"}</span>
        <span>${hashes.adversarial_csv || "n/a"}</span>
      </div>
    `;
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
      showToast("Admin session refreshed.", "success");
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
      updatePipeline(response);
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

  document.getElementById("btn-comparison")?.addEventListener("click", async () => {
    try {
      const version = datasetSelect?.value || "v3";
      const response = await callApi(
        `/privacy/comparison?dataset_version=${encodeURIComponent(version)}&split=all&include_cases=0`,
        { auth: true }
      );
      setViewer("Method Comparison", response);
      renderMethodLeaderboard(response.comparison);
      showToast("Method comparison completed.", "success");
    } catch (err) {
      setViewer("Method Comparison Error", { status: "error", message: String(err) });
      showToast("Method comparison failed.", "error");
    }
  });

  document.getElementById("btn-adversarial")?.addEventListener("click", async () => {
    try {
      const version = datasetSelect?.value || "v3";
      const response = await callApi(
        `/privacy/adversarial?dataset_version=${encodeURIComponent(version)}&split=test&max_cases=20&max_variants=3&include_cases=0`,
        { auth: true }
      );
      setViewer("Adversarial Stress", response);
      renderAdversarialSummary(response.adversarial);
      showToast("Adversarial stress completed.", "success");
    } catch (err) {
      setViewer("Adversarial Stress Error", { status: "error", message: String(err) });
      showToast("Adversarial stress failed.", "error");
    }
  });

  document.getElementById("btn-vault-stats")?.addEventListener("click", async () => {
    try {
      const response = await callApi("/privacy/vault/stats", { auth: true });
      setViewer("Vault Stats", response);
      renderVaultSummary(response);
      showToast("Vault stats refreshed.", "success");
    } catch (err) {
      setViewer("Vault Stats Error", { status: "error", message: String(err) });
      showToast("Vault stats failed.", "error");
    }
  });

  document.getElementById("btn-vault-purge")?.addEventListener("click", async () => {
    try {
      const retentionHours = Number(vaultRetentionInput?.value || 168);
      const response = await callApi("/privacy/vault/purge", {
        method: "POST",
        auth: true,
        body: { retention_hours: retentionHours },
      });
      setViewer("Vault Purge", response);
      const statsResponse = await callApi("/privacy/vault/stats", { auth: true });
      renderVaultSummary(statsResponse);
      showToast("Vault purge completed.", "success");
    } catch (err) {
      setViewer("Vault Purge Error", { status: "error", message: String(err) });
      showToast("Vault purge failed.", "error");
    }
  });

  document.getElementById("btn-viva-export")?.addEventListener("click", async () => {
    try {
      const version = datasetSelect?.value || "v3";
      const response = await callApi("/privacy/viva/export", {
        method: "POST",
        auth: true,
        body: { dataset_version: version },
      });
      setViewer("Viva Export", response);
      renderVivaSummary(response);
      showToast("Viva pack exported.", "success");
    } catch (err) {
      setViewer("Viva Export Error", { status: "error", message: String(err) });
      showToast("Viva export failed.", "error");
    }
  });

  viewButtons.forEach((button) => {
    button.addEventListener("click", () => setActiveView(button.dataset.view || "prompt"));
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

  setActiveView("prompt");
  renderChartCenter(bootstrap.benchmark || {});
  refreshDatasetVersions();
  callApi("/privacy/vault/stats", { auth: true }).then(renderVaultSummary).catch(() => {});
  if (window.location.search.includes("token=")) {
    window.history.replaceState({}, document.title, window.location.pathname);
  }
})();
