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
</body>
</html>
"""


def render_dashboard(logs=None):
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
    
    return render_template_string(DASHBOARD_HTML, logs=logs)
