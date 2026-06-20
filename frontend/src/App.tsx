import { useEffect, useState } from "react";
import { listTrades } from "./api/trades";
import type { Trade } from "./types";
import Dashboard from "./components/Dashboard";
import AnalyzePage from "./pages/AnalyzePage";
import HistoryPage from "./pages/HistoryPage";
import TradePage from "./pages/TradePage";
import MemoryPage from "./pages/MemoryPage";
import SettingsPage from "./pages/SettingsPage";

type Tab = "dashboard" | "analyze" | "history" | "trades" | "memory" | "settings";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "dashboard", label: "Dashboard", icon: "📊" },
  { id: "analyze", label: "Analyze", icon: "🤖" },
  { id: "history", label: "History", icon: "📜" },
  { id: "trades", label: "Journal", icon: "📓" },
  { id: "memory", label: "Memory", icon: "🧠" },
  { id: "settings", label: "Settings", icon: "⚙️" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [trades, setTrades] = useState<Trade[]>([]);

  useEffect(() => {
    if (tab === "dashboard") {
      listTrades().then(setTrades).catch(console.error);
    }
  }, [tab]);

  return (
    <div style={{ minHeight: "100vh", background: "#0f1117" }}>
      {/* Top nav */}
      <nav style={{
        background: "#0a0d14",
        borderBottom: "1px solid #1e2433",
        padding: "0 24px",
        display: "flex",
        alignItems: "center",
        gap: 0,
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ fontWeight: 800, fontSize: 16, color: "#e2e8f0", marginRight: 32, letterSpacing: "-0.02em", paddingRight: 32, borderRight: "1px solid #1e2433" }}>
          📈 Traderjg
        </div>
        {TABS.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              padding: "16px 14px",
              border: "none",
              background: "transparent",
              color: tab === id ? "#e2e8f0" : "#475569",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: tab === id ? 600 : 400,
              borderBottom: `2px solid ${tab === id ? "#6366f1" : "transparent"}`,
              transition: "all 0.15s",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ fontSize: 14 }}>{icon}</span>
            {label}
          </button>
        ))}
      </nav>

      {/* Page content */}
      <main style={{ padding: "32px 24px" }}>
        {tab === "dashboard" && (
          <div style={{ maxWidth: 1100, margin: "0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
              <div>
                <h1 style={{ fontSize: 24, fontWeight: 800, color: "#e2e8f0" }}>Portfolio Overview</h1>
                <p style={{ color: "#64748b", fontSize: 13, marginTop: 4 }}>
                  Powered by TauricResearch/TradingAgents
                </p>
              </div>
              <button
                onClick={() => setTab("analyze")}
                style={{ padding: "10px 22px", borderRadius: 10, border: "none", background: "#6366f1", color: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 700 }}
              >
                🤖 New Analysis →
              </button>
            </div>
            <Dashboard trades={trades} onTabChange={(t) => setTab(t as Tab)} />
          </div>
        )}
        {tab === "analyze" && <AnalyzePage />}
        {tab === "history" && <HistoryPage />}
        {tab === "trades" && <TradePage />}
        {tab === "memory" && <MemoryPage />}
        {tab === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}
