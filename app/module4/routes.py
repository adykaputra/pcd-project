from flask import Blueprint, request, jsonify, redirect, url_for
from app.audit import get_manager
from datetime import datetime, timedelta
import os
import jwt
import json

bp = Blueprint('module4', __name__, url_prefix='/audit')


def _is_admin_request(req):
    # Prefer JWT-based Authorization header: Bearer <token>
    auth = req.headers.get('Authorization')
    if auth and auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1]
    else:
        token = req.args.get('token') or req.cookies.get('pf_session')

    if token:
        secret = os.getenv('JWT_SECRET', 'very-secret')
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return payload.get('role') == 'admin'
        except Exception:
            return False

    # Fallback: Allow admin via X-User-Role header or query param 'role'
    role = req.headers.get('X-User-Role') or req.args.get('role')
    return role == 'admin'

@bp.route('/summary', methods=['GET'])
def summary():
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    # Optionally accept a 'hours' query param to extend/shorten the reporting window
    hours = int(request.args.get('hours', 24))
    since = datetime.utcnow() - timedelta(hours=hours)

    mgr = get_manager()
    result = mgr.summary(since=since)

    # Perform quick integrity check and attach results
    integrity = mgr.verify_integrity(since=since)
    result["integrity_ok"] = integrity.get("integrity_ok")
    result["tampered_ids"] = integrity.get("tampered_ids")[:10] if integrity.get("tampered_ids") else []

    return jsonify({"status": "ok", "summary": result}), 200


@bp.route('/dashboard', methods=['GET'])
def dashboard():
    if not _is_admin_request(request):
        return redirect(url_for("module3.landing"))

    from .dashboard import render_dashboard
    from app.privacy_benchmark import run_privacy_benchmark
    from app.privacy_calibration import calibrate_policy_thresholds
    from app.privacy_autotune import recommend_thresholds_from_audit
    from app.privacy_benchmark_history import get_benchmark_history_manager
    from app.privacy_policy_config import get_policy_thresholds
    from app.privacy_benchmark_dataset import list_dataset_versions
    
    # Fetch recent audit logs to display
    mgr = get_manager()
    conn = mgr._connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, ts, event_type, request_id, user_role, endpoint, message,
               count_id, count_phone, count_email, winning_tool, 
               tool_a_counts, tool_b_counts, tool_c_counts, signature, metadata
        FROM audit_events 
        ORDER BY ts DESC 
        LIMIT 100
    """)
    rows = cur.fetchall()
    conn.close()
    
    # Convert rows to dict-like objects for template rendering
    logs = []
    for row in rows:
        try:
            metadata = json.loads(row[15]) if row[15] else {}
        except Exception:
            metadata = {}
        dispatch_proof = metadata.get("dispatch_proof") if isinstance(metadata, dict) else None
        user_identity = metadata.get("user_identity") if isinstance(metadata, dict) else None
        session_id = metadata.get("session_id") if isinstance(metadata, dict) else None

        logs.append({
            'id': row[0],
            'ts': row[1],
            'event_type': row[2],
            'request_id': row[3],
            'user_role': row[4],
            'endpoint': row[5],
            'message': row[6],
            'count_id': row[7],
            'count_phone': row[8],
            'count_email': row[9],
            'winning_tool': row[10],
            'tool_a_counts': row[11],
            'tool_b_counts': row[12],
            'tool_c_counts': row[13],
            'signature': row[14],
            'metadata': metadata,
            'dispatch_proof': dispatch_proof,
            'user_identity': user_identity,
            'session_id': session_id,
        })

    latest_dispatch_proof = next(
        (
            {
                "ts": log.get("ts"),
                "user_identity": log.get("user_identity"),
                "session_id": log.get("session_id"),
                "proof": log.get("dispatch_proof"),
            }
            for log in logs
            if log.get("event_type") == "PII_TOKENIZED" and isinstance(log.get("dispatch_proof"), dict)
        ),
        None,
    )

    recent_sessions = []
    seen = set()
    for log in logs:
        identity = (log.get("user_identity") or "").strip() if isinstance(log.get("user_identity"), str) else ""
        session_id = (log.get("session_id") or "").strip() if isinstance(log.get("session_id"), str) else ""
        if not identity or not session_id or identity == "unknown" or session_id == "unknown":
            continue
        key = (identity, session_id)
        if key in seen:
            continue
        seen.add(key)
        recent_sessions.append(
            {
                "ts": log.get("ts"),
                "user_identity": identity,
                "session_id": session_id,
                "event_type": log.get("event_type"),
            }
        )
        if len(recent_sessions) >= 8:
            break

    thread_map = {}
    for log in logs:
        proof = log.get("dispatch_proof")
        if not isinstance(proof, dict):
            continue
        identity = (log.get("user_identity") or "unknown").strip() if isinstance(log.get("user_identity"), str) else "unknown"
        session_id = (log.get("session_id") or "unknown").strip() if isinstance(log.get("session_id"), str) else "unknown"
        if identity == "unknown" or session_id == "unknown":
            continue
        key = f"{identity}::{session_id}"
        if key not in thread_map:
            thread_map[key] = {
                "user_identity": identity,
                "session_id": session_id,
                "latest_ts": log.get("ts"),
                "messages": [],
            }
        thread_map[key]["messages"].append(
            {
                "ts": log.get("ts"),
                "redacted_prompt": proof.get("tokenized_prompt_full") or proof.get("tokenized_prompt_preview"),
                "policy_action": ((log.get("metadata") or {}).get("risk_assessment") or {}).get("policy_action"),
            }
        )
    sanitized_threads = sorted(
        thread_map.values(),
        key=lambda item: str(item.get("latest_ts") or ""),
        reverse=True,
    )
    
    dataset_version = "v2" if "v2" in list_dataset_versions() else "v1"
    benchmark = run_privacy_benchmark(dataset_version=dataset_version, split="all")
    calibration = calibrate_policy_thresholds(dataset_version=dataset_version, split="validation")
    autotune = recommend_thresholds_from_audit()
    history_mgr = get_benchmark_history_manager()
    history = history_mgr.list_runs(limit=20)
    if not history:
        history_mgr.record_run(benchmark)
        history = history_mgr.list_runs(limit=20)
    return render_dashboard(
        logs=logs,
        benchmark=benchmark,
        calibration=calibration,
        autotune=autotune,
        benchmark_history=history,
        policy_thresholds=get_policy_thresholds(),
        dataset_version=dataset_version,
        available_dataset_versions=list_dataset_versions(),
        initial_token=request.args.get("token"),
        latest_dispatch_proof=latest_dispatch_proof,
        recent_sessions=recent_sessions,
        sanitized_threads=sanitized_threads[:20],
    ), 200


# Immutability note:
# In production, to make audit records tamper-evident you would:
# - Sign each audit record with an HMAC or public-key signature stored separately, or
# - Append records to a cloud-native append-only audit log (e.g., GCP/AWS audit services) or
# - Use a write-once storage backend (immutable object storage) and store hashes on a blockchain or key-value store
# This code includes the comment and would be extended to include signing/verifiable storage in production.
