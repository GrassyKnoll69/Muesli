from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from muesli_engine.storage.models import Meeting, Template
from muesli_engine import secrets
from muesli_engine.enhance import llm
from muesli_engine.enhance.templates import build_prompt
from muesli_engine.export import assemble_export_markdown, export_filename
from muesli_engine.settings_store import save_settings


class StartRequest(BaseModel):
    title: str | None = None
    template_id: int | None = None


class NotesRequest(BaseModel):
    rough_notes: str


class EnhanceRequest(BaseModel):
    template_id: int | None = None


class SettingsUpdate(BaseModel):
    whisper_model: str | None = None
    whisper_device: str | None = None
    whisper_compute_type: str | None = None
    ollama_model: str | None = None
    ollama_host: str | None = None
    enhancement_backend: str | None = None
    cloud_provider: str | None = None
    cloud_model: str | None = None
    cloud_api_key: str | None = None


class TestCloudRequest(BaseModel):
    provider: str
    model: str
    key: str | None = None


class PreviewRequest(BaseModel):
    prompt: str
    rough_notes: str | None = None
    transcript: str | None = None


def build_router(ctx) -> APIRouter:
    """ctx exposes: db, settings, transcribe_fn, enhance_fn, recorder_factory."""
    router = APIRouter()

    def settings_payload() -> dict:
        s = ctx.settings
        return {
            "whisper_model": s.whisper_model,
            "whisper_device": s.whisper_device,
            "whisper_compute_type": s.whisper_compute_type,
            "ollama_model": s.ollama_model,
            "ollama_host": s.ollama_host,
            "enhancement_backend": s.enhancement_backend,
            "cloud_provider": s.cloud_provider,
            "cloud_model": s.cloud_model,
            "cloud_key_present": {
                "openai": bool(secrets.get_api_key("openai")),
                "anthropic": bool(secrets.get_api_key("anthropic")),
            },
        }

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

    @router.delete("/meetings/{meeting_id}")
    def delete_meeting(meeting_id: int):
        try:
            ctx.db.get_meeting(meeting_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="meeting not found")
        ctx.db.delete_meeting(meeting_id)
        return {"ok": True}

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

    @router.get("/settings")
    def get_settings():
        return settings_payload()

    @router.put("/settings")
    def update_settings(req: SettingsUpdate):
        partial = {k: v for k, v in req.model_dump().items() if v is not None}
        key = partial.pop("cloud_api_key", None)
        save_settings(ctx.db, ctx.settings, partial)
        if key is not None:
            provider = partial.get("cloud_provider") or ctx.settings.cloud_provider
            if not provider:
                raise HTTPException(status_code=422, detail="set a cloud provider before saving a key")
            try:
                secrets.set_api_key(provider, key)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"secure storage unavailable: {exc}")
        return settings_payload()

    @router.post("/settings/test-cloud")
    def test_cloud(req: TestCloudRequest):
        key = req.key or secrets.get_api_key(req.provider)
        if not key:
            return {"ok": False, "message": f"No API key set for {req.provider}"}
        ok, message = llm.validate_cloud(req.provider, key, req.model)
        return {"ok": ok, "message": message}

    @router.get("/ollama/models")
    def ollama_models():
        return llm.list_ollama_models(ctx.settings.ollama_host)

    @router.post("/templates/preview")
    def preview_template(req: PreviewRequest):
        notes = req.rough_notes if req.rough_notes is not None else "Sample rough notes."
        transcript = req.transcript if req.transcript is not None else "Sample transcript text."
        return {"prompt": build_prompt(req.prompt, notes, transcript)}

    @router.get("/meetings/{meeting_id}/export")
    def export_meeting(meeting_id: int):
        try:
            meeting = ctx.db.get_meeting(meeting_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="meeting not found")
        md = assemble_export_markdown(meeting)
        filename = export_filename(meeting)
        return Response(
            content=md,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router
