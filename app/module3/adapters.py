"""LLM adapter implementations for online and offline/demo usage."""
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

import requests


class BaseLLMAdapter(ABC):
    def __init__(self, model: Optional[str] = None, **kwargs):
        self.model = model
        self.provider_name = "base"

    @abstractmethod
    def send_prompt(self, prompt: str) -> Dict[str, Any]:
        """Send the prompt to the LLM and return a dict containing at least:
        - 'text': str (model's generated text)
        - 'usage': dict (optional tokens usage info)
        """
        raise NotImplementedError


class OpenAIAdapter(BaseLLMAdapter):
    def __init__(self, model: Optional[str] = None, **kwargs):
        super().__init__(model=model, **kwargs)
        self.provider_name = "openai"
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Lazy import to avoid hard dependency at import time
        try:
            import openai  # type: ignore
            self._openai = openai
        except Exception:
            self._openai = None

    def is_available(self) -> bool:
        return self._openai is not None and bool(self.api_key)

    def send_prompt(self, prompt: str) -> Dict[str, Any]:
        # If openai SDK/key is not available, raise an informative error.
        if not self.is_available():
            raise RuntimeError("OpenAI provider unavailable: missing SDK or OPENAI_API_KEY")

        # Support both OpenAI SDK v1 and legacy SDK APIs.
        model_name = self.model or os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
        if hasattr(self._openai, "OpenAI"):
            try:
                client = self._openai.OpenAI(api_key=self.api_key)
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = ""
                if getattr(resp, "choices", None):
                    message = resp.choices[0].message
                    text = getattr(message, "content", "") or ""
                usage_obj = getattr(resp, "usage", None)
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                    "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                    "total_tokens": getattr(usage_obj, "total_tokens", None),
                } if usage_obj else {}
                return {"text": text, "usage": usage}
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"OpenAI chat completion failed for model '{model_name}': {exc}") from exc

        # Legacy openai-python path.
        try:
            self._openai.api_key = self.api_key
            resp = self._openai.ChatCompletion.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            choices = resp.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""
            usage = resp.get("usage", {})
            return {"text": text, "usage": usage}
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"OpenAI chat completion failed for model '{model_name}': {exc}") from exc


class MockAdapter(BaseLLMAdapter):
    """Offline-safe adapter for local demos and CI."""

    def __init__(self, model: Optional[str] = None, **kwargs):
        super().__init__(model=model or "mock-privacy-demo", **kwargs)
        self.provider_name = "mock"

    def send_prompt(self, prompt: str) -> Dict[str, Any]:
        preview = (prompt or "").strip().replace("\n", " ")
        if len(preview) > 180:
            preview = f"{preview[:180]}..."
        return {
            "text": (
                "Mock provider response (offline mode). "
                f"Your tokenized prompt was processed safely: {preview}"
            ),
            "usage": {"prompt_tokens": len((prompt or "").split()), "completion_tokens": 18, "total_tokens": len((prompt or "").split()) + 18},
            "provider": "mock",
            "offline_mode": True,
        }


class OllamaAdapter(BaseLLMAdapter):
    """Local-model adapter backed by an Ollama server."""

    def __init__(self, model: Optional[str] = None, **kwargs):
        default_model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2:3b")
        super().__init__(model=model or default_model, **kwargs)
        self.provider_name = "ollama"
        self.base_url = (os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434") or "").rstrip("/")
        self.timeout_s = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))

    def send_prompt(self, prompt: str) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        try:
            response = requests.post(endpoint, json=payload, timeout=self.timeout_s)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Ollama request failed at {endpoint}. Ensure Ollama is running and model '{self.model}' is available: {exc}"
            ) from exc

        body = response.json()
        text = ""
        if isinstance(body.get("message"), dict):
            text = body["message"].get("content") or ""
        if not text:
            text = body.get("response") or ""
        usage = {
            "prompt_tokens": body.get("prompt_eval_count"),
            "completion_tokens": body.get("eval_count"),
            "total_tokens": (body.get("prompt_eval_count") or 0) + (body.get("eval_count") or 0),
        }
        return {"text": text, "usage": usage, "provider": "ollama"}


def get_adapter(
    provider: str = "openai",
    model: Optional[str] = None,
    *,
    fallback_to_mock: bool = True,
    **kwargs,
) -> BaseLLMAdapter:
    provider = (provider or "openai").lower()
    if provider == "openai":
        adapter = OpenAIAdapter(model=model, **kwargs)
        if adapter.is_available():
            return adapter
        if fallback_to_mock:
            return MockAdapter(model=model, **kwargs)
        raise RuntimeError("OpenAI provider unavailable and fallback disabled")
    if provider == "mock":
        return MockAdapter(model=model, **kwargs)
    if provider == "ollama":
        return OllamaAdapter(model=model, **kwargs)
    raise ValueError(f"Unknown provider: {provider}")
