import type {
  DirectToolName, DirectResponse,
  ExecuteResponse,
  ExtractResponse,
  HealthResponse,
  ManualSetupRequest,
  NarrateResponse,
  Plan,
  PlanResponse,
  ScenariosResponse,
  Situation,
  SituationDraft,
  TraceStep,
} from "./types";
import { ApiError } from "./types";

import extractDemo from "../../mocks/extract_demo.json";
import askDemoPlan from "../../mocks/ask_demo_plan.json";
import askDemoExecute from "../../mocks/ask_demo_execute.json";
import askDemoNarrate from "../../mocks/ask_demo_narrate.json";

let stored: Situation | null = null;

function requireSituation(): Situation {
  if (!stored) throw new ApiError(409, { code: "no_situation", message: "no situation stored", fallback: null });
  return stored;
}

function traceExtraction(ms = 4): TraceStep[] {
  return [
    {
      step: "extraction",
      label: "extraction (mock fixture)",
      ms,
      payload: { source: "mocks/extract_demo.json", synthetic: true },
    },
  ];
}

async function health(): Promise<HealthResponse> {
  return {
    status: "ok",
    llm: { state: "up", runtime: "mock", model: "stub:demo", detail: null },
    mode: { profile: "demo", persist: false, handover: false },
    hosted: false,
    has_situation: stored !== null,
    version: "0.1.0",
  };
}

async function extract(_text: string, as_of?: string): Promise<ExtractResponse> {
  const draft = structuredClone(extractDemo) as ExtractResponse;
  if (as_of) draft.as_of = as_of;
  return draft;
}

async function manual(body: ManualSetupRequest): Promise<ExtractResponse> {
  const asOf = body.as_of ?? "2026-10-05";
  const draft: SituationDraft = {
    as_of: asOf,
    balance: { value: body.balance, grounded: true, source_text: null },
    essentials_per_day: {
      value: body.essentials.amount,
      grounded: true,
      source_text: null,
      converted_from: body.essentials.period === "day" ? null : { amount: body.essentials.amount, period: body.essentials.period },
    },
    inflows: body.inflows.map((i, idx) => ({
      id: `inflow_${idx + 1}`,
      label: i.label,
      expected_amount: { value: i.expected_amount, grounded: true, source_text: null },
      expected_date: {
        value: null,
        date_expr: i.date_expr,
        grounded: true,
        source_text: null,
      },
      uncertainty_note: i.uncertainty_note,
    })),
    commitments: body.commitments.map((c, idx) => ({
      id: `commit_${idx + 1}`,
      label: c.label,
      amount: { value: c.amount, grounded: true, source_text: null },
      due_date: {
        value: null,
        date_expr: c.date_expr,
        grounded: true,
        source_text: null,
      },
      flexible: c.flexible,
    })),
    missing: [],
    warnings: [],
  };
  return { ...draft, trace: traceExtraction() };
}

async function putSituation(situation: Situation): Promise<Situation> {
  if (!situation.as_of || situation.balance < 0 || situation.essentials_per_day <= 0) {
    throw new ApiError(422, { code: "invalid_request", message: "invalid situation", fallback: null });
  }
  stored = { ...situation, synthetic: situation.synthetic ?? false };
  return stored;
}

async function getSituation(): Promise<Situation> {
  return structuredClone(requireSituation());
}

async function loadDemo(): Promise<Situation> {
  stored = structuredClone(extractDemo as unknown as Situation);
  return structuredClone(stored);
}

async function scenarios(): Promise<ScenariosResponse> {
  throw new ApiError(501, { code: "not_available_in_mock", message: "scenarios not available in mock mode", fallback: null });
}

async function askPlan(_question: string): Promise<PlanResponse> {
  return structuredClone(askDemoPlan) as PlanResponse;
}

async function askExecute(plan: Plan): Promise<ExecuteResponse> {
  const fixture = structuredClone(askDemoExecute) as ExecuteResponse;
  if ("tool_calls" in plan) {
    for (const tc of plan.tool_calls) {
      if (!fixture.results.some((r: any) => r.tool === tc.tool)) {
        throw new ApiError(422, { code: "invalid_request", message: `unknown tool: ${tc.tool}`, fallback: null });
      }
    }
  }
  return fixture;
}

async function askNarrate(_question: string): Promise<NarrateResponse> {
  return structuredClone(askDemoNarrate) as NarrateResponse;
}

async function askDirect(tool: DirectToolName, args: object): Promise<DirectResponse> {
  throw new ApiError(501, { code: "not_available_in_mock", message: "direct tools not available in mock mode", fallback: null });
}

async function deleteData(): Promise<void> {
  stored = null;
}

export const mockApi = {
  health,
  extract,
  manual,
  putSituation,
  getSituation,
  loadDemo,
  scenarios,
  askPlan,
  askExecute,
  askNarrate,
  askDirect,
  deleteData,
};
