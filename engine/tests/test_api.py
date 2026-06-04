from fastapi.testclient import TestClient

from muesli_engine.app import create_app


def client() -> TestClient:
    # In-memory DB; stub transcribe/enhance so no models are needed.
    app = create_app(
        db_path=":memory:",
        transcribe_fn=lambda path, settings: "stub transcript about pricing",
        enhance_fn=lambda tprompt, notes, transcript: "## Summary\nstub enhanced",
        recorder_factory=None,
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
