(function () {
  const resultSummary = document.getElementById("result-summary");
  const tokenInput = document.getElementById("admin-token");
  const datasetSelect = document.getElementById("benchmark-dataset");
  const scenarioSelect = document.getElementById("comparison-scenario");
  const languageSelect = document.getElementById("comparison-language");
  const comparisonFilterContext = document.getElementById("comparison-filter-context");
  const pipelineScan = document.getElementById("pipeline-scan");
  const pipelinePolicy = document.getElementById("pipeline-policy");
  const pipelineDispatch = document.getElementById("pipeline-dispatch");
  const pipelineTrace = document.getElementById("pipeline-trace");
  const pipelineDetail = document.getElementById("pipeline-detail");
  const methodLeaderboard = document.getElementById("method-leaderboard");
  const comparisonTableBody = document.getElementById("comparison-table-body");
  const metricTopMethod = document.getElementById("metric-top-method");
  const metricTopScore = document.getElementById("metric-top-score");
  const metricTopF1 = document.getElementById("metric-top-f1");
  const metricAdversarialLeak = document.getElementById("metric-adversarial-leak");
  const runbookSummary = document.getElementById("runbook-summary");
  const adversarialSummary = document.getElementById("adversarial-summary");
  const vaultSummary = document.getElementById("vault-summary");
  const vivaSummary = document.getElementById("viva-summary");
  const vaultRetentionInput = document.getElementById("vault-retention-hours");
  const vaultPolicyInput = document.getElementById("vault-policy-hours");
  const qualityCards = document.getElementById("quality-cards");
  const policyBars = document.getElementById("policy-bars");
  const trendChart = document.getElementById("trend-chart");
  const liveTelemetryStatus = document.getElementById("live-telemetry-status");
  const evidenceSessionList = document.getElementById("evidence-session-list");
  const evidenceSessionTitle = document.getElementById("evidence-session-title");
  const evidenceSessionSubtitle = document.getElementById("evidence-session-subtitle");
  const evidenceSessionMessages = document.getElementById("evidence-session-messages");
  const evidenceRefreshButton = document.getElementById("btn-evidence-refresh");
  const toastNode = document.getElementById("toast");
  const viewButtons = Array.from(document.querySelectorAll(".menu-item[data-view]"));
  const sortableHeaders = Array.from(document.querySelectorAll("th.sortable[data-sort]"));
  const viewSections = Array.from(document.querySelectorAll(".view-section"));
  const bootstrap = window.__DASHBOARD_BOOTSTRAP__ || {};
  const logoutButton = document.getElementById("dashboard-logout");
  let comparisonRows = [];
  let comparisonSortKey = "composite_score";
  let comparisonSortDir = "desc";
  let comparisonDimensions = null;
  let evidenceThreads = Array.isArray(bootstrap.sanitizedThreads) ? bootstrap.sanitizedThreads.slice() : [];
  let activeEvidenceThreadKey = "";

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

  function renderQualityCards(live) {
    if (!qualityCards || !live) return;
    const totals = live.totals || {};
    const counts = live.policy_action_counts || {};
    const cards = [
      { label: "Live Requests (24h)", value: String(totals.total_requests ?? 0) },
      { label: "Allow Rate", value: `${(asNumber(totals.allow_rate) * 100).toFixed(1)}%` },
      { label: "Challenge Rate", value: `${(asNumber(totals.challenge_rate) * 100).toFixed(1)}%` },
      { label: "Block Count", value: String(counts.block ?? 0) },
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

  function renderPolicyBars(live) {
    if (!policyBars || !live) return;
    const counts = live.policy_action_counts || {};
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
        trendChart.innerHTML = `<text x="20" y="28" fill="#5f6f89" font-size="13">No live policy events yet. Send prompts to generate telemetry.</text>`;
      }
      return;
    }

    const points = [...history].reverse();
    const isLiveTimeline = Object.prototype.hasOwnProperty.call(points[0] || {}, "allow");
    const width = 760;
    const height = 210;
    const padX = 45;
    const padY = 26;
    const innerW = width - padX * 2;
    const innerH = height - padY * 2;

    if (isLiveTimeline) {
      const maxCount = Math.max(
        1,
        ...points.map((p) => Math.max(asNumber(p.allow), asNumber(p.challenge), asNumber(p.block)))
      );
      const projectX = (idx) => (points.length === 1 ? width / 2 : padX + (idx / (points.length - 1)) * innerW);
      const projectY = (value) => padY + (1 - asNumber(value) / maxCount) * innerH;
      const buildPath = (key) =>
        points
          .map((point, idx) => `${idx === 0 ? "M" : "L"} ${projectX(idx).toFixed(2)} ${projectY(point[key]).toFixed(2)}`)
          .join(" ");

      const allowPath = buildPath("allow");
      const challengePath = buildPath("challenge");
      const blockPath = buildPath("block");

      const dots = points
        .map((point, idx) => {
          const x = projectX(idx);
          const yAllow = projectY(point.allow);
          const yChallenge = projectY(point.challenge);
          const yBlock = projectY(point.block);
          return `
            <circle cx="${x.toFixed(2)}" cy="${yAllow.toFixed(2)}" r="2.8" fill="#10b981"><title>${point.ts}: allow ${point.allow}</title></circle>
            <circle cx="${x.toFixed(2)}" cy="${yChallenge.toFixed(2)}" r="2.8" fill="#f59e0b"><title>${point.ts}: challenge ${point.challenge}</title></circle>
            <circle cx="${x.toFixed(2)}" cy="${yBlock.toFixed(2)}" r="2.8" fill="#ef4444"><title>${point.ts}: block ${point.block}</title></circle>
          `;
        })
        .join("");

      trendChart.innerHTML = `
        <rect x="0" y="0" width="${width}" height="${height}" fill="#ffffff"></rect>
        <line x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}" stroke="#c7d5ea" stroke-width="1"></line>
        <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" stroke="#c7d5ea" stroke-width="1"></line>
        <path d="${allowPath}" fill="none" stroke="#10b981" stroke-width="2.1"></path>
        <path d="${challengePath}" fill="none" stroke="#f59e0b" stroke-width="2.1"></path>
        <path d="${blockPath}" fill="none" stroke="#ef4444" stroke-width="2.1"></path>
        ${dots}
        <text x="${padX}" y="${padY - 8}" fill="#5f6f89" font-size="12">Allow</text>
        <text x="${padX + 48}" y="${padY - 8}" fill="#5f6f89" font-size="12">Challenge</text>
        <text x="${padX + 130}" y="${padY - 8}" fill="#5f6f89" font-size="12">Block</text>
      `;
      return;
    }

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

  function renderLiveTelemetry(live) {
    if (!live) return;
    renderQualityCards(live);
    renderPolicyBars(live);
    renderTrendChart(Array.isArray(live.timeline) ? live.timeline : []);
    if (liveTelemetryStatus) {
      liveTelemetryStatus.textContent = `Live window: last ${live.window_hours || 24} hour(s). Last update ${live.generated_at || "n/a"}`;
    }
  }

  async function refreshLiveTelemetry() {
    try {
      const payload = await callApi("/audit/live?hours=24&bucket_minutes=60", { auth: true });
      renderLiveTelemetry(payload.live);
      return payload;
    } catch (err) {
      if (liveTelemetryStatus) {
        liveTelemetryStatus.textContent = `Live telemetry unavailable: ${String(err)}`;
      }
      return null;
    }
  }

  function renderMethodLeaderboard(comparison) {
    if (!methodLeaderboard) return;
    const rows = comparison?.method_metrics;
    if (!Array.isArray(rows) || rows.length === 0) {
      methodLeaderboard.className = "leaderboard muted";
      methodLeaderboard.textContent = "Run Method Comparison to populate method ranking.";
      if (comparisonTableBody) {
        comparisonTableBody.innerHTML = `<tr><td colspan="7" class="muted">Run Method Comparison to populate this table.</td></tr>`;
      }
      return;
    }

    comparisonRows = rows.slice();
    const top = comparisonRows[0];
    if (metricTopMethod) metricTopMethod.textContent = String(top.method_name || "n/a");
    if (metricTopScore) metricTopScore.textContent = String(top.composite_score ?? "n/a");
    if (metricTopF1) metricTopF1.textContent = String(top.micro_f1 ?? "n/a");

    methodLeaderboard.className = "leaderboard";
    methodLeaderboard.innerHTML = comparisonRows
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

    renderComparisonTable();
  }

  function renderComparisonTable() {
    if (comparisonTableBody) {
      const sorted = comparisonRows
        .slice()
        .sort((a, b) => {
          const av = a?.[comparisonSortKey];
          const bv = b?.[comparisonSortKey];
          const dir = comparisonSortDir === "asc" ? 1 : -1;
          if (comparisonSortKey === "method_name") {
            return String(av || "").localeCompare(String(bv || "")) * dir;
          }
          return (Number(av || 0) - Number(bv || 0)) * dir;
        });
      comparisonTableBody.innerHTML = sorted
        .slice(0, 8)
        .map(
          (row) => `
            <tr>
              <td>${row.method_name}</td>
              <td>${Number(row.composite_score ?? 0).toFixed(3)}</td>
              <td>${Number(row.avg_target_recall ?? 0).toFixed(3)}</td>
              <td>${Number(row.core_pii_leak_rate ?? 0).toFixed(3)}</td>
              <td>${Number(row.micro_f1 ?? 0).toFixed(3)}</td>
              <td>${Number(row.avg_latency_ms ?? 0).toFixed(2)}</td>
              <td>${row.wins || 0}</td>
            </tr>
          `
        )
        .join("");
    }
  }

  function updateSortIndicators() {
    sortableHeaders.forEach((header) => {
      const isActive = header.dataset.sort === comparisonSortKey;
      header.classList.toggle("active", isActive);
      if (isActive) {
        header.dataset.sortDir = comparisonSortDir;
      } else {
        delete header.dataset.sortDir;
      }
    });
  }

  function renderAdversarialSummary(adversarial) {
    if (!adversarialSummary) return;
    if (!adversarial || !adversarial.summary) {
      adversarialSummary.textContent = "Run Adversarial Stress to populate robustness metrics.";
      return;
    }
    const s = adversarial.summary;
    if (metricAdversarialLeak) {
      metricAdversarialLeak.textContent = String(s.attacked_core_leak_rate ?? "n/a");
    }
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

  function threadKey(thread) {
    return `${thread?.user_identity || "unknown"}::${thread?.session_id || "unknown"}`;
  }

  function renderEvidenceViewer(thread) {
    if (!evidenceSessionTitle || !evidenceSessionSubtitle || !evidenceSessionMessages) return;
    if (!thread) {
      evidenceSessionTitle.textContent = "Select a session";
      evidenceSessionSubtitle.textContent = "No session selected yet.";
      evidenceSessionMessages.innerHTML =
        `<p class="muted">Choose a session button on the left to open read-only redacted chat evidence.</p>`;
      return;
    }
    const displayName = thread.user_name || thread.user_identity || "unknown";
    evidenceSessionTitle.textContent = `${displayName} · Session ${thread.session_id || "unknown"}`;
    evidenceSessionSubtitle.textContent = `Read-only mode. Messages are redacted before storage and display.`;
    const messages = Array.isArray(thread.messages) ? thread.messages : [];
    if (messages.length === 0) {
      evidenceSessionMessages.innerHTML = `<p class="muted">No redacted messages captured for this session.</p>`;
      return;
    }
    evidenceSessionMessages.innerHTML = messages
      .map(
        (message) => `
          <div class="evidence-message">
            <div class="meta">${message.ts || "n/a"}${message.policy_action ? ` · ${message.policy_action}` : ""}</div>
            <code>${String(message.redacted_prompt || "n/a")
              .replaceAll("&", "&amp;")
              .replaceAll("<", "&lt;")
              .replaceAll(">", "&gt;")}</code>
          </div>
        `
      )
      .join("");
  }

  function renderEvidenceSessions() {
    if (!evidenceSessionList) return;
    if (!Array.isArray(evidenceThreads) || evidenceThreads.length === 0) {
      evidenceSessionList.innerHTML = `<p class="muted">No session evidence yet. Start a client chat first.</p>`;
      renderEvidenceViewer(null);
      return;
    }
    if (!activeEvidenceThreadKey) {
      activeEvidenceThreadKey = threadKey(evidenceThreads[0]);
    }
    evidenceSessionList.innerHTML = evidenceThreads
      .map((thread) => {
        const key = threadKey(thread);
        const active = key === activeEvidenceThreadKey ? " active" : "";
        const displayName = thread.user_name || thread.user_identity || "unknown";
        return `
          <button type="button" class="evidence-session-btn${active}" data-thread-key="${key}">
            <span class="title">${displayName}</span>
            <span class="meta">session ${thread.session_id || "unknown"} · ${thread.latest_ts || "n/a"}</span>
          </button>
        `;
      })
      .join("");
    const activeThread = evidenceThreads.find((thread) => threadKey(thread) === activeEvidenceThreadKey) || evidenceThreads[0];
    if (activeThread) {
      activeEvidenceThreadKey = threadKey(activeThread);
      renderEvidenceViewer(activeThread);
    }
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

  async function refreshEvidenceSessions() {
    try {
      const payload = await callApi("/audit/evidence?limit=400", { auth: true });
      evidenceThreads = Array.isArray(payload?.sanitized_threads) ? payload.sanitized_threads : [];
      const stillExists = evidenceThreads.some((thread) => threadKey(thread) === activeEvidenceThreadKey);
      if (!stillExists) {
        activeEvidenceThreadKey = "";
      }
      renderEvidenceSessions();
      return payload;
    } catch (err) {
      renderEvidenceSessions();
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

  function populateFilterSelect(selectNode, allLabel, values, counts, preferredValue = "all") {
    if (!selectNode) return;
    const safeValues = Array.isArray(values) ? values : [];
    const current = selectNode.value || preferredValue || "all";
    selectNode.innerHTML = "";
    const allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = `${allLabel} (${Object.values(counts || {}).reduce((acc, n) => acc + asNumber(n), 0) || 0})`;
    selectNode.appendChild(allOption);
    safeValues.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = `${value} (${asNumber((counts || {})[value])})`;
      selectNode.appendChild(option);
    });
    const desired = safeValues.includes(current) ? current : "all";
    selectNode.value = desired;
  }

  function renderComparisonFilterContext(dimensions) {
    if (!comparisonFilterContext) return;
    if (!dimensions) {
      comparisonFilterContext.textContent = "Filter options are loading from the selected dataset.";
      return;
    }
    const scenarioCount = Array.isArray(dimensions.scenarios) ? dimensions.scenarios.length : 0;
    const languageCount = Array.isArray(dimensions.languages) ? dimensions.languages.length : 0;
    comparisonFilterContext.textContent =
      `Dataset ${dimensions.dataset_version || "n/a"} has ${dimensions.total_cases || 0} cases, ${scenarioCount} scenario type(s), and ${languageCount} language profile(s).`;
  }

  async function refreshComparisonOptions() {
    if (!datasetSelect) return null;
    const version = datasetSelect.value || "v3";
    const response = await callApi(
      `/privacy/comparison/options?dataset_version=${encodeURIComponent(version)}&split=all`,
      { auth: true }
    );
    const dimensions = response?.dimensions || null;
    comparisonDimensions = dimensions;
    if (dimensions) {
      populateFilterSelect(
        scenarioSelect,
        "all scenarios",
        dimensions.scenarios || [],
        dimensions.scenario_counts || {},
        "all"
      );
      populateFilterSelect(
        languageSelect,
        "all languages",
        dimensions.languages || [],
        dimensions.language_counts || {},
        "all"
      );
    }
    renderComparisonFilterContext(dimensions);
    return dimensions;
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
      await refreshLiveTelemetry();
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
      await refreshHistory();
      await refreshLiveTelemetry();
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
      await refreshLiveTelemetry();
      showToast("Audit summary refreshed.", "success");
    } catch (err) {
      setViewer("Audit Summary Error", { status: "error", message: String(err) });
      showToast("Audit summary failed.", "error");
    }
  });

  function getComparisonQuery() {
    const version = datasetSelect?.value || "v3";
    const scenario = scenarioSelect?.value || "all";
    const language = languageSelect?.value || "all";
    return `dataset_version=${encodeURIComponent(version)}&split=all&include_cases=0&scenario=${encodeURIComponent(
      scenario
    )}&language=${encodeURIComponent(language)}`;
  }

  async function runMethodComparison() {
    const response = await callApi(`/privacy/comparison?${getComparisonQuery()}`, { auth: true });
    setViewer("Method Comparison", response);
    renderMethodLeaderboard(response.comparison);
    const scenarioFilter = response?.comparison?.filters?.scenario || "all";
    const languageFilter = response?.comparison?.filters?.language || "all";
    if (comparisonFilterContext) {
      comparisonFilterContext.textContent =
        `Comparison scope: ${response?.comparison?.total_cases || 0} case(s), scenario=${scenarioFilter}, language=${languageFilter}.`;
    }
    return response;
  }

  document.getElementById("btn-comparison")?.addEventListener("click", async () => {
    try {
      await runMethodComparison();
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

  document.getElementById("btn-runbook")?.addEventListener("click", async () => {
    const runbookButton = document.getElementById("btn-runbook");
    if (runbookButton) {
      runbookButton.disabled = true;
      runbookButton.textContent = "Running...";
    }
    if (runbookSummary) {
      runbookSummary.textContent = "Running benchmark -> comparison -> adversarial -> viva export...";
    }
    try {
      const version = datasetSelect?.value || "v3";
      const benchmark = await callApi(
        `/privacy/benchmark?dataset_version=${encodeURIComponent(version)}&split=all&persist=1`,
        { auth: true }
      );
      updateMetricsFromBenchmark(benchmark.benchmark);

      const comparison = await runMethodComparison();
      const adversarial = await callApi(
        `/privacy/adversarial?dataset_version=${encodeURIComponent(version)}&split=test&max_cases=20&max_variants=3&include_cases=0`,
        { auth: true }
      );
      renderAdversarialSummary(adversarial.adversarial);

      const viva = await callApi("/privacy/viva/export", {
        method: "POST",
        auth: true,
        body: { dataset_version: version },
      });
      renderVivaSummary(viva);
      await refreshHistory();
      await refreshLiveTelemetry();
      if (runbookSummary) {
        runbookSummary.textContent =
          `Runbook complete: leak=${benchmark.benchmark.metrics.core_pii_leak_rate}, top_method=${
            comparison.comparison.method_metrics?.[0]?.method_name || "n/a"
          }, adversarial_leak=${adversarial.adversarial.summary?.attacked_core_leak_rate ?? "n/a"}`;
      }
      setViewer("Runbook Complete", {
        status: "ok",
        message: "Benchmark, comparison, adversarial stress, and viva export completed.",
        benchmark: benchmark.benchmark,
        comparison: comparison.comparison,
      });
      showToast("Demo runbook completed.", "success");
    } catch (err) {
      setViewer("Runbook Error", { status: "error", message: String(err) });
      if (runbookSummary) {
        runbookSummary.textContent = `Runbook failed: ${String(err)}`;
      }
      showToast("Demo runbook failed.", "error");
    } finally {
      if (runbookButton) {
        runbookButton.disabled = false;
        runbookButton.textContent = "Run Demo Runbook";
      }
    }
  });

  sortableHeaders.forEach((header) => {
    header.addEventListener("click", () => {
      const key = header.dataset.sort;
      if (!key) return;
      if (comparisonSortKey === key) {
        comparisonSortDir = comparisonSortDir === "asc" ? "desc" : "asc";
      } else {
        comparisonSortKey = key;
        comparisonSortDir = key === "method_name" ? "asc" : "desc";
      }
      renderComparisonTable();
      updateSortIndicators();
    });
  });

  document.getElementById("btn-live-refresh")?.addEventListener("click", async () => {
    const payload = await refreshLiveTelemetry();
    if (payload) {
      showToast("Live telemetry refreshed.", "success");
    } else {
      showToast("Live telemetry refresh failed.", "error");
    }
  });

  evidenceSessionList?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest(".evidence-session-btn[data-thread-key]") : null;
    if (!target) return;
    const key = target.getAttribute("data-thread-key") || "";
    if (!key) return;
    activeEvidenceThreadKey = key;
    renderEvidenceSessions();
  });

  evidenceRefreshButton?.addEventListener("click", async () => {
    const payload = await refreshEvidenceSessions();
    if (payload) {
      showToast("Evidence sessions refreshed.", "success");
    } else {
      showToast("Evidence refresh failed.", "error");
    }
  });

  datasetSelect?.addEventListener("change", async () => {
    try {
      await refreshComparisonOptions();
      await runMethodComparison();
      showToast("Dataset scope refreshed.", "success");
    } catch (err) {
      setViewer("Dataset Refresh Error", { status: "error", message: String(err) });
      showToast("Dataset refresh failed.", "error");
    }
  });

  scenarioSelect?.addEventListener("change", async () => {
    try {
      await runMethodComparison();
    } catch (err) {
      setViewer("Scenario Filter Error", { status: "error", message: String(err) });
    }
  });

  languageSelect?.addEventListener("change", async () => {
    try {
      await runMethodComparison();
    } catch (err) {
      setViewer("Language Filter Error", { status: "error", message: String(err) });
    }
  });

  viewButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const nextView = button.dataset.view || "prompt";
      setActiveView(nextView);
      if (nextView === "evidence") {
        await refreshEvidenceSessions();
      }
    });
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

  setActiveView("proof");
  updateSortIndicators();
  refreshLiveTelemetry().catch(() => {});
  refreshDatasetVersions()
    .then(() => refreshComparisonOptions())
    .catch(() => {});
  callApi("/privacy/vault/stats", { auth: true }).then(renderVaultSummary).catch(() => {});
  refreshEvidenceSessions().catch(() => {
    renderEvidenceSessions();
  });
  window.setInterval(() => {
    refreshLiveTelemetry().catch(() => {});
  }, 30000);
  if (window.location.search.includes("token=")) {
    window.history.replaceState({}, document.title, window.location.pathname);
  }
})();
