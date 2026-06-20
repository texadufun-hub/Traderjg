import { api } from "./client";
import type { MemoryEntry } from "../types";

export const getMemory = () => api.get<MemoryEntry[]>("/memory").then((r) => r.data);
