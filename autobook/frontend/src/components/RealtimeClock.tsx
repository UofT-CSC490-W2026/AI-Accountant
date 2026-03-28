import { useEffect, useState } from "react";
import { formatClockTime } from "../utils/dateTime";

type RealtimeClockProps = {
  label?: string;
  variant?: "hero" | "surface";
};

export function RealtimeClock({
  label = "Live Clock",
  variant = "hero",
}: RealtimeClockProps) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(new Date());
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

  return (
    <span
      className={
        variant === "surface"
          ? "hero-pill hero-pill-clock hero-pill-clock-surface"
          : "hero-pill hero-pill-clock"
      }
      role="status"
      aria-live="polite"
    >
      <span className="clock-label">{label}</span>
      <span className="clock-value">{formatClockTime(now)}</span>
    </span>
  );
}
