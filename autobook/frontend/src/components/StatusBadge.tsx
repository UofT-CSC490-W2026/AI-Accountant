import type { Status } from "../api/types";

type StatusBadgeProps = {
  status: Status;
};

const labels: Record<Status, string> = {
  auto_posted: "Auto-posted",
  needs_clarification: "Needs Clarification",
  rejected: "Rejected",
  accepted: "Processing",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`status-badge status-${status}`}>{labels[status]}</span>;
}
