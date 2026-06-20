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

export const getAgentOrder = () =>
  api.get<{ agents: string[] }>("/agents/order").then((r) => r.data.agents);
