from muesli_engine.config import Settings
from muesli_engine.settings_store import load_settings, save_settings
from muesli_engine.storage.db import Database


def make_db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


def test_load_returns_defaults_when_empty():
    db = make_db()
    s = load_settings(db)
    assert s.whisper_model == "large-v3"
    assert s.ollama_model == "qwen2.5:14b"
    assert s.enhancement_backend == "ollama"


def test_save_persists_non_secret_fields_and_mutates_live():
    db = make_db()
    live = Settings()
    out = save_settings(db, live, {"ollama_model": "llama3.1:8b", "cloud_provider": "openai"})
    assert out is live                       # same object, mutated in place
    assert live.ollama_model == "llama3.1:8b"
    assert live.cloud_provider == "openai"
    reloaded = load_settings(db)
    assert reloaded.ollama_model == "llama3.1:8b"
    assert reloaded.cloud_provider == "openai"


def test_save_never_writes_api_key_to_db():
    db = make_db()
    live = Settings()
    save_settings(db, live, {"ollama_model": "x", "cloud_api_key": "sk-secret"})
    assert db.get_setting("cloud_api_key") is None
    assert load_settings(db).cloud_api_key is None


def test_save_ignores_unknown_fields():
    db = make_db()
    live = Settings()
    save_settings(db, live, {"bogus": "nope", "whisper_device": "cpu"})
    assert db.get_setting("bogus") is None
    assert live.whisper_device == "cpu"
