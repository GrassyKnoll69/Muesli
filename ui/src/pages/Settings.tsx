import { useEffect, useState } from "react";
import { api, Settings as S } from "../api/client";

const WHISPER_MODELS = ["large-v3", "medium", "small", "base", "tiny"];
const DEVICES = ["auto", "cuda", "cpu"];
const CLOUD_MODELS: Record<string, string[]> = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
  anthropic: ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"],
};

export default function SettingsPage() {
  const [s, setS] = useState<S | null>(null);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [devices, setDevices] = useState<{ loopback: string[]; input: string[] }>({ loopback: [], input: [] });
  const [key, setKey] = useState("");
  const [test, setTest] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api.getSettings().then(setS);
    api.listOllamaModels().then(setOllamaModels).catch(() => setOllamaModels([]));
    api.listAudioDevices().then(setDevices).catch(() => setDevices({ loopback: [], input: [] }));
  }, []);
  if (!s) return <p>Loading…</p>;

  function set<K extends keyof S>(k: K, v: S[K]) { setS({ ...s!, [k]: v }); }

  async function save() {
    const payload: Partial<S> & { cloud_api_key?: string } = {
      whisper_model: s!.whisper_model,
      whisper_device: s!.whisper_device,
      ollama_model: s!.ollama_model,
      ollama_host: s!.ollama_host,
      enhancement_backend: s!.enhancement_backend,
      cloud_provider: s!.cloud_provider,
      cloud_model: s!.cloud_model,
      enable_diarization: s!.enable_diarization,
      diarization_threshold: s!.diarization_threshold,
      capture_device: s!.capture_device,
      mic_device: s!.mic_device,
    };
    if (key) payload.cloud_api_key = key;
    setS(await api.saveSettings(payload));
    setKey("");
    setSaved("Saved ✓");
    setTimeout(() => setSaved(""), 2000);
  }

  async function runTest() {
    setTest("Testing…");
    const provider = s!.cloud_provider || "openai";
    const res = await api.testCloud(provider, s!.cloud_model || "", key || undefined);
    setTest((res.ok ? "✓ " : "✗ ") + res.message);
  }

  const provider = s.cloud_provider || "openai";
  const models = CLOUD_MODELS[provider] || [];
  const keyPlaceholder = s.cloud_key_present[provider as "openai" | "anthropic"]
    ? "•••• (stored — type to replace)" : "not set";

  return (
    <div>
      <h1>Settings</h1>

      <h3>Transcription</h3>
      <label>Whisper model{" "}
        <select value={s.whisper_model} onChange={(e) => set("whisper_model", e.target.value)}>
          {WHISPER_MODELS.map((m) => <option key={m}>{m}</option>)}
        </select>
      </label>{"   "}
      <label>Device{" "}
        <select value={s.whisper_device} onChange={(e) => set("whisper_device", e.target.value)}>
          {DEVICES.map((d) => <option key={d}>{d}</option>)}
        </select>
      </label>

      <h3>Enhancement</h3>
      <label>Backend{" "}
        <select value={s.enhancement_backend} onChange={(e) => set("enhancement_backend", e.target.value)}>
          <option value="ollama">Ollama (local)</option>
          <option value="cloud">Cloud</option>
        </select>
      </label>

      <h4>Ollama</h4>
      <label>Model{" "}
        <input list="ollama-models" value={s.ollama_model}
               onChange={(e) => set("ollama_model", e.target.value)} />
        <datalist id="ollama-models">
          {ollamaModels.map((m) => <option key={m} value={m} />)}
        </datalist>
      </label>{"   "}
      <label>Host{" "}
        <input value={s.ollama_host} onChange={(e) => set("ollama_host", e.target.value)} style={{ width: 220 }} />
      </label>

      <h4>Cloud</h4>
      <label>Provider{" "}
        <select value={provider} onChange={(e) => set("cloud_provider", e.target.value)}>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
        </select>
      </label>{"   "}
      <label>Model{" "}
        <input list="cloud-models" value={s.cloud_model ?? ""}
               onChange={(e) => set("cloud_model", e.target.value)} />
        <datalist id="cloud-models">
          {models.map((m) => <option key={m} value={m} />)}
        </datalist>
      </label>
      <div style={{ marginTop: 8 }}>
        <label>API key{" "}
          <input type="password" value={key} placeholder={keyPlaceholder}
                 onChange={(e) => setKey(e.target.value)} style={{ width: 300 }} />
        </label>{" "}
        <button onClick={runTest}>Test connection</button>{" "}
        <span>{test}</span>
      </div>

      <h3>Transcription &amp; speakers</h3>
      <div>
        <label>
          <input
            type="checkbox"
            checked={s.enable_diarization}
            onChange={(e) => set("enable_diarization", e.target.checked)}
          />{" "}
          Split speakers (diarization)
        </label>
      </div>
      <div style={{ marginTop: 8 }}>
        <label>
          Clustering sensitivity{" "}
          <input
            type="range"
            min={0.1}
            max={1.0}
            step={0.05}
            value={s.diarization_threshold}
            onChange={(e) => set("diarization_threshold", parseFloat(e.target.value))}
            style={{ verticalAlign: "middle" }}
          />{" "}
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{s.diarization_threshold.toFixed(2)}</span>
        </label>
        <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 2 }}>
          Lower values split speakers more readily; higher values merge more into one speaker.
        </div>
      </div>
      <div style={{ marginTop: 8 }}>
        <label>
          Capture device (system audio){" "}
          <input
            list="capture-devices"
            value={s.capture_device ?? ""}
            placeholder="blank = default output"
            onChange={(e) => set("capture_device", e.target.value || null)}
            style={{ width: 260 }}
          />
          <datalist id="capture-devices">
            {devices.loopback.map((d) => <option key={d} value={d} />)}
          </datalist>
        </label>
      </div>
      <div style={{ marginTop: 8 }}>
        <label>
          Mic device{" "}
          <input
            list="mic-devices"
            value={s.mic_device ?? ""}
            placeholder="blank = default input"
            onChange={(e) => set("mic_device", e.target.value || null)}
            style={{ width: 260 }}
          />
          <datalist id="mic-devices">
            {devices.input.map((d) => <option key={d} value={d} />)}
          </datalist>
        </label>
      </div>

      <div style={{ marginTop: 16 }}>
        <button onClick={save}>Save</button>{" "}
        <span style={{ color: "#2a2" }}>{saved}</span>
      </div>
    </div>
  );
}
