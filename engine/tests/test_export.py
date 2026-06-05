from datetime import datetime, timezone

from muesli_engine.export import assemble_export_markdown, export_filename
from muesli_engine.storage.models import Meeting


def test_assemble_includes_header_and_enhanced_notes():
    m = Meeting(
        title="Sales Call",
        created_at=datetime(2026, 6, 5, 14, 30, tzinfo=timezone.utc),
        enhanced_notes="## Summary\nGreat call",
    )
    md = assemble_export_markdown(m)
    assert md.startswith("# Sales Call")
    assert "2026-06-05" in md
    assert "## Summary" in md


def test_assemble_handles_empty_enhanced():
    m = Meeting(title="x", created_at=datetime(2026, 6, 5, tzinfo=timezone.utc))
    assert "_(not yet enhanced)_" in assemble_export_markdown(m)


def test_export_filename_is_slugged_with_date():
    m = Meeting(title="Sales Call!! 2026", created_at=datetime(2026, 6, 5, tzinfo=timezone.utc))
    assert export_filename(m) == "sales-call-2026-2026-06-05.md"


def test_export_filename_falls_back_when_title_empty():
    m = Meeting(title="", created_at=datetime(2026, 6, 5, tzinfo=timezone.utc))
    assert export_filename(m) == "meeting-2026-06-05.md"
