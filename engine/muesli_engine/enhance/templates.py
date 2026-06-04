from __future__ import annotations

from muesli_engine.storage.models import Template

DEFAULT_TEMPLATES: list[Template] = [
    Template(name="General", prompt=(
        "Rewrite the rough notes into clean, well-structured meeting notes. "
        "Use markdown headings, bullet points, and a short summary at the top."
    )),
    Template(name="1:1", prompt=(
        "Format as 1:1 notes with sections: Summary, Discussion Points, "
        "Action Items (with owners if mentioned), Follow-ups."
    )),
    Template(name="Standup", prompt=(
        "Format as a standup update with sections: Yesterday, Today, Blockers."
    )),
    Template(name="Sales Call", prompt=(
        "Format as sales-call notes with sections: Customer, Needs/Pain Points, "
        "Objections, Next Steps, Action Items."
    )),
]

_PROMPT = """You are an expert meeting-notes assistant. Using the meeting \
transcript and the user's rough notes, produce polished notes in GitHub-flavored \
markdown. Prioritize the user's rough notes; use the transcript to fill gaps and \
add accuracy. Do not invent facts that are not supported by the transcript or notes.

# Formatting instructions
{template_prompt}

# User's rough notes
{rough_notes}

# Transcript
{transcript}

# Output
Return only the finished markdown notes."""


def build_prompt(template_prompt: str, rough_notes: str, transcript: str) -> str:
    notes = rough_notes.strip() or "(no rough notes were taken)"
    body = transcript.strip() or "(no transcript available)"
    return _PROMPT.format(
        template_prompt=template_prompt.strip(),
        rough_notes=notes,
        transcript=body,
    )
