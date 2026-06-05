import { Meeting } from "../api/client";

export type MeetingStateTone = "neutral" | "recording" | "warning" | "success" | "danger" | "busy";

export interface MeetingDisplayState {
  key:
    | "recording"
    | "stopped"
    | "needs-transcription"
    | "transcribing"
    | "needs-enhancement"
    | "enhancing"
    | "complete"
    | "blocked";
  label: string;
  tone: MeetingStateTone;
  nextAction: string;
}

function hasText(value: string | null | undefined): boolean {
  return Boolean(value && value.trim().length > 0);
}

export function deriveMeetingState(meeting: Meeting): MeetingDisplayState {
  const status = meeting.status.toLowerCase();

  if (status.includes("record")) {
    return { key: "recording", label: "Recording", tone: "recording", nextAction: "Keep taking notes or stop recording." };
  }

  if (status.includes("transcrib")) {
    return { key: "transcribing", label: "Transcribing", tone: "busy", nextAction: "Wait for transcription to finish." };
  }

  if (status.includes("enhanc")) {
    return { key: "enhancing", label: "Enhancing", tone: "busy", nextAction: "Wait for note enhancement to finish." };
  }

  if (status.includes("fail") || status.includes("error")) {
    return { key: "blocked", label: "Failed", tone: "danger", nextAction: "Review the error and retry the last action." };
  }

  if (hasText(meeting.enhanced_notes)) {
    return { key: "complete", label: "Complete", tone: "success", nextAction: "Review enhanced notes." };
  }

  if (hasText(meeting.transcript)) {
    return { key: "needs-enhancement", label: "Needs enhancement", tone: "warning", nextAction: "Enhance notes." };
  }

  if (meeting.audio_path || status.includes("stop")) {
    return { key: "needs-transcription", label: "Needs transcription", tone: "warning", nextAction: "Transcribe audio." };
  }

  return { key: "stopped", label: "Stopped", tone: "neutral", nextAction: "Add notes or start processing." };
}
