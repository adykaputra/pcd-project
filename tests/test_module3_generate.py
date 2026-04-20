import pytest
from unittest.mock import Mock
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    with app.test_client() as c:
        yield c


def test_generate_rejects_prompt_with_pii(client):
    # If sanitized_prompt still contains PII, endpoint must reject with 400
    resp = client.post('/generate', json={'sanitized_prompt': 'My phone is 012-3456789'})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body.get('status') == 'denied' or 'PII' in body.get('message', '')
    assert 'X-Request-ID' in resp.headers


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

    # Provide a clean, sanitized prompt
    resp = client.post('/generate', json={'sanitized_prompt': 'Hello world', 'provider': 'openai', 'model': 'mock-model'})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get('status') == 'ok'
    assert body.get('response') == 'This is a mock generation'

    # Ensure adapter was called with the sanitized prompt
    mock_adapter.send_prompt.assert_called_once_with('Hello world')

    # Check that token usage was logged
    assert any('[LLM_PROXY] Token usage' in r.getMessage() for r in caplog.records)
    assert 'X-Request-ID' in resp.headers

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

    # Provide a clean, sanitized prompt
    resp = client.post('/generate', json={'sanitized_prompt': 'Hello world', 'provider': 'openai', 'model': 'mock-model'})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get('status') == 'ok'
    assert body.get('response') == 'This is a mock generation'

    # Ensure adapter was called with the sanitized prompt
    mock_adapter.send_prompt.assert_called_once_with('Hello world')

    # Check that token usage was logged
    assert any('[LLM_PROXY] Token usage' in r.getMessage() for r in caplog.records)
