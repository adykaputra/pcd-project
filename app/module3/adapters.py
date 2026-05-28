"""LLM adapter implementations for online and offline/demo usage."""
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseLLMAdapter(ABC):
    def __init__(self, model: Optional[str] = None, **kwargs):
        self.model = model or "default"
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
        if hasattr(self._openai, "OpenAI"):
            client = self._openai.OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model=self.model or "gpt-4o-mini",
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

        # Legacy openai-python path.
        self._openai.api_key = self.api_key
        resp = self._openai.ChatCompletion.create(
            model=self.model or "gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
        )
        choices = resp.get("choices", [])
        text = choices[0]["message"]["content"] if choices else ""
        usage = resp.get("usage", {})
        return {"text": text, "usage": usage}


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
    raise ValueError(f"Unknown provider: {provider}")
