import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Template } from "../api/client";

export default function ActiveMeeting() {
  const [meetingId, setMeetingId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const nav = useNavigate();
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => { api.listTemplates().then(setTemplates); }, []);

  async function start() {
    const m = await api.start(title || "Untitled meeting", templateId);
    setMeetingId(m.id);
  }
  function onNotes(v: string) {
    setNotes(v);
    if (meetingId) {
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => api.saveNotes(meetingId, v), 600);
    }
  }
  async function stop() {
    if (!meetingId) return;
    await api.saveNotes(meetingId, notes);
    await api.stop(meetingId);
    nav(`/meetings/${meetingId}`);
  }

  if (meetingId === null) {
    return (
      <div>
        <h1>New Meeting</h1>
        <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <select value={templateId ?? ""} onChange={(e) => setTemplateId(e.target.value ? Number(e.target.value) : null)}>
          <option value="">(template)</option>
          {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <button onClick={start}>● Start Recording</button>
      </div>
    );
  }
  return (
    <div>
      <h1>● Recording…</h1>
      <textarea value={notes} onChange={(e) => onNotes(e.target.value)}
                placeholder="Jot rough notes…" rows={18} style={{ width: "100%" }} />
      <button onClick={stop}>■ Stop</button>
    </div>
  );
}
