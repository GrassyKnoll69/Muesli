import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ErrorBanner from "../components/ErrorBanner";
import StatusChip from "../components/StatusChip";
import { api, Template } from "../api/client";

type SaveState = "idle" | "saving" | "saved" | "error";

export default function ActiveMeeting() {
  const [meetingId, setMeetingId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [error, setError] = useState("");
  const nav = useNavigate();
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    api
      .listTemplates()
      .then(setTemplates)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load templates.")
      );

    return () => window.clearTimeout(timer.current);
  }, []);

  async function start() {
    setError("");
    try {
      const meeting = await api.start(title || "Untitled meeting", templateId);
      setMeetingId(meeting.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start recording.");
    }
  }

  function saveNotes(meeting: number, nextNotes: string) {
    setSaveState("saving");
    api
      .saveNotes(meeting, nextNotes)
      .then(() => setSaveState("saved"))
      .catch((err) => {
        setSaveState("error");
        setError(err instanceof Error ? err.message : "Could not save notes.");
      });
  }

  function onNotes(v: string) {
    setNotes(v);
    if (meetingId) {
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => saveNotes(meetingId, v), 600);
    }
  }

  async function stop() {
    if (!meetingId) return;
    setError("");
    window.clearTimeout(timer.current);
    try {
      await api.saveNotes(meetingId, notes);
      await api.stop(meetingId);
      nav(`/meetings/${meetingId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not stop recording.");
    }
  }

  if (meetingId === null) {
    return (
      <section className="page">
        <div className="page-header">
          <div>
            <div className="eyebrow">Record</div>
            <h1 className="page-title">New meeting</h1>
            <p className="page-description">
              Choose a template, start recording, and keep rough notes while Muesli
              captures audio.
            </p>
          </div>
        </div>

        <div className="stack">
          <ErrorBanner message={error} />
          <div className="panel stack">
            <div className="field">
              <label htmlFor="meeting-title">Title</label>
              <input
                id="meeting-title"
                className="input"
                placeholder="Untitled meeting"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="meeting-template">Template</label>
              <select
                id="meeting-template"
                className="select"
                value={templateId ?? ""}
                onChange={(e) =>
                  setTemplateId(e.target.value ? Number(e.target.value) : null)
                }
              >
                <option value="">Use default template</option>
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <button className="button-primary" onClick={start}>
                Start recording
              </button>
            </div>
          </div>
        </div>
      </section>
    );
  }

  const saveLabel =
    saveState === "saving"
      ? "Saving notes"
      : saveState === "saved"
        ? "Notes saved"
        : saveState === "error"
          ? "Save failed"
          : "Ready";

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">Active meeting</div>
          <h1 className="page-title">{title || "Untitled meeting"}</h1>
          <p className="page-description">
            Keep rough notes here. Muesli records in the background.
          </p>
        </div>
        <div className="cluster">
          <StatusChip label="Recording" tone="recording" />
          <StatusChip
            label={saveLabel}
            tone={
              saveState === "error"
                ? "danger"
                : saveState === "saving"
                  ? "busy"
                  : "neutral"
            }
          />
        </div>
      </div>

      <div className="stack">
        <ErrorBanner message={error} />
        <textarea
          className="textarea"
          value={notes}
          onChange={(e) => onNotes(e.target.value)}
          placeholder="Jot rough notes..."
        />
        <div className="cluster">
          <button className="button-danger" onClick={stop}>
            Stop recording
          </button>
        </div>
      </div>
    </section>
  );
}
