interface Props {
  label: string;
  value: string | number;
  positive?: boolean | null;
  subtitle?: string;
}

export default function StatCard({ label, value, positive, subtitle }: Props) {
  const color =
    positive == null ? "#94a3b8" : positive ? "#4ade80" : "#f87171";

  return (
    <div style={{
      background: "#1e2433", borderRadius: 12, padding: "16px 20px",
      display: "flex", flexDirection: "column", gap: 4,
      border: "1px solid #2d3748",
    }}>
      <span style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </span>
      <span style={{ fontSize: 24, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </span>
      {subtitle && <span style={{ fontSize: 11, color: "#475569" }}>{subtitle}</span>}
    </div>
  );
}
