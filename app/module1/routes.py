from flask import Blueprint, request, jsonify, current_app
from .logic import is_authorized

bp = Blueprint('module1', __name__)

@bp.route('/verify', methods=['POST'])
def verify():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "denied", "message": "Invalid request: JSON body required"}), 400

    role = data.get('role')
    prompt = data.get('prompt')

    # Determine forbidden intents first for a richer audit trail
    from .logic import find_forbidden_intents
    matched = find_forbidden_intents(role, prompt)
    if matched:
        from flask import g

        current_app.logger.warning(
            "Denied access attempt: role=%s prompt=%s",
            role,
            prompt,
            extra={
                "event_type": "SECURITY_DENIED",
                "request_id": getattr(g, "request_id", None),
                "user_role": role,
                "endpoint": request.path,
                "forbidden_intents": matched,
            },
        )

        return jsonify({
            "status": "denied",
            "message": "Access Denied: You do not have permission to request this data."
        }), 403

    if is_authorized(role, prompt):
        return jsonify({"status": "authorized", "code": 200}), 200

    # Default deny
    return jsonify({
        "status": "denied",
        "message": "Access Denied: You do not have permission to request this data."
    }), 403
