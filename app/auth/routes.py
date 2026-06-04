from flask import Blueprint, request, jsonify, current_app
import os
import jwt
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('auth', __name__)

# Configuration: admin credentials, JWT, and local auth DB.
JWT_SECRET = os.getenv('JWT_SECRET', 'very-secret')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin-pass')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@privacyfirewall.local').strip().lower()
TOKEN_EXP_MINUTES = int(os.getenv('TOKEN_EXP_MINUTES', '60'))
AUTH_DB_PATH = Path(os.getenv("AUTH_DB_PATH", "data/auth_users.db"))
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _connect_auth_db():
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_auth_db():
    conn = _connect_auth_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _build_token_payload(*, role: str, email: str, name: str):
    now = datetime.utcnow()
    return {
        "role": role,
        "sub": email,
        "name": name,
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_EXP_MINUTES),
    }


def _issue_login_response(*, role: str, email: str, name: str):
    payload = _build_token_payload(role=role, email=email, name=name)
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    redirect_url = (
        f"/audit/dashboard?token={token}"
        if role == "admin"
        else f"/client?token={token}"
    )
    return jsonify(
        {
            "status": "ok",
            "token": token,
            "role": role,
            "name": name,
            "email": email,
            "redirect_url": redirect_url,
        }
    ), 200


@bp.route('/signup', methods=['POST'])
def signup():
    _init_auth_db()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "denied", "message": "Invalid request: JSON body required"}), 400

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    display_name = str(data.get("name") or data.get("display_name") or "").strip()

    if not EMAIL_PATTERN.match(email):
        return jsonify({"status": "denied", "message": "Please provide a valid email address"}), 400
    if email == ADMIN_EMAIL:
        return jsonify({"status": "denied", "message": "This email is reserved for admin access"}), 403
    if len(password) < 8:
        return jsonify({"status": "denied", "message": "Password must be at least 8 characters"}), 400
    if not display_name:
        display_name = email.split("@")[0]

    conn = _connect_auth_db()
    try:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, role, created_at)
            VALUES (?, ?, ?, 'user', ?)
            """,
            (
                email,
                generate_password_hash(password),
                display_name,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"status": "denied", "message": "Account already exists. Please sign in."}), 409
    finally:
        conn.close()

    return jsonify({"status": "ok", "message": "Account created. Please sign in."}), 201


@bp.route('/login', methods=['POST'])
def login():
    _init_auth_db()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "denied", "message": "Invalid request: JSON body required"}), 400

    # Backward compatible admin login: password-only payload.
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    if not email:
        if password == ADMIN_PASSWORD:
            return _issue_login_response(role="admin", email=ADMIN_EMAIL, name="Admin")
        if password:
            current_app.logger.warning('Failed login attempt', extra={"event_type": "SECURITY_DENIED"})
            return jsonify({"status": "denied", "message": "Invalid credentials"}), 403

    if not email or not password:
        return jsonify({"status": "denied", "message": "Email and password are required"}), 400

    if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
        return _issue_login_response(role="admin", email=ADMIN_EMAIL, name="Admin")

    conn = _connect_auth_db()
    try:
        row = conn.execute(
            "SELECT email, password_hash, display_name, role FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()

    if not row or not check_password_hash(row["password_hash"], password):
        current_app.logger.warning('Failed login attempt', extra={"event_type": "SECURITY_DENIED"})
        return jsonify({"status": "denied", "message": "Invalid credentials"}), 403

    return _issue_login_response(
        role=row["role"],
        email=row["email"],
        name=row["display_name"],
    )


@bp.route('/auth/google/start', methods=['GET'])
def google_start():
    return jsonify(
        {
            "status": "not_configured",
            "message": (
                "Google Sign-In requires OAuth setup and an auth plugin such as Authlib. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET before enabling."
            ),
        }
    ), 501
