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
export interface Template { id: number; name: string; prompt: string; }

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export const api = {
  listMeetings: () => fetch("/meetings").then(j<Meeting[]>),
  searchMeetings: (q: string) =>
    fetch(`/meetings/search?q=${encodeURIComponent(q)}`).then(j<Meeting[]>),
  getMeeting: (id: number) => fetch(`/meetings/${id}`).then(j<Meeting>),
  start: (title: string, template_id: number | null) =>
    fetch("/recordings/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, template_id }),
    }).then(j<Meeting>),
  stop: (id: number) =>
    fetch(`/recordings/${id}/stop`, { method: "POST" }).then(j<Meeting>),
  saveNotes: (id: number, rough_notes: string) =>
    fetch(`/meetings/${id}/notes`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rough_notes }),
    }).then(j<{ ok: boolean }>),
  transcribe: (id: number) =>
    fetch(`/meetings/${id}/transcribe`, { method: "POST" }).then(j<Meeting>),
  enhance: (id: number, template_id: number | null) =>
    fetch(`/meetings/${id}/enhance`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_id }),
    }).then(j<Meeting>),
  listTemplates: () => fetch("/templates").then(j<Template[]>),
};
