from flask import Blueprint, request, jsonify, current_app
from app.module2.logic import sanitize_prompt_for_llm

bp = Blueprint('module3', __name__)

@bp.route('/generate', methods=['POST'])
def generate():
    """Proxy endpoint that redacts PII before forwarding to an LLM backend.

    Expected input JSON:
      { "prompt": "...", "model": "optional-model-name" }
      or legacy:
      { "sanitized_prompt": "...", "model": "optional-model-name" }

    Behavior:
      - Accept `prompt` (preferred) or `sanitized_prompt` (legacy).
      - Always run a strict redaction pass before forwarding to the LLM.
      - Reject requests if any core PII patterns still remain after redaction.
      - Forward only the redacted prompt to the LLM backend.
      - Return the model response.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "denied", "message": "Invalid request: JSON body required"}), 400

    raw_prompt = data.get('prompt')
    legacy_prompt = data.get('sanitized_prompt')
    inbound_prompt = raw_prompt if isinstance(raw_prompt, str) else legacy_prompt
    if not inbound_prompt or not isinstance(inbound_prompt, str):
        return jsonify({"status": "denied", "message": "Invalid request: prompt is required"}), 400

    # Always sanitize at the LLM boundary to avoid leaking user PII.
    redaction_result = sanitize_prompt_for_llm(inbound_prompt)
    sanitized_prompt = redaction_result["sanitized_prompt"]
    remaining = redaction_result["remaining_pii_counts"]
    if any((remaining or {}).values()):
        from flask import g
        current_app.logger.warning(
            "[LLM_PROXY] Prompt still contains PII after redaction; rejected",
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
        "response": result.get("text"),
        "redaction_applied": redaction_result["had_pii"],
    }), 200
