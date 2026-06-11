from __future__ import annotations

from fastapi import FastAPI

from muesli_engine.config import Settings, ensure_dirs
from muesli_engine.enhance.templates import DEFAULT_TEMPLATES
from muesli_engine.storage.db import Database
from muesli_engine.settings_store import load_settings


class EngineContext:
    def __init__(self, db, settings, transcribe_fn, enhance_fn, recorder_factory, open_path_fn, diarize_fn):
        self.db = db
        self.settings = settings
        self.transcribe_fn = transcribe_fn
        self.enhance_fn = enhance_fn
        self.recorder_factory = recorder_factory
        self.open_path_fn = open_path_fn
        self.diarize_fn = diarize_fn
        self._recorders: dict[int, object] = {}

    def start_recording(self, meeting_id: int) -> None:
        from muesli_engine.config import RECORDINGS_DIR

        rec = self.recorder_factory(RECORDINGS_DIR / f"{meeting_id}.wav")
        for attr in ("capture_device", "mic_device"):
            if hasattr(rec, attr):
                setattr(rec, attr, getattr(self.settings, attr, None))
        rec.start()
        self._recorders[meeting_id] = rec

    def stop_recording(self, meeting_id: int) -> dict:
        rec = self._recorders.pop(meeting_id)
        return rec.stop()


def _default_transcribe(path, settings):
    from muesli_engine.transcribe.whisper import transcribe_wav

    return transcribe_wav(path, settings)


def _make_default_enhance(settings: Settings):
    """Build the default enhance fn bound to the active settings.

    Closing over ``settings`` (instead of constructing a fresh ``Settings()``)
    ensures the configured model and the optional cloud backend are honored.
    """

    def _enhance(template_prompt, rough_notes, transcript):
        from muesli_engine.enhance.llm import get_backend

        return get_backend(settings).enhance(template_prompt, rough_notes, transcript)

    return _enhance


def _default_recorder_factory(path):
    from muesli_engine.audio.capture import Recorder

    return Recorder(path)


def _default_diarize(loopback_path, mic_path, mic_offset, settings):
    from muesli_engine.diarize.pipeline import diarize_meeting

    return diarize_meeting(loopback_path, mic_path, mic_offset, settings)


def _default_open_path(path, select: bool = False) -> None:
    import os
    import subprocess
    import sys

    if sys.platform.startswith("win"):
        if select:
            subprocess.Popen(["explorer", f"/select,{path}"])
        else:
            os.startfile(path)
        return

    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R" if select else str(path), str(path)] if select else ["open", str(path)])
        return

    subprocess.Popen(["xdg-open", str(path)])


def create_app(
    db_path: str | None = None,
    settings: Settings | None = None,
    transcribe_fn=_default_transcribe,
    enhance_fn=None,
    recorder_factory=_default_recorder_factory,
    open_path_fn=_default_open_path,
    diarize_fn=_default_diarize,
) -> FastAPI:
    from muesli_engine.api.routes import build_router
    from muesli_engine import config

    if db_path is None:
        ensure_dirs()
        db_path = str(config.DB_PATH)

    db = Database(db_path)
    db.init_schema()
    if not db.list_templates():
        for t in DEFAULT_TEMPLATES:
            db.create_template(t)

    if settings is None:
        settings = load_settings(db)
    if enhance_fn is None:
        enhance_fn = _make_default_enhance(settings)

    ctx = EngineContext(db, settings, transcribe_fn, enhance_fn, recorder_factory, open_path_fn, diarize_fn)
    app = FastAPI(title="Muesli Engine")
    app.include_router(build_router(ctx))

    import sys
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles

    # In a PyInstaller bundle the built UI is collected under sys._MEIPASS;
    # from a source checkout it lives at <repo>/ui/dist.
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        ui_dist = base / "ui" / "dist"
    else:
        ui_dist = Path(__file__).resolve().parents[2] / "ui" / "dist"
    if ui_dist.exists():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app
