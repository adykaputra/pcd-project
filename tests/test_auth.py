import pytest


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
