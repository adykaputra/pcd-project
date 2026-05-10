import os
import jwt
from flask import Blueprint, request, jsonify, current_app
from app.module2.logic import tokenize_prompt_for_llm, detokenize_prompt_from_vault

bp = Blueprint('module3', __name__)


def _is_admin_request(req) -> bool:
    auth = req.headers.get('Authorization')
    if auth and auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1]
        secret = os.getenv('JWT_SECRET', 'very-secret')
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return payload.get('role') == 'admin'
        except Exception:
            return False
    role = req.headers.get('X-User-Role') or req.args.get('role')
    return role == 'admin'


@bp.route('/generate', methods=['POST'])
def generate():
    """Privacy firewall endpoint that tokenizes PII before LLM dispatch.

    Expected input JSON:
      { "prompt": "...", "model": "optional-model-name" }
      or legacy:
      { "sanitized_prompt": "...", "model": "optional-model-name" }

    Behavior:
      - Accept `prompt` (preferred) or `sanitized_prompt` (legacy).
      - Always run vault tokenization before forwarding to the LLM.
      - Reject requests if core PII patterns still remain after tokenization.
      - Forward only tokenized prompt to the LLM backend.
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

    # Enforce pseudonymization at the LLM boundary.
    tokenization = tokenize_prompt_for_llm(inbound_prompt)
    tokenized_prompt = tokenization["tokenized_prompt"]
    remaining = tokenization["remaining_pii_counts"]
    if any((remaining or {}).values()):
        from flask import g
        current_app.logger.warning(
            "[PRIVACY_FIREWALL] Prompt still contains PII after tokenization; rejected",
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

    from flask import g
    current_app.logger.info(
        "[PRIVACY_FIREWALL] Forwarding tokenized prompt to provider=%s model=%s",
        provider,
        model,
        extra={
            "event_type": "PII_TOKENIZED",
            "request_id": getattr(g, "request_id", None),
            "user_role": getattr(g, "user_role", None),
            "endpoint": request.path,
            "counts": {
                "id": tokenization["token_counts"].get("id", 0),
                "email": tokenization["token_counts"].get("email", 0),
                "phone": tokenization["token_counts"].get("phone", 0),
            },
            "metadata": {"token_counts": tokenization["token_counts"]},
        },
    )

    try:
        from .adapters import get_adapter

        adapter = get_adapter(provider=provider, model=model)
        result = adapter.send_prompt(tokenized_prompt)
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
        "redaction_applied": tokenization["had_pii"],
        "tokenization": {
            "applied": tokenization["had_pii"],
            "token_counts": tokenization["token_counts"],
        },
    }), 200


@bp.route('/detokenize', methods=['POST'])
def detokenize():
    """Admin-only endpoint to restore vault tokens for audit/legal workflows."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("text"), str):
        return jsonify({"status": "denied", "message": "Invalid request: text is required"}), 400

    result = detokenize_prompt_from_vault(data["text"])
    from flask import g
    current_app.logger.info(
        "[PRIVACY_FIREWALL] Detokenization requested by admin",
        extra={
            "event_type": "PII_DETOKENIZED",
            "request_id": getattr(g, "request_id", None),
            "user_role": "admin",
            "endpoint": request.path,
            "metadata": {
                "resolved_tokens": result["resolved_tokens"],
                "unresolved_tokens": len(result["unresolved_tokens"]),
            },
        },
    )
    return jsonify({"status": "ok", **result}), 200
