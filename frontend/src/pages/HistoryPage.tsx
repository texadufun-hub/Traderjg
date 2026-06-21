import { useEffect, useState } from "react";
import { listRuns, getRun, deleteRun } from "../api/analyses";
import type { RunOut, RunDetail, AnalysisResult } from "../types";
import SignalBadge from "../components/SignalBadge";
import ModelBadge from "../components/ModelBadge";
import AnalysisResultView from "../components/AnalysisResult";
import { exportAnalysesToPdf } from "../utils/exportPdf";
import RunLog from "../components/RunLog";

export default function HistoryPage() {
  const [runs, setRuns] = useState<RunOut[]>([]);
  const [selected, setSelected] = useState<{ detail: RunDetail; result: AnalysisResult | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);

  const refresh = () => {
    setLoading(true);
    setChecked(new Set());
    listRuns().then(setRuns).finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const open = async (run: RunOut) => {
    const detail = await getRun(run.run_id);
    const result = detail.result_json ? JSON.parse(detail.result_json) as AnalysisResult : null;
    setSelected({ detail, result });
  };

  const remove = async (runId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this analysis?")) return;
    await deleteRun(runId);
    refresh();
    if (selected?.detail.run_id === runId) setSelected(null);
  };

  const toggleCheck = (runId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setChecked((prev) => {
      const next = new Set(prev);
      next.has(runId) ? next.delete(runId) : next.add(runId);
      return next;
    });
  };

  const toggleAll = () => {
    const completedIds = runs.filter((r) => r.status === "complete").map((r) => r.run_id);
    setChecked((prev) =>
      prev.size === completedIds.length ? new Set() : new Set(completedIds)
    );
  };

  const exportSelected = async () => {
    if (checked.size === 0) return;
    setExporting(true);
    try {
      const details = await Promise.all([...checked].map((id) => getRun(id)));
      const analyses = details
        .filter((d) => d.result_json)
        .map((d) => ({
          ticker: d.ticker,
          tradeDate: d.trade_date,
          result: JSON.parse(d.result_json!) as AnalysisResult,
        }));
      if (analyses.length > 0) exportAnalysesToPdf(analyses);
    } finally {
      setExporting(false);
    }
  };

  if (selected) {
    const { detail, result } = selected;
    const cfg = detail.config_snapshot ? JSON.parse(detail.config_snapshot) : {};
    return (
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 20, alignItems: "center" }}>
          <button onClick={() => setSelected(null)} style={{ padding: "6px 16px", borderRadius: 8, border: "1px solid #2d3748", background: "transparent", color: "#94a3b8", cursor: "pointer" }}>
            ← Back to History
          </button>
          {result && (
            <button
              onClick={() => exportAnalysesToPdf([{ ticker: detail.ticker, tradeDate: detail.trade_date, result }])}
              style={{ padding: "6px 16px", borderRadius: 8, border: "1px solid #6366f1", background: "transparent", color: "#818cf8", cursor: "pointer", fontSize: 13 }}
            >
              Export PDF
            </button>
          )}
          <ModelBadge provider={selected.detail.llm_provider ?? null} model={selected.detail.deep_think_llm ?? null} />
        </div>

        {detail.status === "error" ? (
          <div style={{ background: "#450a0a", borderRadius: 12, padding: 24, color: "#fca5a5" }}>
            <strong>Analysis failed</strong>
            <pre style={{ marginTop: 10, fontSize: 12, whiteSpace: "pre-wrap" }}>{detail.error}</pre>
          </div>
        ) : result ? (
          <AnalysisResultView result={result} ticker={detail.ticker} tradeDate={detail.trade_date} />
        ) : (
          <div style={{ color: "#64748b", padding: 40, textAlign: "center" }}>No result data available.</div>
        )}

        <div style={{ background: "#1e2433", borderRadius: 10, border: "1px solid #2d3748", padding: 16, marginTop: 16 }}>
          <p style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", marginBottom: 8 }}>Run config</p>
          <pre style={{ fontSize: 12, color: "#94a3b8", whiteSpace: "pre-wrap" }}>{JSON.stringify({ ...cfg, analysts: JSON.parse(detail.analysts) }, null, 2)}</pre>
        </div>

        <RunLog runId={detail.run_id} />
      </div>
    );
  }

  const completedCount = runs.filter((r) => r.status === "complete").length;
  const allChecked = checked.size > 0 && checked.size === completedCount;

  return (
    <div style={{ maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#e2e8f0" }}>Analysis History</h2>
        <div style={{ display: "flex", gap: 8 }}>
          {checked.size > 0 && (
            <button
              onClick={exportSelected}
              disabled={exporting}
              style={{
                padding: "6px 14px", borderRadius: 8, border: "1px solid #6366f1",
                background: "transparent", color: "#818cf8", cursor: "pointer", fontSize: 13,
                opacity: exporting ? 0.6 : 1,
              }}
            >
              {exporting ? "Preparing…" : `Export ${checked.size} PDF${checked.size > 1 ? "s" : ""}`}
            </button>
          )}
          <button onClick={refresh} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid #2d3748", background: "transparent", color: "#94a3b8", cursor: "pointer", fontSize: 13 }}>
            Refresh
          </button>
        </div>
      </div>

      <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>Loading…</div>
        ) : runs.length === 0 ? (
          <div style={{ padding: 60, textAlign: "center", color: "#64748b" }}>No analyses yet. Run your first one!</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #2d3748" }}>
                <th style={{ padding: "10px 16px", width: 36 }}>
                  <input
                    type="checkbox"
                    checked={allChecked}
                    onChange={toggleAll}
                    title="Select all completed"
                    style={{ cursor: "pointer", width: 15, height: 15 }}
                  />
                </th>
                {["Ticker", "Date", "Signal", "Model", "Status", "Run At", ""].map((h) => (
                  <th key={h} style={{ textAlign: "left", padding: "10px 16px", color: "#64748b", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const isChecked = checked.has(run.run_id);
                const canCheck = run.status === "complete";
                return (
                  <tr
                    key={run.run_id}
                    onClick={() => open(run)}
                    style={{ borderBottom: "1px solid #161b27", cursor: "pointer", background: isChecked ? "#1a1f35" : "transparent" }}
                    onMouseEnter={(e) => { if (!isChecked) e.currentTarget.style.background = "#161b27"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = isChecked ? "#1a1f35" : "transparent"; }}
                  >
                    <td style={{ padding: "12px 16px" }} onClick={(e) => canCheck && toggleCheck(run.run_id, e)}>
                      {canCheck && (
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}}
                          style={{ cursor: "pointer", width: 15, height: 15 }}
                        />
                      )}
                    </td>
                    <td style={{ padding: "12px 16px", fontWeight: 700, color: "#e2e8f0" }}>{run.ticker}</td>
                    <td style={{ padding: "12px 16px", color: "#94a3b8" }}>{run.trade_date}</td>
                    <td style={{ padding: "12px 16px" }}><SignalBadge signal={run.signal} /></td>
                    <td style={{ padding: "12px 16px" }}><ModelBadge provider={run.llm_provider} model={run.deep_think_llm} /></td>
                    <td style={{ padding: "12px 16px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 600,
                        background: run.status === "complete" ? "#14532d" : run.status === "error" ? "#450a0a" : "#1e1b4b",
                        color: run.status === "complete" ? "#4ade80" : run.status === "error" ? "#f87171" : "#818cf8",
                      }}>
                        {run.status}
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px", color: "#64748b" }}>
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <button onClick={(e) => remove(run.run_id, e)}
                        style={{ padding: "3px 10px", borderRadius: 6, border: "1px solid #7f1d1d", background: "transparent", color: "#f87171", cursor: "pointer", fontSize: 11 }}>
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
