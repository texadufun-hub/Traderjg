import { useState } from "react";
import type { Trade, TradePayload } from "../types";

interface Props {
  initial?: Trade;
  onSave: (payload: TradePayload) => Promise<void>;
  onCancel: () => void;
}

const input: React.CSSProperties = {
  background: "#0f1117",
  border: "1px solid #2d3748",
  borderRadius: 8,
  color: "#e2e8f0",
  padding: "8px 12px",
  fontSize: 14,
  width: "100%",
  outline: "none",
};

const label: React.CSSProperties = {
  fontSize: 12,
  color: "#94a3b8",
  display: "block",
  marginBottom: 4,
};

export default function TradeForm({ initial, onSave, onCancel }: Props) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState<TradePayload>({
    symbol: initial?.symbol ?? "",
    side: initial?.side ?? "long",
    quantity: initial?.quantity ?? 1,
    entry_price: initial?.entry_price ?? 0,
    entry_date: initial?.entry_date ?? today,
    exit_price: initial?.exit_price ?? null,
    exit_date: initial?.exit_date ?? null,
    notes: initial?.notes ?? null,
  });
  const [loading, setLoading] = useState(false);

  const set = (key: keyof TradePayload, value: string | number | null) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await onSave(form);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <label style={label}>Symbol</label>
          <input style={input} value={form.symbol} onChange={(e) => set("symbol", e.target.value)} required placeholder="AAPL" />
        </div>
        <div>
          <label style={label}>Side</label>
          <select style={input} value={form.side} onChange={(e) => set("side", e.target.value as "long" | "short")}>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </div>
        <div>
          <label style={label}>Quantity</label>
          <input style={input} type="number" step="any" value={form.quantity} onChange={(e) => set("quantity", parseFloat(e.target.value))} required min={0.0001} />
        </div>
        <div>
          <label style={label}>Entry Price</label>
          <input style={input} type="number" step="any" value={form.entry_price} onChange={(e) => set("entry_price", parseFloat(e.target.value))} required min={0} />
        </div>
        <div>
          <label style={label}>Entry Date</label>
          <input style={input} type="date" value={form.entry_date} onChange={(e) => set("entry_date", e.target.value)} required />
        </div>
        <div>
          <label style={label}>Exit Price (optional)</label>
          <input style={input} type="number" step="any" value={form.exit_price ?? ""} onChange={(e) => set("exit_price", e.target.value ? parseFloat(e.target.value) : null)} min={0} placeholder="Leave blank if open" />
        </div>
        <div>
          <label style={label}>Exit Date (optional)</label>
          <input style={input} type="date" value={form.exit_date ?? ""} onChange={(e) => set("exit_date", e.target.value || null)} />
        </div>
      </div>
      <div>
        <label style={label}>Notes</label>
        <textarea style={{ ...input, resize: "vertical", minHeight: 72 }} value={form.notes ?? ""} onChange={(e) => set("notes", e.target.value || null)} placeholder="Optional trade notes..." />
      </div>
      <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
        <button type="button" onClick={onCancel} style={{ padding: "8px 20px", borderRadius: 8, border: "1px solid #2d3748", background: "transparent", color: "#94a3b8", cursor: "pointer", fontSize: 14 }}>
          Cancel
        </button>
        <button type="submit" disabled={loading} style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: "#6366f1", color: "#fff", cursor: loading ? "default" : "pointer", fontSize: 14, fontWeight: 600 }}>
          {loading ? "Saving…" : initial ? "Update Trade" : "Add Trade"}
        </button>
      </div>
    </form>
  );
}
