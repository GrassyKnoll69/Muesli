import pytest

from muesli_engine.config import Settings
from muesli_engine.enhance.llm import OllamaBackend, get_backend


class FakeOllamaClient:
    def __init__(self):
        self.last_prompt = None

    def generate(self, model, prompt):
        self.last_prompt = prompt
        return {"response": "## Summary\nclean notes"}


def test_ollama_backend_returns_markdown_and_passes_prompt():
    fake = FakeOllamaClient()
    backend = OllamaBackend(model="qwen2.5:14b", client=fake)
    out = backend.enhance(
        template_prompt="Summarize.", rough_notes="milk", transcript="talked about milk"
    )
    assert out.startswith("## Summary")
    assert "milk" in fake.last_prompt


def test_get_backend_selects_ollama_by_default():
    backend = get_backend(Settings(), client=FakeOllamaClient())
    assert isinstance(backend, OllamaBackend)


def test_cloud_backend_requires_key():
    with pytest.raises(ValueError):
        get_backend(Settings(enhancement_backend="cloud", cloud_api_key=None))
