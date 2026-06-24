"""Request middleware utilities (request id, role extraction)."""
from uuid import uuid4
import hashlib
import os
import jwt
from flask import g, request


def init_request_middleware(app):
    def _extract_request_token():
        auth = request.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            return auth.split(" ", 1)[1].strip()
        cookie_token = (request.cookies.get("pf_session") or "").strip()
        if cookie_token:
            return cookie_token
        query_token = (request.args.get("token") or "").strip()
        if query_token:
            return query_token
        return ""

    @app.before_request
    def attach_request_id_and_role():
        # Generate a unique request id for every incoming request
        rid = str(uuid4())
        g.request_id = rid

        # Try to extract role from JSON body if present
        try:
            data = request.get_json(silent=True)
            role = data.get('role') if isinstance(data, dict) else None
        except Exception:
            role = None

        g.user_role = role
        g.user_identity = None
        g.user_name = None
        g.session_id = None

        token = _extract_request_token()
        if token:
            # Deterministic short session fingerprint for audit readability.
            g.session_id = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
            try:
                secret = os.getenv("JWT_SECRET", "very-secret")
                payload = jwt.decode(token, secret, algorithms=["HS256"])
                token_role = payload.get("role")
                if token_role:
                    g.user_role = token_role
                g.user_identity = payload.get("sub")
                g.user_name = payload.get("name")
                if payload.get("jti"):
                    g.session_id = str(payload.get("jti"))
            except Exception:
                # Ignore malformed/expired tokens for middleware context.
                pass

        g.endpoint = request.path

    @app.after_request
    def add_request_id_header(response):
        # Ensure the response has the X-Request-ID header
        try:
            response.headers['X-Request-ID'] = g.request_id
        except Exception:
            # If no request context, ignore
            pass

        # Prevent browser history/cache from exposing protected pages after sign-out.
        try:
            path = request.path or ""
            if not path.startswith("/static/"):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
        except Exception:
            pass
        return response
