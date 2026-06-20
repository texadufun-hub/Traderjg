import { useEffect, useState } from "react";
import { getMemory } from "../api/memory";
import type { MemoryEntry } from "../types";
import SignalBadge from "../components/SignalBadge";

export default function MemoryPage() {
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<MemoryEntry | null>(null);

  useEffect(() => {
    getMemory().then(setEntries).finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: "#64748b", padding: 40 }}>Loading memory log…</div>;

  if (entries.length === 0) {
    return (
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#e2e8f0", marginBottom: 12 }}>Memory & Reflections</h2>
        <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", padding: 60, textAlign: "center", color: "#64748b" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🧠</div>
          <p>No memory entries yet.</p>
          <p style={{ fontSize: 13, marginTop: 8 }}>After analyses complete, TradingAgents stores<br />decisions and reflections here for future reference.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#e2e8f0" }}>Memory & Reflections</h2>
          <p style={{ color: "#64748b", fontSize: 13, marginTop: 4 }}>
            Past decisions and post-trade reflections used by agents to improve future analysis.
          </p>
        </div>
        <span style={{ color: "#64748b", fontSize: 13 }}>{entries.length} entries</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: selected ? "1fr 1fr" : "1fr", gap: 16 }}>
        <div>
          {entries.map((e, i) => (
            <div key={i} onClick={() => setSelected(e)}
              style={{
                background: selected === e ? "#1e1b4b" : "#1e2433",
                borderRadius: 10,
                border: `1px solid ${selected === e ? "#6366f1" : "#2d3748"}`,
                padding: "14px 16px",
                marginBottom: 10,
                cursor: "pointer",
              }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontWeight: 700, color: "#e2e8f0", fontSize: 15 }}>
                  {e.ticker ?? "—"}
                </span>
                <SignalBadge signal={e.signal ?? e.decision ?? null} />
              </div>
              <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#64748b" }}>
                {e.trade_date && <span>📅 {e.trade_date}</span>}
                {e.raw_return != null && (
                  <span style={{ color: e.raw_return >= 0 ? "#4ade80" : "#f87171" }}>
                    Return: {e.raw_return >= 0 ? "+" : ""}{(e.raw_return * 100).toFixed(2)}%
                  </span>
                )}
                {e.alpha_return != null && (
                  <span style={{ color: e.alpha_return >= 0 ? "#4ade80" : "#f87171" }}>
                    Alpha: {e.alpha_return >= 0 ? "+" : ""}{(e.alpha_return * 100).toFixed(2)}%
                  </span>
                )}
              </div>
              {e.reflection && (
                <p style={{ marginTop: 8, fontSize: 12, color: "#94a3b8", fontStyle: "italic", lineHeight: 1.5 }}>
                  "{e.reflection.slice(0, 140)}{e.reflection.length > 140 ? "…" : ""}"
                </p>
              )}
            </div>
          ))}
        </div>

        {selected && (
          <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", padding: 20, position: "sticky", top: 20, alignSelf: "flex-start" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <div>
                <span style={{ fontWeight: 800, fontSize: 20, color: "#e2e8f0" }}>{selected.ticker}</span>
                <span style={{ color: "#64748b", fontSize: 13, marginLeft: 10 }}>{selected.trade_date}</span>
              </div>
              <button onClick={() => setSelected(null)}
                style={{ border: "none", background: "transparent", color: "#64748b", cursor: "pointer", fontSize: 18 }}>×</button>
            </div>

            <div style={{ marginBottom: 12 }}>
              <SignalBadge signal={selected.signal ?? selected.decision ?? null} large />
            </div>

            {selected.raw_return != null && (
              <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
                <div style={{ background: "#0f1117", borderRadius: 8, padding: "8px 12px" }}>
                  <div style={{ fontSize: 11, color: "#64748b" }}>Raw Return</div>
                  <div style={{ color: selected.raw_return >= 0 ? "#4ade80" : "#f87171", fontWeight: 700 }}>
                    {selected.raw_return >= 0 ? "+" : ""}{(selected.raw_return * 100).toFixed(2)}%
                  </div>
                </div>
                {selected.alpha_return != null && (
                  <div style={{ background: "#0f1117", borderRadius: 8, padding: "8px 12px" }}>
                    <div style={{ fontSize: 11, color: "#64748b" }}>Alpha</div>
                    <div style={{ color: selected.alpha_return >= 0 ? "#4ade80" : "#f87171", fontWeight: 700 }}>
                      {selected.alpha_return >= 0 ? "+" : ""}{(selected.alpha_return * 100).toFixed(2)}%
                    </div>
                  </div>
                )}
              </div>
            )}

            {selected.reflection && (
              <div>
                <p style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", marginBottom: 8 }}>Reflection</p>
                <p style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.7, fontStyle: "italic" }}>{selected.reflection}</p>
              </div>
            )}

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: 11, color: "#374151", textTransform: "uppercase", marginBottom: 6 }}>Raw Entry</p>
              <pre style={{ fontSize: 11, color: "#374151", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                {JSON.stringify(selected, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
