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

function meetingStatus(meeting: Meeting): string {
  return meeting.status.toLowerCase();
}

export function deriveMeetingState(meeting: Meeting): MeetingDisplayState {
  const status = meetingStatus(meeting);

  if (status === "recording") {
    return { key: "recording", label: "Recording", tone: "recording", nextAction: "Keep taking notes or stop recording." };
  }

  if (status === "transcribing") {
    return { key: "transcribing", label: "Transcribing", tone: "busy", nextAction: "Wait for transcription to finish." };
  }

  if (status === "enhancing") {
    return { key: "enhancing", label: "Enhancing", tone: "busy", nextAction: "Wait for note enhancement to finish." };
  }

  if (status === "failed" || status === "error") {
    return { key: "blocked", label: "Failed", tone: "danger", nextAction: "Review the error and retry the last action." };
  }

  if (status === "enhanced" || hasText(meeting.enhanced_notes)) {
    return { key: "complete", label: "Complete", tone: "success", nextAction: "Review enhanced notes." };
  }

  if (status === "transcribed" || hasText(meeting.transcript)) {
    return { key: "needs-enhancement", label: "Needs enhancement", tone: "warning", nextAction: "Enhance notes." };
  }

  if (status === "recorded" || meeting.audio_path || status === "stopped") {
    return { key: "needs-transcription", label: "Needs transcription", tone: "warning", nextAction: "Transcribe audio." };
  }

  return { key: "stopped", label: "Stopped", tone: "neutral", nextAction: "Add notes or start processing." };
}

export function canTranscribeMeeting(meeting: Meeting): boolean {
  const status = meetingStatus(meeting);
  const hasAudio = hasText(meeting.audio_path);
  const readyForTranscription = status === "recorded" || hasAudio;
  return readyForTranscription && !hasText(meeting.transcript) && !hasText(meeting.enhanced_notes);
}

export function canEnhanceMeeting(meeting: Meeting): boolean {
  const status = meetingStatus(meeting);
  return status === "transcribed" || status === "enhanced" || hasText(meeting.transcript);
}
