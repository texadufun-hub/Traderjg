import { useState } from "react";
import type { Trade, TradePayload, RunOut } from "../types";
import SignalBadge from "./SignalBadge";

interface Props {
  initial?: Trade;
  analyses?: RunOut[];
  onSave: (payload: TradePayload) => Promise<void>;
  onCancel: () => void;
}

const inp: React.CSSProperties = {
  background: "#0f1117", border: "1px solid #2d3748", borderRadius: 8,
  color: "#e2e8f0", padding: "8px 12px", fontSize: 14, width: "100%",
};
const lbl: React.CSSProperties = { fontSize: 12, color: "#94a3b8", display: "block", marginBottom: 4 };

export default function TradeForm({ initial, analyses, onSave, onCancel }: Props) {
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
    analysis_run_id: initial?.analysis_run_id ?? null,
  });
  const [loading, setLoading] = useState(false);

  const set = (k: keyof TradePayload, v: string | number | null) =>
    setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try { await onSave(form); } finally { setLoading(false); }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <label style={lbl}>Symbol</label>
          <input style={inp} value={form.symbol}
            onChange={(e) => set("symbol", e.target.value.toUpperCase())} required placeholder="AAPL" />
        </div>
        <div>
          <label style={lbl}>Side</label>
          <select style={inp} value={form.side} onChange={(e) => set("side", e.target.value)}>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </div>
        <div>
          <label style={lbl}>Quantity</label>
          <input style={inp} type="number" step="any" value={form.quantity}
            onChange={(e) => set("quantity", parseFloat(e.target.value))} required min={0.0001} />
        </div>
        <div>
          <label style={lbl}>Entry Price</label>
          <input style={inp} type="number" step="any" value={form.entry_price}
            onChange={(e) => set("entry_price", parseFloat(e.target.value))} required min={0} />
        </div>
        <div>
          <label style={lbl}>Entry Date</label>
          <input style={inp} type="date" value={form.entry_date}
            onChange={(e) => set("entry_date", e.target.value)} required />
        </div>
        <div>
          <label style={lbl}>Exit Price (optional)</label>
          <input style={inp} type="number" step="any" value={form.exit_price ?? ""}
            onChange={(e) => set("exit_price", e.target.value ? parseFloat(e.target.value) : null)}
            placeholder="Leave blank if open" />
        </div>
        <div>
          <label style={lbl}>Exit Date (optional)</label>
          <input style={inp} type="date" value={form.exit_date ?? ""}
            onChange={(e) => set("exit_date", e.target.value || null)} />
        </div>

        {analyses && analyses.length > 0 && (
          <div style={{ gridColumn: "1 / -1" }}>
            <label style={lbl}>Link to Analysis (optional)</label>
            <select style={inp} value={form.analysis_run_id ?? ""}
              onChange={(e) => set("analysis_run_id", e.target.value || null)}>
              <option value="">— No analysis linked —</option>
              {analyses.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.ticker} · {r.trade_date} · {r.signal ?? "no signal"}
                </option>
              ))}
            </select>
            {form.analysis_run_id && (
              <div style={{ marginTop: 8 }}>
                <SignalBadge signal={analyses.find((r) => r.run_id === form.analysis_run_id)?.signal ?? null} />
              </div>
            )}
          </div>
        )}
      </div>

      <div>
        <label style={lbl}>Notes</label>
        <textarea style={{ ...inp, resize: "vertical", minHeight: 72 }}
          value={form.notes ?? ""}
          onChange={(e) => set("notes", e.target.value || null)}
          placeholder="Trade rationale, observations…" />
      </div>

      <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
        <button type="button" onClick={onCancel}
          style={{ padding: "8px 20px", borderRadius: 8, border: "1px solid #2d3748", background: "transparent", color: "#94a3b8", cursor: "pointer", fontSize: 14 }}>
          Cancel
        </button>
        <button type="submit" disabled={loading}
          style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: "#6366f1", color: "#fff", cursor: loading ? "default" : "pointer", fontSize: 14, fontWeight: 600 }}>
          {loading ? "Saving…" : initial ? "Update" : "Log Trade"}
        </button>
      </div>
    </form>
  );
}
