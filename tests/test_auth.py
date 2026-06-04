import pytest
import jwt
import os
from uuid import uuid4
from urllib.parse import urlparse, parse_qs


def test_login_success_and_failure(client):
    # Successful login with default password
    r = client.post('/login', json={'password': 'admin-pass'})
    assert r.status_code == 200
    body = r.get_json()
    assert body.get('status') == 'ok'
    assert 'token' in body

    # Failed login
    r2 = client.post('/login', json={'password': 'wrong'})
    assert r2.status_code == 403
    body2 = r2.get_json()
    assert body2.get('status') == 'denied'


def test_user_signup_then_login(client):
    email = f"new-user-{uuid4().hex[:8]}@example.com"
    signup = client.post(
        "/signup",
        json={"name": "Nadia", "email": email, "password": "strongpass123"},
    )
    assert signup.status_code == 201

    login = client.post("/login", json={"email": email, "password": "strongpass123"})
    assert login.status_code == 200
    body = login.get_json()
    assert body.get("role") == "user"
    assert body.get("redirect_url", "").startswith("/client?token=")


def test_google_start_redirects_to_landing_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(
        "app.auth.routes._get_google_oauth_client",
        lambda: (None, "Google Sign-In is not configured"),
    )
    resp = client.get("/auth/google/start")
    assert resp.status_code == 302
    assert "/?auth_error=" in resp.headers.get("Location", "")


def test_google_callback_routes_user_to_client(client, monkeypatch):
    class _FakeGoogle:
        def authorize_access_token(self):
            return {"userinfo": {"email": f"oauth-{uuid4().hex[:8]}@example.com", "name": "OAuth User"}}

        def get(self, _resource):
            raise AssertionError("userinfo fallback should not be called in this test")

    monkeypatch.setattr("app.auth.routes._get_google_oauth_client", lambda: (_FakeGoogle(), None))

    resp = client.get("/auth/google/callback?code=fake&state=fake")
    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    assert location.startswith("/client?token=")

    token = parse_qs(urlparse(location).query).get("token", [""])[0]
    payload = jwt.decode(token, os.getenv("JWT_SECRET", "very-secret"), algorithms=["HS256"])
    assert payload.get("role") == "user"
    assert payload.get("name") == "OAuth User"


def test_google_callback_routes_admin_to_dashboard(client, monkeypatch):
    admin_email = os.getenv("ADMIN_EMAIL", "admin@privacyfirewall.local")

    class _FakeGoogle:
        def authorize_access_token(self):
            return {"userinfo": {"email": admin_email, "name": "Admin"}}

        def get(self, _resource):
            raise AssertionError("userinfo fallback should not be called in this test")

    monkeypatch.setattr("app.auth.routes._get_google_oauth_client", lambda: (_FakeGoogle(), None))

    resp = client.get("/auth/google/callback?code=fake&state=fake")
    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    assert location.startswith("/audit/dashboard?token=")

    token = parse_qs(urlparse(location).query).get("token", [""])[0]
    payload = jwt.decode(token, os.getenv("JWT_SECRET", "very-secret"), algorithms=["HS256"])
    assert payload.get("role") == "admin"
