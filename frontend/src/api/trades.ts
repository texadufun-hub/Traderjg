import axios from "axios";
import type { Trade, TradePayload, Stats } from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

const api = axios.create({ baseURL: BASE });

export const getTrades = () => api.get<Trade[]>("/trades").then((r) => r.data);
export const getTrade = (id: number) => api.get<Trade>(`/trades/${id}`).then((r) => r.data);
export const createTrade = (payload: TradePayload) =>
  api.post<Trade>("/trades", payload).then((r) => r.data);
export const updateTrade = (id: number, payload: Partial<TradePayload>) =>
  api.put<Trade>(`/trades/${id}`, payload).then((r) => r.data);
export const deleteTrade = (id: number) => api.delete(`/trades/${id}`);
export const getStats = () => api.get<Stats>("/stats").then((r) => r.data);
