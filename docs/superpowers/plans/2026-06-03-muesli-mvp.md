# Muesli MVP (v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local-first Granola clone where you manually record a meeting, take rough notes, then transcribe (faster-whisper) and enhance (Ollama + template) those notes into clean structured markdown, all browsable/searchable in a desktop window.

**Architecture:** A Python "engine" (audio capture → transcription → LLM enhancement → SQLite/FTS5 storage) exposed over a FastAPI HTTP API, consumed by a React/Vite UI, wrapped in a pywebview desktop window. The engine has zero knowledge of the UI and is unit-tested in isolation.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pywebview, pyaudiowpatch, faster-whisper, ollama, pydantic, SQLite (stdlib) + FTS5; React + Vite + TypeScript.

---

## File Structure

```
engine/
  muesli_engine/
    __init__.py
    config.py                 # paths, Settings model, device detection
    storage/
      __init__.py
      models.py               # pydantic: Meeting, Template
      db.py                   # Database class: schema, FTS5, CRUD, search
    enhance/
      __init__.py
      templates.py            # default templates + prompt builder
      llm.py                  # EnhancementBackend protocol, OllamaBackend, CloudBackend, get_backend()
    transcribe/
      __init__.py
      whisper.py              # transcribe_wav() with GPU/CPU auto
    audio/
      __init__.py
      capture.py              # Recorder: WASAPI loopback + mic -> WAV
    api/
      __init__.py
      routes.py               # FastAPI router over the engine
    app.py                    # create_app(): mounts API + static UI
  tests/
    test_storage.py
    test_templates.py
    test_llm.py
    test_api.py
  requirements.txt
  pyproject.toml
ui/
  index.html, package.json, vite.config.ts, tsconfig.json
  src/{main.tsx, App.tsx, api/client.ts, pages/*.tsx, components/*.tsx}
run.py                        # uvicorn (background thread) + pywebview window
.gitignore
README.md
```

**Boundary rule:** `api/` imports from `storage/`, `enhance/`, `transcribe/`, `audio/`. Nothing in those modules imports from `api/` or `ui/`.

---

## Task 1: Repo scaffold + dependencies

**Files:**
- Create: `.gitignore`, `engine/requirements.txt`, `engine/pyproject.toml`, `engine/muesli_engine/__init__.py`, and empty `__init__.py` in each subpackage.

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/

# Node
node_modules/
ui/dist/

# Muesli runtime data
.muesli/
*.wav

# OS / editors
.DS_Store
.idea/
.vscode/
```

- [ ] **Step 2: Create `engine/requirements.txt`**

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
pydantic==2.*
pywebview==5.*
PyAudioWPatch==0.2.12.7
faster-whisper==1.*
ollama==0.3.*
httpx==0.27.*
pytest==8.*
```

- [ ] **Step 3: Create `engine/pyproject.toml`**

```toml
[project]
name = "muesli-engine"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Create package `__init__.py` files (all empty)**

Create empty files: `engine/muesli_engine/__init__.py`, `engine/muesli_engine/storage/__init__.py`, `engine/muesli_engine/enhance/__init__.py`, `engine/muesli_engine/transcribe/__init__.py`, `engine/muesli_engine/audio/__init__.py`, `engine/muesli_engine/api/__init__.py`, `engine/tests/__init__.py`.

- [ ] **Step 5: Create venv + install**

Run:
```bash
cd engine && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
```
Expected: installs without error. (GPU faster-whisper needs NVIDIA CUDA libraries on PATH; CPU fallback works regardless.)

- [ ] **Step 6: Commit**

```bash
git add .gitignore engine/requirements.txt engine/pyproject.toml engine/muesli_engine engine/tests/__init__.py
git commit -m "chore: scaffold Muesli engine package"
```

---

## Task 2: Config + paths

**Files:**
- Create: `engine/muesli_engine/config.py`

- [ ] **Step 1: Write `config.py`**

```python
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

APP_DIR = Path(os.environ.get("MUESLI_HOME", str(Path.home() / ".muesli")))
DB_PATH = APP_DIR / "muesli.db"
RECORDINGS_DIR = APP_DIR / "recordings"


class Settings(BaseModel):
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"            # "auto" | "cuda" | "cpu"
    whisper_compute_type: str = "float16"   # "int8" recommended on CPU
    ollama_model: str = "qwen2.5:14b"
    ollama_host: str = "http://localhost:11434"
    enhancement_backend: str = "ollama"     # "ollama" | "cloud"
    cloud_provider: str | None = None       # "openai" | "anthropic"
    cloud_api_key: str | None = None


def ensure_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_whisper_device(device: str) -> tuple[str, str]:
    """Return (device, compute_type), auto-detecting CUDA when device='auto'."""
    if device != "auto":
        return device, ("float16" if device == "cuda" else "int8")
    try:
        import ctranslate2  # bundled with faster-whisper

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"
```

- [ ] **Step 2: Commit**

```bash
git add engine/muesli_engine/config.py
git commit -m "feat: add engine config and path helpers"
```

---

## Task 3: Storage models

**Files:**
- Create: `engine/muesli_engine/storage/models.py`

- [ ] **Step 1: Write `models.py`**

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Template(BaseModel):
    id: int | None = None
    name: str
    prompt: str


class Meeting(BaseModel):
    id: int | None = None
    title: str
    created_at: datetime
    audio_path: str | None = None
    rough_notes: str = ""
    transcript: str = ""
    enhanced_notes: str = ""
    template_id: int | None = None
    status: str = "recording"   # recording | recorded | transcribed | enhanced
```

- [ ] **Step 2: Commit**

```bash
git add engine/muesli_engine/storage/models.py
git commit -m "feat: add Meeting and Template models"
```

---

## Task 4: Storage layer (SQLite + FTS5) — TDD

**Files:**
- Create: `engine/muesli_engine/storage/db.py`
- Test: `engine/tests/test_storage.py`

- [ ] **Step 1: Write failing tests `tests/test_storage.py`**

```python
from datetime import datetime, timezone

from muesli_engine.storage.db import Database
from muesli_engine.storage.models import Meeting, Template


def make_db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


def test_create_and_get_meeting():
    db = make_db()
    m = Meeting(title="Standup", created_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    saved = db.create_meeting(m)
    assert saved.id is not None
    fetched = db.get_meeting(saved.id)
    assert fetched.title == "Standup"
    assert fetched.status == "recording"


def test_update_notes_and_status():
    db = make_db()
    m = db.create_meeting(Meeting(title="1:1", created_at=datetime.now(timezone.utc)))
    db.update_rough_notes(m.id, "buy milk")
    db.set_transcript(m.id, "we discussed milk")
    db.set_enhanced(m.id, "## Action items\n- buy milk")
    got = db.get_meeting(m.id)
    assert got.rough_notes == "buy milk"
    assert got.transcript == "we discussed milk"
    assert got.enhanced_notes.startswith("## Action items")
    assert got.status == "enhanced"


def test_list_meetings_newest_first():
    db = make_db()
    a = db.create_meeting(Meeting(title="A", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    b = db.create_meeting(Meeting(title="B", created_at=datetime(2026, 2, 1, tzinfo=timezone.utc)))
    titles = [m.title for m in db.list_meetings()]
    assert titles == ["B", "A"]


def test_full_text_search_matches_enhanced_and_transcript():
    db = make_db()
    m = db.create_meeting(Meeting(title="Sales call", created_at=datetime.now(timezone.utc)))
    db.set_transcript(m.id, "customer asked about pricing tiers")
    db.set_enhanced(m.id, "## Summary\nDiscussed enterprise pricing")
    assert [x.id for x in db.search_meetings("pricing")] == [m.id]
    assert db.search_meetings("nonexistentword") == []


def test_template_crud():
    db = make_db()
    t = db.create_template(Template(name="Standup", prompt="Summarize as standup."))
    assert t.id is not None
    assert [x.name for x in db.list_templates()] == ["Standup"]
    db.update_template(t.id, Template(name="Daily Standup", prompt="Summarize."))
    assert db.get_template(t.id).name == "Daily Standup"
    db.delete_template(t.id)
    assert db.list_templates() == []


def test_settings_roundtrip():
    db = make_db()
    db.set_setting("ollama_model", "llama3.1:8b")
    assert db.get_setting("ollama_model") == "llama3.1:8b"
    assert db.get_setting("missing") is None
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd engine && .venv/Scripts/python -m pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: muesli_engine.storage.db` / `ImportError: Database`.

- [ ] **Step 3: Write `storage/db.py`**

```python
from __future__ import annotations

import sqlite3
from datetime import datetime

from muesli_engine.storage.models import Meeting, Template

_STATUS_ORDER = ["recording", "recorded", "transcribed", "enhanced"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    audio_path TEXT,
    rough_notes TEXT NOT NULL DEFAULT '',
    transcript TEXT NOT NULL DEFAULT '',
    enhanced_notes TEXT NOT NULL DEFAULT '',
    template_id INTEGER,
    status TEXT NOT NULL DEFAULT 'recording'
);
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    prompt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS meetings_fts USING fts5(
    title, enhanced_notes, transcript,
    content='meetings', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS meetings_ai AFTER INSERT ON meetings BEGIN
    INSERT INTO meetings_fts(rowid, title, enhanced_notes, transcript)
    VALUES (new.id, new.title, new.enhanced_notes, new.transcript);
END;
CREATE TRIGGER IF NOT EXISTS meetings_ad AFTER DELETE ON meetings BEGIN
    INSERT INTO meetings_fts(meetings_fts, rowid, title, enhanced_notes, transcript)
    VALUES ('delete', old.id, old.title, old.enhanced_notes, old.transcript);
END;
CREATE TRIGGER IF NOT EXISTS meetings_au AFTER UPDATE ON meetings BEGIN
    INSERT INTO meetings_fts(meetings_fts, rowid, title, enhanced_notes, transcript)
    VALUES ('delete', old.id, old.title, old.enhanced_notes, old.transcript);
    INSERT INTO meetings_fts(rowid, title, enhanced_notes, transcript)
    VALUES (new.id, new.title, new.enhanced_notes, new.transcript);
END;
"""


class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # --- meetings ---
    def create_meeting(self, m: Meeting) -> Meeting:
        cur = self.conn.execute(
            "INSERT INTO meetings(title, created_at, audio_path, rough_notes, "
            "transcript, enhanced_notes, template_id, status) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (m.title, m.created_at.isoformat(), m.audio_path, m.rough_notes,
             m.transcript, m.enhanced_notes, m.template_id, m.status),
        )
        self.conn.commit()
        return self.get_meeting(cur.lastrowid)

    def get_meeting(self, meeting_id: int) -> Meeting:
        row = self.conn.execute(
            "SELECT * FROM meetings WHERE id=?", (meeting_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"meeting {meeting_id} not found")
        return self._row_to_meeting(row)

    def list_meetings(self) -> list[Meeting]:
        rows = self.conn.execute(
            "SELECT * FROM meetings ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [self._row_to_meeting(r) for r in rows]

    def search_meetings(self, query: str) -> list[Meeting]:
        rows = self.conn.execute(
            "SELECT m.* FROM meetings_fts f JOIN meetings m ON m.id=f.rowid "
            "WHERE meetings_fts MATCH ? ORDER BY rank",
            (query,),
        ).fetchall()
        return [self._row_to_meeting(r) for r in rows]

    def update_rough_notes(self, meeting_id: int, notes: str) -> None:
        self.conn.execute(
            "UPDATE meetings SET rough_notes=? WHERE id=?", (notes, meeting_id)
        )
        self.conn.commit()

    def set_audio_path(self, meeting_id: int, path: str) -> None:
        self._update_status(meeting_id, "recorded")
        self.conn.execute(
            "UPDATE meetings SET audio_path=? WHERE id=?", (path, meeting_id)
        )
        self.conn.commit()

    def set_transcript(self, meeting_id: int, transcript: str) -> None:
        self.conn.execute(
            "UPDATE meetings SET transcript=? WHERE id=?", (transcript, meeting_id)
        )
        self._update_status(meeting_id, "transcribed")
        self.conn.commit()

    def set_enhanced(self, meeting_id: int, enhanced: str) -> None:
        self.conn.execute(
            "UPDATE meetings SET enhanced_notes=? WHERE id=?", (enhanced, meeting_id)
        )
        self._update_status(meeting_id, "enhanced")
        self.conn.commit()

    def set_template(self, meeting_id: int, template_id: int) -> None:
        self.conn.execute(
            "UPDATE meetings SET template_id=? WHERE id=?", (template_id, meeting_id)
        )
        self.conn.commit()

    def _update_status(self, meeting_id: int, new_status: str) -> None:
        current = self.conn.execute(
            "SELECT status FROM meetings WHERE id=?", (meeting_id,)
        ).fetchone()[0]
        if _STATUS_ORDER.index(new_status) > _STATUS_ORDER.index(current):
            self.conn.execute(
                "UPDATE meetings SET status=? WHERE id=?", (new_status, meeting_id)
            )

    # --- templates ---
    def create_template(self, t: Template) -> Template:
        cur = self.conn.execute(
            "INSERT INTO templates(name, prompt) VALUES(?,?)", (t.name, t.prompt)
        )
        self.conn.commit()
        return self.get_template(cur.lastrowid)

    def get_template(self, template_id: int) -> Template:
        row = self.conn.execute(
            "SELECT * FROM templates WHERE id=?", (template_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"template {template_id} not found")
        return Template(id=row["id"], name=row["name"], prompt=row["prompt"])

    def list_templates(self) -> list[Template]:
        rows = self.conn.execute("SELECT * FROM templates ORDER BY name").fetchall()
        return [Template(id=r["id"], name=r["name"], prompt=r["prompt"]) for r in rows]

    def update_template(self, template_id: int, t: Template) -> None:
        self.conn.execute(
            "UPDATE templates SET name=?, prompt=? WHERE id=?",
            (t.name, t.prompt, template_id),
        )
        self.conn.commit()

    def delete_template(self, template_id: int) -> None:
        self.conn.execute("DELETE FROM templates WHERE id=?", (template_id,))
        self.conn.commit()

    # --- settings ---
    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row[0] if row else None

    def _row_to_meeting(self, row: sqlite3.Row) -> Meeting:
        return Meeting(
            id=row["id"],
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            audio_path=row["audio_path"],
            rough_notes=row["rough_notes"],
            transcript=row["transcript"],
            enhanced_notes=row["enhanced_notes"],
            template_id=row["template_id"],
            status=row["status"],
        )
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd engine && .venv/Scripts/python -m pytest tests/test_storage.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/muesli_engine/storage/db.py engine/tests/test_storage.py
git commit -m "feat: add SQLite storage with FTS5 search"
```

---

## Task 5: Templates + prompt builder — TDD

**Files:**
- Create: `engine/muesli_engine/enhance/templates.py`
- Test: `engine/tests/test_templates.py`

- [ ] **Step 1: Write failing tests `tests/test_templates.py`**

```python
from muesli_engine.enhance.templates import DEFAULT_TEMPLATES, build_prompt


def test_default_templates_present():
    names = {t.name for t in DEFAULT_TEMPLATES}
    assert {"General", "1:1", "Standup", "Sales Call"}.issubset(names)


def test_build_prompt_includes_notes_transcript_and_instructions():
    prompt = build_prompt(
        template_prompt="Format as a standup update.",
        rough_notes="talked about milk",
        transcript="We discussed buying milk tomorrow.",
    )
    assert "Format as a standup update." in prompt
    assert "talked about milk" in prompt
    assert "We discussed buying milk tomorrow." in prompt


def test_build_prompt_handles_empty_notes():
    prompt = build_prompt(
        template_prompt="Summarize.",
        rough_notes="",
        transcript="Some transcript.",
    )
    assert "(no rough notes were taken)" in prompt
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd engine && .venv/Scripts/python -m pytest tests/test_templates.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `enhance/templates.py`**

```python
from __future__ import annotations

from muesli_engine.storage.models import Template

DEFAULT_TEMPLATES: list[Template] = [
    Template(name="General", prompt=(
        "Rewrite the rough notes into clean, well-structured meeting notes. "
        "Use markdown headings, bullet points, and a short summary at the top."
    )),
    Template(name="1:1", prompt=(
        "Format as 1:1 notes with sections: Summary, Discussion Points, "
        "Action Items (with owners if mentioned), Follow-ups."
    )),
    Template(name="Standup", prompt=(
        "Format as a standup update with sections: Yesterday, Today, Blockers."
    )),
    Template(name="Sales Call", prompt=(
        "Format as sales-call notes with sections: Customer, Needs/Pain Points, "
        "Objections, Next Steps, Action Items."
    )),
]

_PROMPT = """You are an expert meeting-notes assistant. Using the meeting \
transcript and the user's rough notes, produce polished notes in GitHub-flavored \
markdown. Prioritize the user's rough notes; use the transcript to fill gaps and \
add accuracy. Do not invent facts that are not supported by the transcript or notes.

# Formatting instructions
{template_prompt}

# User's rough notes
{rough_notes}

# Transcript
{transcript}

# Output
Return only the finished markdown notes."""


def build_prompt(template_prompt: str, rough_notes: str, transcript: str) -> str:
    notes = rough_notes.strip() or "(no rough notes were taken)"
    body = transcript.strip() or "(no transcript available)"
    return _PROMPT.format(
        template_prompt=template_prompt.strip(),
        rough_notes=notes,
        transcript=body,
    )
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd engine && .venv/Scripts/python -m pytest tests/test_templates.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/muesli_engine/enhance/templates.py engine/tests/test_templates.py
git commit -m "feat: add default templates and prompt builder"
```

---

## Task 6: Enhancement backends — TDD

**Files:**
- Create: `engine/muesli_engine/enhance/llm.py`
- Test: `engine/tests/test_llm.py`

- [ ] **Step 1: Write failing tests `tests/test_llm.py`**

```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd engine && .venv/Scripts/python -m pytest tests/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `enhance/llm.py`**

```python
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
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd engine && .venv/Scripts/python -m pytest tests/test_llm.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/muesli_engine/enhance/llm.py engine/tests/test_llm.py
git commit -m "feat: add Ollama and optional cloud enhancement backends"
```

---

## Task 7: Transcription wrapper

> Not unit-tested (requires a real audio file + model download). Verified manually in Task 11.

**Files:**
- Create: `engine/muesli_engine/transcribe/whisper.py`

- [ ] **Step 1: Write `transcribe/whisper.py`**

```python
from __future__ import annotations

from muesli_engine.config import Settings, resolve_whisper_device

_model_cache: dict[tuple[str, str, str], object] = {}


def _get_model(settings: Settings):
    device, compute_type = resolve_whisper_device(settings.whisper_device)
    key = (settings.whisper_model, device, compute_type)
    if key not in _model_cache:
        from faster_whisper import WhisperModel

        _model_cache[key] = WhisperModel(
            settings.whisper_model, device=device, compute_type=compute_type
        )
    return _model_cache[key]


def transcribe_wav(path: str, settings: Settings) -> str:
    """Transcribe a WAV file into a single plain-text transcript."""
    model = _get_model(settings)
    segments, _info = model.transcribe(path, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()
```

- [ ] **Step 2: Commit**

```bash
git add engine/muesli_engine/transcribe/whisper.py
git commit -m "feat: add faster-whisper transcription wrapper"
```

---

## Task 8: Audio capture (WASAPI loopback + mic)

> Not unit-tested (requires real audio devices). Verified manually in Task 11.

**Files:**
- Create: `engine/muesli_engine/audio/capture.py`

- [ ] **Step 1: Write `audio/capture.py`**

```python
from __future__ import annotations

import threading
import wave
from pathlib import Path

import pyaudiowpatch as pyaudio

_CHUNK = 1024


class Recorder:
    """Records the default WASAPI loopback (system audio) to a WAV file.

    Captures system output (what you hear in the meeting). Mic mixing is a
    follow-up; loopback alone already captures remote participants when audio
    plays through the speakers/headset output device.
    """

    def __init__(self, out_path: str | Path):
        self.out_path = str(out_path)
        self._pa = pyaudio.PyAudio()
        self._frames: list[bytes] = []
        self._stream = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._channels = 2
        self._rate = 48000

    def _loopback_device(self) -> dict:
        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = self._pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        for i in range(self._pa.get_device_count()):
            dev = self._pa.get_device_info_by_index(i)
            if dev.get("isLoopbackDevice") and default_out["name"] in dev["name"]:
                return dev
        raise RuntimeError("No WASAPI loopback device found for the default output.")

    def start(self) -> None:
        dev = self._loopback_device()
        self._channels = int(dev["maxInputChannels"]) or 2
        self._rate = int(dev["defaultSampleRate"])
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self._channels,
            rate=self._rate,
            frames_per_buffer=_CHUNK,
            input=True,
            input_device_index=dev["index"],
        )
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            self._frames.append(self._stream.read(_CHUNK, exception_on_overflow=False))

    def stop(self) -> str:
        self._running = False
        if self._thread:
            self._thread.join()
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        with wave.open(self.out_path, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self._rate)
            wf.writeframes(b"".join(self._frames))
        self._pa.terminate()
        return self.out_path
```

- [ ] **Step 2: Commit**

```bash
git add engine/muesli_engine/audio/capture.py
git commit -m "feat: add WASAPI loopback audio recorder"
```

---

## Task 9: FastAPI app + routes — TDD (storage paths)

**Files:**
- Create: `engine/muesli_engine/api/routes.py`, `engine/muesli_engine/app.py`
- Test: `engine/tests/test_api.py`

- [ ] **Step 1: Write failing tests `tests/test_api.py`**

```python
from fastapi.testclient import TestClient

from muesli_engine.app import create_app


def client() -> TestClient:
    # In-memory DB; stub transcribe/enhance so no models are needed.
    app = create_app(
        db_path=":memory:",
        transcribe_fn=lambda path, settings: "stub transcript about pricing",
        enhance_fn=lambda tprompt, notes, transcript: "## Summary\nstub enhanced",
        recorder_factory=None,
    )
    return TestClient(app)


def test_templates_seeded_on_startup():
    c = client()
    names = {t["name"] for t in c.get("/templates").json()}
    assert "Standup" in names


def test_meeting_lifecycle_without_audio():
    c = client()
    mid = c.post("/recordings/start", json={"title": "Test"}).json()["id"]
    c.put(f"/meetings/{mid}/notes", json={"rough_notes": "milk"})
    # No real audio: simulate stop by directly transcribing/enhancing.
    assert c.post(f"/meetings/{mid}/transcribe").json()["transcript"] == "stub transcript about pricing"
    enhanced = c.post(f"/meetings/{mid}/enhance", json={"template_id": None}).json()
    assert enhanced["enhanced_notes"].startswith("## Summary")


def test_search_finds_enhanced_meeting():
    c = client()
    mid = c.post("/recordings/start", json={"title": "Sales"}).json()["id"]
    c.post(f"/meetings/{mid}/transcribe")
    c.post(f"/meetings/{mid}/enhance", json={"template_id": None})
    results = c.get("/meetings/search", params={"q": "pricing"}).json()
    assert any(m["id"] == mid for m in results)
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd engine && .venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: muesli_engine.app`.

- [ ] **Step 3: Write `api/routes.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from muesli_engine.storage.models import Meeting, Template


class StartRequest(BaseModel):
    title: str | None = None
    template_id: int | None = None


class NotesRequest(BaseModel):
    rough_notes: str


class EnhanceRequest(BaseModel):
    template_id: int | None = None


def build_router(ctx) -> APIRouter:
    """ctx exposes: db, settings, transcribe_fn, enhance_fn, recorder_factory."""
    router = APIRouter()

    @router.post("/recordings/start")
    def start(req: StartRequest):
        title = req.title or datetime.now().strftime("Meeting %Y-%m-%d %H:%M")
        meeting = ctx.db.create_meeting(
            Meeting(title=title, created_at=datetime.now(timezone.utc),
                    template_id=req.template_id)
        )
        if ctx.recorder_factory is not None:
            ctx.start_recording(meeting.id)
        return meeting

    @router.post("/recordings/{meeting_id}/stop")
    def stop(meeting_id: int):
        if ctx.recorder_factory is not None:
            path = ctx.stop_recording(meeting_id)
            ctx.db.set_audio_path(meeting_id, path)
        return ctx.db.get_meeting(meeting_id)

    @router.put("/meetings/{meeting_id}/notes")
    def save_notes(meeting_id: int, req: NotesRequest):
        ctx.db.update_rough_notes(meeting_id, req.rough_notes)
        return {"ok": True}

    @router.post("/meetings/{meeting_id}/transcribe")
    def transcribe(meeting_id: int):
        meeting = ctx.db.get_meeting(meeting_id)
        source = meeting.audio_path or ""
        transcript = ctx.transcribe_fn(source, ctx.settings)
        ctx.db.set_transcript(meeting_id, transcript)
        return ctx.db.get_meeting(meeting_id)

    @router.post("/meetings/{meeting_id}/enhance")
    def enhance(meeting_id: int, req: EnhanceRequest):
        meeting = ctx.db.get_meeting(meeting_id)
        template_id = req.template_id or meeting.template_id
        if template_id:
            template_prompt = ctx.db.get_template(template_id).prompt
        else:
            template_prompt = ctx.db.list_templates()[0].prompt
        enhanced = ctx.enhance_fn(template_prompt, meeting.rough_notes, meeting.transcript)
        ctx.db.set_enhanced(meeting_id, enhanced)
        return ctx.db.get_meeting(meeting_id)

    @router.get("/meetings")
    def list_meetings():
        return ctx.db.list_meetings()

    @router.get("/meetings/search")
    def search(q: str):
        return ctx.db.search_meetings(q)

    @router.get("/meetings/{meeting_id}")
    def get_meeting(meeting_id: int):
        try:
            return ctx.db.get_meeting(meeting_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="meeting not found")

    @router.get("/templates")
    def list_templates():
        return ctx.db.list_templates()

    @router.post("/templates")
    def create_template(t: Template):
        return ctx.db.create_template(t)

    @router.put("/templates/{template_id}")
    def update_template(template_id: int, t: Template):
        ctx.db.update_template(template_id, t)
        return ctx.db.get_template(template_id)

    @router.delete("/templates/{template_id}")
    def delete_template(template_id: int):
        ctx.db.delete_template(template_id)
        return {"ok": True}

    return router
```

- [ ] **Step 4: Write `app.py`**

```python
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
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `cd engine && .venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Run the full suite**

Run: `cd engine && .venv/Scripts/python -m pytest -v`
Expected: PASS (all tasks 4-9 green).

- [ ] **Step 7: Commit**

```bash
git add engine/muesli_engine/api/routes.py engine/muesli_engine/app.py engine/tests/test_api.py
git commit -m "feat: add FastAPI engine API with seeded templates"
```

---

## Task 10: React UI

> UI verified manually in Task 11. Build a minimal, clean SPA.

**Files:**
- Create: `ui/package.json`, `ui/vite.config.ts`, `ui/tsconfig.json`, `ui/index.html`,
  `ui/src/main.tsx`, `ui/src/App.tsx`, `ui/src/api/client.ts`,
  `ui/src/pages/{Library,ActiveMeeting,MeetingDetail,Templates}.tsx`

- [ ] **Step 1: Scaffold Vite app**

Run:
```bash
cd ui && npm create vite@latest . -- --template react-ts && npm install && npm install react-router-dom
```

- [ ] **Step 2: Configure dev proxy in `ui/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    proxy: {
      "/meetings": "http://localhost:8731",
      "/recordings": "http://localhost:8731",
      "/templates": "http://localhost:8731",
    },
  },
});
```

- [ ] **Step 3: Write `ui/src/api/client.ts`**

```typescript
export interface Meeting {
  id: number;
  title: string;
  created_at: string;
  rough_notes: string;
  transcript: string;
  enhanced_notes: string;
  template_id: number | null;
  status: string;
}
export interface Template { id: number; name: string; prompt: string; }

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export const api = {
  listMeetings: () => fetch("/meetings").then(j<Meeting[]>),
  searchMeetings: (q: string) =>
    fetch(`/meetings/search?q=${encodeURIComponent(q)}`).then(j<Meeting[]>),
  getMeeting: (id: number) => fetch(`/meetings/${id}`).then(j<Meeting>),
  start: (title: string, template_id: number | null) =>
    fetch("/recordings/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, template_id }),
    }).then(j<Meeting>),
  stop: (id: number) =>
    fetch(`/recordings/${id}/stop`, { method: "POST" }).then(j<Meeting>),
  saveNotes: (id: number, rough_notes: string) =>
    fetch(`/meetings/${id}/notes`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rough_notes }),
    }),
  transcribe: (id: number) =>
    fetch(`/meetings/${id}/transcribe`, { method: "POST" }).then(j<Meeting>),
  enhance: (id: number, template_id: number | null) =>
    fetch(`/meetings/${id}/enhance`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_id }),
    }).then(j<Meeting>),
  listTemplates: () => fetch("/templates").then(j<Template[]>),
};
```

- [ ] **Step 4: Write `ui/src/App.tsx` (router)**

```typescript
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Library from "./pages/Library";
import ActiveMeeting from "./pages/ActiveMeeting";
import MeetingDetail from "./pages/MeetingDetail";
import Templates from "./pages/Templates";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ display: "flex", gap: 16, padding: 12, borderBottom: "1px solid #ddd" }}>
        <Link to="/">Library</Link>
        <Link to="/new">New Meeting</Link>
        <Link to="/templates">Templates</Link>
      </nav>
      <div style={{ padding: 16, maxWidth: 820, margin: "0 auto" }}>
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/new" element={<ActiveMeeting />} />
          <Route path="/meetings/:id" element={<MeetingDetail />} />
          <Route path="/templates" element={<Templates />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
```

- [ ] **Step 5: Write `ui/src/pages/Library.tsx`**

```typescript
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Meeting } from "../api/client";

export default function Library() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [q, setQ] = useState("");

  async function load() {
    setMeetings(q.trim() ? await api.searchMeetings(q.trim()) : await api.listMeetings());
  }
  useEffect(() => { load(); }, []);

  return (
    <div>
      <h1>Meetings</h1>
      <form onSubmit={(e) => { e.preventDefault(); load(); }}>
        <input placeholder="Search notes & transcripts" value={q}
               onChange={(e) => setQ(e.target.value)} style={{ width: "70%" }} />
        <button>Search</button>
      </form>
      <ul>
        {meetings.map((m) => (
          <li key={m.id}>
            <Link to={`/meetings/${m.id}`}>{m.title}</Link>
            <span style={{ color: "#888" }}> — {m.status}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 6: Write `ui/src/pages/ActiveMeeting.tsx`**

```typescript
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Template } from "../api/client";

export default function ActiveMeeting() {
  const [meetingId, setMeetingId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const nav = useNavigate();
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => { api.listTemplates().then(setTemplates); }, []);

  async function start() {
    const m = await api.start(title || "Untitled meeting", templateId);
    setMeetingId(m.id);
  }
  function onNotes(v: string) {
    setNotes(v);
    if (meetingId) {
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => api.saveNotes(meetingId, v), 600);
    }
  }
  async function stop() {
    if (!meetingId) return;
    await api.saveNotes(meetingId, notes);
    await api.stop(meetingId);
    nav(`/meetings/${meetingId}`);
  }

  if (meetingId === null) {
    return (
      <div>
        <h1>New Meeting</h1>
        <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <select value={templateId ?? ""} onChange={(e) => setTemplateId(e.target.value ? Number(e.target.value) : null)}>
          <option value="">(template)</option>
          {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <button onClick={start}>● Start Recording</button>
      </div>
    );
  }
  return (
    <div>
      <h1>● Recording…</h1>
      <textarea value={notes} onChange={(e) => onNotes(e.target.value)}
                placeholder="Jot rough notes…" rows={18} style={{ width: "100%" }} />
      <button onClick={stop}>■ Stop</button>
    </div>
  );
}
```

- [ ] **Step 7: Write `ui/src/pages/MeetingDetail.tsx`**

```typescript
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, Meeting } from "../api/client";

type Tab = "enhanced" | "notes" | "transcript";

export default function MeetingDetail() {
  const { id } = useParams();
  const mid = Number(id);
  const [m, setM] = useState<Meeting | null>(null);
  const [tab, setTab] = useState<Tab>("enhanced");
  const [busy, setBusy] = useState("");

  async function reload() { setM(await api.getMeeting(mid)); }
  useEffect(() => { reload(); }, [mid]);

  async function doTranscribe() {
    setBusy("Transcribing…"); setM(await api.transcribe(mid)); setBusy("");
  }
  async function doEnhance() {
    setBusy("Enhancing…"); setM(await api.enhance(mid, m?.template_id ?? null));
    setBusy(""); setTab("enhanced");
  }
  if (!m) return <p>Loading…</p>;

  const body = tab === "enhanced" ? m.enhanced_notes
    : tab === "notes" ? m.rough_notes : m.transcript;

  return (
    <div>
      <h1>{m.title}</h1>
      <div style={{ marginBottom: 8 }}>
        <button onClick={doTranscribe}>Transcribe</button>{" "}
        <button onClick={doEnhance}>Enhance</button>{" "}
        <span style={{ color: "#c60" }}>{busy}</span>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        {(["enhanced", "notes", "transcript"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
                  style={{ fontWeight: tab === t ? "bold" : "normal" }}>{t}</button>
        ))}
      </div>
      <pre style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>{body || "(empty)"}</pre>
    </div>
  );
}
```

- [ ] **Step 8: Write `ui/src/pages/Templates.tsx`**

```typescript
import { useEffect, useState } from "react";
import { api, Template } from "../api/client";

export default function Templates() {
  const [templates, setTemplates] = useState<Template[]>([]);
  useEffect(() => { api.listTemplates().then(setTemplates); }, []);
  return (
    <div>
      <h1>Templates</h1>
      <ul>
        {templates.map((t) => (
          <li key={t.id}><strong>{t.name}</strong>: {t.prompt}</li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 9: Commit**

```bash
git add ui
git commit -m "feat: add React UI (library, recording, detail, templates)"
```

---

## Task 11: Desktop shell + manual end-to-end

**Files:**
- Create: `run.py`
- Modify: `engine/muesli_engine/app.py` (serve built UI static files)

- [ ] **Step 1: Add static-file serving to `app.py`**

Add to `create_app` before `return app` (only when the build exists):

```python
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles

    ui_dist = Path(__file__).resolve().parents[2] / "ui" / "dist"
    if ui_dist.exists():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
```

- [ ] **Step 2: Write `run.py`**

```python
from __future__ import annotations

import threading

import uvicorn
import webview

from muesli_engine.app import create_app

PORT = 8731


def _serve():
    uvicorn.run(create_app(), host="127.0.0.1", port=PORT, log_level="info")


def main():
    threading.Thread(target=_serve, daemon=True).start()
    webview.create_window("Muesli", f"http://127.0.0.1:{PORT}", width=1000, height=720)
    webview.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Build the UI**

Run: `cd ui && npm run build`
Expected: produces `ui/dist/`.

- [ ] **Step 4: Verify Ollama is ready**

Run: `ollama list`
Expected: shows `qwen2.5:14b`. If missing: `ollama pull qwen2.5:14b`.

- [ ] **Step 5: Manual end-to-end test**

Run: `python run.py` (from repo root, with `engine` on `PYTHONPATH` — i.e. run `cd engine && ../ui` build present, or set `PYTHONPATH=engine`).
1. Play a short talking YouTube clip, click **Start Recording**, type a couple rough notes, let the clip play ~20s.
2. Click **Stop** → lands on Meeting Detail.
3. Click **Transcribe** → transcript tab fills with the clip's speech (confirms system-audio loopback works).
4. Click **Enhance** → enhanced tab shows clean markdown notes.
5. Go to **Library**, search a word spoken in the clip → the meeting appears.

Expected: all five steps succeed. If transcript is empty, the loopback device wasn't found — check `Step 1 of Task 8`'s device match against `ollama`-independent audio output.

- [ ] **Step 6: Commit**

```bash
git add run.py engine/muesli_engine/app.py
git commit -m "feat: add pywebview desktop shell and static UI serving"
```

---

## Task 12: README + wrap-up

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write `README.md`** with: what Muesli is, prerequisites (Python 3.11+, Node, Ollama + `ollama pull qwen2.5:14b`, NVIDIA CUDA optional), setup (`pip install -r engine/requirements.txt`, `npm install && npm run build` in `ui/`), run (`python run.py`), and the v1 feature list.

- [ ] **Step 2: Run full test suite**

Run: `cd engine && .venv/Scripts/python -m pytest -v`
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add Muesli setup and usage README"
```

---

## Self-Review Notes

- **Spec coverage:** AI enhancement (Tasks 5,6,9), templates (Tasks 5,9,10), search (Task 4 FTS + Tasks 9,10), Granola-style notepad + manual Start/Stop (Task 10), manual Transcribe/Enhance buttons (Tasks 9,10,11), local-first + optional cloud (Task 6), pywebview shell (Task 11), GPU Whisper defaults (Tasks 2,7). All covered.
- **Type consistency:** `Meeting`/`Template` fields are identical across `models.py`, `db.py`, `routes.py`, and `client.ts`. Engine methods (`create_meeting`, `set_transcript`, `set_enhanced`, `search_meetings`, `list_templates`) are referenced consistently.
- **Known v1 simplification:** audio capture records system-loopback only (remote participants + shared audio). Mic-mixing is deferred to M2; noted in `capture.py` docstring so it isn't mistaken for a bug.
- **Cloud backend:** only OpenAI wired in `CloudBackend`; Anthropic raises a clear error. Acceptable for v1 since cloud is opt-in and off by default.
```
