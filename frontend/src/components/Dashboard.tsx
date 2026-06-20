import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from "recharts";
import { getStats } from "../api/trades";
import { listRuns } from "../api/analyses";
import type { PortfolioStats, Trade, RunOut } from "../types";
import StatCard from "./StatCard";
import SignalBadge from "./SignalBadge";

interface Props {
  trades: Trade[];
  onTabChange?: (tab: string) => void;
}

const fmt = (n: number) => (n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`);

export default function Dashboard({ trades, onTabChange }: Props) {
  const [stats, setStats] = useState<PortfolioStats | null>(null);
  const [runs, setRuns] = useState<RunOut[]>([]);

  useEffect(() => {
    getStats().then(setStats).catch(console.error);
    listRuns().then((r) => setRuns(r.slice(0, 5))).catch(console.error);
  }, [trades]);

  const chartData = trades
    .filter((t) => t.pnl !== null)
    .slice(0, 20).reverse()
    .map((t) => ({ symbol: t.symbol, pnl: t.pnl as number }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
        <StatCard label="Total P&L" value={stats ? fmt(stats.total_pnl) : "—"} positive={stats ? stats.total_pnl >= 0 : null} />
        <StatCard label="Win Rate" value={stats ? `${stats.win_rate}%` : "—"} positive={stats ? stats.win_rate >= 50 : null} />
        <StatCard label="Avg Trade" value={stats ? fmt(stats.avg_pnl) : "—"} positive={stats ? stats.avg_pnl >= 0 : null} />
        <StatCard label="Open" value={stats?.open_trades ?? "—"} positive={null} subtitle="positions" />
        <StatCard label="Closed" value={stats?.closed_trades ?? "—"} positive={null} subtitle="trades" />
        <StatCard label="Analyses" value={runs.length > 0 ? `${runs.length}` : "—"} positive={null} subtitle="this session" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* P&L chart */}
        {chartData.length > 0 && (
          <div style={{ background: "#1e2433", borderRadius: 12, padding: "16px 20px", border: "1px solid #2d3748" }}>
            <p style={{ marginBottom: 12, color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              P&L per Closed Trade
            </p>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                <XAxis dataKey="symbol" tick={{ fill: "#64748b", fontSize: 10 }} />
                <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: "#0f1117", border: "1px solid #2d3748", borderRadius: 8 }}
                  formatter={(v: number) => [fmt(v), "P&L"]}
                />
                <ReferenceLine y={0} stroke="#2d3748" />
                <Bar dataKey="pnl" radius={[3, 3, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={entry.pnl >= 0 ? "#4ade80" : "#f87171"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Recent analyses */}
        <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", overflow: "hidden" }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid #2d3748", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <p style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>Recent Analyses</p>
            {onTabChange && (
              <button onClick={() => onTabChange("history")}
                style={{ fontSize: 11, color: "#6366f1", background: "none", border: "none", cursor: "pointer" }}>
                View all →
              </button>
            )}
          </div>
          {runs.length === 0 ? (
            <div style={{ padding: "30px 16px", textAlign: "center", color: "#374151", fontSize: 13 }}>
              No analyses yet.{" "}
              {onTabChange && (
                <button onClick={() => onTabChange("analyze")}
                  style={{ color: "#6366f1", background: "none", border: "none", cursor: "pointer", fontSize: 13 }}>
                  Run one →
                </button>
              )}
            </div>
          ) : (
            runs.map((r) => (
              <div key={r.run_id} style={{ padding: "10px 16px", borderBottom: "1px solid #161b27", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <span style={{ fontWeight: 700, color: "#e2e8f0", fontSize: 14 }}>{r.ticker}</span>
                  <span style={{ color: "#64748b", fontSize: 12, marginLeft: 8 }}>{r.trade_date}</span>
                </div>
                <SignalBadge signal={r.signal} />
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
