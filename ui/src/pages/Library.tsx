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
