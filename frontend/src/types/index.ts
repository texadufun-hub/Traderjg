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
}

export interface Stats {
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  total_pnl: number;
  win_rate: number;
  avg_pnl: number;
  best_trade: number;
  worst_trade: number;
}
