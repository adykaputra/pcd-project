from flask import Blueprint, request, jsonify, redirect, url_for, render_template
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


def _query_audit_logs(limit: int = 300):
    mgr = get_manager()
    conn = mgr._connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, ts, event_type, request_id, user_role, endpoint, message,
               count_id, count_phone, count_email, winning_tool,
               tool_a_counts, tool_b_counts, tool_c_counts, signature, metadata
        FROM audit_events
        ORDER BY ts DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cur.fetchall()
    conn.close()

    logs = []
    for row in rows:
        try:
            metadata = json.loads(row[15]) if row[15] else {}
        except Exception:
            metadata = {}
        dispatch_proof = metadata.get("dispatch_proof") if isinstance(metadata, dict) else None
        user_identity = metadata.get("user_identity") if isinstance(metadata, dict) else None
        user_name = metadata.get("user_name") if isinstance(metadata, dict) else None
        session_id = metadata.get("session_id") if isinstance(metadata, dict) else None
        if isinstance(dispatch_proof, dict):
            user_identity = user_identity or dispatch_proof.get("user_identity")
            user_name = user_name or dispatch_proof.get("user_name")
            session_id = session_id or dispatch_proof.get("session_id")

        logs.append(
            {
                "id": row[0],
                "ts": row[1],
                "event_type": row[2],
                "request_id": row[3],
                "user_role": row[4],
                "endpoint": row[5],
                "message": row[6],
                "count_id": row[7],
                "count_phone": row[8],
                "count_email": row[9],
                "winning_tool": row[10],
                "tool_a_counts": row[11],
                "tool_b_counts": row[12],
                "tool_c_counts": row[13],
                "signature": row[14],
                "metadata": metadata,
                "dispatch_proof": dispatch_proof,
                "user_identity": user_identity,
                "user_name": user_name,
                "session_id": session_id,
            }
        )
    return logs


def _build_evidence_from_logs(logs, *, max_recent: int = 8, max_threads: int = 20):
    thread_map = {}
    for log in logs:
        identity = (log.get("user_identity") or "").strip() if isinstance(log.get("user_identity"), str) else ""
        session_id = (log.get("session_id") or "").strip() if isinstance(log.get("session_id"), str) else ""
        if not identity or not session_id or identity == "unknown" or session_id == "unknown":
            continue
        key = f"{identity}::{session_id}"
        if key not in thread_map:
            thread_map[key] = {
                "user_identity": identity,
                "user_name": log.get("user_name"),
                "session_id": session_id,
                "latest_ts": log.get("ts"),
                "turns": 0,
                "message_count": 0,
                "messages": [],
                "_has_chat_events": False,
            }
        thread = thread_map[key]
        ts_value = log.get("ts")
        if str(ts_value or "") > str(thread.get("latest_ts") or ""):
            thread["latest_ts"] = ts_value
        if log.get("user_name") and not thread.get("user_name"):
            thread["user_name"] = log.get("user_name")

        metadata = log.get("metadata") or {}
        event_type = str(log.get("event_type") or "")
        if event_type == "CHAT_SESSION_REDACTED":
            content = str(metadata.get("content") or "").strip()
            if not content:
                continue
            role = str(metadata.get("turn_role") or "message").strip().lower()
            thread["_has_chat_events"] = True
            if role == "user":
                thread["turns"] += 1
            thread["message_count"] += 1
            thread["messages"].append(
                {
                    "ts": ts_value,
                    "role": role,
                    "redacted_prompt": content,
                    "policy_action": metadata.get("policy_action"),
                }
            )
            continue

        # Backward compatibility: for older logs, derive redacted user prompt
        # from dispatch proof only when richer chat events are absent.
        if thread["_has_chat_events"]:
            continue
        proof = log.get("dispatch_proof")
        if not isinstance(proof, dict):
            continue
        content = proof.get("tokenized_prompt_full") or proof.get("tokenized_prompt_preview")
        if not content:
            continue
        thread["turns"] += 1
        thread["message_count"] += 1
        thread["messages"].append(
            {
                "ts": ts_value,
                "role": "user",
                "redacted_prompt": content,
                "policy_action": (metadata.get("risk_assessment") or {}).get("policy_action"),
            }
        )

    sanitized_threads = sorted(
        thread_map.values(),
        key=lambda item: str(item.get("latest_ts") or ""),
        reverse=True,
    )
    for thread in sanitized_threads:
        thread["messages"] = sorted(
            thread.get("messages") or [],
            key=lambda item: str(item.get("ts") or ""),
        )
        thread.pop("_has_chat_events", None)
        thread["open_url"] = url_for(
            "module4.evidence_session",
            user=thread.get("user_identity"),
            session=thread.get("session_id"),
        )

    recent_sessions = [
        {
            "ts": thread.get("latest_ts"),
            "user_identity": thread.get("user_identity"),
            "user_name": thread.get("user_name"),
            "session_id": thread.get("session_id"),
            "event_type": "CHAT_SESSION_REDACTED",
        }
        for thread in sanitized_threads[:max_recent]
    ]
    return recent_sessions[:max_recent], sanitized_threads[:max_threads]

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


@bp.route('/live', methods=['GET'])
def live():
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    hours = max(1, int(request.args.get('hours', 24)))
    bucket_minutes = max(5, int(request.args.get('bucket_minutes', 60)))
    since = datetime.utcnow() - timedelta(hours=hours)
    telemetry = get_manager().live_telemetry(since=since, bucket_minutes=bucket_minutes)
    return jsonify({"status": "ok", "live": telemetry}), 200


@bp.route('/dashboard', methods=['GET'])
def dashboard():
    if not _is_admin_request(request):
        return redirect(url_for("module3.landing"))

    from .dashboard import render_dashboard
    from app.privacy_benchmark_history import get_benchmark_history_manager
    from app.privacy_policy_config import get_policy_thresholds
    from app.privacy_benchmark_dataset import list_dataset_versions
    
    logs = _query_audit_logs(limit=300)

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

    recent_sessions, sanitized_threads = _build_evidence_from_logs(logs, max_recent=8, max_threads=20)
    
    versions = list_dataset_versions()
    dataset_version = "v3" if "v3" in versions else ("v2" if "v2" in versions else "v1")
    benchmark = None
    # Keep admin login/dashboard entry fast: avoid expensive calibration/autotune
    # computations during initial page render. Dedicated buttons/endpoints trigger
    # these analyses on demand.
    calibration = None
    autotune = None
    eager_analysis = str(os.getenv("DASHBOARD_EAGER_ANALYSIS", "0")).lower() in {"1", "true", "yes"}
    if eager_analysis:
        from app.privacy_calibration import calibrate_policy_thresholds
        from app.privacy_autotune import recommend_thresholds_from_audit

        calibration = calibrate_policy_thresholds(dataset_version=dataset_version, split="validation")
        autotune = recommend_thresholds_from_audit()
    history_mgr = get_benchmark_history_manager()
    history = history_mgr.list_runs(limit=20)
    return render_dashboard(
        logs=logs,
        benchmark=benchmark,
        calibration=calibration,
        autotune=autotune,
        benchmark_history=history,
        policy_thresholds=get_policy_thresholds(),
        dataset_version=dataset_version,
        available_dataset_versions=versions,
        initial_token=request.args.get("token"),
        latest_dispatch_proof=latest_dispatch_proof,
        recent_sessions=recent_sessions,
        sanitized_threads=sanitized_threads[:20],
    ), 200


@bp.route('/evidence', methods=['GET'])
def evidence():
    if not _is_admin_request(request):
        return jsonify({"status": "denied", "message": "Admin role required"}), 403

    limit = max(50, min(1200, int(request.args.get("limit", 400))))
    logs = _query_audit_logs(limit=limit)
    recent_sessions, sanitized_threads = _build_evidence_from_logs(logs, max_recent=40, max_threads=120)
    sessions = [
        {
            "user_identity": thread.get("user_identity"),
            "user_name": thread.get("user_name"),
            "session_id": thread.get("session_id"),
            "latest_ts": thread.get("latest_ts"),
            "turns": thread.get("turns", 0),
            "message_count": thread.get("message_count", 0),
            "open_url": thread.get("open_url"),
        }
        for thread in sanitized_threads
    ]
    return jsonify(
        {"status": "ok", "recent_sessions": recent_sessions, "sessions": sessions, "sanitized_threads": sanitized_threads}
    ), 200


@bp.route('/evidence/session', methods=['GET'])
def evidence_session():
    if not _is_admin_request(request):
        return redirect(url_for("module3.landing"))

    user_identity = str(request.args.get("user") or request.args.get("user_identity") or "").strip().lower()
    session_id = str(request.args.get("session") or request.args.get("session_id") or "").strip()
    if not user_identity or not session_id:
        return redirect(url_for("module4.dashboard"))

    logs = _query_audit_logs(limit=1500)
    _, sanitized_threads = _build_evidence_from_logs(logs, max_recent=200, max_threads=200)
    selected = next(
        (
            thread
            for thread in sanitized_threads
            if str(thread.get("user_identity") or "").strip().lower() == user_identity
            and str(thread.get("session_id") or "").strip() == session_id
        ),
        None,
    )
    sessions = [
        {
            "user_identity": thread.get("user_identity"),
            "user_name": thread.get("user_name"),
            "session_id": thread.get("session_id"),
            "latest_ts": thread.get("latest_ts"),
            "turns": thread.get("turns", 0),
            "message_count": thread.get("message_count", 0),
            "open_url": thread.get("open_url"),
        }
        for thread in sanitized_threads[:80]
    ]
    return render_template("evidence_session.html", thread=selected, sessions=sessions), 200


# Immutability note:
# In production, to make audit records tamper-evident you would:
# - Sign each audit record with an HMAC or public-key signature stored separately, or
# - Append records to a cloud-native append-only audit log (e.g., GCP/AWS audit services) or
# - Use a write-once storage backend (immutable object storage) and store hashes on a blockchain or key-value store
# This code includes the comment and would be extended to include signing/verifiable storage in production.
