from flask import Blueprint, request, jsonify, current_app
from app.module2.logic import redact_pii

bp = Blueprint('module3', __name__)

@bp.route('/generate', methods=['POST'])
def generate():
    """Proxy endpoint to send sanitized prompt to an LLM backend.

    Expected input JSON:
      { "sanitized_prompt": "...", "model": "optional-model-name" }

    Behavior:
      - Require `sanitized_prompt` field.
      - Re-run `redact_pii` as a safety check; if PII is still present, reject (400).
      - Forward ONLY the sanitized prompt to the LLM backend (here we mock the call).
      - Return the model response.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "denied", "message": "Invalid request: JSON body required"}), 400

    sanitized_prompt = data.get('sanitized_prompt')
    if not sanitized_prompt or not isinstance(sanitized_prompt, str):
        return jsonify({"status": "denied", "message": "Invalid request: sanitized_prompt is required"}), 400

    # Safety check: ensure no PII remains
    rechecked = redact_pii(sanitized_prompt)
    if rechecked != sanitized_prompt:
        # If PII is found during the final check, log and reject
        from flask import g
        current_app.logger.warning(
            "[LLM_PROXY] Attempt to forward prompt containing PII; rejected",
            extra={
                "event_type": "SECURITY_DENIED",
                "request_id": getattr(g, "request_id", None),
                "user_role": getattr(g, "user_role", None),
                "endpoint": request.path,
            },
        )
        return jsonify({"status": "denied", "message": "Request contains PII after sanitization. Aborting."}), 400

    provider = data.get('provider', 'openai')
    model = data.get('model', None)

    current_app.logger.info("[LLM_PROXY] Forwarding sanitized prompt to provider=%s model=%s", provider, model)

    try:
        from .adapters import get_adapter

        adapter = get_adapter(provider=provider, model=model)
        result = adapter.send_prompt(sanitized_prompt)
    except Exception as e:
        current_app.logger.error("[LLM_PROXY] Adapter error: %s", e)
        return jsonify({"status": "error", "message": "LLM adapter failed to process the request."}), 500

    # Log token usage if present
    usage = result.get("usage") or {}
    if usage:
        from flask import g
        current_app.logger.info(
            "[LLM_PROXY] Token usage: %s",
            usage,
            extra={
                "event_type": "LLM_TOKEN_USAGE",
                "request_id": getattr(g, "request_id", None),
                "user_role": getattr(g, "user_role", None),
                "endpoint": request.path,
                "usage": usage,
            },
        )

    return jsonify({
        "status": "ok",
        "provider": provider,
        "model": model,
        "response": result.get("text")
    }), 200
