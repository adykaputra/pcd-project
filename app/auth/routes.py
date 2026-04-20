from flask import Blueprint, request, jsonify, current_app
import os
import jwt
from datetime import datetime, timedelta

bp = Blueprint('auth', __name__)

# Configuration: secret and hardcoded password (can be overridden by env)
JWT_SECRET = os.getenv('JWT_SECRET', 'very-secret')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin-pass')
TOKEN_EXP_MINUTES = int(os.getenv('TOKEN_EXP_MINUTES', '60'))


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "denied", "message": "Invalid request: JSON body required"}), 400

    password = data.get('password')
    if password != ADMIN_PASSWORD:
        current_app.logger.warning('Failed login attempt', extra={"event_type": "SECURITY_DENIED"})
        return jsonify({"status": "denied", "message": "Invalid credentials"}), 403

    now = datetime.utcnow()
    payload = {
        "role": "admin",
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_EXP_MINUTES),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')

    return jsonify({"status": "ok", "token": token}), 200
