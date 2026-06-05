import pytest

from muesli_engine.config import Settings
from muesli_engine.enhance.llm import (
    CloudBackend,
    OllamaBackend,
    get_backend,
    list_ollama_models,
    validate_cloud,
)


class FakeOllamaClient:
    def __init__(self, models=None):
        self.last_prompt = None
        self._models = models or []

    def generate(self, model, prompt):
        self.last_prompt = prompt
        return {"response": "## Summary\nclean notes"}

    def list(self):
        return {"models": [{"name": m} for m in self._models]}


class FakeResp:
    def __init__(self, data, status=200, text=""):
        self._data = data
        self.status_code = status
        self.text = text

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class FakePost:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.response


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


def test_get_backend_cloud_requires_provider():
    with pytest.raises(ValueError):
        get_backend(Settings(enhancement_backend="cloud", cloud_provider=None))


def test_get_backend_cloud_requires_key(monkeypatch):
    monkeypatch.setattr("muesli_engine.secrets.get_api_key", lambda provider: None)
    with pytest.raises(ValueError):
        get_backend(Settings(enhancement_backend="cloud", cloud_provider="openai"))


def test_get_backend_cloud_uses_keyring_key_and_model(monkeypatch):
    monkeypatch.setattr("muesli_engine.secrets.get_api_key", lambda provider: "kr-key")
    s = Settings(enhancement_backend="cloud", cloud_provider="openai", cloud_model="gpt-4o")
    backend = get_backend(s)
    assert isinstance(backend, CloudBackend)
    assert backend.api_key == "kr-key"
    assert backend.model == "gpt-4o"


def test_anthropic_backend_builds_request_and_parses_response():
    fake = FakePost(FakeResp({"content": [{"text": "## Notes\nok"}]}))
    backend = CloudBackend("anthropic", "key", model="claude-3-5-sonnet-latest", post=fake)
    out = backend.enhance("Summarize.", "milk", "talked about milk")
    assert out.startswith("## Notes")
    call = fake.calls[0]
    assert "api.anthropic.com" in call["url"]
    assert call["headers"]["x-api-key"] == "key"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["json"]["model"] == "claude-3-5-sonnet-latest"
    assert "milk" in call["json"]["messages"][0]["content"]


def test_openai_backend_builds_request_and_parses_response():
    fake = FakePost(FakeResp({"choices": [{"message": {"content": "## Out\nhi"}}]}))
    backend = CloudBackend("openai", "key", model="gpt-4o-mini", post=fake)
    out = backend.enhance("Summarize.", "milk", "talked about milk")
    assert out.startswith("## Out")
    assert "api.openai.com" in fake.calls[0]["url"]
    assert fake.calls[0]["json"]["model"] == "gpt-4o-mini"


def test_validate_cloud_ok():
    ok, msg = validate_cloud("openai", "key", "gpt-4o-mini", post=FakePost(FakeResp({}, 200)))
    assert ok is True


def test_validate_cloud_reports_bad_status():
    ok, msg = validate_cloud(
        "anthropic", "bad", "claude-3-5-sonnet-latest",
        post=FakePost(FakeResp({}, 401, text="unauthorized")),
    )
    assert ok is False
    assert "401" in msg


def test_list_ollama_models_returns_names():
    client = FakeOllamaClient(models=["qwen2.5:14b", "llama3.1:8b"])
    assert list_ollama_models(client=client) == ["qwen2.5:14b", "llama3.1:8b"]


def test_list_ollama_models_empty_on_error():
    class Boom:
        def list(self):
            raise RuntimeError("ollama down")

    assert list_ollama_models(client=Boom()) == []
