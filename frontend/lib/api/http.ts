/**
 * Typed HTTP client for the real FastAPI backend. Only used when
 * NEXT_PUBLIC_MOCK is not "1" (see client.ts). The base URL comes from
 * NEXT_PUBLIC_API_BASE, defaulting to the local backend at 127.0.0.1:8000.
 */
import {
  ApiError,
  type DirectResponse,
  type DirectToolName,
  type ExecuteResponse,
  type ExtractResponse,
  type HealthResponse,
  type ManualSetupRequest,
  type NarrateResponse,
  type Plan,
  type PlanResponse,
  type ScenariosResponse,
  type Situation,
  type StretchApi,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

const PATHS = {
  health: "/api/health",
  setupExtract: "/api/setup/extract",
  setupManual: "/api/setup/manual",
  situation: "/api/situation",
  situationDemo: "/api/situation/demo",
  scenarios: "/api/runway/scenarios",
  askPlan: "/api/ask/plan",
  askExecute: "/api/ask/execute",
  askNarrate: "/api/ask/narrate",
  askDirect: "/api/ask/direct",
  data: "/api/data",
} as const;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
    credentials: "omit",
  });
  if (!res.ok) {
    let code = "internal";
    let message = res.statusText;
    let fallback: "manual" | null = null;
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        fallback = body.error.fallback ?? null;
      }
    } catch {
      // keep defaults
    }
    throw new ApiError(res.status, { code, message, fallback: fallback ?? null });
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const httpApi: StretchApi = {
  health: () => request<HealthResponse>(PATHS.health),
  extract: (text, as_of) =>
    request<ExtractResponse>(PATHS.setupExtract, {
      method: "POST",
      body: JSON.stringify({ text, ...(as_of ? { as_of } : {}) }),
    }),
  manual: (body: ManualSetupRequest) =>
    request<ExtractResponse>(PATHS.setupManual, { method: "POST", body: JSON.stringify(body) }),
  putSituation: (situation) =>
    request<Situation>(PATHS.situation, { method: "PUT", body: JSON.stringify(situation) }),
  getSituation: () => request<Situation>(PATHS.situation),
  loadDemo: () => request<Situation>(PATHS.situationDemo, { method: "POST" }),
  scenarios: (body) =>
    request<ScenariosResponse>(PATHS.scenarios, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  askPlan: (question) =>
    request<PlanResponse>(PATHS.askPlan, { method: "POST", body: JSON.stringify({ question }) }),
  askExecute: (plan: Plan) =>
    request<ExecuteResponse>(PATHS.askExecute, { method: "POST", body: JSON.stringify({ plan }) }),
  askNarrate: (question, results) =>
    request<NarrateResponse>(PATHS.askNarrate, {
      method: "POST",
      body: JSON.stringify({ question, results }),
    }),
  askDirect: (tool: DirectToolName, args: object) =>
    request<DirectResponse>(PATHS.askDirect, { method: "POST", body: JSON.stringify({ tool, args }) }),
  deleteData: () => request<void>(PATHS.data, { method: "DELETE" }),
};
