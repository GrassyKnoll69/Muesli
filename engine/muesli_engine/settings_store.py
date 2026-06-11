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
    "enable_diarization",
    "diarization_threshold",
    "mic_device",
]


def load_settings(db: Database) -> Settings:
    """Start from defaults and overlay any persisted non-secret values.

    Loaded string values are coerced to their correct types by building a fresh
    Settings via pydantic validation (pydantic v2 coerces "True"/"False"/"0"/"1"
    → bool and "0.5" → float automatically).
    """
    overrides: dict = {}
    for field in PERSISTED_FIELDS:
        value = db.get_setting(field)
        if value is not None:
            overrides[field] = value
    return Settings.model_validate({**Settings().model_dump(), **overrides})


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
