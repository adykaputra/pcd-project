import pytest
from uuid import uuid4


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
