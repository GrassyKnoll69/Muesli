import { type FormEvent, useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import { api, Template } from "../api/client";

interface TemplateForm {
  id: number | null;
  name: string;
  prompt: string;
}

const EMPTY_FORM: TemplateForm = { id: null, name: "", prompt: "" };

export default function Templates() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<TemplateForm>(EMPTY_FORM);
  const [editing, setEditing] = useState(false);

  async function loadTemplates() {
    setLoading(true);
    setError("");
    try {
      setTemplates(await api.listTemplates());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load templates.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { loadTemplates(); }, []);

  function startNewTemplate() {
    setForm(EMPTY_FORM);
    setEditing(true);
    setError("");
  }

  function startEditTemplate(template: Template) {
    setForm({ id: template.id, name: template.name, prompt: template.prompt });
    setEditing(true);
    setError("");
  }

  async function saveTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = form.name.trim();
    const prompt = form.prompt.trim();
    if (!name || !prompt) {
      setError("Template name and prompt are required.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      if (form.id === null) {
        await api.createTemplate({ name, prompt });
      } else {
        await api.updateTemplate(form.id, { name, prompt });
      }
      setForm(EMPTY_FORM);
      setEditing(false);
      await loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save template.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteTemplate(template: Template) {
    if (!window.confirm(`Delete the "${template.name}" template?`)) return;
    setError("");
    try {
      await api.deleteTemplate(template.id);
      if (form.id === template.id) {
        setForm(EMPTY_FORM);
        setEditing(false);
      }
      await loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete template.");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Templates</div>
          <h1 className="page-title">Note templates</h1>
          <p className="page-description">Create and tune the prompts Muesli uses to shape enhanced notes.</p>
        </div>
        <button className="button-primary" onClick={startNewTemplate} type="button">
          New template
        </button>
      </div>

      <div className="stack">
        <ErrorBanner message={error} />

        {editing && (
          <form className="panel stack" onSubmit={saveTemplate}>
            <div>
              <div className="eyebrow">{form.id === null ? "Create" : "Edit"} template</div>
              <h2>{form.id === null ? "New template" : form.name || "Template"}</h2>
            </div>
            <div className="field">
              <label htmlFor="template-name">Name</label>
              <input
                className="input"
                id="template-name"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </div>
            <div className="field">
              <label htmlFor="template-prompt">Prompt</label>
              <textarea
                className="textarea textarea-compact"
                id="template-prompt"
                value={form.prompt}
                onChange={(event) => setForm((current) => ({ ...current, prompt: event.target.value }))}
              />
            </div>
            <div className="cluster">
              <button className="button-primary" disabled={saving} type="submit">
                {saving ? "Saving..." : "Save template"}
              </button>
              <button disabled={saving} onClick={() => { setEditing(false); setForm(EMPTY_FORM); }} type="button">
                Cancel
              </button>
            </div>
          </form>
        )}

        {loading && <div className="panel muted">Loading templates...</div>}

        {!loading && !error && templates.length === 0 && !editing && (
          <EmptyState
            title="No templates found"
            description="Create a template to guide how Muesli rewrites meeting notes."
            action={<button className="button-primary" onClick={startNewTemplate} type="button">New template</button>}
          />
        )}

        {!loading && templates.map((template) => (
          <article className="panel stack" key={template.id}>
            <div className="split-row">
              <div>
                <div className="eyebrow">Template</div>
                <h2>{template.name}</h2>
              </div>
              <div className="cluster">
                <button onClick={() => startEditTemplate(template)} type="button">Edit</button>
                <button className="button-danger" onClick={() => deleteTemplate(template)} type="button">Delete</button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
