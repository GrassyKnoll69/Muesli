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
              <button
                key={t}
                className={`tab${tab === t ? " active" : ""}`}
                role="tab"
                aria-selected={tab === t}
                type="button"
                onClick={() => setTab(t)}
              >
                {t === "enhanced" ? "Enhanced" : t === "notes" ? "My notes" : "Transcript"}
              </button>
            ))}
          </div>
          <div className="pre" role="tabpanel">{body || "Nothing here yet."}</div>
        </div>

        <div className="panel">
          <div className="eyebrow">Future M3 space</div>
          <p className="muted">Live transcript, speaker labels, and calendar details will belong beside this post-meeting workflow when those features are built.</p>
        </div>
      </div>
    </section>
  );
}
