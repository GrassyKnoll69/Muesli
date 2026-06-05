from __future__ import annotations

from muesli_engine.config import Settings
from muesli_engine.storage.db import Database

# Non-secret fields that round-trip through the DB settings table.
# cloud_api_key is deliberately excluded — it lives only in the OS keyring.
PERSISTED_FIELDS = [
    "whisper_model",
    "whisper_device",
    "whisper_compute_type",
    "ollama_model",
    "ollama_host",
    "enhancement_backend",
    "cloud_provider",
    "cloud_model",
]


def load_settings(db: Database) -> Settings:
    """Start from defaults and overlay any persisted non-secret values."""
    s = Settings()
    for field in PERSISTED_FIELDS:
        value = db.get_setting(field)
        if value is not None:
            setattr(s, field, value)
    return s


def save_settings(db: Database, live: Settings, partial: dict) -> Settings:
    """Persist non-secret fields to the DB and mutate the live object in place.

    The API key (``cloud_api_key``) is never written here; the API layer stores
    it in the OS keyring instead.
    """
    for field, value in partial.items():
        if field not in PERSISTED_FIELDS:
            continue
        db.set_setting(field, "" if value is None else str(value))
        setattr(live, field, value)
    return live
