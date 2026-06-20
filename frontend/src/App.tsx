import { useEffect, useState } from "react";
import { getTrades, createTrade, updateTrade, deleteTrade } from "./api/trades";
import type { Trade, TradePayload } from "./types";
import Dashboard from "./components/Dashboard";
import TradeForm from "./components/TradeForm";
import TradeList from "./components/TradeList";

type View = "list" | "add" | "edit";

export default function App() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [view, setView] = useState<View>("list");
  const [editing, setEditing] = useState<Trade | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = () =>
    getTrades()
      .then(setTrades)
      .catch(() => setError("Failed to load trades"))
      .finally(() => setLoading(false));

  useEffect(() => { refresh(); }, []);

  const handleSave = async (payload: TradePayload) => {
    setError(null);
    try {
      if (editing) {
        await updateTrade(editing.id, payload);
      } else {
        await createTrade(payload);
      }
      setView("list");
      setEditing(null);
      await refresh();
    } catch {
      setError("Failed to save trade");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteTrade(id);
      await refresh();
    } catch {
      setError("Failed to delete trade");
    }
  };

  const handleEdit = (trade: Trade) => {
    setEditing(trade);
    setView("edit");
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: "#e2e8f0", letterSpacing: "-0.02em" }}>
            📈 Traderjg
          </h1>
          <p style={{ color: "#64748b", fontSize: 14, marginTop: 4 }}>Your personal trading journal</p>
        </div>
        {view === "list" && (
          <button
            onClick={() => { setEditing(null); setView("add"); }}
            style={{ padding: "10px 20px", borderRadius: 8, border: "none", background: "#6366f1", color: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 600 }}
          >
            + Add Trade
          </button>
        )}
        {view !== "list" && (
          <button
            onClick={() => { setView("list"); setEditing(null); }}
            style={{ padding: "10px 20px", borderRadius: 8, border: "1px solid #2d3748", background: "transparent", color: "#94a3b8", cursor: "pointer", fontSize: 14 }}
          >
            ← Back
          </button>
        )}
      </header>

      {error && (
        <div style={{ background: "#7f1d1d", color: "#fca5a5", padding: "12px 16px", borderRadius: 8, marginBottom: 24, fontSize: 14 }}>
          {error}
        </div>
      )}

      {view === "list" && (
        <>
          <Dashboard trades={trades} />
          <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", marginTop: 24, overflow: "hidden" }}>
            <div style={{ padding: "16px 24px", borderBottom: "1px solid #2d3748" }}>
              <h2 style={{ fontSize: 16, fontWeight: 600, color: "#e2e8f0" }}>Trade History</h2>
            </div>
            <div style={{ padding: "0 8px 8px" }}>
              {loading ? (
                <div style={{ textAlign: "center", padding: "40px 0", color: "#64748b" }}>Loading…</div>
              ) : (
                <TradeList trades={trades} onEdit={handleEdit} onDelete={handleDelete} />
              )}
            </div>
          </div>
        </>
      )}

      {(view === "add" || view === "edit") && (
        <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", padding: 24 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20, color: "#e2e8f0" }}>
            {view === "edit" ? "Edit Trade" : "Add New Trade"}
          </h2>
          <TradeForm
            initial={editing ?? undefined}
            onSave={handleSave}
            onCancel={() => { setView("list"); setEditing(null); }}
          />
        </div>
      )}
    </div>
  );
}
