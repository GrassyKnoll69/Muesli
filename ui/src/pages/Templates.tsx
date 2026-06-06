import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import { api, Template } from "../api/client";

export default function Templates() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Template | null>(null);
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [preview, setPreview] = useState("");

  async function load() {
    try {
      setTemplates(await api.listTemplates());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load templates.");
    } finally {
      setLoading(false);
    }
  }
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
    <section className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Templates</div>
          <h1 className="page-title">Note templates</h1>
          <p className="page-description">Templates shape how Muesli rewrites rough notes and transcripts.</p>
        </div>
        <button className="button-primary" onClick={startNew}>+ New template</button>
      </div>

      <div className="stack">
        <ErrorBanner message={error} />
        {loading && <div className="panel muted">Loading templates...</div>}
        {!loading && !error && templates.length === 0 && (
          <EmptyState title="No templates found" description="Default templates should appear here after the engine seeds them." />
        )}
        {!loading && templates.map((t) => (
          <article className="panel stack" key={t.id}>
            <div>
              <div className="eyebrow">Template</div>
              <h2>{t.name}</h2>
            </div>
            <div className="pre">{t.prompt}</div>
            <div className="cluster">
              <button onClick={() => startEdit(t)}>Edit</button>
              <button onClick={() => duplicate(t)}>Duplicate</button>
              <button onClick={() => remove(t)}>Delete</button>
            </div>
          </article>
        ))}

        {editing && (
          <div className="panel stack">
            <h3>{editing.id ? "Edit template" : "New template"}</h3>
            <input className="input" placeholder="Name" value={name}
                   onChange={(e) => setName(e.target.value)} />
            <textarea className="textarea" placeholder="Prompt / formatting instructions" value={prompt}
                      onChange={(e) => setPrompt(e.target.value)} rows={8} />
            <div className="cluster">
              <button className="button-primary" onClick={save} disabled={!name.trim()}>Save</button>
              <button onClick={cancel}>Cancel</button>
              <button onClick={doPreview} disabled={!prompt.trim()}>Preview prompt</button>
            </div>
            {preview && <div className="pre">{preview}</div>}
          </div>
        )}
      </div>
    </section>
  );
}
