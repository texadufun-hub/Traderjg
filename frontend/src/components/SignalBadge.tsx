import type { Signal } from "../types";

const COLORS: Record<string, { bg: string; text: string }> = {
  BUY:         { bg: "#14532d", text: "#4ade80" },
  OVERWEIGHT:  { bg: "#166534", text: "#86efac" },
  HOLD:        { bg: "#713f12", text: "#fbbf24" },
  UNDERWEIGHT: { bg: "#7f1d1d", text: "#fca5a5" },
  SELL:        { bg: "#450a0a", text: "#ef4444" },
};

interface Props {
  signal: Signal | string | null;
  large?: boolean;
}

export default function SignalBadge({ signal, large }: Props) {
  if (!signal) return <span style={{ color: "#64748b" }}>—</span>;
  const s = signal.toUpperCase();
  const c = COLORS[s] ?? { bg: "#1e2433", text: "#94a3b8" };
  return (
    <span style={{
      display: "inline-block",
      padding: large ? "6px 18px" : "3px 10px",
      borderRadius: 999,
      background: c.bg,
      color: c.text,
      fontWeight: 700,
      fontSize: large ? 18 : 12,
      letterSpacing: "0.06em",
      textTransform: "uppercase",
    }}>
      {s}
    </span>
  );
}
