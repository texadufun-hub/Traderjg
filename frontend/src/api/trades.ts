import { api } from "./client";
import type { Trade, TradePayload, PortfolioStats } from "../types";

export const listTrades = () => api.get<Trade[]>("/trades").then((r) => r.data);
export const getTrade = (id: number) => api.get<Trade>(`/trades/${id}`).then((r) => r.data);
export const createTrade = (p: TradePayload) => api.post<Trade>("/trades", p).then((r) => r.data);
export const updateTrade = (id: number, p: Partial<TradePayload>) =>
  api.put<Trade>(`/trades/${id}`, p).then((r) => r.data);
export const deleteTrade = (id: number) => api.delete(`/trades/${id}`);
export const getStats = () => api.get<PortfolioStats>("/stats").then((r) => r.data);
