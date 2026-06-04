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
        template_id = req.template_id if req.template_id is not None else meeting.template_id
        if template_id is not None:
            template_prompt = ctx.db.get_template(template_id).prompt
        else:
            templates = ctx.db.list_templates()
            if not templates:
                raise HTTPException(status_code=422, detail="no template available to enhance with")
            template_prompt = templates[0].prompt
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
