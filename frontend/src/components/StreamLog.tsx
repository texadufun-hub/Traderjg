import { useEffect, useRef } from "react";
import type { SSEEvent } from "../types";

interface Props {
  events: SSEEvent[];
}

const EVENT_ICON: Record<string, string> = {
  analysis_started: "🚀",
  agent_start: "🤖",
  agent_end: "✅",
  tool_call: "🔧",
  tool_result: "📊",
  llm_start: "💭",
  llm_error: "❌",
  tool_error: "❌",
  complete: "🎯",
  error: "💥",
  heartbeat: "💓",
};

const EVENT_COLOR: Record<string, string> = {
  analysis_started: "#6366f1",
  agent_start: "#818cf8",
  agent_end: "#4ade80",
  tool_call: "#fbbf24",
  tool_result: "#94a3b8",
  llm_start: "#a78bfa",
  llm_error: "#f87171",
  tool_error: "#f87171",
  complete: "#4ade80",
  error: "#ef4444",
  heartbeat: "#374151",
};

function formatEvent(e: SSEEvent): string {
  switch (e.type) {
    case "analysis_started": return `Starting analysis for ${e.ticker} on ${e.date}`;
    case "agent_start": return `${e.agent} — started`;
    case "agent_end": return `${e.agent} — finished`;
    case "tool_call": return `[${e.tool}] ${e.input?.slice(0, 120) ?? ""}`;
    case "tool_result": return `↳ ${e.preview?.slice(0, 150) ?? ""}`;
    case "llm_start": return `LLM call — ${e.model ?? "model"}`;
    case "llm_error": return `LLM error: ${e.error}`;
    case "tool_error": return `Tool error: ${e.error}`;
    case "complete": return "Analysis complete";
    case "error": return `Error: ${e.message}`;
    case "heartbeat": return "…";
    default: return e.type;
  }
}

export default function StreamLog({ events }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const visible = events.filter((e) => e.type !== "heartbeat");

  return (
    <div style={{
      background: "#0a0d14",
      borderRadius: 8,
      padding: "12px 16px",
      fontFamily: "monospace",
      fontSize: 12,
      color: "#94a3b8",
      height: 320,
      overflowY: "auto",
      border: "1px solid #1e2433",
    }}>
      {visible.length === 0 && (
        <span style={{ color: "#374151" }}>Waiting for agents to start…</span>
      )}
      {visible.map((e, i) => (
        <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4, alignItems: "flex-start" }}>
          <span>{EVENT_ICON[e.type] ?? "·"}</span>
          <span style={{ color: "#374151", flexShrink: 0 }}>
            {e.ts ? new Date(e.ts).toLocaleTimeString() : ""}
          </span>
          <span style={{ color: EVENT_COLOR[e.type] ?? "#94a3b8", wordBreak: "break-all" }}>
            {formatEvent(e)}
          </span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
