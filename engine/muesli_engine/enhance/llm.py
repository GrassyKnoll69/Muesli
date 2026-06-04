from __future__ import annotations

from typing import Protocol

from muesli_engine.config import Settings
from muesli_engine.enhance.templates import build_prompt


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
    def __init__(self, provider: str, api_key: str, model: str = "gpt-4o-mini"):
        self.provider = provider
        self.api_key = api_key
        self.model = model

    def enhance(self, template_prompt: str, rough_notes: str, transcript: str) -> str:
        prompt = build_prompt(template_prompt, rough_notes, transcript)
        import httpx

        if self.provider == "openai":
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        raise ValueError(f"unsupported cloud provider: {self.provider}")


def get_backend(settings: Settings, client=None) -> EnhancementBackend:
    if settings.enhancement_backend == "cloud":
        if not settings.cloud_api_key or not settings.cloud_provider:
            raise ValueError("cloud backend requires cloud_provider and cloud_api_key")
        return CloudBackend(settings.cloud_provider, settings.cloud_api_key)
    return OllamaBackend(settings.ollama_model, settings.ollama_host, client=client)
