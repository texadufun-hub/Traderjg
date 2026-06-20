import axios from "axios";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

export const api = axios.create({ baseURL: BASE });

export const sseUrl = (path: string) =>
  `${BASE}${path}`;
