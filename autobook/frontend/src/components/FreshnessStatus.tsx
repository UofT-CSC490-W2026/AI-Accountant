import { formatClockTime } from "../utils/dateTime";

type FreshnessStatusProps = {
  label: string;
  lastUpdatedAt: Date | null;
  variant?: "hero" | "surface";
};

export function FreshnessStatus({
  label,
  lastUpdatedAt,
  variant = "surface",
}: FreshnessStatusProps) {
  const className =
    variant === "hero"
      ? "hero-pill freshness-pill"
      : "hero-pill freshness-pill freshness-pill-surface";

  return (
    <span className={className} role="status" aria-live="polite">
      <span className="freshness-label">{label}</span>
      <span className="freshness-value">
        {lastUpdatedAt ? formatClockTime(lastUpdatedAt) : "Waiting for first sync"}
      </span>
    </span>
  );
}
