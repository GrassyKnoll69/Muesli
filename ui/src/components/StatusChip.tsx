import { MeetingStateTone } from "../lib/meetingState";

interface StatusChipProps {
  label: string;
  tone: MeetingStateTone;
}

export default function StatusChip({ label, tone }: StatusChipProps) {
  return <span className={`status-chip status-${tone}`}>{label}</span>;
}
