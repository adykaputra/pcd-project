from flask import Blueprint, request, jsonify, current_app
from app.module1.logic import is_authorized
from .logic import redact_pii, run_redaction_jury

bp = Blueprint('module2', __name__)

@bp.route('/sanitize', methods=['POST'])
def sanitize():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "denied", "message": "Invalid request: JSON body required"}), 400

    role = data.get('role')
    prompt = data.get('prompt')

    # Check authorization first
    if not is_authorized(role, prompt):
        current_app.logger.warning("Denied access attempt to /sanitize: role=%s prompt=%s", role, prompt)
        return jsonify({
            "status": "denied",
            "message": "Access Denied: You do not have permission to request this data."
        }), 403

    # Run the Redaction Jury system
    jury_result = run_redaction_jury(prompt)
    sanitized = jury_result["sanitized_prompt"]
    winning_tool = jury_result["winning_tool"]
    tool_scores = jury_result["tool_scores"]
    tool_counts = jury_result["tool_counts"]

    # If redaction occurred, log an audit entry for Privacy Shield (Module 4 Auditor)
    if sanitized != (prompt or ""):
        from flask import g
        from app.audit import get_manager
        import datetime

        # Log to audit database with jury comparison data
        get_manager().record_event({
            "ts": datetime.datetime.utcnow(),
            "event_type": "PII_REDACTED_JURY",
            "request_id": getattr(g, "request_id", None),
            "user_role": role,
            "endpoint": request.path,
            "message": f"PII detected and redacted using Redaction Jury. Winner: Tool {winning_tool}",
            "count_id": tool_counts.get(winning_tool, {}).get("id", 0),
            "count_phone": tool_counts.get(winning_tool, {}).get("phone", 0),
            "count_email": tool_counts.get(winning_tool, {}).get("email", 0),
            "winning_tool": winning_tool,
            "tool_a_counts": tool_counts.get("A", {}),
            "tool_b_counts": tool_counts.get("B", {}),
            "tool_c_counts": tool_counts.get("C", {}),
            "metadata": {
                "original_prompt_sample": (prompt[:200] if prompt else None),
                "tool_scores": tool_scores,
            },
        })

    return jsonify({
        "status": "sanitized",
        "sanitized_prompt": sanitized,
        "reliability_summary": {
            "winning_tool": winning_tool,
            "tool_comparison": {
                "Tool_A_Regex_Count": tool_scores.get("A", 0),
                "Tool_B_Dictionary_Count": tool_scores.get("B", 0),
                "Tool_C_MockAI_Count": tool_scores.get("C", 0),
            },
            "detailed_counts": {
                "Tool_A": tool_counts.get("A", {}),
                "Tool_B": tool_counts.get("B", {}),
                "Tool_C": tool_counts.get("C", {}),
            }
        }
    }), 200
