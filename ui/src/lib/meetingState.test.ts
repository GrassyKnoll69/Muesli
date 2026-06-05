import { describe, expect, it } from "vitest";
import { Meeting } from "../api/client";
import { deriveMeetingState } from "./meetingState";

function meeting(overrides: Partial<Meeting> = {}): Meeting {
  return {
    id: 1,
    title: "Weekly sync",
    created_at: "2026-06-05T18:00:00Z",
    rough_notes: "",
    transcript: "",
    enhanced_notes: "",
    template_id: null,
    audio_path: null,
    status: "created",
    ...overrides,
  };
}

describe("deriveMeetingState", () => {
  it("shows recording when the backend status says recording", () => {
    expect(deriveMeetingState(meeting({ status: "recording" })).label).toBe("Recording");
  });

  it("asks for transcription after a stopped meeting has audio but no transcript", () => {
    expect(deriveMeetingState(meeting({ status: "stopped", audio_path: "meeting.wav" })).label).toBe("Needs transcription");
  });

  it("asks for enhancement when transcript exists but enhanced notes are empty", () => {
    expect(deriveMeetingState(meeting({ transcript: "Full transcript" })).label).toBe("Needs enhancement");
  });

  it("marks a meeting complete when enhanced notes exist", () => {
    expect(deriveMeetingState(meeting({ enhanced_notes: "# Notes" })).label).toBe("Complete");
  });

  it("marks failed backend statuses as blocked", () => {
    expect(deriveMeetingState(meeting({ status: "failed" })).tone).toBe("danger");
  });
});
