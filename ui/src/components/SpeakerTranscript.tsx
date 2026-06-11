import { useRef, useState } from "react";
import { api, Segment } from "../api/client";

interface Props {
  meetingId: number;
  segments: Segment[];
  onRenamed: () => void;
}

interface Turn {
  speaker_key: string;
  display_name: string;
  text: string;
}

function hashSpeakerKey(key: string): number {
  let h = 0;
  for (let i = 0; i < key.length; i++) {
    h = (Math.imul(31, h) + key.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function speakerColor(speaker_key: string): string {
  const hue = hashSpeakerKey(speaker_key) % 360;
  return `hsl(${hue}, 65%, 45%)`;
}

function groupIntoTurns(segments: Segment[]): Turn[] {
  const turns: Turn[] = [];
  for (const seg of segments) {
    const last = turns[turns.length - 1];
    if (last && last.speaker_key === seg.speaker_key) {
      last.text = last.text + " " + seg.text;
    } else {
      turns.push({
        speaker_key: seg.speaker_key,
        display_name: seg.display_name,
        text: seg.text,
      });
    }
  }
  return turns;
}

interface ChipProps {
  meetingId: number;
  speaker_key: string;
  display_name: string;
  color: string;
  onRenamed: () => void;
}

function SpeakerChip({ meetingId, speaker_key, display_name, color, onRenamed }: ChipProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(display_name);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function startEdit() {
    setDraft(display_name);
    setEditing(true);
    // focus after render
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function cancelEdit() {
    setEditing(false);
    setDraft(display_name);
  }

  async function commitEdit() {
    const trimmed = draft.trim();
    if (!trimmed || trimmed === display_name) {
      cancelEdit();
      return;
    }
    setSaving(true);
    try {
      await api.renameSpeaker(meetingId, speaker_key, trimmed);
      setEditing(false);
      onRenamed();
    } catch {
      // revert on error
      setDraft(display_name);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        className="speaker-chip-input"
        value={draft}
        disabled={saving}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); void commitEdit(); }
          if (e.key === "Escape") { e.preventDefault(); cancelEdit(); }
        }}
        onBlur={() => { void commitEdit(); }}
        aria-label="Speaker name"
        style={{ borderColor: color }}
      />
    );
  }

  return (
    <button
      className="speaker-chip"
      style={{ backgroundColor: color }}
      onClick={startEdit}
      title="Click to rename speaker"
      type="button"
    >
      {display_name}
    </button>
  );
}

export default function SpeakerTranscript({ meetingId, segments, onRenamed }: Props) {
  if (segments.length === 0) {
    return <div className="pre">Nothing here yet.</div>;
  }

  const turns = groupIntoTurns(segments);

  return (
    <div className="speaker-transcript">
      {turns.map((turn, i) => {
        const color = speakerColor(turn.speaker_key);
        return (
          <div key={i} className="speaker-turn">
            <SpeakerChip
              meetingId={meetingId}
              speaker_key={turn.speaker_key}
              display_name={turn.display_name}
              color={color}
              onRenamed={onRenamed}
            />
            <span className="speaker-turn-text">{turn.text}</span>
          </div>
        );
      })}
    </div>
  );
}
