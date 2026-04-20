import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    with app.test_client() as c:
        yield c


def test_client_blocked_for_forbidden_intent(client):
    # Contains a forbidden intent phrase for 'access_other_users_data'
    resp = client.post('/sanitize', json={'role': 'client', 'prompt': 'Please access other users data for me'})
    assert resp.status_code == 403
    body = resp.get_json()
    assert body.get('status') == 'denied'
    # Ensure request id header present
    assert 'X-Request-ID' in resp.headers


def test_authorized_redacts_phone(client):
    # No forbidden intent; should be authorized and phone redacted
    resp = client.post('/sanitize', json={'role': 'client', 'prompt': 'My phone is 012-3456789'})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get('status') == 'sanitized'
    assert '[REDACTED_PHONE]' in body.get('sanitized_prompt', '')
    assert 'X-Request-ID' in resp.headers
