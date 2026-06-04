from __future__ import annotations

from fastapi import FastAPI

from muesli_engine.config import Settings, ensure_dirs
from muesli_engine.enhance.templates import DEFAULT_TEMPLATES
from muesli_engine.storage.db import Database


class EngineContext:
    def __init__(self, db, settings, transcribe_fn, enhance_fn, recorder_factory):
        self.db = db
        self.settings = settings
        self.transcribe_fn = transcribe_fn
        self.enhance_fn = enhance_fn
        self.recorder_factory = recorder_factory
        self._recorders: dict[int, object] = {}

    def start_recording(self, meeting_id: int) -> None:
        from muesli_engine.config import RECORDINGS_DIR

        rec = self.recorder_factory(RECORDINGS_DIR / f"{meeting_id}.wav")
        rec.start()
        self._recorders[meeting_id] = rec

    def stop_recording(self, meeting_id: int) -> str:
        rec = self._recorders.pop(meeting_id)
        return rec.stop()


def _default_transcribe(path, settings):
    from muesli_engine.transcribe.whisper import transcribe_wav

    return transcribe_wav(path, settings)


def _default_enhance(template_prompt, rough_notes, transcript):
    from muesli_engine.config import Settings as S
    from muesli_engine.enhance.llm import get_backend

    return get_backend(S()).enhance(template_prompt, rough_notes, transcript)


def _default_recorder_factory(path):
    from muesli_engine.audio.capture import Recorder

    return Recorder(path)


def create_app(
    db_path: str | None = None,
    settings: Settings | None = None,
    transcribe_fn=_default_transcribe,
    enhance_fn=_default_enhance,
    recorder_factory=_default_recorder_factory,
) -> FastAPI:
    from muesli_engine.api.routes import build_router
    from muesli_engine import config

    settings = settings or Settings()
    if db_path is None:
        ensure_dirs()
        db_path = str(config.DB_PATH)

    db = Database(db_path)
    db.init_schema()
    if not db.list_templates():
        for t in DEFAULT_TEMPLATES:
            db.create_template(t)

    ctx = EngineContext(db, settings, transcribe_fn, enhance_fn, recorder_factory)
    app = FastAPI(title="Muesli Engine")
    app.include_router(build_router(ctx))
    return app
