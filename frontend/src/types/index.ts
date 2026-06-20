// ── Trades ────────────────────────────────────────────────────

export type TradeSide = "long" | "short";
export type TradeStatus = "open" | "closed";

export interface Trade {
  id: number;
  symbol: string;
  side: TradeSide;
  status: TradeStatus;
  quantity: number;
  entry_price: number;
  exit_price: number | null;
  entry_date: string;
  exit_date: string | null;
  pnl: number | null;
  notes: string | null;
  analysis_run_id: string | null;
}

export interface TradePayload {
  symbol: string;
  side: TradeSide;
  quantity: number;
  entry_price: number;
  entry_date: string;
  exit_price?: number | null;
  exit_date?: string | null;
  notes?: string | null;
  analysis_run_id?: string | null;
}

export interface PortfolioStats {
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  total_pnl: number;
  win_rate: number;
  avg_pnl: number;
  best_trade: number;
  worst_trade: number;
}

// ── Analysis ──────────────────────────────────────────────────

export type Signal = "BUY" | "OVERWEIGHT" | "HOLD" | "UNDERWEIGHT" | "SELL";

export type AnalystKey = "market" | "social" | "news" | "fundamentals";

export type LLMProvider =
  | "openai" | "anthropic" | "google" | "xai" | "deepseek"
  | "dashscope" | "zhipu" | "minimax" | "openrouter"
  | "ollama" | "bedrock" | "azure";

export interface RunCreate {
  ticker: string;
  trade_date: string;
  analysts: AnalystKey[];
  llm_provider: LLMProvider;
  deep_think_llm: string;
  quick_think_llm: string;
  max_debate_rounds: number;
  max_risk_discuss_rounds: number;
  analyst_concurrency: number;
  output_language: string;
  temperature?: number | null;
  backend_url?: string | null;
  benchmark_ticker?: string | null;
  checkpoint_enabled: boolean;
}

export interface RunOut {
  run_id: string;
  ticker: string;
  trade_date: string;
  status: "running" | "complete" | "error";
  signal: Signal | null;
  created_at: string;
}

export interface AnalysisResult {
  signal: Signal | null;
  market_report: string | null;
  fundamentals_report: string | null;
  sentiment_report: string | Record<string, unknown> | null;
  news_report: string | null;
  trader_investment_plan: string | Record<string, unknown> | null;
  final_trade_decision: string | Record<string, unknown> | null;
  investment_debate: string | null;
  risk_debate: string | null;
}

export interface RunDetail extends RunOut {
  analysts: string;
  config_snapshot: string | null;
  result_json: string | null;
  error: string | null;
}

// ── SSE Events ────────────────────────────────────────────────

export interface SSEEvent {
  type:
    | "analysis_started"
    | "agent_start"
    | "agent_end"
    | "tool_call"
    | "tool_result"
    | "llm_start"
    | "llm_error"
    | "tool_error"
    | "complete"
    | "error"
    | "heartbeat";
  ts?: string;
  agent?: string;
  tool?: string;
  model?: string;
  input?: string;
  preview?: string;
  result?: AnalysisResult;
  message?: string;
  ticker?: string;
  date?: string;
  error?: string;
}

// ── Memory ────────────────────────────────────────────────────

export interface MemoryEntry {
  ticker?: string;
  trade_date?: string;
  decision?: string;
  signal?: string;
  raw_return?: number | null;
  alpha_return?: number | null;
  reflection?: string | null;
  timestamp?: string;
  [key: string]: unknown;
}

// ── Config ────────────────────────────────────────────────────

export interface AppConfig {
  openai_api_key: string | null;
  anthropic_api_key: string | null;
  google_api_key: string | null;
  xai_api_key: string | null;
  deepseek_api_key: string | null;
  dashscope_api_key: string | null;
  fred_api_key: string | null;
  default_llm_provider: string;
  default_deep_think_llm: string;
  default_quick_think_llm: string;
}
