import { useState } from "react";
import type { AnalysisResult as Result } from "../types";
import SignalBadge from "./SignalBadge";

interface Props {
  result: Result;
  ticker: string;
  tradeDate: string;
}

const section: React.CSSProperties = {
  background: "#1e2433",
  borderRadius: 10,
  border: "1px solid #2d3748",
  marginBottom: 12,
  overflow: "hidden",
};

const sectionHead: React.CSSProperties = {
  padding: "12px 16px",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  userSelect: "none",
};

const sectionBody: React.CSSProperties = {
  padding: "0 16px 16px",
  color: "#cbd5e1",
  fontSize: 13,
  lineHeight: 1.7,
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};

function toText(v: unknown): string {
  if (!v) return "No data available.";
  if (typeof v === "string") return v;
  return JSON.stringify(v, null, 2);
}

function Section({ title, content, defaultOpen = false }: {
  title: string; content: unknown; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const text = toText(content);
  if (!text || text === "No data available." && !defaultOpen) return null;
  return (
    <div style={section}>
      <div style={sectionHead} onClick={() => setOpen((o) => !o)}>
        <span style={{ fontWeight: 600, color: "#e2e8f0", fontSize: 14 }}>{title}</span>
        <span style={{ color: "#64748b", fontSize: 18, lineHeight: 1 }}>{open ? "−" : "+"}</span>
      </div>
      {open && <div style={sectionBody}>{text}</div>}
    </div>
  );
}

export default function AnalysisResult({ result, ticker, tradeDate }: Props) {
  return (
    <div>
      {/* Hero signal */}
      <div style={{
        background: "#1e2433",
        borderRadius: 12,
        padding: "24px",
        border: "1px solid #2d3748",
        marginBottom: 20,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: 12,
      }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#e2e8f0" }}>{ticker}</div>
          <div style={{ color: "#64748b", fontSize: 13 }}>Analysis date: {tradeDate}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ color: "#64748b", fontSize: 12, marginBottom: 6 }}>PORTFOLIO MANAGER SIGNAL</div>
          <SignalBadge signal={result.signal} large />
        </div>
      </div>

      <Section title="📊 Portfolio Manager Decision" content={result.final_trade_decision} defaultOpen />
      <Section title="🤝 Trader's Investment Plan" content={result.trader_investment_plan} defaultOpen />
      <Section title="⚖️ Bull vs Bear Research Debate" content={result.investment_debate} />
      <Section title="🛡️ Risk Analysis Debate" content={result.risk_debate} />
      <Section title="📈 Technical Analysis Report" content={result.market_report} />
      <Section title="📰 News Analysis Report" content={result.news_report} />
      <Section title="💬 Sentiment Analysis Report" content={result.sentiment_report} />
      <Section title="📋 Fundamentals Report" content={result.fundamentals_report} />
    </div>
  );
}
