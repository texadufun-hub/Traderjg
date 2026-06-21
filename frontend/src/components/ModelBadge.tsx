interface Props {
  provider: string | null;
  model: string | null;
}

const PROVIDER_LABEL: Record<string, { label: string; color: string; bg: string }> = {
  google_genai: { label: "Gemini", color: "#1e40af", bg: "#dbeafe" },
  openai:       { label: "OpenAI", color: "#065f46", bg: "#d1fae5" },
  anthropic:    { label: "Claude", color: "#6b21a8", bg: "#f3e8ff" },
  ollama:       { label: "Local",  color: "#92400e", bg: "#fef3c7" },
  xai:          { label: "Grok",   color: "#1e293b", bg: "#e2e8f0" },
  openrouter:   { label: "OpenRouter", color: "#374151", bg: "#f3f4f6" },
};

export default function ModelBadge({ provider, model }: Props) {
  if (!provider) return null;
  const meta = PROVIDER_LABEL[provider] ?? { label: provider, color: "#374151", bg: "#f3f4f6" };
  const modelShort = model ? model.split(":")[0] : "";

  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 600,
      background: meta.bg, color: meta.color,
      border: `1px solid ${meta.color}22`,
    }}>
      {meta.label}
      {modelShort && (
        <span style={{ fontWeight: 400, opacity: 0.75 }}>{modelShort}</span>
      )}
    </span>
  );
}
