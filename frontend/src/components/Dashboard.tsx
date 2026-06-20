import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";
import { getStats } from "../api/trades";
import type { Stats, Trade } from "../types";
import StatCard from "./StatCard";

interface Props {
  trades: Trade[];
}

const fmt = (n: number) =>
  n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`;

export default function Dashboard({ trades }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    getStats().then(setStats).catch(console.error);
  }, [trades]);

  const chartData = trades
    .filter((t) => t.pnl !== null)
    .slice(0, 20)
    .reverse()
    .map((t) => ({ symbol: t.symbol, pnl: t.pnl as number }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16 }}>
        <StatCard label="Total P&L" value={stats ? fmt(stats.total_pnl) : "—"} positive={stats ? stats.total_pnl >= 0 : null} />
        <StatCard label="Win Rate" value={stats ? `${stats.win_rate}%` : "—"} positive={stats ? stats.win_rate >= 50 : null} />
        <StatCard label="Avg Trade" value={stats ? fmt(stats.avg_pnl) : "—"} positive={stats ? stats.avg_pnl >= 0 : null} />
        <StatCard label="Open" value={stats?.open_trades ?? "—"} positive={null} subtitle="active positions" />
        <StatCard label="Best Trade" value={stats && stats.best_trade !== 0 ? fmt(stats.best_trade) : "—"} positive={true} />
        <StatCard label="Worst Trade" value={stats && stats.worst_trade !== 0 ? fmt(stats.worst_trade) : "—"} positive={false} />
      </div>

      {chartData.length > 0 && (
        <div style={{ background: "#1e2433", borderRadius: 12, padding: "20px 24px", border: "1px solid #2d3748" }}>
          <p style={{ marginBottom: 16, color: "#94a3b8", fontSize: 13, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Recent P&L per Trade
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <XAxis dataKey="symbol" tick={{ fill: "#64748b", fontSize: 11 }} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#0f1117", border: "1px solid #2d3748", borderRadius: 8 }}
                formatter={(v: number) => [fmt(v), "P&L"]}
              />
              <ReferenceLine y={0} stroke="#2d3748" />
              <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.pnl >= 0 ? "#4ade80" : "#f87171"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
