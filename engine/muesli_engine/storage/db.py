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
        row = self.conn.execute(
            "SELECT status FROM meetings WHERE id=?", (meeting_id,)
        ).fetchone()
        if row is None:
            return
        current = row[0]
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
