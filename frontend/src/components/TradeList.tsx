import type { Trade } from "../types";

interface Props {
  trades: Trade[];
  onEdit: (trade: Trade) => void;
  onDelete: (id: number) => void;
}

const badge = (_text: string, color: string): React.CSSProperties => ({
  display: "inline-block",
  padding: "2px 8px",
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 600,
  background: color + "22",
  color,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
});

const fmt = (n: number | null) => {
  if (n === null) return <span style={{ color: "#64748b" }}>—</span>;
  const color = n >= 0 ? "#4ade80" : "#f87171";
  const sign = n >= 0 ? "+" : "";
  return <span style={{ color, fontWeight: 600 }}>{sign}${n.toFixed(2)}</span>;
};

export default function TradeList({ trades, onEdit, onDelete }: Props) {
  if (trades.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "60px 0", color: "#64748b" }}>
        No trades yet. Add your first trade above.
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #2d3748" }}>
            {["Symbol", "Side", "Qty", "Entry", "Exit", "Entry Date", "P&L", "Status", ""].map((h) => (
              <th key={h} style={{ textAlign: "left", padding: "8px 12px", color: "#64748b", fontWeight: 600, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.04em" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id} style={{ borderBottom: "1px solid #1e2433" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#1e2433")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <td style={{ padding: "10px 12px", fontWeight: 700, color: "#e2e8f0" }}>{t.symbol}</td>
              <td style={{ padding: "10px 12px" }}>
                <span style={badge(t.side, t.side === "long" ? "#60a5fa" : "#f472b6")}>{t.side}</span>
              </td>
              <td style={{ padding: "10px 12px", color: "#cbd5e1" }}>{t.quantity}</td>
              <td style={{ padding: "10px 12px", color: "#cbd5e1" }}>${t.entry_price.toFixed(2)}</td>
              <td style={{ padding: "10px 12px", color: "#cbd5e1" }}>{t.exit_price != null ? `$${t.exit_price.toFixed(2)}` : <span style={{ color: "#64748b" }}>—</span>}</td>
              <td style={{ padding: "10px 12px", color: "#94a3b8" }}>{t.entry_date}</td>
              <td style={{ padding: "10px 12px" }}>{fmt(t.pnl)}</td>
              <td style={{ padding: "10px 12px" }}>
                <span style={badge(t.status, t.status === "closed" ? "#94a3b8" : "#facc15")}>{t.status}</span>
              </td>
              <td style={{ padding: "10px 12px" }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => onEdit(t)} style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid #2d3748", background: "transparent", color: "#94a3b8", cursor: "pointer", fontSize: 12 }}>
                    Edit
                  </button>
                  <button onClick={() => { if (confirm("Delete this trade?")) onDelete(t.id); }} style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid #7f1d1d", background: "transparent", color: "#f87171", cursor: "pointer", fontSize: 12 }}>
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
