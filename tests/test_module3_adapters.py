import pytest
import requests

from app.module3.adapters import OllamaAdapter, get_adapter


def test_get_adapter_supports_ollama():
    adapter = get_adapter(provider="ollama", model="llama3.2:3b")
    assert isinstance(adapter, OllamaAdapter)
    assert adapter.provider_name == "ollama"


def test_ollama_adapter_parses_chat_response(monkeypatch):
    adapter = OllamaAdapter(model="llama3.2:3b")

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {"content": "Hello from local model"},
                "prompt_eval_count": 12,
                "eval_count": 34,
            }

    monkeypatch.setattr("app.module3.adapters.requests.post", lambda *args, **kwargs: DummyResponse())
    result = adapter.send_prompt("Hello")
    assert result["provider"] == "ollama"
    assert "Hello from local model" in result["text"]
    assert result["usage"]["total_tokens"] == 46


def test_ollama_adapter_raises_runtime_on_http_error(monkeypatch):
    adapter = OllamaAdapter(model="llama3.2:3b")

    def _boom(*args, **kwargs):
        raise requests.RequestException("connection refused")

    monkeypatch.setattr("app.module3.adapters.requests.post", _boom)
    with pytest.raises(RuntimeError):
        adapter.send_prompt("Hello")
