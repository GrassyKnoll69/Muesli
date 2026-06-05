from __future__ import annotations

from typing import Protocol

import httpx

from muesli_engine import secrets
from muesli_engine.config import Settings
from muesli_engine.enhance.templates import build_prompt

_DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-3-5-sonnet-latest"}
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class EnhancementBackend(Protocol):
    def enhance(self, template_prompt: str, rough_notes: str, transcript: str) -> str:
        ...


class OllamaBackend:
    def __init__(self, model: str, host: str = "http://localhost:11434", client=None):
        self.model = model
        if client is None:
            import ollama

            client = ollama.Client(host=host)
        self.client = client

    def enhance(self, template_prompt: str, rough_notes: str, transcript: str) -> str:
        prompt = build_prompt(template_prompt, rough_notes, transcript)
        result = self.client.generate(model=self.model, prompt=prompt)
        return result["response"].strip()


class CloudBackend:
    def __init__(self, provider: str, api_key: str, model: str,
                 max_tokens: int = 4096, post=None):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self._post = post or httpx.post

    def enhance(self, template_prompt: str, rough_notes: str, transcript: str) -> str:
        prompt = build_prompt(template_prompt, rough_notes, transcript)
        if self.provider == "openai":
            resp = self._post(
                _OPENAI_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        if self.provider == "anthropic":
            resp = self._post(
                _ANTHROPIC_URL,
                headers={"x-api-key": self.api_key,
                         "anthropic-version": _ANTHROPIC_VERSION},
                json={"model": self.model, "max_tokens": self.max_tokens,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"].strip()
        raise ValueError(f"unsupported cloud provider: {self.provider}")


def get_backend(settings: Settings, client=None) -> EnhancementBackend:
    if settings.enhancement_backend == "cloud":
        provider = settings.cloud_provider
        if not provider:
            raise ValueError("cloud backend requires a cloud_provider")
        key = settings.cloud_api_key or secrets.get_api_key(provider)
        if not key:
            raise ValueError(f"No API key set for {provider}; add one in Settings.")
        model = settings.cloud_model or _DEFAULT_MODELS.get(provider, "")
        return CloudBackend(provider, key, model=model)
    return OllamaBackend(settings.ollama_model, settings.ollama_host, client=client)


def validate_cloud(provider: str, key: str, model: str, post=None) -> tuple[bool, str]:
    """Make one cheap call to confirm the key+model work. Never raises."""
    post = post or httpx.post
    try:
        if provider == "openai":
            resp = post(
                _OPENAI_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "max_tokens": 1,
                      "messages": [{"role": "user", "content": "ping"}]},
                timeout=30,
            )
        elif provider == "anthropic":
            resp = post(
                _ANTHROPIC_URL,
                headers={"x-api-key": key, "anthropic-version": _ANTHROPIC_VERSION},
                json={"model": model, "max_tokens": 1,
                      "messages": [{"role": "user", "content": "ping"}]},
                timeout=30,
            )
        else:
            return False, f"unsupported provider: {provider}"
    except Exception as exc:  # network / timeout
        return False, str(exc)
    if resp.status_code == 200:
        return True, "Connection OK"
    return False, f"{resp.status_code}: {resp.text[:200]}"


def list_ollama_models(host: str = "http://localhost:11434", client=None) -> list[str]:
    """Best-effort list of installed Ollama model names; [] if unreachable."""
    try:
        if client is None:
            import ollama

            client = ollama.Client(host=host)
        data = client.list()
        models = data.get("models", []) if isinstance(data, dict) else getattr(data, "models", [])
        names = []
        for m in models:
            name = (m.get("name") or m.get("model")) if isinstance(m, dict) else getattr(m, "model", None)
            if name:
                names.append(name)
        return names
    except Exception:
        return []
