# Muesli M2.5 UX Foundation

> Design spec - 2026-06-05. Approved by Michael during brainstorming.

## Context

Muesli has an MVP desktop UI that can exercise the core notetaker workflow, but
the interface is still mostly a simple React shell with inline styles and
minimal workflow guidance. M3 is expected to add live transcript, speaker
diarization, calendar auto-detect, and packaging. Those features will increase
the amount of state and navigation the UI must explain.

The next milestone should be a focused UX foundation pass before M3. This is
not a final visual polish milestone. It should make the current app coherent,
pleasant, and extensible enough that M3 features have clear places to land.

## Goals

- Replace the MVP shell with a consistent app layout, visual system, and
  workflow hierarchy.
- Make the everyday flow clear: Library -> New Meeting -> Active Meeting ->
  Meeting Detail.
- Surface recording and processing state so users understand what the app is
  doing and what action is available next.
- Improve empty, loading, and error states enough that the app feels dependable.
- Shape Meeting Detail so future M3 surfaces can be added without a redesign.

## Non-Goals

- Do not build M3 features in this milestone: no live transcript, diarization,
  calendar integration, or installer work.
- Do not chase final brand polish or marketing-site presentation.
- Do not introduce a large component framework unless it clearly reduces work
  and fits the existing React/Vite app.
- Do not restructure the Python engine except where a narrow UI-facing state or
  error contract is needed.

## UX Direction

Muesli should feel like a quiet desktop work tool: focused, readable, and useful
during repeated meeting workflows. The UI should avoid marketing-style heroes or
decorative layouts. It should prioritize clear hierarchy, visible status, fast
scanning, and low-friction note taking.

The visual system should use:

- A stable application shell with persistent navigation.
- Consistent typography, spacing, buttons, inputs, tabs, and status chips.
- Restrained color, with status color used intentionally for recording,
  processing, success, and error states.
- Dense but calm layouts that work in a pywebview desktop window.

## Core Screens

### App Shell

The shell should provide obvious navigation between the main surfaces:

- Meetings / Library
- New or active meeting
- Templates
- Settings if the current codebase includes M2 settings locally

The layout should make the current location and primary action obvious without
requiring explanatory copy.

### Library

The Library should become a useful meeting index instead of a plain list. It
should include search, meeting status, created date, and compact previews where
available. Empty states should guide the user toward starting the first meeting.

### New And Active Meeting

The pre-recording state should make title and template selection clear. The
active-recording state should prioritize the rough notes editor and recording
status. Autosave should feel trustworthy through subtle save/status feedback,
without distracting from note taking.

### Meeting Detail

Meeting Detail should organize the post-meeting workflow around what the user
can do next:

- Review rough notes
- Transcribe when transcript is missing
- Enhance when transcript or notes are ready
- Read enhanced notes
- Inspect transcript

The screen should reserve clear structural space for M3 additions such as live
transcript history, speaker labels, and calendar metadata, but should not render
fake M3 functionality.

### Templates

Templates should have enough structure to support repeated use: readable list
items, selected/edit states if available in the current backend, and clear
empty/error states. If full template CRUD exists locally, the UI should present
it coherently; if it does not, M2.5 should only polish the available template
surface and avoid expanding backend scope.

## State Model

The UI should consistently describe the meeting lifecycle:

- Recording
- Stopped
- Needs transcription
- Transcribing
- Needs enhancement
- Enhancing
- Complete
- Failed or blocked

If the current backend status values are too coarse, add a narrow mapping layer
in the UI first. Only change the backend contract if the UI cannot reliably
derive the needed state.

## Error Handling

Errors should appear near the action that caused them and should be written as
practical next steps. Examples:

- Recording failed because no audio device is available.
- Transcription failed because the model is missing or the audio file cannot be
  read.
- Enhancement failed because Ollama is not running or the selected model is not
  available.

The UI should avoid swallowing errors or only logging them to the console.

## Testing And Verification

Implementation should include focused verification appropriate to the UI change:

- `npm run build` must pass.
- Existing engine tests should still pass if any API contracts change.
- Browser verification should cover the main desktop workflow:
  Library -> New Meeting -> Active Meeting -> Meeting Detail.
- Visual checks should confirm no obvious overlap or layout breakage at common
  desktop and narrow pywebview-sized viewports.
- Error, loading, and empty states should be manually exercised where practical.

## Planning Assumptions

- The implementation plan must inspect the local codebase first and base M2.5 on
  the features actually present in the working tree.
- A lightweight icon package such as `lucide-react` may be added if it makes the
  UI clearer and does not pull in a large component framework.
- Backend status changes should be avoided unless the React app cannot reliably
  derive the necessary display state from existing meeting fields.
