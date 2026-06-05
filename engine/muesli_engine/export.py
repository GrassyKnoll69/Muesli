from __future__ import annotations

import re

from muesli_engine.storage.models import Meeting


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "meeting"


def export_filename(meeting: Meeting) -> str:
    date = meeting.created_at.strftime("%Y-%m-%d")
    return f"{_slug(meeting.title)}-{date}.md"


def assemble_export_markdown(meeting: Meeting) -> str:
    date = meeting.created_at.strftime("%Y-%m-%d %H:%M")
    body = meeting.enhanced_notes.strip() or "_(not yet enhanced)_"
    return f"# {meeting.title}\n\n_{date}_\n\n{body}\n"
