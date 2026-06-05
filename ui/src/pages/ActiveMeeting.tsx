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
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const nav = useNavigate();
  const timer = useRef<number | undefined>(undefined);
  const saveQueue = useRef<Promise<void>>(Promise.resolve());
  const saveRequest = useRef(0);
  const startingRef = useRef(false);
  const stoppingRef = useRef(false);

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
    if (startingRef.current) return;
    startingRef.current = true;
    setStarting(true);
    setError("");
    try {
      const meeting = await api.start(title || "Untitled meeting", templateId);
      setMeetingId(meeting.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start recording.");
    } finally {
      startingRef.current = false;
      setStarting(false);
    }
  }

  function saveNotes(meeting: number, nextNotes: string): Promise<void> {
    const requestId = ++saveRequest.current;
    setSaveState("saving");
    const run = async () => {
      try {
        await api.saveNotes(meeting, nextNotes);
        if (saveRequest.current === requestId) {
          setSaveState("saved");
        }
      } catch (err) {
        if (saveRequest.current === requestId) {
          setSaveState("error");
          setError(err instanceof Error ? err.message : "Could not save notes.");
        }
      }
    };
    const queuedSave = saveQueue.current.then(run, run);
    saveQueue.current = queuedSave.catch(() => undefined);
    return queuedSave;
  }

  function onNotes(v: string) {
    setNotes(v);
    if (meetingId) {
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => saveNotes(meetingId, v), 600);
    }
  }

  async function stop() {
    if (!meetingId || stoppingRef.current) return;
    stoppingRef.current = true;
    setStopping(true);
    setError("");
    window.clearTimeout(timer.current);
    try {
      await saveQueue.current;
      const requestId = ++saveRequest.current;
      setSaveState("saving");
      await api.saveNotes(meetingId, notes);
      if (saveRequest.current === requestId) {
        setSaveState("saved");
      }
    } catch (err) {
      setSaveState("error");
      setError(err instanceof Error ? err.message : "Could not save notes.");
      stoppingRef.current = false;
      setStopping(false);
      return;
    }

    try {
      await api.stop(meetingId);
      nav(`/meetings/${meetingId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not stop recording.");
      stoppingRef.current = false;
      setStopping(false);
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
                disabled={starting}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="meeting-template">Template</label>
              <select
                id="meeting-template"
                className="select"
                value={templateId ?? ""}
                disabled={starting}
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
              <button className="button-primary" onClick={start} disabled={starting}>
                {starting ? "Starting..." : "Start recording"}
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
        <div className="cluster" role="status" aria-live="polite">
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
          aria-label="Rough meeting notes"
          value={notes}
          disabled={stopping}
          onChange={(e) => onNotes(e.target.value)}
          placeholder="Jot rough notes..."
        />
        <div className="cluster">
          <button className="button-danger" onClick={stop} disabled={stopping}>
            {stopping ? "Stopping..." : "Stop recording"}
          </button>
        </div>
      </div>
    </section>
  );
}
