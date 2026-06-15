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
    def send_prompt(self, prompt: str, *, images: Optional[list[str]] = None) -> Dict[str, Any]:
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

    def send_prompt(self, prompt: str, *, images: Optional[list[str]] = None) -> Dict[str, Any]:
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

    def _compose_reply(self, prompt: str) -> str:
        text = (prompt or "").strip()
        lower = text.lower()
        if not text:
            return "Hi! Tell me what you want help with and I will respond right away."
        if any(greet in lower for greet in ("hi", "hello", "hey", "salam")):
            return "Hey! I am ready to help. Ask me anything and I will reply in a clear, practical way."
        if "your name" in lower or "who are you" in lower:
            return "I am your Privacy Firewall Assistant. I help with answers while protecting sensitive information."
        if "my name" in lower:
            return "Nice to meet you. I will keep your personal identifiers protected while we chat."
        if "summarize" in lower or "summary" in lower:
            return "Summary: the key idea is to reduce risk, keep data private, and apply clear controls before sharing with AI."
        if "what" in lower and "safe" in lower and "data" in lower:
            return (
                "Share non-sensitive context only. Avoid IDs, phone numbers, private addresses, credentials, "
                "and anything that can identify a real person."
            )
        if "?" in text:
            return (
                "Good question. Based on what you asked, start with a short objective, include only necessary context, "
                "and avoid private identifiers. I can refine this further if you want."
            )
        preview = text.replace("\n", " ")
        if len(preview) > 180:
            preview = f"{preview[:180]}..."
        return f"I received your request: \"{preview}\". I can now help you turn it into a clearer, safer prompt."

    def send_prompt(self, prompt: str, *, images: Optional[list[str]] = None) -> Dict[str, Any]:
        attachment_note = ""
        if images:
            attachment_note = " I also received image attachments and treated them as case evidence context."
        return {
            "text": f"{self._compose_reply(prompt)}{attachment_note}",
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
        self.vision_model = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")
        base_url = (os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434") or "").rstrip("/")
        base_urls_raw = (os.getenv("OLLAMA_BASE_URLS", "") or "").strip()
        candidates = []
        if base_urls_raw:
            candidates.extend([item.strip().rstrip("/") for item in base_urls_raw.split(",") if item.strip()])
        if base_url:
            candidates.append(base_url)
        # Docker/WSL reliability fallback: host gateway address can work even if
        # host.docker.internal is unavailable in some host setups.
        if "http://host.docker.internal:11434" not in candidates:
            candidates.append("http://host.docker.internal:11434")
        if "http://172.17.0.1:11434" not in candidates:
            candidates.append("http://172.17.0.1:11434")
        if "http://localhost:11434" not in candidates:
            candidates.append("http://localhost:11434")
        # Preserve order while removing duplicates.
        deduped = []
        for item in candidates:
            if item not in deduped:
                deduped.append(item)
        self.base_urls = deduped
        self.base_url = self.base_urls[0]
        self.timeout_s = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
        # Keep connection failures fast so chat UI does not appear frozen.
        self.connect_timeout_s = int(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "5"))

    def send_prompt(self, prompt: str, *, images: Optional[list[str]] = None) -> Dict[str, Any]:
        model_name = self.model
        image_payloads = list(images or [])
        if image_payloads and self.vision_model:
            model_name = self.vision_model
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if image_payloads:
            payload["messages"][0]["images"] = image_payloads
        last_exc = None
        response = None
        endpoint = ""
        for base in self.base_urls:
            endpoint = f"{base}/api/chat"
            try:
                response = requests.post(
                    endpoint,
                    json=payload,
                    timeout=(self.connect_timeout_s, self.timeout_s),
                )
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                last_exc = exc
                response = None
                continue
        if response is None:
            raise RuntimeError(
                f"Ollama request failed on all endpoints {self.base_urls}. Ensure Ollama is running and model '{model_name}' is available. Last error: {last_exc}"
            ) from last_exc

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
        return {"text": text, "usage": usage, "provider": "ollama", "model": model_name}


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
