import pytest
import sqlite3
from app import create_app
from app.audit import get_manager


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    with app.test_client() as c:
        yield c


def test_signatures_present_after_event(client):
    # Trigger an event
    r = client.post('/sanitize', json={'role': 'client', 'prompt': 'My IC 800101-01-1234 and email a@ex.com'})
    assert r.status_code == 200

    mgr = get_manager()
    conn = sqlite3.connect(str(mgr.db_path))
    cur = conn.cursor()
    cur.execute('SELECT id, signature FROM audit_events ORDER BY id DESC LIMIT 1')
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[1] is not None and len(row[1]) > 10


def test_integrity_detects_tampering(client):
    # Trigger an event
    r = client.post('/sanitize', json={'role': 'client', 'prompt': 'My IC 800101-01-1234 and email a@ex.com'})
    assert r.status_code == 200

    mgr = get_manager()
    # Tamper with the DB: change the message of the most recent row
    conn = sqlite3.connect(str(mgr.db_path))
    cur = conn.cursor()
    cur.execute('SELECT id FROM audit_events ORDER BY id DESC LIMIT 1')
    rid = cur.fetchone()[0]
    cur.execute('UPDATE audit_events SET message = ? WHERE id = ?', ('tampered message', rid))
    conn.commit()
    conn.close()

    # Acquire admin token
    r2 = client.post('/login', json={'password': 'admin-pass'})
    token = r2.get_json().get('token')

    # Now call summary; it should detect tampering
    r3 = client.get('/audit/summary', headers={'Authorization': f'Bearer {token}'})
    assert r3.status_code == 200
    body = r3.get_json()
    assert body['summary']['integrity_ok'] is False
    assert isinstance(body['summary']['tampered_ids'], list)
    assert len(body['summary']['tampered_ids']) >= 1
