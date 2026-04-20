import pytest
from app import create_app
from datetime import datetime, timedelta


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    with app.test_client() as c:
        yield c


def test_admin_required_for_summary(client):
    r = client.get('/audit/summary')
    assert r.status_code == 403


def _get_admin_token(client):
    # Hardcoded password (matches ADMIN_PASSWORD default in auth/routes)
    r = client.post('/login', json={'password': 'admin-pass'})
    assert r.status_code == 200
    return r.get_json().get('token')


def test_audit_records_and_summary(client):
    # Trigger a PII redaction event
    r = client.post('/sanitize', json={'role': 'client', 'prompt': 'My IC 800101-01-1234 and email a@ex.com'})
    assert r.status_code == 200
    assert 'X-Request-ID' in r.headers

    # Trigger a denied attempt (forbidden intent)
    r2 = client.post('/verify', json={'role': 'client', 'prompt': 'access other users data'})
    assert r2.status_code == 403

    # Acquire admin token and query summary
    token = _get_admin_token(client)
    r3 = client.get('/audit/summary', headers={'Authorization': f'Bearer {token}'})
    assert r3.status_code == 200
    body = r3.get_json()
    assert body.get('status') == 'ok'

    summary = body.get('summary')
    assert summary['total_blocked_last_24h'] >= 1
    # At least one email and one id should be redacted
    assert summary['pii_redacted_last_24h']['malaysian_ic'] >= 1
    assert summary['pii_redacted_last_24h']['emails'] >= 1
    assert isinstance(summary['frequent_forbidden_intents'], list)


def test_dashboard_serves_html_and_accepts_token(client):
    token = _get_admin_token(client)
    r = client.get(f'/audit/dashboard?token={token}')
    assert r.status_code == 200
    assert 'Chart' in r.get_data(as_text=True)

