import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Meeting } from "../api/client";

export default function Library() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [q, setQ] = useState("");

  async function load() {
    setMeetings(q.trim() ? await api.searchMeetings(q.trim()) : await api.listMeetings());
  }
  useEffect(() => { load(); }, []);

  return (
    <div>
      <h1>Meetings</h1>
      <form onSubmit={(e) => { e.preventDefault(); load(); }}>
        <input placeholder="Search notes & transcripts" value={q}
               onChange={(e) => setQ(e.target.value)} style={{ width: "70%" }} />
        <button>Search</button>
      </form>
      <ul>
        {meetings.map((m) => (
          <li key={m.id}>
            <Link to={`/meetings/${m.id}`}>{m.title}</Link>
            <span style={{ color: "#888" }}> — {m.status}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
