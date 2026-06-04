from muesli_engine.enhance.templates import DEFAULT_TEMPLATES, build_prompt


def test_default_templates_present():
    names = {t.name for t in DEFAULT_TEMPLATES}
    assert {"General", "1:1", "Standup", "Sales Call"}.issubset(names)


def test_build_prompt_includes_notes_transcript_and_instructions():
    prompt = build_prompt(
        template_prompt="Format as a standup update.",
        rough_notes="talked about milk",
        transcript="We discussed buying milk tomorrow.",
    )
    assert "Format as a standup update." in prompt
    assert "talked about milk" in prompt
    assert "We discussed buying milk tomorrow." in prompt


def test_build_prompt_handles_empty_notes():
    prompt = build_prompt(
        template_prompt="Summarize.",
        rough_notes="",
        transcript="Some transcript.",
    )
    assert "(no rough notes were taken)" in prompt
