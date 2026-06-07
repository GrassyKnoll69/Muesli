from fastapi.testclient import TestClient

from muesli_engine.app import create_app
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
