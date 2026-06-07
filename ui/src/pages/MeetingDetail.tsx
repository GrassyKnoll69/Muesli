import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ErrorBanner from "../components/ErrorBanner";
import MarkdownContent from "../components/MarkdownContent";
import StatusChip from "../components/StatusChip";
import { api, Meeting } from "../api/client";
import { canEnhanceMeeting, canTranscribeMeeting, deriveMeetingState } from "../lib/meetingState";

type Tab = "enhanced" | "notes" | "transcript";

const TABS: Tab[] = ["enhanced", "notes", "transcript"];

function parseMeetingId(value: string | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

export default function MeetingDetail() {
  const { id } = useParams();
  const mid = parseMeetingId(id);
  const nav = useNavigate();
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [tab, setTab] = useState<Tab>("enhanced");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesSaving, setNotesSaving] = useState(false);
  const loadRequest = useRef(0);
  const currentMeetingId = useRef<number | null>(mid);
  const activeAction = useRef<{ request: number; meetingId: number } | null>(null);
  const actionRequest = useRef(0);
  currentMeetingId.current = mid;

  async function reload() {
    const request = ++loadRequest.current;
    activeAction.current = null;
    setMeeting(null);
    setBusy("");
    setError("");

    if (mid === null) {
      setError("Invalid meeting id.");
      return;
    }

    try {
      const nextMeeting = await api.getMeeting(mid);
      if (loadRequest.current === request) {
        setMeeting(nextMeeting);
        setNotesDraft(nextMeeting.rough_notes);
      }
    } catch (err) {
      if (loadRequest.current === request) {
        setError(err instanceof Error ? err.message : "Could not load meeting.");
      }
    }
  }

  useEffect(() => { reload(); }, [mid]);

  async function runAction(label: string, meetingId: number, action: () => Promise<Meeting>, nextTab?: Tab) {
    if (currentMeetingId.current !== meetingId || activeAction.current) return;
    const request = ++actionRequest.current;
    activeAction.current = { request, meetingId };
    setBusy(label);
    setError("");
    try {
      const nextMeeting = await action();
      if (activeAction.current?.request === request && activeAction.current.meetingId === meetingId && currentMeetingId.current === meetingId) {
        setMeeting(nextMeeting);
        setNotesDraft(nextMeeting.rough_notes);
        if (nextTab) setTab(nextTab);
      }
    } catch (err) {
      if (activeAction.current?.request === request && activeAction.current.meetingId === meetingId && currentMeetingId.current === meetingId) {
        setError(err instanceof Error ? err.message : `Could not ${label.toLowerCase()}.`);
      }
    } finally {
      if (activeAction.current?.request === request && activeAction.current.meetingId === meetingId && currentMeetingId.current === meetingId) {
        activeAction.current = null;
        setBusy("");
      }
    }
  }

  async function saveNotes(nextNotes = notesDraft) {
    const current = mid !== null && meeting?.id === mid ? meeting : null;
    if (!current || notesSaving) return;
    setNotesSaving(true);
    setError("");
    try {
      await api.saveNotes(current.id, nextNotes);
      setMeeting({ ...current, rough_notes: nextNotes });
      setNotesDraft(nextNotes);
      setEditingNotes(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save notes.");
    } finally {
      setNotesSaving(false);
    }
  }

  async function deleteMeeting() {
    const current = mid !== null && meeting?.id === mid ? meeting : null;
    if (!current || !window.confirm(`Delete "${current.title}"?`)) return;
    setBusy("Deleting");
    setError("");
    try {
      await api.deleteMeeting(current.id);
      nav("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete meeting.");
      setBusy("");
    }
  }

  const activeMeeting = mid !== null && meeting?.id === mid ? meeting : null;

  if (!activeMeeting) {
    const displayError = mid === null ? "Invalid meeting id." : error;
    return (
      <section className="page">
        <ErrorBanner message={displayError} />
        {!displayError && <div className="panel muted">Loading meeting...</div>}
      </section>
    );
  }

  const state = deriveMeetingState(activeMeeting);
  const body = tab === "notes" ? activeMeeting.rough_notes : activeMeeting.transcript;
  const canTranscribe = canTranscribeMeeting(activeMeeting);
  const canEnhance = canEnhanceMeeting(activeMeeting);
  const notesDirty = notesDraft !== activeMeeting.rough_notes;
  const selectedTabId = `meeting-tab-${tab}`;
  const selectedPanelId = `meeting-panel-${tab}`;

  function tabLabel(value: Tab): string {
    return value === "enhanced" ? "Enhanced" : value === "notes" ? "My notes" : "Transcript";
  }

  function selectTab(value: Tab) {
    if (value !== "notes") {
      setEditingNotes(false);
      setNotesDraft(meeting?.rough_notes ?? "");
    }
    setTab(value);
  }

  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, value: Tab) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const currentIndex = TABS.indexOf(value);
    const nextIndex = event.key === "ArrowLeft"
      ? (currentIndex + TABS.length - 1) % TABS.length
      : (currentIndex + 1) % TABS.length;
    selectTab(TABS[nextIndex]);
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Meeting detail</div>
          <h1 className="page-title">{activeMeeting.title}</h1>
          <p className="page-description">{state.nextAction}</p>
        </div>
        <span role="status" aria-live="polite">
          <StatusChip label={busy || state.label} tone={busy ? "busy" : state.tone} />
        </span>
      </div>

      <div className="stack">
        <ErrorBanner message={error} />

        <div className="panel cluster">
          <button
            disabled={Boolean(busy) || !canTranscribe}
            onClick={() => runAction("Transcribing", activeMeeting.id, () => api.transcribe(activeMeeting.id), "transcript")}
          >
            Transcribe
          </button>
          <button
            className="button-primary"
            disabled={Boolean(busy) || !canEnhance}
            onClick={() => runAction("Enhancing", activeMeeting.id, () => api.enhance(activeMeeting.id, activeMeeting.template_id ?? null), "enhanced")}
          >
            Enhance
          </button>
          <button className="button-danger" disabled={Boolean(busy)} onClick={deleteMeeting} type="button">
            Delete meeting
          </button>
        </div>

        <div className="panel stack">
          <div className="tabs" role="tablist" aria-label="Meeting content">
            {TABS.map((t) => (
              <button
                key={t}
                id={`meeting-tab-${t}`}
                className={`tab${tab === t ? " active" : ""}`}
                aria-controls={`meeting-panel-${t}`}
                aria-selected={tab === t}
                role="tab"
                tabIndex={tab === t ? 0 : -1}
                type="button"
                onClick={() => selectTab(t)}
                onKeyDown={(event) => onTabKeyDown(event, t)}
              >
                {tabLabel(t)}
              </button>
            ))}
          </div>
          {tab === "notes" && (
            <div className="cluster">
              {!editingNotes && <button onClick={() => setEditingNotes(true)} type="button">Edit notes</button>}
              {editingNotes && (
                <>
                  <button className="button-primary" disabled={notesSaving} onClick={() => saveNotes()} type="button">
                    {notesSaving ? "Saving..." : "Save notes"}
                  </button>
                  <button
                    disabled={notesSaving}
                    onClick={() => { setEditingNotes(false); setNotesDraft(activeMeeting.rough_notes); }}
                    type="button"
                  >
                    Cancel
                  </button>
                </>
              )}
              <button
                className="button-danger"
                disabled={notesSaving || (!activeMeeting.rough_notes && !notesDraft)}
                onClick={() => saveNotes("")}
                type="button"
              >
                Clear notes
              </button>
              {notesDirty && <span className="muted">Unsaved changes</span>}
            </div>
          )}
          <div aria-labelledby={selectedTabId} id={selectedPanelId} role="tabpanel">
            {tab === "enhanced" && (
              <div className="markdown-panel">
                <MarkdownContent markdown={activeMeeting.enhanced_notes} />
              </div>
            )}
            {tab === "notes" && editingNotes && (
              <textarea
                aria-label="Edit rough meeting notes"
                className="textarea"
                value={notesDraft}
                onChange={(event) => setNotesDraft(event.target.value)}
              />
            )}
            {tab !== "enhanced" && !editingNotes && (
              <div className="pre">{body || "Nothing here yet."}</div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="eyebrow">Future M3 space</div>
          <p className="muted">Live transcript, speaker labels, and calendar details will belong beside this post-meeting workflow when those features are built.</p>
        </div>
      </div>
    </section>
  );
}
