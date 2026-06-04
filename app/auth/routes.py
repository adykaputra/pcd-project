from flask import Blueprint, request, jsonify, current_app, redirect, url_for
import os
import jwt
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('auth', __name__)

# Configuration: admin credentials, JWT, and local auth DB.
JWT_SECRET = os.getenv('JWT_SECRET', 'very-secret')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin-pass')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@privacyfirewall.local').strip().lower()
TOKEN_EXP_MINUTES = int(os.getenv('TOKEN_EXP_MINUTES', '60'))
AUTH_DB_PATH = Path(os.getenv("AUTH_DB_PATH", "data/auth_users.db"))
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GOOGLE_DISCOVERY_URL = os.getenv(
    "GOOGLE_DISCOVERY_URL",
    "https://accounts.google.com/.well-known/openid-configuration",
)
GOOGLE_SCOPE = os.getenv("GOOGLE_SCOPE", "openid email profile")


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


def _build_login_result(*, role: str, email: str, name: str):
    payload = _build_token_payload(role=role, email=email, name=name)
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    redirect_url = (
        f"/audit/dashboard?token={token}"
        if role == "admin"
        else f"/client?token={token}"
    )
    return {
        "status": "ok",
        "token": token,
        "role": role,
        "name": name,
        "email": email,
        "redirect_url": redirect_url,
    }


def _issue_login_response(*, role: str, email: str, name: str):
    return jsonify(_build_login_result(role=role, email=email, name=name)), 200


def _issue_login_redirect(*, role: str, email: str, name: str):
    result = _build_login_result(role=role, email=email, name=name)
    return redirect(result["redirect_url"])


def _upsert_google_user(email: str, display_name: str) -> Tuple[str, str]:
    normalized_email = email.strip().lower()
    if normalized_email == ADMIN_EMAIL:
        return "admin", "Admin"

    _init_auth_db()
    fallback_name = normalized_email.split("@")[0]
    safe_name = (display_name or fallback_name).strip()[:80] or "User"

    conn = _connect_auth_db()
    try:
        row = conn.execute(
            "SELECT email, display_name, role FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()

        if row:
            current_name = (row["display_name"] or "").strip()
            if current_name != safe_name:
                conn.execute(
                    "UPDATE users SET display_name = ? WHERE email = ?",
                    (safe_name, normalized_email),
                )
                conn.commit()
            return row["role"] or "user", safe_name

        conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, role, created_at)
            VALUES (?, ?, ?, 'user', ?)
            """,
            (
                normalized_email,
                generate_password_hash(f"google-oauth-{os.urandom(8).hex()}"),
                safe_name,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return "user", safe_name


def _get_google_oauth_client() -> Tuple[Optional[object], Optional[str]]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None, "Google Sign-In is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."

    try:
        from authlib.integrations.flask_client import OAuth
    except ImportError:
        return None, "Google Sign-In requires the Authlib plugin. Install with `pip install authlib`."

    oauth = current_app.extensions.get("privacy_oauth")
    if oauth is None:
        oauth = OAuth()
        oauth.init_app(current_app)
        current_app.extensions["privacy_oauth"] = oauth

    google = oauth.create_client("google")
    if google is None:
        oauth.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url=GOOGLE_DISCOVERY_URL,
            client_kwargs={"scope": GOOGLE_SCOPE},
        )
        google = oauth.create_client("google")

    return google, None


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
    google, error = _get_google_oauth_client()
    if not google:
        return redirect(url_for("module3.landing", auth_error=error))

    callback_url = url_for("auth.google_callback", _external=True)
    return google.authorize_redirect(callback_url)


@bp.route('/auth/google/callback', methods=['GET'])
def google_callback():
    google, error = _get_google_oauth_client()
    if not google:
        return redirect(url_for("module3.landing", auth_error=error))

    oauth_error = request.args.get("error")
    if oauth_error:
        return redirect(url_for("module3.landing", auth_error=f"Google OAuth error: {oauth_error}"))

    try:
        token = google.authorize_access_token()
        user_info = token.get("userinfo") if isinstance(token, dict) else None
        if not user_info:
            user_info_response = google.get("userinfo")
            user_info = user_info_response.json() if user_info_response else {}
    except Exception:
        current_app.logger.exception("Google callback token exchange failed", extra={"event_type": "SECURITY_DENIED"})
        return redirect(url_for("module3.landing", auth_error="Google sign-in failed. Please try again."))

    email = str((user_info or {}).get("email") or "").strip().lower()
    if not EMAIL_PATTERN.match(email):
        return redirect(url_for("module3.landing", auth_error="Google account did not return a valid email."))

    name = str((user_info or {}).get("name") or (user_info or {}).get("given_name") or "").strip()
    role, display_name = _upsert_google_user(email=email, display_name=name)
    return _issue_login_redirect(role=role, email=email, name=display_name)
