import type { AnalysisResult } from "../types";

interface AnalysisExport {
  ticker: string;
  tradeDate: string;
  result: AnalysisResult;
}

const SIGNAL_COLORS: Record<string, string> = {
  BUY: "#16a34a",
  OVERWEIGHT: "#2563eb",
  HOLD: "#d97706",
  UNDERWEIGHT: "#ea580c",
  SELL: "#dc2626",
};

const SECTIONS = [
  { label: "Portfolio Manager Decision", key: "final_trade_decision" as keyof AnalysisResult },
  { label: "Trader's Investment Plan", key: "trader_investment_plan" as keyof AnalysisResult },
  { label: "Bull vs Bear Research Debate", key: "investment_debate" as keyof AnalysisResult },
  { label: "Risk Analysis Debate", key: "risk_debate" as keyof AnalysisResult },
  { label: "Technical Analysis Report", key: "market_report" as keyof AnalysisResult },
  { label: "News Analysis Report", key: "news_report" as keyof AnalysisResult },
  { label: "Sentiment Analysis Report", key: "sentiment_report" as keyof AnalysisResult },
  { label: "Fundamentals Report", key: "fundamentals_report" as keyof AnalysisResult },
];

// Detect Python object repr strings like "signal='HOLD' size_fraction=0.0 ..."
function isPythonRepr(s: string): boolean {
  return /^\w+=('.*?'|\d[\d.]*|None|True|False)/.test(s.trim());
}

function toText(v: unknown): string {
  if (!v) return "";
  if (typeof v === "string") {
    if (isPythonRepr(v)) return "";
    return v;
  }
  if (typeof v === "object") {
    const obj = v as Record<string, unknown>;
    // Try common text fields on structured objects
    for (const key of ["content", "text", "report", "decision", "plan", "summary"]) {
      if (typeof obj[key] === "string") return obj[key] as string;
    }
    return JSON.stringify(v, null, 2);
  }
  return String(v);
}

// Minimal markdown → HTML renderer
function md(text: string): string {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const lines = text.split("\n");
  const out: string[] = [];
  let inTable = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    // Table row
    if (/^\|/.test(line)) {
      const cells = line.split("|").slice(1, -1).map((c) => c.trim());
      const isSep = cells.every((c) => /^[-: ]+$/.test(c));
      if (isSep) { continue; }
      if (!inTable) {
        out.push('<table><thead><tr>');
        cells.forEach((c) => out.push(`<th>${md(c)}</th>`));
        out.push('</tr></thead><tbody>');
        inTable = true;
        continue;
      }
      out.push('<tr>');
      cells.forEach((c) => out.push(`<td>${md(c)}</td>`));
      out.push('</tr>');
      continue;
    }
    if (inTable) { out.push('</tbody></table>'); inTable = false; }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) { out.push('<hr>'); continue; }

    // ATX headers
    const hm = line.match(/^(#{1,4})\s+(.*)/);
    if (hm) {
      const level = Math.min(hm[1].length + 2, 6);
      out.push(`<h${level}>${md(hm[2])}</h${level}>`);
      continue;
    }

    // Unordered list
    const ulm = line.match(/^[\*\-]\s+(.*)/);
    if (ulm) { out.push(`<li>${md(ulm[1])}</li>`); continue; }

    // Numbered list
    const olm = line.match(/^\d+\.\s+(.*)/);
    if (olm) { out.push(`<li>${md(olm[1])}</li>`); continue; }

    // Blank line → paragraph break
    if (line.trim() === "") { out.push('<br>'); continue; }

    // Inline: bold+italic, bold, italic, code
    let l = esc(line);
    l = l.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    l = l.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    l = l.replace(/\*(.*?)\*/g, '<em>$1</em>');
    l = l.replace(/`([^`]+)`/g, '<code>$1</code>');
    out.push(`<p>${l}</p>`);
  }

  if (inTable) out.push('</tbody></table>');
  return out.join('\n');
}

function renderAnalysis(a: AnalysisExport): string {
  const signalColor = a.result.signal ? (SIGNAL_COLORS[a.result.signal] ?? "#64748b") : "#64748b";

  const sections = SECTIONS.map(({ label, key }) => {
    const text = toText(a.result[key]);
    if (!text) return "";
    return `
      <div class="section">
        <h3 class="section-title">${label}</h3>
        <div class="section-body">${md(text)}</div>
      </div>`;
  }).join("");

  return `
    <div class="analysis">
      <div class="header">
        <div class="header-left">
          <div class="ticker">${a.ticker}</div>
          <div class="date">Analysis date: ${a.tradeDate}</div>
        </div>
        <div class="signal" style="background:${signalColor}">
          ${a.result.signal ?? "—"}
        </div>
      </div>
      ${sections}
    </div>`;
}

export function exportAnalysesToPdf(analyses: AnalysisExport[]): void {
  const title =
    analyses.length === 1
      ? `${analyses[0].ticker} ${analyses[0].tradeDate} Analysis`
      : `TradingAgents Analysis Report — ${new Date().toLocaleDateString()}`;

  const body = analyses.map(renderAnalysis).join('<div class="page-break"></div>');

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>${title}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 10pt;
    color: #1e293b;
    background: #fff;
  }
  .analysis { padding: 20mm 18mm; }
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 16px;
    margin-bottom: 20px;
  }
  .ticker { font-size: 24pt; font-weight: 800; color: #0f172a; }
  .date { font-size: 10pt; color: #64748b; margin-top: 4px; }
  .signal {
    font-size: 14pt; font-weight: 800; color: #fff;
    padding: 8px 20px; border-radius: 8px; letter-spacing: 0.05em;
  }
  .section { margin-bottom: 18px; }
  .section-title {
    font-size: 11pt; font-weight: 700; color: #1d4ed8;
    border-left: 3px solid #1d4ed8; padding-left: 8px; margin-bottom: 8px;
  }
  .section-body {
    font-size: 9pt; line-height: 1.7; color: #374151;
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 6px; padding: 10px 14px;
    word-break: break-word;
  }
  .section-body p { margin-bottom: 6px; }
  .section-body h4, .section-body h5, .section-body h6 {
    font-size: 9.5pt; font-weight: 700; color: #1e293b;
    margin: 8px 0 4px;
  }
  .section-body strong { font-weight: 700; }
  .section-body em { font-style: italic; }
  .section-body code {
    background: #e2e8f0; padding: 1px 4px; border-radius: 3px;
    font-family: monospace; font-size: 8.5pt;
  }
  .section-body li { margin-left: 16px; margin-bottom: 3px; list-style: disc; }
  .section-body hr { border: none; border-top: 1px solid #e2e8f0; margin: 8px 0; }
  .section-body table {
    width: 100%; border-collapse: collapse; font-size: 8.5pt; margin: 8px 0;
  }
  .section-body th {
    background: #e2e8f0; font-weight: 700; padding: 4px 8px;
    border: 1px solid #cbd5e1; text-align: left;
  }
  .section-body td { padding: 4px 8px; border: 1px solid #e2e8f0; }
  .section-body tr:nth-child(even) td { background: #f1f5f9; }
  .page-break { page-break-after: always; }
  @media print {
    .analysis { padding: 12mm 15mm; }
    .page-break { page-break-after: always; }
  }
  @page { size: A4; margin: 0; }
</style>
</head>
<body>
${body}
<script>
  window.onload = function() { setTimeout(function() { window.print(); }, 400); };
<\/script>
</body>
</html>`;

  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const win = window.open(url, "_blank");
  if (win) {
    win.onunload = () => URL.revokeObjectURL(url);
  }
}
