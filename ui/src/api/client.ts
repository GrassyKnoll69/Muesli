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

export interface Settings {
  whisper_model: string;
  whisper_device: string;
  whisper_compute_type: string;
  ollama_model: string;
  ollama_host: string;
  enhancement_backend: string;
  cloud_provider: string | null;
  cloud_model: string | null;
  cloud_key_present: { openai: boolean; anthropic: boolean };
}

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
  getSettings: () => fetch("/settings").then(j<Settings>),
  saveSettings: (s: Partial<Settings> & { cloud_api_key?: string }) =>
    fetch("/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(s),
    }).then(j<Settings>),
  testCloud: (provider: string, model: string, key?: string) =>
    fetch("/settings/test-cloud", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, model, key }),
    }).then(j<{ ok: boolean; message: string }>),
  listOllamaModels: () => fetch("/ollama/models").then(j<string[]>),
  previewTemplate: (prompt: string, rough_notes?: string, transcript?: string) =>
    fetch("/templates/preview", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, rough_notes, transcript }),
    }).then(j<{ prompt: string }>),
  createTemplate: (t: { name: string; prompt: string }) =>
    fetch("/templates", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(t),
    }).then(j<Template>),
  updateTemplate: (id: number, t: { name: string; prompt: string }) =>
    fetch(`/templates/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(t),
    }).then(j<Template>),
  deleteTemplate: (id: number) =>
    fetch(`/templates/${id}`, { method: "DELETE" }).then(j<{ ok: boolean }>),
  exportUrl: (id: number) => `/meetings/${id}/export`,
};
