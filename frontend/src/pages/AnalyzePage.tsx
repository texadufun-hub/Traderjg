import { useEffect, useRef, useState } from "react";
import { createRun } from "../api/analyses";
import { sseUrl } from "../api/client";
import type { RunCreate, SSEEvent, AnalysisResult, AnalystKey, LLMProvider } from "../types";
import AgentTimeline from "../components/AgentTimeline";
import StreamLog from "../components/StreamLog";
import AnalysisResultView from "../components/AnalysisResult";
import { exportAnalysesToPdf } from "../utils/exportPdf";
import ModelBadge from "../components/ModelBadge";

const inp: React.CSSProperties = {
  background: "#0f1117", border: "1px solid #2d3748", borderRadius: 8,
  color: "#e2e8f0", padding: "8px 12px", fontSize: 14, width: "100%",
};
const lbl: React.CSSProperties = { fontSize: 12, color: "#94a3b8", display: "block", marginBottom: 4 };
const card: React.CSSProperties = {
  background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", padding: 20, marginBottom: 16,
};

const LLM_PROVIDERS: { value: LLMProvider; label: string }[] = [
  { value: "google_genai", label: "Google (Gemini)" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic (Claude)" },
  { value: "xai", label: "xAI (Grok)" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "ollama", label: "Ollama (local)" },
  { value: "huggingface", label: "HuggingFace" },
  { value: "litellm", label: "LiteLLM" },
];

const ANALYST_OPTIONS: { key: AnalystKey; label: string; desc: string }[] = [
  { key: "market", label: "Technical Analyst", desc: "MACD, RSI, price patterns" },
  { key: "social", label: "Sentiment Analyst", desc: "Reddit, StockTwits, social media" },
  { key: "news", label: "News Analyst", desc: "Macro indicators, global events" },
  { key: "fundamentals", label: "Fundamentals Analyst", desc: "Financials, earnings, valuation" },
];

const LANGUAGES = ["English", "Chinese", "Japanese", "Korean", "French", "Spanish", "German"];

type Phase = "form" | "streaming" | "done" | "error";

export default function AnalyzePage() {
  const today = new Date().toISOString().slice(0, 10);

  const [form, setForm] = useState<RunCreate>({
    ticker: "NVDA",
    trade_date: today,
    analysts: ["market", "social", "news", "fundamentals"],
    llm_provider: "ollama",
    deep_think_llm: "qwen3:8b",
    quick_think_llm: "qwen3:8b",
    max_debate_rounds: 1,
    max_risk_discuss_rounds: 1,
    analyst_concurrency: 1,
    output_language: "English",
    temperature: 0.1,
    backend_url: "http://10.0.0.189:11434",
    benchmark_ticker: null,
    checkpoint_enabled: false,
  });

  const [phase, setPhase] = useState<Phase>("form");
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [doneAgents, setDoneAgents] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const set = <K extends keyof RunCreate>(k: K, v: RunCreate[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const toggleAnalyst = (key: AnalystKey) =>
    setForm((f) => ({
      ...f,
      analysts: f.analysts.includes(key)
        ? f.analysts.filter((a) => a !== key)
        : [...f.analysts, key],
    }));

  const startRun = async () => {
    setPhase("streaming");
    setEvents([]);
    setActiveAgent(null);
    setDoneAgents(new Set());
    setResult(null);
    setErrorMsg(null);

    try {
      const run = await createRun(form);
      setRunId(run.run_id);
      const url = sseUrl(`/runs/${run.run_id}/stream`);
      const es = new EventSource(url);
      esRef.current = es;

      es.onmessage = (e) => {
        const event: SSEEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, event]);

        if (event.type === "agent_start" && event.agent) {
          setActiveAgent(event.agent);
        }
        if (event.type === "agent_end" && event.agent) {
          setDoneAgents((prev) => new Set([...prev, event.agent!]));
          setActiveAgent(null);
        }
        if (event.type === "complete") {
          setResult(event.result ?? null);
          setActiveAgent(null);
          setPhase("done");
          es.close();
        }
        if (event.type === "error") {
          setErrorMsg(event.message ?? "Unknown error");
          setPhase("error");
          es.close();
        }
      };

      es.onerror = () => {
        setErrorMsg("Connection lost. The analysis may still be running.");
        setPhase("error");
        es.close();
      };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to start analysis";
      setErrorMsg(msg);
      setPhase("error");
    }
  };

  useEffect(() => () => esRef.current?.close(), []);

  const reset = () => {
    esRef.current?.close();
    setPhase("form");
    setEvents([]);
    setActiveAgent(null);
    setDoneAgents(new Set());
    setResult(null);
    setErrorMsg(null);
    setRunId(null);
  };

  if (phase === "form") {
    return (
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#e2e8f0", marginBottom: 20 }}>
          New Analysis
        </h2>

        <div style={card}>
          <p style={{ ...lbl, marginBottom: 12, fontSize: 13, color: "#6366f1" }}>Target</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <label style={lbl}>Ticker / Symbol</label>
              <input style={inp} value={form.ticker} onChange={(e) => set("ticker", e.target.value.toUpperCase())}
                placeholder="AAPL, NVDA, 0700.HK, BTC-USD" />
            </div>
            <div>
              <label style={lbl}>Analysis Date</label>
              <input style={inp} type="date" value={form.trade_date}
                onChange={(e) => set("trade_date", e.target.value)} />
            </div>
          </div>
        </div>

        <div style={card}>
          <p style={{ ...lbl, marginBottom: 12, fontSize: 13, color: "#6366f1" }}>Analyst Team</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {ANALYST_OPTIONS.map(({ key, label, desc }) => {
              const on = form.analysts.includes(key);
              return (
                <div key={key} onClick={() => toggleAnalyst(key)} style={{
                  padding: "10px 14px", borderRadius: 8, cursor: "pointer",
                  border: `1px solid ${on ? "#6366f1" : "#2d3748"}`,
                  background: on ? "#1e1b4b" : "transparent",
                  transition: "all 0.15s",
                }}>
                  <div style={{ fontWeight: 600, color: on ? "#c7d2fe" : "#94a3b8", fontSize: 13 }}>{label}</div>
                  <div style={{ color: "#475569", fontSize: 11, marginTop: 2 }}>{desc}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div style={card}>
          <p style={{ ...lbl, marginBottom: 12, fontSize: 13, color: "#6366f1" }}>LLM Configuration</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={lbl}>Provider</label>
              <select style={inp} value={form.llm_provider}
                onChange={(e) => set("llm_provider", e.target.value as LLMProvider)}>
                {LLM_PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label style={lbl}>Deep Think Model</label>
              <input style={inp} value={form.deep_think_llm}
                onChange={(e) => set("deep_think_llm", e.target.value)}
                placeholder="gpt-4o, claude-opus-4-8…" />
            </div>
            <div>
              <label style={lbl}>Quick Think Model</label>
              <input style={inp} value={form.quick_think_llm}
                onChange={(e) => set("quick_think_llm", e.target.value)}
                placeholder="gpt-4o-mini, claude-haiku…" />
            </div>
            {form.llm_provider === "ollama" && (
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={lbl}>Backend URL</label>
                <input style={inp} value={form.backend_url ?? ""}
                  onChange={(e) => set("backend_url", e.target.value || null)}
                  placeholder="http://localhost:11434/v1" />
              </div>
            )}
            <div>
              <label style={lbl}>Temperature (optional)</label>
              <input style={inp} type="number" step="0.1" min="0" max="2"
                value={form.temperature ?? ""}
                onChange={(e) => set("temperature", e.target.value ? parseFloat(e.target.value) : null)}
                placeholder="default" />
            </div>
            <div>
              <label style={lbl}>Output Language</label>
              <select style={inp} value={form.output_language}
                onChange={(e) => set("output_language", e.target.value)}>
                {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
              </select>
            </div>
          </div>
        </div>

        <div style={card}>
          <p style={{ ...lbl, marginBottom: 12, fontSize: 13, color: "#6366f1" }}>Research Depth</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16 }}>
            <div>
              <label style={lbl}>Bull/Bear Debate Rounds</label>
              <input style={inp} type="number" min={1} max={5} value={form.max_debate_rounds}
                onChange={(e) => set("max_debate_rounds", parseInt(e.target.value))} />
            </div>
            <div>
              <label style={lbl}>Risk Discussion Rounds</label>
              <input style={inp} type="number" min={1} max={5} value={form.max_risk_discuss_rounds}
                onChange={(e) => set("max_risk_discuss_rounds", parseInt(e.target.value))} />
            </div>
            <div>
              <label style={lbl}>Analyst Concurrency</label>
              <input style={inp} type="number" min={1} max={4} value={form.analyst_concurrency}
                onChange={(e) => set("analyst_concurrency", parseInt(e.target.value))} />
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
            <div>
              <label style={lbl}>Benchmark Ticker (optional)</label>
              <input style={inp} value={form.benchmark_ticker ?? ""}
                onChange={(e) => set("benchmark_ticker", e.target.value || null)}
                placeholder="SPY (auto-detected)" />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, paddingTop: 22 }}>
              <input type="checkbox" id="chk" checked={form.checkpoint_enabled}
                onChange={(e) => set("checkpoint_enabled", e.target.checked)}
                style={{ width: 16, height: 16, cursor: "pointer" }} />
              <label htmlFor="chk" style={{ color: "#94a3b8", fontSize: 13, cursor: "pointer" }}>
                Enable checkpoint resume
              </label>
            </div>
          </div>
        </div>

        <button onClick={startRun} disabled={form.analysts.length === 0}
          style={{
            width: "100%", padding: "14px", borderRadius: 10, border: "none",
            background: form.analysts.length === 0 ? "#374151" : "#6366f1",
            color: "#fff", fontWeight: 700, fontSize: 16, cursor: "pointer",
          }}>
          Run Analysis →
        </button>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <div style={{ background: "#450a0a", borderRadius: 12, padding: 24, color: "#fca5a5", marginBottom: 20 }}>
          <strong>Analysis failed</strong>
          <pre style={{ marginTop: 10, fontSize: 12, whiteSpace: "pre-wrap", color: "#fca5a5" }}>{errorMsg}</pre>
        </div>
        <button onClick={reset} style={{ padding: "10px 24px", borderRadius: 8, border: "1px solid #2d3748", background: "transparent", color: "#94a3b8", cursor: "pointer" }}>
          ← Try Again
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
        {phase === "streaming" && (
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#6366f1", animation: "pulse 1s infinite" }} />
        )}
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0" }}>
          {phase === "streaming"
            ? `Analyzing ${form.ticker} · ${form.trade_date}`
            : `Result — ${form.ticker}`}
        </h2>
        <ModelBadge provider={form.llm_provider} model={form.deep_think_llm} />
        {phase === "done" && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            {result && (
              <button
                onClick={() => exportAnalysesToPdf([{ ticker: form.ticker, tradeDate: form.trade_date, result }])}
                style={{ padding: "6px 16px", borderRadius: 8, border: "1px solid #6366f1", background: "transparent", color: "#818cf8", cursor: "pointer", fontSize: 13 }}
              >
                Export PDF
              </button>
            )}
            <button onClick={reset} style={{ padding: "6px 16px", borderRadius: 8, border: "1px solid #2d3748", background: "transparent", color: "#94a3b8", cursor: "pointer", fontSize: 13 }}>
              + New Analysis
            </button>
          </div>
        )}
      </div>

      {phase === "done" && result ? (
        <AnalysisResultView result={result} ticker={form.ticker} tradeDate={form.trade_date} />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 20 }}>
          <div style={{ background: "#1e2433", borderRadius: 12, border: "1px solid #2d3748", padding: 16 }}>
            <p style={{ fontSize: 11, color: "#64748b", marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Agent Pipeline
            </p>
            <AgentTimeline
              activeAgent={activeAgent}
              doneAgents={doneAgents}
              selectedAgents={form.analysts}
            />
          </div>
          <div>
            <StreamLog events={events} />
            {runId && (
              <p style={{ color: "#374151", fontSize: 11, marginTop: 8 }}>run_id: {runId}</p>
            )}
          </div>
        </div>
      )}

      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }`}</style>
    </div>
  );
}
