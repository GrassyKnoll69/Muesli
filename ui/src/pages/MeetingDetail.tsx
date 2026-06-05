import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { api, Meeting } from "../api/client";

type Tab = "enhanced" | "notes" | "transcript";

export default function MeetingDetail() {
  const { id } = useParams();
  const mid = Number(id);
  const [m, setM] = useState<Meeting | null>(null);
  const [tab, setTab] = useState<Tab>("enhanced");
  const [busy, setBusy] = useState("");

  async function reload() { setM(await api.getMeeting(mid)); }
  useEffect(() => { reload(); }, [mid]);

  async function doTranscribe() {
    setBusy("Transcribing…"); setM(await api.transcribe(mid)); setBusy("");
  }
  async function doEnhance() {
    setBusy("Enhancing…"); setM(await api.enhance(mid, m?.template_id ?? null));
    setBusy(""); setTab("enhanced");
  }
  if (!m) return <p>Loading…</p>;

  return (
    <div>
      <h1>{m.title}</h1>
      <div style={{ marginBottom: 8 }}>
        <button onClick={doTranscribe}>Transcribe</button>{" "}
        <button onClick={doEnhance}>Enhance</button>{" "}
        <a href={api.exportUrl(mid)} download
           style={{ marginLeft: 8 }}>Export .md</a>{" "}
        <span style={{ color: "#c60" }}>{busy}</span>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        {(["enhanced", "notes", "transcript"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
                  style={{ fontWeight: tab === t ? "bold" : "normal" }}>{t}</button>
        ))}
      </div>
      {tab === "enhanced" ? (
        <div style={{ marginTop: 12 }}>
          {m.enhanced_notes ? <ReactMarkdown>{m.enhanced_notes}</ReactMarkdown> : "(empty)"}
        </div>
      ) : (
        <pre style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>
          {(tab === "notes" ? m.rough_notes : m.transcript) || "(empty)"}
        </pre>
      )}
    </div>
  );
}
