import { useEffect, useState } from "react";
import { api, Template } from "../api/client";

export default function Templates() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [editing, setEditing] = useState<Template | null>(null);
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [preview, setPreview] = useState("");

  async function load() { setTemplates(await api.listTemplates()); }
  useEffect(() => { load(); }, []);

  function startNew() {
    setEditing({ id: 0, name: "", prompt: "" });
    setName(""); setPrompt(""); setPreview("");
  }
  function startEdit(t: Template) {
    setEditing(t); setName(t.name); setPrompt(t.prompt); setPreview("");
  }
  function cancel() { setEditing(null); setPreview(""); }

  async function save() {
    if (editing && editing.id) await api.updateTemplate(editing.id, { name, prompt });
    else await api.createTemplate({ name, prompt });
    setEditing(null); setPreview(""); await load();
  }
  async function duplicate(t: Template) {
    await api.createTemplate({ name: `${t.name} (copy)`, prompt: t.prompt });
    await load();
  }
  async function remove(t: Template) {
    if (!confirm(`Delete template "${t.name}"?`)) return;
    await api.deleteTemplate(t.id); await load();
  }
  async function doPreview() {
    setPreview((await api.previewTemplate(prompt)).prompt);
  }

  return (
    <div>
      <h1>Templates</h1>
      <button onClick={startNew}>+ New template</button>
      <ul>
        {templates.map((t) => (
          <li key={t.id} style={{ marginBottom: 6 }}>
            <strong>{t.name}</strong>{"  "}
            <button onClick={() => startEdit(t)}>Edit</button>{" "}
            <button onClick={() => duplicate(t)}>Duplicate</button>{" "}
            <button onClick={() => remove(t)}>Delete</button>
          </li>
        ))}
      </ul>

      {editing && (
        <div style={{ borderTop: "1px solid #ddd", marginTop: 12, paddingTop: 12 }}>
          <h3>{editing.id ? "Edit template" : "New template"}</h3>
          <div>
            <input placeholder="Name" value={name}
                   onChange={(e) => setName(e.target.value)} style={{ width: "60%" }} />
          </div>
          <textarea placeholder="Prompt / formatting instructions" value={prompt}
                    onChange={(e) => setPrompt(e.target.value)} rows={8}
                    style={{ width: "100%", marginTop: 8 }} />
          <div style={{ marginTop: 8 }}>
            <button onClick={save} disabled={!name.trim()}>Save</button>{" "}
            <button onClick={cancel}>Cancel</button>{" "}
            <button onClick={doPreview} disabled={!prompt.trim()}>Preview prompt</button>
          </div>
          {preview && (
            <pre style={{ whiteSpace: "pre-wrap", background: "#f6f6f6", padding: 8, marginTop: 8 }}>
              {preview}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
