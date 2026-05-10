"""Simple dashboard HTML generation for audit visualization - Redaction Reliability Comparison."""
from flask import render_template_string
import json

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Redaction Reliability Audit Dashboard</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background: #f4f4f9; }
        h1 { color: #333; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 0 20px rgba(0,0,0,0.1); margin-bottom: 30px; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #007bff; color: white; text-transform: uppercase; letter-spacing: 0.1em; }
        tr:hover { background-color: #f1f1f1; }
        .signature { font-family: monospace; font-size: 0.8em; color: #666; }
        .winning-tool { font-weight: bold; color: #28a745; background-color: #f0f9f7; padding: 4px 8px; border-radius: 4px; }
        .jury-section { background: #fff; padding: 15px; border-left: 4px solid #ffc107; margin-bottom: 20px; border-radius: 4px; }
        .metric { display: inline-block; margin-right: 20px; }
        .metric-label { color: #666; font-size: 0.9em; }
        .metric-value { font-size: 1.4em; font-weight: bold; color: #007bff; }
        .bar-wrap { background: #e9ecef; border-radius: 8px; height: 16px; width: 220px; overflow: hidden; display: inline-block; vertical-align: middle; margin-right: 8px; }
        .bar { height: 100%; }
        .bar-allow { background: #28a745; }
        .bar-challenge { background: #ffc107; }
        .bar-block { background: #dc3545; }
        .small-muted { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>🎯 Redaction Reliability Comparison Dashboard</h1>
    <p>This dashboard tracks PII redaction performance across three independent tools competing for accuracy.</p>
    
    <div class="jury-section">
        <h2>Jury System Overview</h2>
        <div class="metric">
            <div class="metric-label">Tool A (Regex)</div>
            <div class="metric-value">Advanced Pattern Matching</div>
        </div>
        <div class="metric">
            <div class="metric-label">Tool B (Dictionary)</div>
            <div class="metric-value">Keyword-based Matching</div>
        </div>
        <div class="metric">
            <div class="metric-label">Tool C (Mock AI)</div>
            <div class="metric-value">NLP Simulation</div>
        </div>
    </div>
    
    <h2>🔐 Security Audit Logs</h2>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Timestamp</th>
                <th>Event Type</th>
                <th>User Role</th>
                <th>Winner</th>
                <th>Items Detected</th>
                <th>Security Signature</th>
            </tr>
        </thead>
        <tbody>
            {% for row in logs %}
            <tr>
                <td>{{ row.id }}</td>
                <td>{{ row.ts }}</td>
                <td><strong>{{ row.event_type }}</strong></td>
                <td>{{ row.user_role }}</td>
                <td>
                    {% if row.winning_tool %}
                        <span class="winning-tool">Tool {{ row.winning_tool }}</span>
                    {% else %}
                        N/A
                    {% endif %}
                </td>
                <td>ID: {{ row.count_id }}, Phone: {{ row.count_phone }}, Email: {{ row.count_email }}</td>
                <td class="signature">{{ row.signature[:20] if row.signature else 'N/A' }}...</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <h2>📊 Jury Tool Reliability Summary</h2>
    <p><strong>Chart:</strong> Reliability comparison table for Tool A/B/C detections.</p>
    <table>
        <thead>
            <tr>
                <th>Event ID</th>
                <th>Tool A Detections</th>
                <th>Tool B Detections</th>
                <th>Tool C Detections</th>
                <th>Winner</th>
            </tr>
        </thead>
        <tbody>
            {% for row in logs %}
            {% if row.winning_tool %}
            <tr>
                <td>#{{ row.id }}</td>
                <td>
                    {% if row.tool_a_counts_parsed %}
                        {{ row.tool_a_counts_parsed.id | default(0) }} ID, 
                        {{ row.tool_a_counts_parsed.phone | default(0) }} Phone
                    {% else %}
                        -
                    {% endif %}
                </td>
                <td>
                    {% if row.tool_b_counts_parsed %}
                        {{ row.tool_b_counts_parsed.id | default(0) }} ID, 
                        {{ row.tool_b_counts_parsed.phone | default(0) }} Phone
                    {% else %}
                        -
                    {% endif %}
                </td>
                <td>
                    {% if row.tool_c_counts_parsed %}
                        {{ row.tool_c_counts_parsed.id | default(0) }} ID, 
                        {{ row.tool_c_counts_parsed.phone | default(0) }} Phone
                    {% else %}
                        -
                    {% endif %}
                </td>
                <td><span class="winning-tool">Tool {{ row.winning_tool }}</span></td>
            </tr>
            {% endif %}
            {% endfor %}
        </tbody>
    </table>

    {% if benchmark %}
    <h2>📈 Phase 3/4 Privacy Benchmark Chart</h2>
    <p class="small-muted">Adversarial benchmark on explicit/obfuscated PII prompts.</p>
    <table>
        <thead>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
        </thead>
        <tbody>
            <tr><td>Total Cases</td><td>{{ benchmark.metrics.total_cases }}</td></tr>
            <tr><td>PII Cases</td><td>{{ benchmark.metrics.pii_cases }}</td></tr>
            <tr><td>Leak Rate</td><td>{{ benchmark.metrics.core_pii_leak_rate }}</td></tr>
            <tr><td>Avg Utility Score</td><td>{{ benchmark.metrics.avg_utility_score }}</td></tr>
            <tr><td>Avg Latency (ms)</td><td>{{ benchmark.metrics.avg_latency_ms }}</td></tr>
        </tbody>
    </table>

    <table>
        <thead>
            <tr>
                <th>Policy Action</th>
                <th>Distribution</th>
            </tr>
        </thead>
        <tbody>
            {% set total_actions = benchmark.metrics.total_cases if benchmark.metrics.total_cases else 1 %}
            {% for item in benchmark.visualization.policy_action_chart %}
            {% set pct = ((item.value / total_actions) * 100) | round(1) %}
            <tr>
                <td>{{ item.label }}</td>
                <td>
                    <span class="bar-wrap">
                        <span class="bar bar-{{ item.label }}" style="width: {{ pct }}%;"></span>
                    </span>
                    {{ item.value }} ({{ pct }}%)
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}

    {% if calibration %}
    <h2>🎛️ Policy Threshold Calibration</h2>
    <p class="small-muted">Suggested thresholds derived from benchmark alignment objective.</p>
    <table>
        <thead>
            <tr>
                <th>Challenge Threshold</th>
                <th>Block Threshold</th>
                <th>Objective Cost</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>{{ calibration.challenge_threshold }}</td>
                <td>{{ calibration.block_threshold }}</td>
                <td>{{ calibration.objective_cost }}</td>
            </tr>
        </tbody>
    </table>
    {% endif %}

    {% if autotune %}
    <h2>🤖 Auto-tuning Recommendation (Audit Telemetry)</h2>
    <table>
        <thead>
            <tr>
                <th>Source</th>
                <th>Samples</th>
                <th>Suggested Challenge</th>
                <th>Suggested Block</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>{{ autotune.source }}</td>
                <td>{{ autotune.sample_count }}</td>
                <td>{{ autotune.challenge_threshold }}</td>
                <td>{{ autotune.block_threshold }}</td>
            </tr>
        </tbody>
    </table>
    {% endif %}

    {% if policy_thresholds %}
    <h2>⚙️ Active Policy Thresholds</h2>
    <p class="small-muted">Loaded by privacy engine from environment overrides or persisted policy config.</p>
    <table>
        <thead>
            <tr>
                <th>Challenge</th>
                <th>Block</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>{{ policy_thresholds.challenge_threshold }}</td>
                <td>{{ policy_thresholds.block_threshold }}</td>
            </tr>
        </tbody>
    </table>
    {% endif %}

    {% if benchmark_history %}
    <h2>📉 Benchmark Trend History</h2>
    <p class="small-muted">Most recent benchmark runs, useful for showing trajectory over time.</p>
    <table>
        <thead>
            <tr>
                <th>Timestamp</th>
                <th>Leak Rate</th>
                <th>Utility</th>
                <th>Latency (ms)</th>
                <th>Actions (A/C/B)</th>
            </tr>
        </thead>
        <tbody>
            {% for run in benchmark_history %}
            <tr>
                <td>{{ run.ts }}</td>
                <td>{{ run.leak_rate }}</td>
                <td>{{ run.utility_score }}</td>
                <td>{{ run.latency_ms }}</td>
                <td>{{ run.allow_count }}/{{ run.challenge_count }}/{{ run.block_count }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}
</body>
</html>
"""


def render_dashboard(logs=None, benchmark=None, calibration=None, autotune=None, benchmark_history=None, policy_thresholds=None):
    if logs is None:
        logs = []
    
    # Parse JSON strings in tool_counts for template rendering
    for log in logs:
        for key in ['tool_a_counts', 'tool_b_counts', 'tool_c_counts']:
            try:
                if log.get(key):
                    log[f'{key}_parsed'] = json.loads(log[key])
                else:
                    log[f'{key}_parsed'] = {}
            except:
                log[f'{key}_parsed'] = {}
    
    return render_template_string(
        DASHBOARD_HTML,
        logs=logs,
        benchmark=benchmark,
        calibration=calibration,
        autotune=autotune,
        benchmark_history=benchmark_history or [],
        policy_thresholds=policy_thresholds,
    )
