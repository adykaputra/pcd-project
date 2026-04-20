"""LLM adapter skeleton and a simple OpenAI adapter implementation."""
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseLLMAdapter(ABC):
    def __init__(self, model: Optional[str] = None, **kwargs):
        self.model = model or "default"

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
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Lazy import to avoid hard dependency at import time
        try:
            import openai  # type: ignore
            self._openai = openai
            if self.api_key:
                self._openai.api_key = self.api_key
        except Exception:
            self._openai = None

    def send_prompt(self, prompt: str) -> Dict[str, Any]:
        # If openai SDK is not available, raise an informative error
        if self._openai is None:
            raise RuntimeError("OpenAI SDK is not available in the environment")

        # Example usage: call the ChatCompletion API (model dependent)
        # This is a minimal implementation; production code should handle retries, timeouts, etc.
        resp = self._openai.ChatCompletion.create(
            model=self.model or "gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text and usage
        choices = resp.get("choices", [])
        text = choices[0]["message"]["content"] if choices else ""
        usage = resp.get("usage", {})
        return {"text": text, "usage": usage}


def get_adapter(provider: str = "openai", model: Optional[str] = None, **kwargs) -> BaseLLMAdapter:
    provider = (provider or "openai").lower()
    if provider == "openai":
        return OpenAIAdapter(model=model, **kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")
