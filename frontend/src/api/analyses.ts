import { api } from "./client";
import type { RunCreate, RunOut, RunDetail } from "../types";

export const createRun = (payload: RunCreate) =>
  api.post<RunOut>("/runs", payload).then((r) => r.data);

export const listRuns = () =>
  api.get<RunOut[]>("/runs").then((r) => r.data);

export const getRun = (runId: string) =>
  api.get<RunDetail>(`/runs/${runId}`).then((r) => r.data);

export const deleteRun = (runId: string) =>
  api.delete(`/runs/${runId}`);

export const getRunLog = (runId: string) =>
  api.get<{ run_id: string; entries: LogEntry[] }>(`/runs/${runId}/log`).then((r) => r.data);

export interface LogEntry {
  ts: string;
  type: string;
  agent?: string;
  node?: string;
  model?: string;
  prompt?: string;
  response?: string;
  tool?: string;
  input?: string;
  output?: string;
  error?: string;
  tokens?: { prompt: number; completion: number; total: number };
  tokens_cumulative?: { prompt: number; completion: number; total: number };
  total_tokens?: { prompt: number; completion: number; total: number };
}

export const getAgentOrder = () =>
  api.get<{ agents: string[] }>("/agents/order").then((r) => r.data.agents);
