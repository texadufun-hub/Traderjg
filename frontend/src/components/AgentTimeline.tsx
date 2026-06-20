const AGENTS = [
  "Technical Analyst",
  "Sentiment Analyst",
  "News Analyst",
  "Fundamentals Analyst",
  "Bull Researcher",
  "Bear Researcher",
  "Research Manager",
  "Trader",
  "Aggressive Risk Analyst",
  "Neutral Risk Analyst",
  "Conservative Risk Analyst",
  "Portfolio Manager",
];

type AgentState = "pending" | "active" | "done";

interface Props {
  activeAgent: string | null;
  doneAgents: Set<string>;
  selectedAgents?: string[];
}

const ANALYST_MAP: Record<string, string> = {
  market: "Technical Analyst",
  social: "Sentiment Analyst",
  news: "News Analyst",
  fundamentals: "Fundamentals Analyst",
};

export default function AgentTimeline({ activeAgent, doneAgents, selectedAgents }: Props) {
  const selected = new Set(
    selectedAgents
      ? selectedAgents.map((k) => ANALYST_MAP[k] ?? k)
      : AGENTS,
  );

  const visible = AGENTS.filter((a) => {
    const isAnalyst = Object.values(ANALYST_MAP).includes(a);
    return !isAnalyst || selected.has(a);
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {visible.map((agent, i) => {
        let state: AgentState = "pending";
        if (doneAgents.has(agent)) state = "done";
        else if (activeAgent === agent) state = "active";

        const dotColor =
          state === "done" ? "#4ade80" :
          state === "active" ? "#6366f1" :
          "#2d3748";

        const textColor =
          state === "done" ? "#e2e8f0" :
          state === "active" ? "#c7d2fe" :
          "#475569";

        return (
          <div key={agent} style={{ display: "flex", alignItems: "center", gap: 12, position: "relative" }}>
            {/* connector line */}
            {i < visible.length - 1 && (
              <div style={{
                position: "absolute",
                left: 7,
                top: 20,
                width: 2,
                height: 24,
                background: doneAgents.has(agent) ? "#4ade80" : "#2d3748",
                zIndex: 0,
              }} />
            )}
            {/* dot */}
            <div style={{
              width: 16,
              height: 16,
              borderRadius: "50%",
              background: dotColor,
              flexShrink: 0,
              zIndex: 1,
              boxShadow: state === "active" ? `0 0 0 3px #6366f133` : undefined,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}>
              {state === "done" && (
                <svg width="8" height="8" viewBox="0 0 8 8">
                  <path d="M1 4l2 2 4-4" stroke="#0f1117" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                </svg>
              )}
              {state === "active" && (
                <div style={{
                  width: 6, height: 6, borderRadius: "50%",
                  background: "#fff",
                  animation: "pulse 1s infinite",
                }} />
              )}
            </div>
            <span style={{
              fontSize: 13,
              color: textColor,
              fontWeight: state === "active" ? 600 : 400,
              padding: "4px 0",
            }}>
              {agent}
              {state === "active" && (
                <span style={{ color: "#6366f1", marginLeft: 6, fontSize: 11 }}>running…</span>
              )}
            </span>
          </div>
        );
      })}
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }`}</style>
    </div>
  );
}
