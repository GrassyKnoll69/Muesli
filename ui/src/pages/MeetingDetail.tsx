import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import ErrorBanner from "../components/ErrorBanner";
import StatusChip from "../components/StatusChip";
import { api, Meeting } from "../api/client";
import { deriveMeetingState } from "../lib/meetingState";

type Tab = "enhanced" | "notes" | "transcript";

function parseMeetingId(value: string | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

export default function MeetingDetail() {
  const { id } = useParams();
  const mid = parseMeetingId(id);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [tab, setTab] = useState<Tab>("enhanced");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
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
  const body = tab === "enhanced" ? activeMeeting.enhanced_notes : tab === "notes" ? activeMeeting.rough_notes : activeMeeting.transcript;

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
          <button disabled={Boolean(busy)} onClick={() => runAction("Transcribing", activeMeeting.id, () => api.transcribe(activeMeeting.id), "transcript")}>
            Transcribe
          </button>
          <button className="button-primary" disabled={Boolean(busy)} onClick={() => runAction("Enhancing", activeMeeting.id, () => api.enhance(activeMeeting.id, activeMeeting.template_id ?? null), "enhanced")}>
            Enhance
          </button>
        </div>

        <div className="panel stack">
          <div className="tabs" aria-label="Meeting content">
            {(["enhanced", "notes", "transcript"] as Tab[]).map((t) => (
              <button
                key={t}
                className={`tab${tab === t ? " active" : ""}`}
                aria-pressed={tab === t}
                type="button"
                onClick={() => setTab(t)}
              >
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
