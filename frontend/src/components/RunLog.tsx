import { useEffect, useState } from "react";
import { getRunLog } from "../api/analyses";
import type { LogEntry } from "../api/analyses";

const TYPE_COLOR: Record<string, string> = {
  agent_start:  "#6366f1",
  agent_end:    "#6366f1",
  llm_prompt:   "#0ea5e9",
  llm_response: "#10b981",
  tool_call:    "#f59e0b",
  tool_result:  "#84cc16",
  llm_error:    "#ef4444",
  tool_error:   "#ef4444",
  summary:      "#a855f7",
};

function TokenPill({ t }: { t?: { prompt: number; completion: number; total: number } }) {
  if (!t || t.total === 0) return null;
  return (
    <span style={{ fontSize: 10, color: "#94a3b8", marginLeft: 8 }}>
      ↑{t.prompt} ↓{t.completion} ={t.total}
    </span>
  );
}

function EntryRow({ e, open, onToggle }: { e: LogEntry; open: boolean; onToggle: () => void }) {
  const color = TYPE_COLOR[e.type] ?? "#64748b";
  const hasBody = e.prompt || e.response || e.input || e.output || e.error;

  return (
    <div style={{ borderBottom: "1px solid #1e293b" }}>
      <div
        onClick={hasBody ? onToggle : undefined}
        style={{
          display: "flex", alignItems: "baseline", gap: 8, padding: "6px 12px",
          cursor: hasBody ? "pointer" : "default",
          background: open ? "#0f172a" : "transparent",
        }}
      >
        <span style={{ color: "#475569", fontSize: 10, whiteSpace: "nowrap", minWidth: 80 }}>
          {e.ts ? new Date(e.ts).toLocaleTimeString() : ""}
        </span>
        <span style={{ color, fontSize: 11, fontWeight: 700, minWidth: 110 }}>{e.type}</span>
        {e.agent && <span style={{ color: "#94a3b8", fontSize: 11 }}>{e.agent}</span>}
        {e.tool && <span style={{ color: "#f59e0b", fontSize: 11 }}>{e.tool}</span>}
        {e.model && <span style={{ color: "#64748b", fontSize: 10 }}>{e.model}</span>}
        <TokenPill t={e.tokens ?? e.total_tokens} />
        {e.tokens_cumulative && e.type === "llm_response" && (
          <span style={{ fontSize: 10, color: "#475569", marginLeft: 4 }}>
            (cumulative: {e.tokens_cumulative.total})
          </span>
        )}
        {hasBody && (
          <span style={{ marginLeft: "auto", color: "#475569", fontSize: 12 }}>{open ? "▲" : "▼"}</span>
        )}
      </div>
      {open && hasBody && (
        <pre style={{
          margin: 0, padding: "8px 16px 12px 24px",
          fontSize: 11, color: "#cbd5e1", background: "#0f172a",
          whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 400, overflow: "auto",
        }}>
          {e.prompt || e.response || e.input || e.output || e.error}
        </pre>
      )}
    </div>
  );
}

export default function RunLog({ runId }: { runId: string }) {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    getRunLog(runId)
      .then((d) => setEntries(d.entries))
      .catch(() => setError("Log not available for this run."))
      .finally(() => setLoading(false));
  }, [runId]);

  const summary = entries.find((e) => e.type === "summary");
  const agentTokens = (summary as any)?.agent_tokens as Record<string, { prompt: number; completion: number; total: number; model: string; calls: number }> | undefined;
  const [showTokenTable, setShowTokenTable] = useState(false);
  const types = ["all", "llm_prompt", "llm_response", "tool_call", "tool_result", "agent_start", "llm_error"];
  const visible = filter === "all" ? entries : entries.filter((e) => e.type === filter);

  return (
    <div style={{ background: "#0d1117", borderRadius: 10, border: "1px solid #1e293b", overflow: "hidden", marginTop: 16 }}>
      <div style={{ padding: "12px 16px", borderBottom: "1px solid #1e293b", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ color: "#e2e8f0", fontWeight: 700, fontSize: 13 }}>Run Log</span>
        {summary?.total_tokens && (
          <span style={{ fontSize: 12, color: "#94a3b8" }}>
            Total — prompt: <strong style={{ color: "#e2e8f0" }}>{summary.total_tokens.prompt.toLocaleString()}</strong>{" "}
            completion: <strong style={{ color: "#e2e8f0" }}>{summary.total_tokens.completion.toLocaleString()}</strong>{" "}
            total: <strong style={{ color: "#a855f7" }}>{summary.total_tokens.total.toLocaleString()}</strong>
          </span>
        )}
        {agentTokens && (
          <button onClick={() => setShowTokenTable(t => !t)} style={{
            padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 600, cursor: "pointer",
            border: "1px solid #334155", background: "transparent", color: "#94a3b8",
          }}>
            {showTokenTable ? "Hide breakdown" : "By agent ▾"}
          </button>
        )}
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {types.map((t) => (
            <button key={t} onClick={() => setFilter(t)} style={{
              padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 600, cursor: "pointer",
              border: `1px solid ${filter === t ? "#6366f1" : "#2d3748"}`,
              background: filter === t ? "#1e1b4b" : "transparent",
              color: filter === t ? "#c7d2fe" : "#64748b",
            }}>{t === "all" ? "All" : t.replace("_", " ")}</button>
          ))}
        </div>
      </div>
      {showTokenTable && agentTokens && (
        <div style={{ borderBottom: "1px solid #1e293b", overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
            <thead>
              <tr style={{ background: "#0f172a" }}>
                {["Agent", "Model", "Calls", "Prompt", "Completion", "Total"].map(h => (
                  <th key={h} style={{ padding: "6px 12px", textAlign: h === "Agent" || h === "Model" ? "left" : "right", color: "#64748b", fontWeight: 600, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(agentTokens).sort((a, b) => b[1].total - a[1].total).map(([agent, t]) => (
                <tr key={agent} style={{ borderTop: "1px solid #1e293b" }}>
                  <td style={{ padding: "5px 12px", color: "#cbd5e1" }}>{agent}</td>
                  <td style={{ padding: "5px 12px", color: "#64748b", fontFamily: "monospace", fontSize: 10 }}>{t.model || "—"}</td>
                  <td style={{ padding: "5px 12px", color: "#64748b", textAlign: "right" }}>{t.calls}</td>
                  <td style={{ padding: "5px 12px", color: "#94a3b8", textAlign: "right" }}>{t.prompt.toLocaleString()}</td>
                  <td style={{ padding: "5px 12px", color: "#94a3b8", textAlign: "right" }}>{t.completion.toLocaleString()}</td>
                  <td style={{ padding: "5px 12px", color: "#a855f7", textAlign: "right", fontWeight: 700 }}>{t.total.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ maxHeight: 500, overflow: "auto" }}>
        {loading && <div style={{ padding: 24, textAlign: "center", color: "#475569" }}>Loading log…</div>}
        {error && <div style={{ padding: 24, textAlign: "center", color: "#64748b" }}>{error}</div>}
        {!loading && !error && visible.map((e, i) => (
          <EntryRow key={i} e={e} open={openIdx === i} onToggle={() => setOpenIdx(openIdx === i ? null : i)} />
        ))}
      </div>
    </div>
  );
}
