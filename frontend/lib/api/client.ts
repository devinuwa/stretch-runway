/**
 * Client selector: mock layer (fixtures) vs real backend.
 *
 * NEXT_PUBLIC_MOCK=1  -> mock layer over frontend/mocks/*.json (no backend)
 * otherwise           -> real FastAPI at NEXT_PUBLIC_API_BASE (default 127.0.0.1:8000)
 */
import { httpApi } from "./http";
import { mockApi } from "./mock";
import type { StretchApi } from "./types";

export const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";

export const api: StretchApi = MOCK ? mockApi : httpApi;
