import { useEffect, useState } from "react";
import { getConfig, updateConfig } from "../api/config";
import type { AppConfig } from "../types";

const inp: React.CSSProperties = {
  background: "#0f1117", border: "1px solid #2d3748", borderRadius: 8,
  color: "#e2e8f0", padding: "8px 12px", fontSize: 14, width: "100%",
};
const lbl: React.CSSProperties = { fontSize: 12, color: "#94a3b8", display: "block", marginBottom: 4 };

const PROVIDERS = [
  { key: "openai_api_key" as keyof AppConfig, label: "OpenAI API Key", env: "OPENAI_API_KEY", placeholder: "sk-…" },
  { key: "anthropic_api_key" as keyof AppConfig, label: "Anthropic API Key", env: "ANTHROPIC_API_KEY", placeholder: "sk-ant-…" },
  { key: "google_api_key" as keyof AppConfig, label: "Google Gemini API Key", env: "GOOGLE_API_KEY", placeholder: "AIza…" },
  { key: "xai_api_key" as keyof AppConfig, label: "xAI (Grok) API Key", env: "XAI_API_KEY", placeholder: "xai-…" },
  { key: "deepseek_api_key" as keyof AppConfig, label: "DeepSeek API Key", env: "DEEPSEEK_API_KEY", placeholder: "" },
  { key: "dashscope_api_key" as keyof AppConfig, label: "DashScope (Qwen) API Key", env: "DASHSCOPE_API_KEY", placeholder: "" },
  { key: "fred_api_key" as keyof AppConfig, label: "FRED API Key (macro data)", env: "FRED_API_KEY", placeholder: "" },
];

export default function SettingsPage() {
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [edits, setEdits] = useState<Partial<AppConfig>>({});
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getConfig().then((c) => { setCfg(c); setLoading(false); });
  }, []);

  const set = (key: keyof AppConfig, value: string) =>
    setEdits((e) => ({ ...e, [key]: value }));

  const save = async () => {
    await updateConfig(edits);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    const updated = await getConfig();
    setCfg(updated);
    setEdits({});
  };

  if (loading) return <div style={{ color: "#64748b", padding: 40 }}>Loading…</div>;

  return (
    <div style={{ maxWidth: 680, margin: "0 auto" }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, color: "#e2e8f0", marginBottom: 8 }}>Settings</h2>
      <p style={{ color: "#64748b", fontSize: 13, marginBottom: 24 }}>
        API keys are stored as environment variables in the backend process.<br />
        They are never logged or returned in plaintext — masked keys show <code style={{ color: "#6366f1" }}>***</code>.
      </p>

      <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", padding: 24, marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0", marginBottom: 16 }}>API Keys</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {PROVIDERS.map(({ key, label, placeholder }) => {
            const current = cfg?.[key] as string | null;
            const editing = edits[key] as string | undefined;
            return (
              <div key={key}>
                <label style={lbl}>
                  {label}
                  {current === "***" && (
                    <span style={{ color: "#4ade80", marginLeft: 6, fontSize: 11 }}>✓ set</span>
                  )}
                </label>
                <input
                  style={inp}
                  type="password"
                  value={editing ?? ""}
                  onChange={(e) => set(key, e.target.value)}
                  placeholder={current === "***" ? "••••••••• (already set)" : placeholder || "Enter API key"}
                />
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", padding: 24, marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0", marginBottom: 16 }}>Default LLM Configuration</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={lbl}>Default Provider</label>
            <input style={inp}
              value={(edits.default_llm_provider ?? cfg?.default_llm_provider) || ""}
              onChange={(e) => set("default_llm_provider", e.target.value)}
              placeholder="openai" />
          </div>
          <div>
            <label style={lbl}>Default Deep Think Model</label>
            <input style={inp}
              value={(edits.default_deep_think_llm ?? cfg?.default_deep_think_llm) || ""}
              onChange={(e) => set("default_deep_think_llm", e.target.value)}
              placeholder="gpt-4o" />
          </div>
          <div>
            <label style={lbl}>Default Quick Think Model</label>
            <input style={inp}
              value={(edits.default_quick_think_llm ?? cfg?.default_quick_think_llm) || ""}
              onChange={(e) => set("default_quick_think_llm", e.target.value)}
              placeholder="gpt-4o-mini" />
          </div>
        </div>
      </div>

      <div style={{ background: "#1e1b4b", borderRadius: 10, border: "1px solid #3730a3", padding: 16, marginBottom: 20 }}>
        <p style={{ fontSize: 13, color: "#a5b4fc" }}>
          <strong>Supported Markets:</strong> US equities (AAPL, NVDA, SPY), crypto (BTC-USD, ETH-USD),
          Hong Kong (0700.HK), Tokyo (7203.T), Shanghai (600519.SS), and any Yahoo Finance ticker.
        </p>
      </div>

      <button onClick={save}
        style={{
          width: "100%", padding: "12px", borderRadius: 10, border: "none",
          background: saved ? "#14532d" : "#6366f1",
          color: "#fff", fontWeight: 700, fontSize: 15, cursor: "pointer",
          transition: "background 0.2s",
        }}>
        {saved ? "✓ Saved!" : "Save Settings"}
      </button>
    </div>
  );
}
