export interface Meeting {
  id: number;
  title: string;
  created_at: string;
  rough_notes: string;
  transcript: string;
  enhanced_notes: string;
  template_id: number | null;
  audio_path: string | null;
  loopback_path: string | null;
  mic_path: string | null;
  diarized: boolean;
  status: string;
}

export interface Segment {
  start: number;
  end: number;
  speaker_key: string;
  display_name: string;
  source: "mic" | "loopback";
  text: string;
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
    const parsed: unknown = JSON.parse(text);
    return errorMessage(parsed, text);
  } catch {
    return text;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringifyOrText(value: unknown, text: string): string {
  try {
    return JSON.stringify(value) ?? text;
  } catch {
    return text;
  }
}

function arrayMessages(value: unknown[]): string | null {
  const messages = value.flatMap((item) => {
    if (typeof item === "string" && item.trim()) return [item];
    if (isRecord(item) && typeof item.msg === "string" && item.msg.trim()) {
      return [item.msg];
    }
    return [];
  });
  return messages.length > 0 ? messages.join("; ") : null;
}

function errorMessage(value: unknown, text: string): string {
  if (isRecord(value)) {
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
    if (Array.isArray(value.detail)) {
      return arrayMessages(value.detail) ?? stringifyOrText(value.detail, text);
    }
    return stringifyOrText(value, text);
  }

  if (Array.isArray(value)) return stringifyOrText(value, text);
  if (typeof value === "string") return value;
  return text;
}

export interface Health {
  ollama: boolean;
  webview2: boolean | null;
  diarization_models: boolean;
  whisper_model: boolean;
  gpu_present: boolean;
  cuda_libraries: boolean;
}

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
  enable_diarization: boolean;
  diarization_threshold: number;
  capture_device: string | null;
  mic_device: string | null;
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
  deleteMeeting: (id: number) =>
    fetch(`/meetings/${id}`, { method: "DELETE" }).then(j<{ ok: boolean }>),
  openMeetingLocation: (id: number) =>
    fetch(`/meetings/${id}/open-location`, { method: "POST" }).then(j<{ ok: boolean; path: string }>),
  transcribe: (id: number) =>
    fetch(`/meetings/${id}/transcribe`, { method: "POST" }).then(j<Meeting>),
  enhance: (id: number, template_id: number | null) =>
    fetch(`/meetings/${id}/enhance`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_id }),
    }).then(j<Meeting>),
  getSegments: (id: number) => fetch(`/meetings/${id}/segments`).then(j<Segment[]>),
  renameSpeaker: (id: number, speaker_key: string, display_name: string) =>
    fetch(`/meetings/${id}/speakers`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ speaker_key, display_name }),
    }).then(j<Segment[]>),
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
  listAudioDevices: () => fetch("/audio/devices").then(j<{ loopback: string[]; input: string[] }>),
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
  getHealth: () => fetch("/health").then(j<Health>),
  downloadDiarizationModels: () =>
    fetch("/models/diarization/download", { method: "POST" }).then(j<{ ok: boolean }>),
  downloadCudaLibraries: () =>
    fetch("/cuda/download", { method: "POST" }).then(j<{ ok: boolean }>),
};
