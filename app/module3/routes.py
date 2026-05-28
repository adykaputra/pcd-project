import os
import jwt
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, render_template, redirect, url_for
from app.audit import get_manager
from app.module2.logic import tokenize_prompt_for_llm, detokenize_prompt_from_vault
from app.privacy_risk import evaluate_prompt_risk
from app.privacy_benchmark import run_privacy_benchmark, run_privacy_benchmark_cross_split
from app.privacy_calibration import calibrate_policy_thresholds
from app.privacy_autotune import recommend_thresholds_from_audit
from app.privacy_policy_config import save_policy_thresholds, get_policy_thresholds
from app.privacy_benchmark_history import get_benchmark_history_manager
from app.privacy_benchmark_dataset import list_dataset_versions

bp = Blueprint('module3', __name__)


@bp.route('/', methods=['GET'])
def landing():
    """Role-based product entry point (client vs admin)."""
    return render_template("entry_portal.html"), 200


@bp.route('/client', methods=['GET'])
def client_portal():
    """Client-facing chat UI."""
    display_name = (request.args.get("name") or "Client").strip()[:40]
    return render_template("client_chat.html", display_name=display_name), 200


@bp.route('/healthz', methods=['GET'])
def healthz():
    """Liveness/readiness probe for deployment platforms."""
    checks = {
        "service": "ok",
        "audit_db": "unknown",
        "dataset_catalog": "unknown",
    }
    status_code = 200

    try:
        # Ensures DB path/table exists and can be queried.
        get_manager().summary()
        checks["audit_db"] = "ok"
    except Exception as exc:
        checks["audit_db"] = f"error: {exc}"
        status_code = 503

    try:
        checks["dataset_catalog"] = "ok" if list_dataset_versions() else "empty"
    except Exception as exc:
        checks["dataset_catalog"] = f"error: {exc}"
        status_code = 503

    return jsonify(
        {
            "status": "ok" if status_code == 200 else "degraded",
            "service": "llm-privacy-firewall",
            "ts": datetime.utcnow().isoformat() + "Z",
            "checks": checks,
        }
    ), status_code


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


def _run_firewall_pipeline(
    *,
    inbound_prompt: str,
    provider: str,
    model: str | None,
    challenge_override: int | None = None,
    block_override: int | None = None,
):
    """Run tokenization, policy evaluation, and provider dispatch."""
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
        return {"status": "denied", "message": "Request contains PII after sanitization. Aborting."}, 400

    risk = evaluate_prompt_risk(
        original_prompt=inbound_prompt,
        tokenization=tokenization,
        tokenized_prompt=tokenized_prompt,
        challenge_threshold=challenge_override,
        block_threshold=block_override,
    )
    if risk["policy_action"] == "block":
        from flask import g
        current_app.logger.warning(
            "[PRIVACY_FIREWALL] Policy engine blocked high-risk prompt",
            extra={
                "event_type": "PRIVACY_POLICY_BLOCK",
                "request_id": getattr(g, "request_id", None),
                "user_role": getattr(g, "user_role", None),
                "endpoint": request.path,
                "metadata": {"risk": risk},
            },
        )
        return {
            "status": "denied",
            "message": "Prompt blocked by privacy policy engine.",
            "risk_assessment": risk,
        }, 403

    if risk["policy_action"] == "challenge":
        from flask import g
        current_app.logger.warning(
            "[PRIVACY_FIREWALL] Policy engine challenged medium-risk prompt",
            extra={
                "event_type": "PRIVACY_POLICY_CHALLENGE",
                "request_id": getattr(g, "request_id", None),
                "user_role": getattr(g, "user_role", None),
                "endpoint": request.path,
                "metadata": {"risk": risk},
            },
        )
        return {
            "status": "challenge",
            "message": "Prompt requires human review before LLM forwarding.",
            "risk_assessment": risk,
        }, 409

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
            "metadata": {"token_counts": tokenization["token_counts"], "risk_assessment": risk, "risk_score": risk.get("risk_score")},
        },
    )

    try:
        from .adapters import get_adapter

        adapter = get_adapter(provider=provider, model=model)
        result = adapter.send_prompt(tokenized_prompt)
        resolved_provider = result.get("provider")
        if not isinstance(resolved_provider, str) or not resolved_provider:
            provider_name = getattr(adapter, "provider_name", None)
            resolved_provider = provider_name if isinstance(provider_name, str) and provider_name else provider
    except ValueError as e:
        return {"status": "denied", "message": str(e)}, 400
    except Exception as e:
        current_app.logger.error("[LLM_PROXY] Adapter error: %s", e)
        return {"status": "error", "message": "LLM adapter failed to process the request."}, 500

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

    return {
        "status": "ok",
        "provider": resolved_provider,
        "model": model,
        "response": result.get("text"),
        "offline_mode": bool(result.get("offline_mode", False)),
        "redaction_applied": tokenization["had_pii"],
        "tokenization": {
            "applied": tokenization["had_pii"],
            "token_counts": tokenization["token_counts"],
            "ner_backend": tokenization.get("ner_backend"),
            "ner_entities_detected": tokenization.get("ner_entities_detected"),
        },
        "risk_assessment": risk,
    }, 200


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
      - Run risk policy engine (allow/challenge/block) before LLM forwarding.
      - Optional threshold overrides via payload fields:
          `policy_challenge_threshold`, `policy_block_threshold`.
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

    challenge_override = data.get("policy_challenge_threshold")
    block_override = data.get("policy_block_threshold")
    if challenge_override is not None and not isinstance(challenge_override, int):
        return jsonify({"status": "denied", "message": "policy_challenge_threshold must be integer"}), 400
    if block_override is not None and not isinstance(block_override, int):
        return jsonify({"status": "denied", "message": "policy_block_threshold must be integer"}), 400

    provider = data.get('provider', os.getenv("LLM_DEFAULT_PROVIDER", "mock"))
    model = data.get('model', None)
    payload, status_code = _run_firewall_pipeline(
        inbound_prompt=inbound_prompt,
        provider=provider,
        model=model,
        challenge_override=challenge_override,
        block_override=block_override,
    )
    return jsonify(payload), status_code


@bp.route('/client/chat', methods=['POST'])
def client_chat():
    """Client-facing chat endpoint backed by the privacy firewall."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "denied", "message": "Invalid request: JSON body required"}), 400

    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"status": "denied", "message": "Prompt is required"}), 400

    provider = data.get("provider", os.getenv("LLM_DEFAULT_PROVIDER", "mock"))
    model = data.get("model")
    payload, status_code = _run_firewall_pipeline(
        inbound_prompt=prompt.strip(),
        provider=provider,
        model=model,
    )

    if status_code == 200:
        return jsonify(
            {
                "status": "ok",
                "reply": payload.get("response"),
                "provider": payload.get("provider"),
                "offline_mode": payload.get("offline_mode", False),
                "risk_assessment": payload.get("risk_assessment"),
                "tokenization": payload.get("tokenization"),
            }
        ), 200

    if status_code == 409:
        return jsonify(
            {
                "status": "challenge",
                "reply": "I detected sensitive details. Please remove personal identifiers and try again.",
                "message": payload.get("message"),
                "risk_assessment": payload.get("risk_assessment"),
            }
        ), 409

    if status_code == 403:
        return jsonify(
            {
                "status": "denied",
                "reply": "I cannot process that request because it is too sensitive under privacy policy.",
                "message": payload.get("message"),
                "risk_assessment": payload.get("risk_assessment"),
            }
        ), 403

    return jsonify(payload), status_code


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


@bp.route('/privacy/benchmark', methods=['GET'])
def privacy_benchmark():
    """Admin-only benchmark endpoint for adversarial privacy evaluation."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403
    dataset_version = request.args.get("dataset_version", "v1")
    split = request.args.get("split", "all")
    mode = request.args.get("mode", "single").lower()

    try:
        if mode == "cross_split":
            results = run_privacy_benchmark_cross_split(dataset_version=dataset_version)
        else:
            results = run_privacy_benchmark(dataset_version=dataset_version, split=split)
    except FileNotFoundError:
        return jsonify({"status": "denied", "message": f"Unknown benchmark dataset version: {dataset_version}"}), 400

    persist = str(request.args.get("persist", "1")).lower() not in {"0", "false", "no"}
    run_id = None
    if persist and mode != "cross_split":
        run_id = get_benchmark_history_manager().record_run(results)
    return jsonify({"status": "ok", "benchmark": results, "persisted": persist, "run_id": run_id}), 200


@bp.route('/privacy/calibrate', methods=['GET'])
def privacy_calibrate():
    """Admin-only threshold calibration endpoint for policy tuning."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    dataset_version = request.args.get("dataset_version", "v1")
    split = request.args.get("split", "validation")
    try:
        recommendation = calibrate_policy_thresholds(dataset_version=dataset_version, split=split)
    except FileNotFoundError:
        return jsonify({"status": "denied", "message": f"Unknown benchmark dataset version: {dataset_version}"}), 400
    return jsonify({"status": "ok", "calibration": recommendation}), 200


@bp.route('/privacy/autotune', methods=['GET'])
def privacy_autotune():
    """Admin-only policy autotune endpoint using live audit telemetry."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    hours = int(request.args.get("hours", 24 * 7))
    min_samples = int(request.args.get("min_samples", 10))
    persist = str(request.args.get("persist", "0")).lower() in {"1", "true", "yes"}

    recommendation = recommend_thresholds_from_audit(hours=hours, min_samples=min_samples)
    persisted_config = None
    if persist:
        persisted_config = save_policy_thresholds(
            challenge_threshold=int(recommendation["challenge_threshold"]),
            block_threshold=int(recommendation["block_threshold"]),
            source=f"autotune:{recommendation.get('source', 'unknown')}",
        )

    return jsonify(
        {
            "status": "ok",
            "recommendation": recommendation,
            "current_thresholds": get_policy_thresholds(),
            "persisted_config": persisted_config,
        }
    ), 200


@bp.route('/privacy/benchmark/history', methods=['GET'])
def privacy_benchmark_history():
    """Admin-only benchmark history endpoint for trend visualization."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    limit = int(request.args.get("limit", 20))
    history = get_benchmark_history_manager().list_runs(limit=limit)
    return jsonify({"status": "ok", "history": history}), 200


@bp.route('/privacy/benchmark/datasets', methods=['GET'])
def privacy_benchmark_datasets():
    """Admin-only endpoint to list available benchmark dataset versions."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403
    return jsonify({"status": "ok", "versions": list_dataset_versions()}), 200
