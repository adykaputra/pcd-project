from flask import Blueprint, request, jsonify
from app.audit import get_manager
from datetime import datetime, timedelta

bp = Blueprint('module4', __name__, url_prefix='/audit')


def _is_admin_request(req):
    # Prefer JWT-based Authorization header: Bearer <token>
    auth = req.headers.get('Authorization')
    if auth and auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1]
        import os
        import jwt
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
    # Dashboard optionally takes a token query param for the frontend to call /audit/summary
    from .dashboard import render_dashboard
    import sqlite3
    
    # Fetch recent audit logs to display
    mgr = get_manager()
    conn = mgr._connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, ts, event_type, request_id, user_role, endpoint, message, 
               count_id, count_phone, count_email, winning_tool, 
               tool_a_counts, tool_b_counts, tool_c_counts, signature
        FROM audit_events 
        ORDER BY ts DESC 
        LIMIT 100
    """)
    rows = cur.fetchall()
    conn.close()
    
    # Convert rows to dict-like objects for template rendering
    logs = []
    for row in rows:
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
        })
    
    return render_dashboard(logs=logs), 200


# Immutability note:
# In production, to make audit records tamper-evident you would:
# - Sign each audit record with an HMAC or public-key signature stored separately, or
# - Append records to a cloud-native append-only audit log (e.g., GCP/AWS audit services) or
# - Use a write-once storage backend (immutable object storage) and store hashes on a blockchain or key-value store
# This code includes the comment and would be extended to include signing/verifiable storage in production.
