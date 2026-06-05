# Muesli M2.5 UX Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a focused UX foundation for the existing Muesli MVP UI so the app feels coherent now and has clear places for M3 features later.

**Architecture:** Keep the existing React/Vite frontend and FastAPI engine boundary. Add a small UI system, pure meeting-state helper, and focused page refactors without expanding backend feature scope unless the existing API cannot surface a needed UI state.

**Tech Stack:** React 18, TypeScript, Vite, React Router, CSS, optional Vitest for pure frontend logic tests, FastAPI engine only if a narrow API contract adjustment becomes necessary.

---

## Scope Check

The approved spec is one bounded UI milestone. It covers one subsystem: the existing React desktop UI. M3 features remain out of scope.

## File Structure

- Modify: `ui/package.json` - add a frontend test script and `vitest` dev dependency if tests are introduced.
- Modify: `ui/src/main.tsx` - import global styles.
- Modify: `ui/src/App.tsx` - replace inline nav with an app shell.
- Create: `ui/src/styles.css` - global tokens, layout, controls, tabs, cards, status chips, responsive rules.
- Create: `ui/src/lib/meetingState.ts` - derive user-facing meeting state from existing `Meeting` fields.
- Create: `ui/src/lib/meetingState.test.ts` - unit tests for state derivation.
- Create: `ui/src/components/StatusChip.tsx` - reusable status display.
- Create: `ui/src/components/EmptyState.tsx` - reusable empty state.
- Create: `ui/src/components/ErrorBanner.tsx` - reusable error display.
- Modify: `ui/src/api/client.ts` - normalize API error messages and expose the current existing API.
- Modify: `ui/src/pages/Library.tsx` - searchable meeting index with status, dates, and empty/error/loading states.
- Modify: `ui/src/pages/ActiveMeeting.tsx` - clearer pre-recording form, active notes editor, save feedback, recording error handling.
- Modify: `ui/src/pages/MeetingDetail.tsx` - structured workflow view with tabs, actions, state-aware prompts, and future M3 slots.
- Modify: `ui/src/pages/Templates.tsx` - readable template index with loading/error/empty states.

## Task 1: Add Frontend Test Harness And Meeting State Helper

**Files:**
- Modify: `ui/package.json`
- Create: `ui/src/lib/meetingState.ts`
- Create: `ui/src/lib/meetingState.test.ts`

- [ ] **Step 1: Add Vitest to the frontend scripts**

Edit `ui/package.json` so the scripts and dev dependencies include:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.4",
    "vite": "^8.0.16",
    "vitest": "^2.1.1"
  }
}
```

Keep the existing `dependencies` block unchanged.

- [ ] **Step 2: Write failing meeting-state tests**

Create `ui/src/lib/meetingState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { Meeting } from "../api/client";
import { deriveMeetingState } from "./meetingState";

function meeting(overrides: Partial<Meeting> = {}): Meeting {
  return {
    id: 1,
    title: "Weekly sync",
    created_at: "2026-06-05T18:00:00Z",
    rough_notes: "",
    transcript: "",
    enhanced_notes: "",
    template_id: null,
    audio_path: null,
    status: "created",
    ...overrides,
  };
}

describe("deriveMeetingState", () => {
  it("shows recording when the backend status says recording", () => {
    expect(deriveMeetingState(meeting({ status: "recording" })).label).toBe("Recording");
  });

  it("asks for transcription after a stopped meeting has audio but no transcript", () => {
    expect(deriveMeetingState(meeting({ status: "stopped", audio_path: "meeting.wav" })).label).toBe("Needs transcription");
  });

  it("asks for enhancement when transcript exists but enhanced notes are empty", () => {
    expect(deriveMeetingState(meeting({ transcript: "Full transcript" })).label).toBe("Needs enhancement");
  });

  it("marks a meeting complete when enhanced notes exist", () => {
    expect(deriveMeetingState(meeting({ enhanced_notes: "# Notes" })).label).toBe("Complete");
  });

  it("marks failed backend statuses as blocked", () => {
    expect(deriveMeetingState(meeting({ status: "failed" })).tone).toBe("danger");
  });
});
```

- [ ] **Step 3: Run the tests and verify they fail**

Run:

```bash
cd ui
npm install
npm run test -- meetingState
```

Expected: tests fail because `ui/src/lib/meetingState.ts` does not exist.

- [ ] **Step 4: Implement the meeting-state helper**

Create `ui/src/lib/meetingState.ts`:

```ts
import { Meeting } from "../api/client";

export type MeetingStateTone = "neutral" | "recording" | "warning" | "success" | "danger" | "busy";

export interface MeetingDisplayState {
  key:
    | "recording"
    | "stopped"
    | "needs-transcription"
    | "transcribing"
    | "needs-enhancement"
    | "enhancing"
    | "complete"
    | "blocked";
  label: string;
  tone: MeetingStateTone;
  nextAction: string;
}

function hasText(value: string | null | undefined): boolean {
  return Boolean(value && value.trim().length > 0);
}

export function deriveMeetingState(meeting: Meeting): MeetingDisplayState {
  const status = meeting.status.toLowerCase();

  if (status.includes("record")) {
    return { key: "recording", label: "Recording", tone: "recording", nextAction: "Keep taking notes or stop recording." };
  }

  if (status.includes("transcrib")) {
    return { key: "transcribing", label: "Transcribing", tone: "busy", nextAction: "Wait for transcription to finish." };
  }

  if (status.includes("enhanc")) {
    return { key: "enhancing", label: "Enhancing", tone: "busy", nextAction: "Wait for note enhancement to finish." };
  }

  if (status.includes("fail") || status.includes("error")) {
    return { key: "blocked", label: "Failed", tone: "danger", nextAction: "Review the error and retry the last action." };
  }

  if (hasText(meeting.enhanced_notes)) {
    return { key: "complete", label: "Complete", tone: "success", nextAction: "Review enhanced notes." };
  }

  if (hasText(meeting.transcript)) {
    return { key: "needs-enhancement", label: "Needs enhancement", tone: "warning", nextAction: "Enhance notes." };
  }

  if (meeting.audio_path || status.includes("stop")) {
    return { key: "needs-transcription", label: "Needs transcription", tone: "warning", nextAction: "Transcribe audio." };
  }

  return { key: "stopped", label: "Stopped", tone: "neutral", nextAction: "Add notes or start processing." };
}
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
cd ui
npm run test -- meetingState
npm run build
```

Expected: meeting-state tests pass and the Vite build succeeds.

Commit:

```bash
git add ui/package.json ui/package-lock.json ui/src/lib/meetingState.ts ui/src/lib/meetingState.test.ts
git commit -m "test: add meeting state derivation"
```

## Task 2: Add UI System And Reusable Components

**Files:**
- Modify: `ui/src/main.tsx`
- Create: `ui/src/styles.css`
- Create: `ui/src/components/StatusChip.tsx`
- Create: `ui/src/components/EmptyState.tsx`
- Create: `ui/src/components/ErrorBanner.tsx`

- [ ] **Step 1: Import global styles**

Modify `ui/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 2: Create global styles**

Create `ui/src/styles.css`:

```css
:root {
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #1f2933;
  background: #f6f7f4;
  --bg: #f6f7f4;
  --surface: #ffffff;
  --surface-muted: #eef1ed;
  --border: #d8ded4;
  --text: #1f2933;
  --muted: #68746a;
  --accent: #256f5c;
  --accent-strong: #174b3f;
  --danger: #b42318;
  --warning: #ad6200;
  --success: #237a4b;
  --busy: #3858a8;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background: var(--bg);
}

a { color: inherit; text-decoration: none; }

button, input, select, textarea {
  font: inherit;
}

button {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
}

button:hover { border-color: var(--accent); }
button:disabled { cursor: not-allowed; opacity: 0.6; }

.button-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.button-danger {
  background: var(--danger);
  border-color: var(--danger);
  color: white;
}

.app-shell {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}

.sidebar {
  border-right: 1px solid var(--border);
  background: #fbfcfa;
  padding: 20px 16px;
}

.brand {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 24px;
}

.brand-title {
  font-size: 22px;
  font-weight: 750;
}

.brand-subtitle {
  color: var(--muted);
  font-size: 13px;
}

.nav-list {
  display: grid;
  gap: 6px;
}

.nav-link {
  border-radius: 6px;
  color: var(--muted);
  padding: 9px 10px;
}

.nav-link.active {
  background: var(--surface-muted);
  color: var(--accent-strong);
  font-weight: 650;
}

.main {
  padding: 24px;
}

.page {
  max-width: 1040px;
  margin: 0 auto;
}

.page-header {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.eyebrow {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-title {
  font-size: 30px;
  line-height: 1.15;
  margin: 4px 0;
}

.page-description {
  color: var(--muted);
  margin: 0;
}

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}

.stack {
  display: grid;
  gap: 14px;
}

.cluster {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.field {
  display: grid;
  gap: 6px;
}

.field label {
  color: var(--muted);
  font-size: 13px;
  font-weight: 650;
}

.input, .select, .textarea {
  background: white;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  min-height: 40px;
  padding: 9px 10px;
  width: 100%;
}

.textarea {
  min-height: 360px;
  resize: vertical;
}

.status-chip {
  border-radius: 999px;
  display: inline-flex;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  padding: 6px 9px;
}

.status-neutral { background: #eef1ed; color: #48534a; }
.status-recording { background: #fee4e2; color: #b42318; }
.status-warning { background: #fff2cc; color: #8a4b00; }
.status-success { background: #dcf4e7; color: #19613a; }
.status-danger { background: #fee4e2; color: #9f1f17; }
.status-busy { background: #e8edff; color: #2d4c9a; }

.tabs {
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 4px;
}

.tab {
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  color: var(--muted);
  padding: 10px 12px;
}

.tab.active {
  border-bottom-color: var(--accent);
  color: var(--accent-strong);
  font-weight: 700;
}

.muted { color: var(--muted); }
.error-banner {
  background: #fff1f0;
  border: 1px solid #ffcbc5;
  border-radius: 8px;
  color: var(--danger);
  padding: 12px 14px;
}

.empty-state {
  align-items: center;
  background: var(--surface);
  border: 1px dashed var(--border);
  border-radius: 8px;
  display: grid;
  justify-items: center;
  padding: 32px;
  text-align: center;
}

.meeting-grid {
  display: grid;
  gap: 10px;
}

.meeting-row {
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  gap: 8px;
  grid-template-columns: 1fr auto;
  padding: 14px;
}

.pre {
  background: #fbfcfa;
  border: 1px solid var(--border);
  border-radius: 8px;
  line-height: 1.55;
  min-height: 280px;
  overflow: auto;
  padding: 16px;
  white-space: pre-wrap;
}

@media (max-width: 760px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid var(--border); }
  .nav-list { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .main { padding: 16px; }
  .page-header { display: grid; }
  .meeting-row { grid-template-columns: 1fr; }
}
```

- [ ] **Step 3: Add reusable components**

Create `ui/src/components/StatusChip.tsx`:

```tsx
import { MeetingStateTone } from "../lib/meetingState";

interface StatusChipProps {
  label: string;
  tone: MeetingStateTone;
}

export default function StatusChip({ label, tone }: StatusChipProps) {
  return <span className={`status-chip status-${tone}`}>{label}</span>;
}
```

Create `ui/src/components/EmptyState.tsx`:

```tsx
import { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export default function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <h2>{title}</h2>
      <p className="muted">{description}</p>
      {action}
    </div>
  );
}
```

Create `ui/src/components/ErrorBanner.tsx`:

```tsx
interface ErrorBannerProps {
  message: string;
}

export default function ErrorBanner({ message }: ErrorBannerProps) {
  if (!message) return null;
  return <div className="error-banner">{message}</div>;
}
```

- [ ] **Step 4: Build and commit**

Run:

```bash
cd ui
npm run build
```

Expected: TypeScript and Vite build succeed.

Commit:

```bash
git add ui/src/main.tsx ui/src/styles.css ui/src/components/StatusChip.tsx ui/src/components/EmptyState.tsx ui/src/components/ErrorBanner.tsx
git commit -m "feat: add muesli ui system"
```

## Task 3: Normalize API Error Messages

**Files:**
- Modify: `ui/src/api/client.ts`

- [ ] **Step 1: Update the API client**

Replace `ui/src/api/client.ts` with:

```ts
export interface Meeting {
  id: number;
  title: string;
  created_at: string;
  rough_notes: string;
  transcript: string;
  enhanced_notes: string;
  template_id: number | null;
  audio_path: string | null;
  status: string;
}

export interface Template {
  id: number;
  name: string;
  prompt: string;
}

async function readError(r: Response): Promise<string> {
  const text = await r.text();
  if (!text) return `${r.status} ${r.statusText}`.trim();
  try {
    const parsed = JSON.parse(text);
    return parsed.detail || parsed.message || text;
  } catch {
    return text;
  }
}

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
}

export const api = {
  listMeetings: () => fetch("/meetings").then(j<Meeting[]>),
  searchMeetings: (q: string) =>
    fetch(`/meetings/search?q=${encodeURIComponent(q)}`).then(j<Meeting[]>),
  getMeeting: (id: number) => fetch(`/meetings/${id}`).then(j<Meeting>),
  start: (title: string, template_id: number | null) =>
    fetch("/recordings/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, template_id }),
    }).then(j<Meeting>),
  stop: (id: number) =>
    fetch(`/recordings/${id}/stop`, { method: "POST" }).then(j<Meeting>),
  saveNotes: (id: number, rough_notes: string) =>
    fetch(`/meetings/${id}/notes`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rough_notes }),
    }).then(j<{ ok: boolean }>),
  transcribe: (id: number) =>
    fetch(`/meetings/${id}/transcribe`, { method: "POST" }).then(j<Meeting>),
  enhance: (id: number, template_id: number | null) =>
    fetch(`/meetings/${id}/enhance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_id }),
    }).then(j<Meeting>),
  listTemplates: () => fetch("/templates").then(j<Template[]>),
};
```

- [ ] **Step 2: Build and commit**

Run:

```bash
cd ui
npm run build
```

Expected: build succeeds.

Commit:

```bash
git add ui/src/api/client.ts
git commit -m "fix: surface readable api errors"
```

## Task 4: Replace The MVP App Shell

**Files:**
- Modify: `ui/src/App.tsx`

- [ ] **Step 1: Replace inline nav with app shell**

Replace `ui/src/App.tsx` with:

```tsx
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import ActiveMeeting from "./pages/ActiveMeeting";
import Library from "./pages/Library";
import MeetingDetail from "./pages/MeetingDetail";
import Templates from "./pages/Templates";

function navClass({ isActive }: { isActive: boolean }) {
  return `nav-link${isActive ? " active" : ""}`;
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-title">Muesli</div>
            <div className="brand-subtitle">Local AI meeting notes</div>
          </div>
          <nav className="nav-list" aria-label="Primary navigation">
            <NavLink className={navClass} to="/">Meetings</NavLink>
            <NavLink className={navClass} to="/new">Record</NavLink>
            <NavLink className={navClass} to="/templates">Templates</NavLink>
          </nav>
        </aside>
        <main className="main">
          <Routes>
            <Route path="/" element={<Library />} />
            <Route path="/new" element={<ActiveMeeting />} />
            <Route path="/meetings/:id" element={<MeetingDetail />} />
            <Route path="/templates" element={<Templates />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Build and commit**

Run:

```bash
cd ui
npm run build
```

Expected: build succeeds and nav links compile with React Router.

Commit:

```bash
git add ui/src/App.tsx
git commit -m "feat: add app shell navigation"
```

## Task 5: Upgrade Library To Meeting Index

**Files:**
- Modify: `ui/src/pages/Library.tsx`

- [ ] **Step 1: Replace the Library page**

Replace `ui/src/pages/Library.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import StatusChip from "../components/StatusChip";
import { api, Meeting } from "../api/client";
import { deriveMeetingState } from "../lib/meetingState";

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export default function Library() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(nextQuery = q) {
    setLoading(true);
    setError("");
    try {
      setMeetings(nextQuery.trim() ? await api.searchMeetings(nextQuery.trim()) : await api.listMeetings());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load meetings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(""); }, []);

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Library</div>
          <h1 className="page-title">Meetings</h1>
          <p className="page-description">Search transcripts and notes from past recordings.</p>
        </div>
        <Link className="button-primary" to="/new">Record meeting</Link>
      </div>

      <div className="stack">
        <form className="panel cluster" onSubmit={(e) => { e.preventDefault(); load(); }}>
          <input className="input" placeholder="Search notes and transcripts" value={q} onChange={(e) => setQ(e.target.value)} />
          <button type="submit">Search</button>
          {q && <button type="button" onClick={() => { setQ(""); load(""); }}>Clear</button>}
        </form>

        <ErrorBanner message={error} />

        {loading && <div className="panel muted">Loading meetings...</div>}

        {!loading && meetings.length === 0 && (
          <EmptyState
            title={q.trim() ? "No meetings found" : "No meetings yet"}
            description={q.trim() ? "Try a different search term." : "Start a recording to create your first meeting note."}
            action={<Link className="button-primary" to="/new">Record meeting</Link>}
          />
        )}

        {!loading && meetings.length > 0 && (
          <div className="meeting-grid">
            {meetings.map((meeting) => {
              const state = deriveMeetingState(meeting);
              return (
                <Link className="meeting-row" key={meeting.id} to={`/meetings/${meeting.id}`}>
                  <div>
                    <strong>{meeting.title}</strong>
                    <div className="muted">{formatDate(meeting.created_at)}</div>
                  </div>
                  <StatusChip label={state.label} tone={state.tone} />
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Build and commit**

Run:

```bash
cd ui
npm run build
```

Expected: build succeeds.

Commit:

```bash
git add ui/src/pages/Library.tsx
git commit -m "feat: upgrade meeting library"
```

## Task 6: Upgrade New And Active Meeting Workflow

**Files:**
- Modify: `ui/src/pages/ActiveMeeting.tsx`

- [ ] **Step 1: Replace the Active Meeting page**

Replace `ui/src/pages/ActiveMeeting.tsx` with:

```tsx
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ErrorBanner from "../components/ErrorBanner";
import StatusChip from "../components/StatusChip";
import { api, Template } from "../api/client";

type SaveState = "idle" | "saving" | "saved" | "error";

export default function ActiveMeeting() {
  const [meetingId, setMeetingId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [error, setError] = useState("");
  const nav = useNavigate();
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    api.listTemplates()
      .then(setTemplates)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load templates."));
  }, []);

  async function start() {
    setError("");
    try {
      const meeting = await api.start(title || "Untitled meeting", templateId);
      setMeetingId(meeting.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start recording.");
    }
  }

  function saveNotes(meeting: number, nextNotes: string) {
    setSaveState("saving");
    api.saveNotes(meeting, nextNotes)
      .then(() => setSaveState("saved"))
      .catch((err) => {
        setSaveState("error");
        setError(err instanceof Error ? err.message : "Could not save notes.");
      });
  }

  function onNotes(v: string) {
    setNotes(v);
    if (meetingId) {
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => saveNotes(meetingId, v), 600);
    }
  }

  async function stop() {
    if (!meetingId) return;
    setError("");
    try {
      await api.saveNotes(meetingId, notes);
      await api.stop(meetingId);
      nav(`/meetings/${meetingId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not stop recording.");
    }
  }

  if (meetingId === null) {
    return (
      <section className="page">
        <div className="page-header">
          <div>
            <div className="eyebrow">Record</div>
            <h1 className="page-title">New meeting</h1>
            <p className="page-description">Choose a template, start recording, and keep rough notes while Muesli captures audio.</p>
          </div>
        </div>

        <div className="stack">
          <ErrorBanner message={error} />
          <div className="panel stack">
            <div className="field">
              <label htmlFor="meeting-title">Title</label>
              <input id="meeting-title" className="input" placeholder="Untitled meeting" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="meeting-template">Template</label>
              <select id="meeting-template" className="select" value={templateId ?? ""} onChange={(e) => setTemplateId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Use default template</option>
                {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div>
              <button className="button-primary" onClick={start}>Start recording</button>
            </div>
          </div>
        </div>
      </section>
    );
  }

  const saveLabel = saveState === "saving" ? "Saving notes" : saveState === "saved" ? "Notes saved" : saveState === "error" ? "Save failed" : "Ready";

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Active meeting</div>
          <h1 className="page-title">{title || "Untitled meeting"}</h1>
          <p className="page-description">Keep rough notes here. Muesli records in the background.</p>
        </div>
        <div className="cluster">
          <StatusChip label="Recording" tone="recording" />
          <StatusChip label={saveLabel} tone={saveState === "error" ? "danger" : saveState === "saving" ? "busy" : "neutral"} />
        </div>
      </div>

      <div className="stack">
        <ErrorBanner message={error} />
        <textarea className="textarea" value={notes} onChange={(e) => onNotes(e.target.value)} placeholder="Jot rough notes..." />
        <div className="cluster">
          <button className="button-danger" onClick={stop}>Stop recording</button>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Build and commit**

Run:

```bash
cd ui
npm run build
```

Expected: build succeeds.

Commit:

```bash
git add ui/src/pages/ActiveMeeting.tsx
git commit -m "feat: improve recording workflow"
```

## Task 7: Upgrade Meeting Detail Workflow

**Files:**
- Modify: `ui/src/pages/MeetingDetail.tsx`

- [ ] **Step 1: Replace Meeting Detail**

Replace `ui/src/pages/MeetingDetail.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ErrorBanner from "../components/ErrorBanner";
import StatusChip from "../components/StatusChip";
import { api, Meeting } from "../api/client";
import { deriveMeetingState } from "../lib/meetingState";

type Tab = "enhanced" | "notes" | "transcript";

export default function MeetingDetail() {
  const { id } = useParams();
  const mid = Number(id);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [tab, setTab] = useState<Tab>("enhanced");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function reload() {
    setError("");
    try {
      setMeeting(await api.getMeeting(mid));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load meeting.");
    }
  }

  useEffect(() => { reload(); }, [mid]);

  async function runAction(label: string, action: () => Promise<Meeting>, nextTab?: Tab) {
    setBusy(label);
    setError("");
    try {
      const nextMeeting = await action();
      setMeeting(nextMeeting);
      if (nextTab) setTab(nextTab);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not ${label.toLowerCase()}.`);
    } finally {
      setBusy("");
    }
  }

  if (!meeting) {
    return (
      <section className="page">
        <ErrorBanner message={error} />
        {!error && <div className="panel muted">Loading meeting...</div>}
      </section>
    );
  }

  const state = deriveMeetingState(meeting);
  const body = tab === "enhanced" ? meeting.enhanced_notes : tab === "notes" ? meeting.rough_notes : meeting.transcript;

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Meeting detail</div>
          <h1 className="page-title">{meeting.title}</h1>
          <p className="page-description">{state.nextAction}</p>
        </div>
        <StatusChip label={busy || state.label} tone={busy ? "busy" : state.tone} />
      </div>

      <div className="stack">
        <ErrorBanner message={error} />

        <div className="panel cluster">
          <button disabled={Boolean(busy)} onClick={() => runAction("Transcribing", () => api.transcribe(mid), "transcript")}>
            Transcribe
          </button>
          <button className="button-primary" disabled={Boolean(busy)} onClick={() => runAction("Enhancing", () => api.enhance(mid, meeting.template_id ?? null), "enhanced")}>
            Enhance
          </button>
        </div>

        <div className="panel stack">
          <div className="tabs" role="tablist" aria-label="Meeting content">
            {(["enhanced", "notes", "transcript"] as Tab[]).map((t) => (
              <button key={t} className={`tab${tab === t ? " active" : ""}`} onClick={() => setTab(t)}>
                {t === "enhanced" ? "Enhanced" : t === "notes" ? "My notes" : "Transcript"}
              </button>
            ))}
          </div>
          <div className="pre">{body || "Nothing here yet."}</div>
        </div>

        <div className="panel">
          <div className="eyebrow">Future M3 space</div>
          <p className="muted">Live transcript, speaker labels, and calendar details will belong beside this post-meeting workflow when those features are built.</p>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Build and commit**

Run:

```bash
cd ui
npm run build
```

Expected: build succeeds.

Commit:

```bash
git add ui/src/pages/MeetingDetail.tsx
git commit -m "feat: improve meeting detail workflow"
```

## Task 8: Upgrade Templates Surface

**Files:**
- Modify: `ui/src/pages/Templates.tsx`

- [ ] **Step 1: Replace Templates page**

Replace `ui/src/pages/Templates.tsx` with:

```tsx
import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import { api, Template } from "../api/client";

export default function Templates() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listTemplates()
      .then(setTemplates)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load templates."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Templates</div>
          <h1 className="page-title">Note templates</h1>
          <p className="page-description">Templates shape how Muesli rewrites rough notes and transcripts.</p>
        </div>
      </div>

      <div className="stack">
        <ErrorBanner message={error} />
        {loading && <div className="panel muted">Loading templates...</div>}
        {!loading && templates.length === 0 && (
          <EmptyState title="No templates found" description="Default templates should appear here after the engine seeds them." />
        )}
        {!loading && templates.map((template) => (
          <article className="panel stack" key={template.id}>
            <div>
              <div className="eyebrow">Template</div>
              <h2>{template.name}</h2>
            </div>
            <div className="pre">{template.prompt}</div>
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Build and commit**

Run:

```bash
cd ui
npm run build
```

Expected: build succeeds.

Commit:

```bash
git add ui/src/pages/Templates.tsx
git commit -m "feat: improve templates view"
```

## Task 9: Verify Desktop UX And Finalize

**Files:**
- Modify only files needed to fix issues found during verification.

- [ ] **Step 1: Run automated verification**

Run:

```bash
cd ui
npm run test
npm run build
cd ../engine
.venv/Scripts/python -m pytest -q
```

Expected:

- Frontend tests pass.
- Frontend build succeeds.
- Existing engine tests pass if the local venv is available.

If the engine venv is unavailable, record the exact missing dependency or path error in the final handoff.

- [ ] **Step 2: Run the app for browser verification**

From the repository root:

```bash
PYTHONPATH=engine engine/.venv/Scripts/python run.py
```

If PowerShell rejects inline environment syntax, run:

```powershell
$env:PYTHONPATH="engine"
engine/.venv/Scripts/python run.py
```

Expected: pywebview opens the app and the engine serves the UI at `http://127.0.0.1:8731`.

- [ ] **Step 3: Verify the main desktop workflow**

Use the in-app browser or pywebview window to check:

- Library loads with a clear empty state or meeting rows.
- Search form does not shift layout.
- Record page shows title, template, and primary start action.
- Active meeting shows recording state, notes editor, save state, and stop action.
- Meeting Detail shows status, Transcribe, Enhance, tabs, and M3 future space.
- Templates page shows loading, error, empty, or template rows cleanly.
- At a narrow desktop-like viewport around 760px wide, navigation and text do not overlap.

- [ ] **Step 4: Fix verification issues with focused patches**

For each issue, change the smallest relevant file and rerun:

```bash
cd ui
npm run build
```

If a pure state-helper issue appears, also rerun:

```bash
cd ui
npm run test
```

- [ ] **Step 5: Commit final verification fixes**

If fixes were required:

```bash
git add ui
git commit -m "fix: polish ux foundation verification"
```

If no fixes were required, do not create an empty commit.

## Self-Review Notes

- Spec coverage: Tasks cover app shell, visual system, Library, New/Active Meeting, Meeting Detail, Templates, state model, errors, and verification.
- Non-goals honored: no live transcript, diarization, calendar integration, installer, or backend expansion is planned.
- Type consistency: `Meeting`, `Template`, `deriveMeetingState`, `StatusChip`, `EmptyState`, and `ErrorBanner` are defined before use in later tasks.
- Dependency risk: `vitest` requires `npm install`. If network access blocks install, implement Task 1 without the test script and rely on `npm run build` plus browser verification, then record that test harness installation was blocked.
