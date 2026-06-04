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
