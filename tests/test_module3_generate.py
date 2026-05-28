import pytest
import re
from unittest.mock import Mock
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    with app.test_client() as c:
        yield c


def test_generate_success_uses_adapter_and_logs_usage(client, monkeypatch, caplog):
    # Mock adapter to ensure we don't call external API
    mock_adapter = Mock()
    mock_adapter.send_prompt.return_value = {
        'text': 'This is a mock generation',
        'usage': {'total_tokens': 42}
    }

    # Patch the adapter factory to return our mock
    monkeypatch.setattr('app.module3.adapters.get_adapter', lambda provider, model=None: mock_adapter)

    # Ensure INFO logs are captured
    import logging
    caplog.set_level(logging.INFO)

    # Provide a clean prompt; endpoint sanitizes at send-time.
    resp = client.post('/generate', json={'prompt': 'Hello world', 'provider': 'openai', 'model': 'mock-model'})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get('status') == 'ok'
    assert body.get('response') == 'This is a mock generation'

    # Ensure adapter was called with the sanitized prompt
    mock_adapter.send_prompt.assert_called_once_with('Hello world')
    assert body.get('redaction_applied') is False

    # Check that token usage was logged
    assert any('[LLM_PROXY] Token usage' in r.getMessage() for r in caplog.records)
    assert 'X-Request-ID' in resp.headers

def test_generate_auto_redacts_pii_before_adapter(client, monkeypatch):
    # Mock adapter to ensure we don't call external API
    mock_adapter = Mock()
    mock_adapter.send_prompt.return_value = {
        'text': 'Safe response',
        'usage': {}
    }

    monkeypatch.setattr('app.module3.adapters.get_adapter', lambda provider, model=None: mock_adapter)

    raw_prompt = 'My phone is 012-3456789 and email is alice@example.com'
    resp = client.post('/generate', json={'prompt': raw_prompt, 'provider': 'openai'})

    body = resp.get_json()
    assert resp.status_code == 200
    assert body.get('status') == 'ok'
    assert body.get('response') == 'Safe response'
    assert body.get('redaction_applied') is True
    assert body.get('tokenization', {}).get('applied') is True

    sent_prompt = mock_adapter.send_prompt.call_args[0][0]
    assert re.search(r"\[PHONE_[A-F0-9]{12}\]", sent_prompt)
    assert re.search(r"\[EMAIL_[A-F0-9]{12}\]", sent_prompt)
    assert '012-3456789' not in sent_prompt
    assert 'alice@example.com' not in sent_prompt


def test_generate_accepts_legacy_sanitized_prompt_field(client, monkeypatch):
    mock_adapter = Mock()
    mock_adapter.send_prompt.return_value = {'text': 'Legacy ok', 'usage': {}}
    monkeypatch.setattr('app.module3.adapters.get_adapter', lambda provider, model=None: mock_adapter)

    resp = client.post('/generate', json={'sanitized_prompt': 'Hello world'})
    assert resp.status_code == 200
    assert resp.get_json().get('status') == 'ok'
    mock_adapter.send_prompt.assert_called_once_with('Hello world')


def test_generate_rejects_when_prompt_missing(client):
    resp = client.post('/generate', json={'provider': 'openai'})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body.get('status') == 'denied'


def test_generate_defaults_to_mock_provider_for_offline_demo(client):
    resp = client.post('/generate', json={'prompt': 'Explain hashing in simple terms.'})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get('status') == 'ok'
    assert body.get('provider') == 'mock'
    assert body.get('offline_mode') is True


def test_generate_unknown_provider_returns_400(client):
    resp = client.post('/generate', json={'prompt': 'Hello world', 'provider': 'unknown-provider'})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body.get('status') == 'denied'
    assert 'Unknown provider' in body.get('message', '')


def test_detokenize_requires_admin(client):
    resp = client.post('/detokenize', json={'text': '[EMAIL_ABCDEF123456]'})
    assert resp.status_code == 403
    assert resp.get_json().get('status') == 'denied'


def test_detokenize_admin_round_trip(client, monkeypatch):
    mock_adapter = Mock()
    mock_adapter.send_prompt.return_value = {'text': 'ok', 'usage': {}}
    monkeypatch.setattr('app.module3.adapters.get_adapter', lambda provider, model=None: mock_adapter)

    raw_prompt = 'Email me at ali@example.com'
    gen_resp = client.post('/generate', json={'prompt': raw_prompt, 'provider': 'openai'})
    assert gen_resp.status_code == 200
    tokenized_prompt = mock_adapter.send_prompt.call_args[0][0]

    login = client.post('/login', json={'password': 'admin-pass'})
    token = login.get_json().get('token')
    detok_resp = client.post(
        '/detokenize',
        json={'text': tokenized_prompt},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert detok_resp.status_code == 200
    body = detok_resp.get_json()
    assert body.get('status') == 'ok'
    assert body.get('detokenized_text') == raw_prompt
