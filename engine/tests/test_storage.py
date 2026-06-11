import sqlite3
import tempfile
import os
from datetime import datetime, timezone

from muesli_engine.storage.db import Database
from muesli_engine.storage.models import Meeting, Segment, Template


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


def test_delete_meeting_removes_it_from_listing_and_search():
    db = make_db()
    m = db.create_meeting(Meeting(title="Sales call", created_at=datetime.now(timezone.utc)))
    db.set_transcript(m.id, "customer asked about pricing tiers")

    db.delete_meeting(m.id)

    assert db.list_meetings() == []
    assert db.search_meetings("pricing") == []


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


# --- M3 storage tests ---

def test_replace_and_list_segments():
    db = make_db()
    m = db.create_meeting(Meeting(title="Seg Test", created_at=datetime.now(timezone.utc)))
    segs = [
        Segment(meeting_id=m.id, start=0.0, end=2.5, speaker_key="you", source="mic", text="Hello"),
        Segment(meeting_id=m.id, start=2.5, end=5.0, speaker_key="spk1", source="loopback", text="World"),
        Segment(meeting_id=m.id, start=1.0, end=2.5, speaker_key="spk2", source="loopback", text="Middle"),
    ]
    db.replace_segments(m.id, segs)
    result = db.list_segments(m.id)
    # ordered by start, id
    assert [s.start for s in result] == [0.0, 1.0, 2.5]
    assert result[0].text == "Hello"
    assert result[0].speaker_key == "you"
    assert result[1].text == "Middle"
    assert result[2].source == "loopback"


def test_replace_segments_replaces_existing():
    db = make_db()
    m = db.create_meeting(Meeting(title="Rep Test", created_at=datetime.now(timezone.utc)))
    db.replace_segments(m.id, [
        Segment(meeting_id=m.id, start=0.0, end=1.0, speaker_key="you", source="mic", text="Old"),
    ])
    db.replace_segments(m.id, [
        Segment(meeting_id=m.id, start=0.0, end=1.0, speaker_key="spk1", source="loopback", text="New"),
    ])
    result = db.list_segments(m.id)
    assert len(result) == 1
    assert result[0].text == "New"


def test_list_segments_empty():
    db = make_db()
    m = db.create_meeting(Meeting(title="Empty", created_at=datetime.now(timezone.utc)))
    assert db.list_segments(m.id) == []


def test_set_and_get_speaker_names():
    db = make_db()
    m = db.create_meeting(Meeting(title="Speaker Test", created_at=datetime.now(timezone.utc)))
    db.set_speaker_name(m.id, "spk1", "Alice")
    db.set_speaker_name(m.id, "spk2", "Bob")
    names = db.get_speaker_names(m.id)
    assert names == {"spk1": "Alice", "spk2": "Bob"}


def test_set_speaker_name_upsert():
    db = make_db()
    m = db.create_meeting(Meeting(title="Upsert Test", created_at=datetime.now(timezone.utc)))
    db.set_speaker_name(m.id, "spk1", "Alice")
    db.set_speaker_name(m.id, "spk1", "Alicia")
    names = db.get_speaker_names(m.id)
    assert names["spk1"] == "Alicia"


def test_get_speaker_names_empty():
    db = make_db()
    m = db.create_meeting(Meeting(title="No Speakers", created_at=datetime.now(timezone.utc)))
    assert db.get_speaker_names(m.id) == {}


def test_set_audio_paths():
    db = make_db()
    m = db.create_meeting(Meeting(title="Paths Test", created_at=datetime.now(timezone.utc)))
    db.set_audio_paths(m.id, loopback="/tmp/loop.wav", mic="/tmp/mic.wav")
    got = db.get_meeting(m.id)
    assert got.loopback_path == "/tmp/loop.wav"
    assert got.mic_path == "/tmp/mic.wav"


def test_set_audio_path_also_sets_loopback():
    """Deprecated set_audio_path should also set loopback_path for back-compat."""
    db = make_db()
    m = db.create_meeting(Meeting(title="Compat Test", created_at=datetime.now(timezone.utc)))
    db.set_audio_path(m.id, "/tmp/audio.wav")
    got = db.get_meeting(m.id)
    assert got.audio_path == "/tmp/audio.wav"
    assert got.loopback_path == "/tmp/audio.wav"


def test_set_diarized():
    db = make_db()
    m = db.create_meeting(Meeting(title="Diarized Test", created_at=datetime.now(timezone.utc)))
    assert db.get_meeting(m.id).diarized is False
    db.set_diarized(m.id, True)
    assert db.get_meeting(m.id).diarized is True
    db.set_diarized(m.id, False)
    assert db.get_meeting(m.id).diarized is False


def test_forward_migration_pre_m3_db(tmp_path):
    """A pre-M3 database (no new columns/tables) migrates forward without error."""
    db_path = str(tmp_path / "old.db")
    # Create a pre-M3 DB with old schema (no loopback_path, mic_path, diarized)
    old_schema = """
CREATE TABLE meetings (
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
CREATE TABLE templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    prompt TEXT NOT NULL
);
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
    conn = sqlite3.connect(db_path)
    conn.executescript(old_schema)
    conn.execute(
        "INSERT INTO meetings(title, created_at, status) VALUES(?,?,?)",
        ("Old Meeting", datetime(2025, 1, 1).isoformat(), "recorded"),
    )
    conn.commit()
    conn.close()

    # Now open with the new Database class and call init_schema (migration)
    db = Database(db_path)
    db.init_schema()  # should not raise

    # New columns exist and old meeting is readable
    old_meeting = db.get_meeting(1)
    assert old_meeting.title == "Old Meeting"
    assert old_meeting.diarized is False
    assert old_meeting.loopback_path is None
    assert old_meeting.mic_path is None

    # New tables exist
    result = db.list_segments(1)
    assert result == []
    names = db.get_speaker_names(1)
    assert names == {}
