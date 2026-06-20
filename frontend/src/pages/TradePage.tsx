import { useEffect, useState } from "react";
import { listTrades, createTrade, updateTrade, deleteTrade, getStats } from "../api/trades";
import { listRuns } from "../api/analyses";
import type { Trade, TradePayload, PortfolioStats, RunOut } from "../types";
import StatCard from "../components/StatCard";
import TradeForm from "../components/TradeForm";
import TradeList from "../components/TradeList";

type View = "list" | "add" | "edit";

const fmt = (n: number) => (n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`);

export default function TradePage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [stats, setStats] = useState<PortfolioStats | null>(null);
  const [runs, setRuns] = useState<RunOut[]>([]);
  const [view, setView] = useState<View>("list");
  const [editing, setEditing] = useState<Trade | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    const [t, s, r] = await Promise.all([listTrades(), getStats(), listRuns()]);
    setTrades(t);
    setStats(s);
    setRuns(r.filter((r) => r.status === "complete"));
    setLoading(false);
  };

  useEffect(() => { refresh(); }, []);

  const handleSave = async (payload: TradePayload) => {
    setError(null);
    try {
      if (editing) await updateTrade(editing.id, payload);
      else await createTrade(payload);
      setView("list");
      setEditing(null);
      await refresh();
    } catch {
      setError("Failed to save trade");
    }
  };

  const handleDelete = async (id: number) => {
    try { await deleteTrade(id); await refresh(); }
    catch { setError("Failed to delete trade"); }
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#e2e8f0" }}>Trade Journal</h2>
        {view === "list" && (
          <button onClick={() => { setEditing(null); setView("add"); }}
            style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: "#6366f1", color: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 600 }}>
            + Log Trade
          </button>
        )}
        {view !== "list" && (
          <button onClick={() => { setView("list"); setEditing(null); }}
            style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #2d3748", background: "transparent", color: "#94a3b8", cursor: "pointer" }}>
            ← Cancel
          </button>
        )}
      </div>

      {error && (
        <div style={{ background: "#450a0a", color: "#fca5a5", padding: "10px 16px", borderRadius: 8, marginBottom: 16, fontSize: 14 }}>
          {error}
        </div>
      )}

      {view === "list" && (
        <>
          {stats && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 20 }}>
              <StatCard label="Total P&L" value={fmt(stats.total_pnl)} positive={stats.total_pnl >= 0} />
              <StatCard label="Win Rate" value={`${stats.win_rate}%`} positive={stats.win_rate >= 50} />
              <StatCard label="Avg Trade" value={fmt(stats.avg_pnl)} positive={stats.avg_pnl >= 0} />
              <StatCard label="Open Positions" value={stats.open_trades} positive={null} />
              <StatCard label="Closed Trades" value={stats.closed_trades} positive={null} />
              <StatCard label="Best Trade" value={stats.best_trade !== 0 ? fmt(stats.best_trade) : "—"} positive={true} />
            </div>
          )}
          <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", overflow: "hidden" }}>
            <div style={{ padding: "14px 20px", borderBottom: "1px solid #2d3748" }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: "#e2e8f0" }}>Positions</h3>
            </div>
            {loading ? (
              <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>Loading…</div>
            ) : (
              <TradeList trades={trades}
                onEdit={(t) => { setEditing(t); setView("edit"); }}
                onDelete={handleDelete} />
            )}
          </div>
        </>
      )}

      {(view === "add" || view === "edit") && (
        <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", padding: 24 }}>
          <h3 style={{ fontSize: 17, fontWeight: 600, marginBottom: 20, color: "#e2e8f0" }}>
            {view === "edit" ? "Edit Trade" : "Log New Trade"}
          </h3>
          <TradeForm
            initial={editing ?? undefined}
            analyses={runs}
            onSave={handleSave}
            onCancel={() => { setView("list"); setEditing(null); }}
          />
        </div>
      )}
    </div>
  );
}
