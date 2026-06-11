from fastapi.testclient import TestClient

from muesli_engine.app import create_app
from muesli_engine.config import Settings
import muesli_engine.secrets as secrets


def client(open_path_fn=None) -> TestClient:
    # In-memory DB; stub transcribe/enhance so no models are needed.
    app = create_app(
        db_path=":memory:",
        transcribe_fn=lambda path, settings: "stub transcript about pricing",
        enhance_fn=lambda tprompt, notes, transcript: "## Summary\nstub enhanced",
        recorder_factory=None,
        open_path_fn=open_path_fn or (lambda path, select=False: None),
    )
    return TestClient(app)


# ---------------------------------------------------------------------------
# Diarization helpers
# ---------------------------------------------------------------------------

CANNED = [
    {"start": 0.0, "end": 1.0, "speaker_key": "you",  "source": "mic",      "text": "Hi there."},
    {"start": 1.0, "end": 2.0, "speaker_key": "spk1", "source": "loopback", "text": "Hello!"},
    {"start": 2.0, "end": 3.0, "speaker_key": "spk2", "source": "loopback", "text": "Afternoon."},
]


class _StubRecorder:
    """Minimal recorder stub: start is a no-op; stop returns a paths dict."""

    def __init__(self, path):
        self._path = str(path)

    def start(self):
        pass

    def stop(self) -> dict:
        return {"loopback": self._path + "-loopback.wav", "mic": None, "mic_offset": 0.0}


def _diarize_client(settings: Settings | None = None) -> TestClient:
    """Client wired with a stub recorder_factory and a stub diarize_fn."""
    app = create_app(
        db_path=":memory:",
        transcribe_fn=lambda path, settings: "stub transcript about pricing",
        enhance_fn=lambda tprompt, notes, transcript: "## Summary\nstub enhanced",
        recorder_factory=_StubRecorder,
        open_path_fn=lambda path, select=False: None,
        diarize_fn=lambda loopback, mic, offset, s: CANNED,
        settings=settings,
    )
    return TestClient(app)


def test_transcribe_falls_back_to_flat_when_diarization_fails():
    """Diarization is on by default but the models download lazily; a failing
    diarize_fn must fall back to a flat transcript, not 500 the request."""
    def boom(loopback, mic, offset, s):
        raise RuntimeError("diarization models not downloaded")

    app = create_app(
        db_path=":memory:",
        transcribe_fn=lambda path, settings: "flat fallback transcript",
        enhance_fn=lambda tprompt, notes, transcript: "## Summary\nstub",
        recorder_factory=_StubRecorder,
        open_path_fn=lambda path, select=False: None,
        diarize_fn=boom,
    )
    c = TestClient(app)
    mid = c.post("/recordings/start", json={"title": "Fallback"}).json()["id"]
    c.post(f"/recordings/{mid}/stop")
    r = c.post(f"/meetings/{mid}/transcribe")
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"] == "flat fallback transcript"
    assert body["diarized"] is False
    assert c.get(f"/meetings/{mid}/segments").json() == []


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


def test_get_settings_returns_defaults_without_key(monkeypatch):
    monkeypatch.setattr(secrets, "get_api_key", lambda provider: None)
    c = client()
    data = c.get("/settings").json()
    assert data["whisper_model"] == "large-v3"
    assert data["enhancement_backend"] == "ollama"
    assert data["cloud_key_present"] == {"openai": False, "anthropic": False}
    assert "cloud_api_key" not in data


def test_put_settings_persists_and_stores_key_in_keyring(monkeypatch):
    store = {}
    monkeypatch.setattr(secrets, "set_api_key", lambda p, k: store.__setitem__(p, k))
    monkeypatch.setattr(secrets, "get_api_key", lambda p: store.get(p))
    c = client()
    body = c.put("/settings", json={
        "ollama_model": "llama3.1:8b",
        "cloud_provider": "openai",
        "cloud_api_key": "sk-test",
    }).json()
    assert body["ollama_model"] == "llama3.1:8b"
    assert body["cloud_provider"] == "openai"
    assert body["cloud_key_present"]["openai"] is True
    assert "cloud_api_key" not in body
    assert store["openai"] == "sk-test"
    assert c.get("/settings").json()["ollama_model"] == "llama3.1:8b"


def test_test_cloud_uses_validator(monkeypatch):
    from muesli_engine.enhance import llm
    monkeypatch.setattr(llm, "validate_cloud", lambda provider, key, model: (True, "Connection OK"))
    monkeypatch.setattr(secrets, "get_api_key", lambda p: "stored-key")
    c = client()
    res = c.post("/settings/test-cloud", json={"provider": "openai", "model": "gpt-4o-mini"}).json()
    assert res["ok"] is True
    assert res["message"] == "Connection OK"


def test_test_cloud_without_key_reports_not_ok(monkeypatch):
    monkeypatch.setattr(secrets, "get_api_key", lambda p: None)
    c = client()
    res = c.post("/settings/test-cloud", json={"provider": "anthropic", "model": "claude-3-5-sonnet-latest"}).json()
    assert res["ok"] is False


def test_ollama_models_endpoint(monkeypatch):
    from muesli_engine.enhance import llm
    monkeypatch.setattr(llm, "list_ollama_models", lambda host: ["a", "b"])
    c = client()
    assert c.get("/ollama/models").json() == ["a", "b"]


def test_export_endpoint_sets_attachment_headers():
    c = client()
    mid = c.post("/recordings/start", json={"title": "Sales"}).json()["id"]
    c.post(f"/meetings/{mid}/transcribe")
    c.post(f"/meetings/{mid}/enhance", json={"template_id": None})
    r = c.get(f"/meetings/{mid}/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert ".md" in r.headers["content-disposition"]
    assert r.text.startswith("# Sales")


def test_template_preview_returns_assembled_prompt():
    c = client()
    p = c.post("/templates/preview", json={"prompt": "Format as standup.", "rough_notes": "hi"}).json()["prompt"]
    assert "Format as standup." in p
    assert "hi" in p


def test_delete_meeting_removes_old_note():
    c = client()
    mid = c.post("/recordings/start", json={"title": "Old notes"}).json()["id"]

    assert c.delete(f"/meetings/{mid}").json() == {"ok": True}
    assert c.get(f"/meetings/{mid}").status_code == 404


def test_open_meeting_location_uses_file_explorer_hook():
    opened = []
    c = client(open_path_fn=lambda path, select=False: opened.append((str(path), select)))
    mid = c.post("/recordings/start", json={"title": "Open me"}).json()["id"]

    response = c.post(f"/meetings/{mid}/open-location")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert len(opened) == 1
    assert opened[0][1] is False


# ---------------------------------------------------------------------------
# Diarization tests
# ---------------------------------------------------------------------------

def test_diarize_transcribe_persists_segments_and_returns_them_ordered():
    """Start → stop → transcribe persists canned segments; GET /segments returns
    3 items ordered by start with correct fields and human display_names."""
    c = _diarize_client()
    mid = c.post("/recordings/start", json={"title": "Diarized"}).json()["id"]
    c.post(f"/recordings/{mid}/stop")
    c.post(f"/meetings/{mid}/transcribe")

    segs = c.get(f"/meetings/{mid}/segments").json()
    assert len(segs) == 3
    # Ordered by start
    assert [s["start"] for s in segs] == [0.0, 1.0, 2.0]
    # speaker_key, source, text correct
    assert segs[0]["speaker_key"] == "you"
    assert segs[0]["source"] == "mic"
    assert segs[0]["text"] == "Hi there."
    assert segs[1]["speaker_key"] == "spk1"
    assert segs[1]["source"] == "loopback"
    assert segs[1]["text"] == "Hello!"
    assert segs[2]["speaker_key"] == "spk2"
    assert segs[2]["source"] == "loopback"
    assert segs[2]["text"] == "Afternoon."
    # display_names humanized from keys
    assert segs[0]["display_name"] == "You"
    assert segs[1]["display_name"] == "Speaker 1"
    assert segs[2]["display_name"] == "Speaker 2"


def test_diarize_transcribe_sets_attributed_transcript_and_diarized_flag():
    """After diarization, the meeting transcript is the attributed string and
    diarized is True."""
    c = _diarize_client()
    mid = c.post("/recordings/start", json={"title": "Attributed"}).json()["id"]
    c.post(f"/recordings/{mid}/stop")
    meeting = c.post(f"/meetings/{mid}/transcribe").json()

    expected_transcript = "You: Hi there.\nSpeaker 1: Hello!\nSpeaker 2: Afternoon."
    assert meeting["transcript"] == expected_transcript
    assert meeting["diarized"] is True


def test_rename_speaker_updates_attributed_transcript_and_segments():
    """PUT /meetings/{id}/speakers with {speaker_key, display_name} updates the
    attributed transcript and GET /segments shows the new display_name."""
    c = _diarize_client()
    mid = c.post("/recordings/start", json={"title": "Rename"}).json()["id"]
    c.post(f"/recordings/{mid}/stop")
    c.post(f"/meetings/{mid}/transcribe")

    # Rename spk1 → Alice
    segs = c.put(f"/meetings/{mid}/speakers",
                 json={"speaker_key": "spk1", "display_name": "Alice"}).json()

    # Segments payload shows updated display_name
    assert any(s["display_name"] == "Alice" and s["speaker_key"] == "spk1" for s in segs)
    # spk2 still has humanized default
    assert any(s["display_name"] == "Speaker 2" for s in segs)

    # Meeting transcript now contains "Alice:"
    meeting = c.get(f"/meetings/{mid}").json()
    assert "Alice: Hello!" in meeting["transcript"]
    assert "You: Hi there." in meeting["transcript"]
    assert "Speaker 2: Afternoon." in meeting["transcript"]

    # GET /segments also shows Alice
    segs2 = c.get(f"/meetings/{mid}/segments").json()
    alice_seg = next(s for s in segs2 if s["speaker_key"] == "spk1")
    assert alice_seg["display_name"] == "Alice"


def test_transcribe_flat_path_when_diarization_disabled():
    """With enable_diarization=False, transcribe still works via the flat
    transcribe_fn path and persists no segments."""
    c = _diarize_client(settings=Settings(enable_diarization=False))
    mid = c.post("/recordings/start", json={"title": "Flat"}).json()["id"]
    # No real recorder → no audio path; just call transcribe directly
    meeting = c.post(f"/meetings/{mid}/transcribe").json()

    # Flat transcribe_fn stub used
    assert meeting["transcript"] == "stub transcript about pricing"
    assert meeting["diarized"] is False

    # No segments stored
    segs = c.get(f"/meetings/{mid}/segments").json()
    assert segs == []


def test_get_settings_includes_diarization_fields(monkeypatch):
    """GET /settings returns the three new diarization fields."""
    monkeypatch.setattr(secrets, "get_api_key", lambda provider: None)
    c = client()
    data = c.get("/settings").json()
    assert data["enable_diarization"] is True
    assert data["diarization_threshold"] == 0.5
    assert data["mic_device"] is None


def test_put_settings_diarization_fields_persist(monkeypatch):
    """PUT /settings with enable_diarization=False and diarization_threshold=0.7
    persists and returns the updated values."""
    monkeypatch.setattr(secrets, "get_api_key", lambda p: None)
    monkeypatch.setattr(secrets, "set_api_key", lambda p, k: None)
    c = client()
    body = c.put("/settings", json={
        "enable_diarization": False,
        "diarization_threshold": 0.7,
    }).json()
    assert body["enable_diarization"] is False
    assert abs(body["diarization_threshold"] - 0.7) < 1e-9
    # Confirm persisted — re-read settings
    reloaded = c.get("/settings").json()
    assert reloaded["enable_diarization"] is False
    assert abs(reloaded["diarization_threshold"] - 0.7) < 1e-9


def test_audio_devices_endpoint_returns_correct_shape(monkeypatch):
    """GET /audio/devices returns a dict with list-typed 'loopback' and 'input' keys."""
    from muesli_engine.audio import capture
    monkeypatch.setattr(capture, "list_devices", lambda: {"loopback": ["Speaker A [Loopback]"], "input": ["Mic B"]})
    c = client()
    data = c.get("/audio/devices").json()
    assert "loopback" in data
    assert "input" in data
    assert isinstance(data["loopback"], list)
    assert isinstance(data["input"], list)


def test_put_settings_capture_device_round_trips(monkeypatch):
    """PUT capture_device='Arctis' then GET shows capture_device == 'Arctis'."""
    monkeypatch.setattr(secrets, "get_api_key", lambda p: None)
    monkeypatch.setattr(secrets, "set_api_key", lambda p, k: None)
    c = client()
    body = c.put("/settings", json={"capture_device": "Arctis"}).json()
    assert body["capture_device"] == "Arctis"
    reloaded = c.get("/settings").json()
    assert reloaded["capture_device"] == "Arctis"


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

def test_health_endpoint_returns_expected_keys(monkeypatch):
    """GET /health returns a dict with exactly the six required keys."""
    import muesli_engine.health as health

    monkeypatch.setattr(health, "check_ollama", lambda host: True)
    monkeypatch.setattr(health, "check_webview2", lambda: True)
    monkeypatch.setattr(health, "check_diarization_models", lambda: False)
    monkeypatch.setattr(health, "check_whisper_model", lambda settings: False)
    monkeypatch.setattr(health, "check_gpu", lambda: False)
    monkeypatch.setattr(health, "check_cuda_libraries", lambda: False)

    c = client()
    data = c.get("/health").json()

    assert set(data.keys()) == {
        "ollama",
        "webview2",
        "diarization_models",
        "whisper_model",
        "gpu_present",
        "cuda_libraries",
    }


# ---------------------------------------------------------------------------
# Download trigger endpoints
# ---------------------------------------------------------------------------

def test_download_diarization_models_returns_ok(monkeypatch):
    """POST /models/diarization/download returns ok=True with model paths when
    ensure_diarization_models succeeds."""
    import muesli_engine.models_store as ms
    monkeypatch.setattr(
        ms,
        "ensure_diarization_models",
        lambda: {"segmentation": "/models/seg.onnx", "embedding": "/models/emb.onnx"},
    )
    c = client()
    r = c.post("/models/diarization/download")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["segmentation"] == "/models/seg.onnx"
    assert data["embedding"] == "/models/emb.onnx"


def test_download_diarization_models_returns_500_on_error(monkeypatch):
    """POST /models/diarization/download returns 500 when ensure_diarization_models
    raises an exception."""
    import muesli_engine.models_store as ms
    monkeypatch.setattr(
        ms,
        "ensure_diarization_models",
        lambda: (_ for _ in ()).throw(RuntimeError("network error")),
    )
    c = client()
    r = c.post("/models/diarization/download")
    assert r.status_code == 500
    assert "model download failed" in r.json()["detail"]


def test_download_cuda_libraries_returns_ok(monkeypatch):
    """POST /cuda/download returns ok=True with path when ensure_cuda_libraries
    succeeds."""
    import muesli_engine.models_store as ms
    monkeypatch.setattr(ms, "ensure_cuda_libraries", lambda: "/cuda/libs")
    c = client()
    r = c.post("/cuda/download")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["path"] == "/cuda/libs"


def test_download_cuda_libraries_returns_500_on_error(monkeypatch):
    """POST /cuda/download returns 500 when ensure_cuda_libraries raises."""
    import muesli_engine.models_store as ms
    monkeypatch.setattr(
        ms,
        "ensure_cuda_libraries",
        lambda: (_ for _ in ()).throw(RuntimeError("disk full")),
    )
    c = client()
    r = c.post("/cuda/download")
    assert r.status_code == 500
    assert "CUDA download failed" in r.json()["detail"]


def test_health_endpoint_reflects_stub_values(monkeypatch):
    """GET /health values reflect the monkeypatched check functions."""
    import muesli_engine.health as health

    monkeypatch.setattr(health, "check_ollama", lambda host: True)
    monkeypatch.setattr(health, "check_webview2", lambda: True)
    monkeypatch.setattr(health, "check_diarization_models", lambda: True)
    monkeypatch.setattr(health, "check_whisper_model", lambda settings: True)
    monkeypatch.setattr(health, "check_gpu", lambda: False)
    monkeypatch.setattr(health, "check_cuda_libraries", lambda: False)

    c = client()
    data = c.get("/health").json()

    assert data["ollama"] is True
    assert data["webview2"] is True
    assert data["diarization_models"] is True
    assert data["whisper_model"] is True
    assert data["gpu_present"] is False
    assert data["cuda_libraries"] is False
