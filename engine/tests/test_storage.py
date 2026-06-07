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
