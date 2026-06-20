import { api } from "./client";
import type { AppConfig } from "../types";

export const getConfig = () => api.get<AppConfig>("/config").then((r) => r.data);
export const updateConfig = (payload: Partial<AppConfig>) =>
  api.put("/config", payload).then((r) => r.data);
