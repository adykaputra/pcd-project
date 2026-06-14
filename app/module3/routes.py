import os
import hashlib
import jwt
import re
from datetime import datetime
from typing import Optional
from flask import Blueprint, request, jsonify, current_app, render_template, redirect, url_for
from app.audit import get_manager
from app.module2.logic import tokenize_prompt_for_llm, detokenize_prompt_from_vault, COMMON_NAMES, COMMON_LOCATIONS
from app.privacy_risk import evaluate_prompt_risk
from app.privacy_benchmark import run_privacy_benchmark, run_privacy_benchmark_cross_split
from app.privacy_calibration import calibrate_policy_thresholds
from app.privacy_autotune import recommend_thresholds_from_audit
from app.privacy_policy_config import save_policy_thresholds, get_policy_thresholds
from app.privacy_benchmark_history import get_benchmark_history_manager
from app.privacy_benchmark_dataset import list_dataset_versions
from app.privacy_comparison import run_privacy_comparison, route_prompt_adaptive
from app.privacy_adversarial import run_adversarial_stress
from app.privacy_vault import get_vault, maybe_sweep_retention
from app.privacy_viva import generate_viva_pack
from app.privacy_ner import detect_named_entities

bp = Blueprint('module3', __name__)


def _count_dictionary_terms(text: str, terms: set[str]) -> int:
    if not text:
        return 0
    total = 0
    for term in terms:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        total += len(pattern.findall(text))
    return total


def _decode_bearer_token(req):
    auth = req.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    return None


def _extract_auth_token(req):
    return _decode_bearer_token(req) or req.args.get("token") or req.cookies.get("pf_session")


def _decode_auth_payload(token: Optional[str]):
    if not token:
        return None
    secret = os.getenv('JWT_SECRET', 'very-secret')
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        return None


@bp.route('/', methods=['GET'])
def landing():
    """Unified auth gateway (single login/signup page)."""
    return render_template(
        "auth_gateway.html",
        auth_error=(request.args.get("auth_error") or "").strip(),
        auth_message=(request.args.get("auth_message") or "").strip(),
    ), 200


@bp.route('/client', methods=['GET'])
def client_portal():
    """Client-facing chat UI."""
    token = _extract_auth_token(request)
    payload = _decode_auth_payload(token)
    if not payload:
        return redirect(url_for("module3.landing"))
    role = payload.get("role")
    if role not in {"user", "admin"}:
        return redirect(url_for("module3.landing"))

    display_name = (payload.get("name") or payload.get("sub") or "Client").strip()[:40]
    default_provider = os.getenv("LLM_DEFAULT_PROVIDER", "mock")
    default_model = (
        os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2:3b")
        if default_provider == "ollama"
        else os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o-mini") if default_provider == "openai" else ""
    )
    return render_template(
        "client_chat.html",
        display_name=display_name,
        user_identity=(payload.get("sub") or "").strip().lower(),
        default_provider=default_provider,
        default_model=default_model,
        auth_token=_decode_bearer_token(request) or request.args.get("token") or "",
    ), 200


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
    token = _extract_auth_token(req)
    payload = _decode_auth_payload(token)
    if payload:
        return payload.get('role') == 'admin'
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
    requested_provider = str(provider or os.getenv("LLM_DEFAULT_PROVIDER", "mock")).strip().lower()
    requested_model = str(model or "").strip().lower()
    # Common UX pitfall: user selects mock but types a local model name.
    if requested_provider == "mock" and any(tag in requested_model for tag in ("llama", "mistral", "qwen", "gemma")):
        requested_provider = "ollama"

    retention_result = maybe_sweep_retention()
    if retention_result and int(retention_result.get("deleted_entries", 0)) > 0:
        from flask import g
        current_app.logger.info(
            "[PRIVACY_VAULT] Retention sweep purged old tokens",
            extra={
                "event_type": "PII_VAULT_PURGED",
                "request_id": getattr(g, "request_id", None),
                "user_role": getattr(g, "user_role", None),
                "endpoint": request.path,
                "metadata": retention_result,
            },
        )

    router_mode = str(os.getenv("PRIVACY_RUNTIME_ROUTER", "adaptive")).strip().lower()
    routing_details = {}
    if router_mode == "adaptive":
        routed = route_prompt_adaptive(inbound_prompt)
        tokenized_prompt = routed["redacted_prompt"]
        base_token_counts = dict(routed.get("token_counts", {}))
        # Preserve conservative policy behavior: contextual signals should still
        # contribute to risk scoring even if the selected runtime method focuses
        # mainly on core identifiers.
        base_token_counts["name"] = max(
            int(base_token_counts.get("name", 0)),
            _count_dictionary_terms(inbound_prompt, COMMON_NAMES),
        )
        base_token_counts["location"] = max(
            int(base_token_counts.get("location", 0)),
            _count_dictionary_terms(inbound_prompt, COMMON_LOCATIONS),
        )
        ner_entities = detect_named_entities(inbound_prompt).get("entities", [])
        ner_person = sum(1 for entity in ner_entities if str(entity.get("label", "")).upper() in {"PERSON", "PER"})
        ner_location = sum(1 for entity in ner_entities if str(entity.get("label", "")).upper() in {"GPE", "LOC", "LOCATION"})
        ner_org = sum(1 for entity in ner_entities if str(entity.get("label", "")).upper() in {"ORG", "ORGANIZATION"})
        base_token_counts["ner_person"] = max(int(base_token_counts.get("ner_person", 0)), ner_person)
        base_token_counts["ner_location"] = max(int(base_token_counts.get("ner_location", 0)), ner_location)
        base_token_counts["ner_organization"] = max(int(base_token_counts.get("ner_organization", 0)), ner_org)
        tokenization = {
            "tokenized_prompt": tokenized_prompt,
            "had_pii": bool(routed.get("redaction_applied", tokenized_prompt != inbound_prompt)),
            "token_counts": base_token_counts,
            "remaining_pii_counts": routed.get("remaining_pii_counts", {}),
            "ner_backend": (routed.get("selected_metadata") or {}).get("backend"),
            "ner_entities_detected": max(
                int((routed.get("selected_metadata") or {}).get("entities_detected", 0) or 0),
                len(ner_entities),
            ),
            "router": {
                "mode": "adaptive",
                "selected_method_id": routed.get("selected_method_id"),
                "selected_method_name": routed.get("selected_method_name"),
                "has_pii_signals": routed.get("has_pii_signals"),
                "candidates": routed.get("candidates", []),
            },
        }
        routing_details = tokenization["router"]
    else:
        tokenization = tokenize_prompt_for_llm(inbound_prompt)
        tokenized_prompt = tokenization["tokenized_prompt"]
        routing_details = {"mode": "legacy", "selected_method_id": "keyword_vault"}

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
    redaction_proof = {
        "model_input_is_tokenized": True,
        "redaction_applied": bool(tokenization["had_pii"]),
        "tokenized_prompt_full": tokenized_prompt[:4000],
        "tokenized_prompt_preview": (tokenized_prompt[:220] + "...") if len(tokenized_prompt) > 220 else tokenized_prompt,
        "original_prompt_sha256": hashlib.sha256(inbound_prompt.encode("utf-8")).hexdigest()[:16],
        "router_mode": routing_details.get("mode"),
        "selected_method_id": routing_details.get("selected_method_id"),
        "selected_method_name": routing_details.get("selected_method_name"),
        "router_candidates": routing_details.get("candidates", [])[:5],
        "user_identity": getattr(g, "user_identity", None),
        "user_name": getattr(g, "user_name", None),
        "session_id": getattr(g, "session_id", None),
    }
    current_app.logger.info(
        "[PRIVACY_FIREWALL] Forwarding tokenized prompt to provider=%s model=%s",
        requested_provider,
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
            "metadata": {
                "token_counts": tokenization["token_counts"],
                "risk_assessment": risk,
                "risk_score": risk.get("risk_score"),
                "router": routing_details,
                "dispatch_proof": redaction_proof,
            },
        },
    )

    try:
        from .adapters import get_adapter

        adapter = get_adapter(provider=requested_provider, model=model)
        result = adapter.send_prompt(tokenized_prompt)
        resolved_provider = result.get("provider")
        if not isinstance(resolved_provider, str) or not resolved_provider:
            provider_name = getattr(adapter, "provider_name", None)
            resolved_provider = provider_name if isinstance(provider_name, str) and provider_name else requested_provider
    except ValueError as e:
        return {"status": "denied", "message": str(e)}, 400
    except Exception as e:
        if requested_provider == "ollama":
            # Keep chat responsive even when Ollama is unavailable.
            current_app.logger.warning("[LLM_PROXY] Ollama failed, falling back to mock: %s", e)
            from .adapters import get_adapter

            adapter = get_adapter(provider="mock", model=model)
            result = adapter.send_prompt(tokenized_prompt)
            resolved_provider = "mock"
            result["fallback_reason"] = "ollama_unavailable"
        else:
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
            "router": tokenization.get("router", routing_details),
        },
        "dispatch_proof": redaction_proof,
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
    token = _extract_auth_token(request)
    payload = _decode_auth_payload(token)
    if not payload or payload.get("role") not in {"user", "admin"}:
        return jsonify({"status": "denied", "message": "Authentication required"}), 401

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
                "fallback_reason": payload.get("fallback_reason"),
                "risk_assessment": payload.get("risk_assessment"),
                "tokenization": payload.get("tokenization"),
                "dispatch_proof": payload.get("dispatch_proof"),
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


@bp.route('/privacy/comparison', methods=['GET'])
def privacy_comparison():
    """Admin-only endpoint for multi-method redaction comparison."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    dataset_version = request.args.get("dataset_version", "v3")
    split = request.args.get("split", "all")
    include_cases = str(request.args.get("include_cases", "0")).lower() in {"1", "true", "yes"}
    raw_methods = (request.args.get("methods") or "").strip()
    methods = [item.strip() for item in raw_methods.split(",") if item.strip()] if raw_methods else None

    try:
        comparison = run_privacy_comparison(
            dataset_version=dataset_version,
            split=split,
            methods=methods,
            include_cases=include_cases,
        )
    except FileNotFoundError:
        return jsonify({"status": "denied", "message": f"Unknown benchmark dataset version: {dataset_version}"}), 400

    return jsonify({"status": "ok", "comparison": comparison}), 200


@bp.route('/privacy/adversarial', methods=['GET'])
def privacy_adversarial():
    """Admin-only endpoint for adversarial robustness stress testing."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    dataset_version = request.args.get("dataset_version", "v3")
    split = request.args.get("split", "test")
    max_cases = int(request.args.get("max_cases", 20))
    max_variants = int(request.args.get("max_variants", 3))
    include_cases = str(request.args.get("include_cases", "0")).lower() in {"1", "true", "yes"}
    try:
        stress = run_adversarial_stress(
            dataset_version=dataset_version,
            split=split,
            max_cases=max_cases,
            max_variants=max_variants,
        )
    except FileNotFoundError:
        return jsonify({"status": "denied", "message": f"Unknown benchmark dataset version: {dataset_version}"}), 400

    if not include_cases:
        stress = {**stress, "cases": []}
    return jsonify({"status": "ok", "adversarial": stress}), 200


@bp.route('/privacy/vault/purge', methods=['POST'])
def privacy_vault_purge():
    """Admin-only endpoint to purge vault entries by retention hours."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    data = request.get_json(silent=True) or {}
    retention_hours = int(data.get("retention_hours", os.getenv("PII_VAULT_RETENTION_HOURS", "0") or "0"))
    result = get_vault().purge_expired_entries(retention_hours=retention_hours)

    from flask import g
    current_app.logger.info(
        "[PRIVACY_VAULT] Manual purge executed",
        extra={
            "event_type": "PII_VAULT_PURGED",
            "request_id": getattr(g, "request_id", None),
            "user_role": getattr(g, "user_role", None),
            "endpoint": request.path,
            "metadata": result,
        },
    )
    return jsonify({"status": "ok", "purge": result}), 200


@bp.route('/privacy/vault/stats', methods=['GET'])
def privacy_vault_stats():
    """Admin-only endpoint to inspect vault retention/utilization stats."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403
    stats = get_vault().stats()
    retention_hours = int(os.getenv("PII_VAULT_RETENTION_HOURS", "0") or "0")
    return jsonify({"status": "ok", "retention_hours": retention_hours, "vault": stats}), 200


@bp.route('/privacy/viva/export', methods=['POST'])
def privacy_viva_export():
    """Admin-only endpoint to generate viva evidence artifacts on demand."""
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    data = request.get_json(silent=True) or {}
    dataset_version = str(data.get("dataset_version", "v3")).strip() or "v3"
    report_dir = str(data.get("report_dir", "reports/viva")).strip() or "reports/viva"

    try:
        viva = generate_viva_pack(dataset_version=dataset_version, report_dir=report_dir)
    except FileNotFoundError:
        return jsonify({"status": "denied", "message": f"Unknown benchmark dataset version: {dataset_version}"}), 400

    from flask import g
    current_app.logger.info(
        "[PRIVACY_VIVA] Viva pack generated",
        extra={
            "event_type": "VIVA_PACK_EXPORTED",
            "request_id": getattr(g, "request_id", None),
            "user_role": getattr(g, "user_role", None),
            "endpoint": request.path,
            "metadata": {"dataset_version": dataset_version, "artifacts": viva.get("artifacts", {})},
        },
    )
    return jsonify({"status": "ok", "viva": viva}), 200


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
