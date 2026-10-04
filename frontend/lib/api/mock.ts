/**
 * Mock layer — serves JSON fixtures copied into frontend/mocks/ when
 * NEXT_PUBLIC_MOCK=1. No backend required.
 *
 * Mock behaviour notes:
 * - Mutations live in module memory only (never localStorage/IndexedDB).
 * - Fixtures carry "synthetic": true; the mock keeps it on every situation.
 * - /api/runway/scenarios and /api/ask/direct recompute from the stored
 *   situation with the same deterministic rules as the fixtures
 *   (lib/api/engine.ts), so edits in the confirmation card are honoured.
 * - /api/ask/plan, /execute, /narrate serve the fixtures verbatim, which makes
 *   the 6-step ribbon advance from real staged responses, not a timer.
 * - Regenerate the fixture copies with:  node scripts/gen-fixtures.mjs
 */
import { DEMO_SITUATION } from "./demo-situation";
import {
  affordability,
  daysBetween,
  EngineError,
  essentialsReserve,
  presetScenarios,
  resolveDateExpr,
  runway,
  safeSpend,
} from "./engine";
import { numberRegistry } from "./numbers";
import extractDemo from "../../mocks/extract_demo.json";
import askDemoPlan from "../../mocks/ask_demo_plan.json";
import askDemoExecute from "../../mocks/ask_demo_execute.json";
import askDemoNarrate from "../../mocks/ask_demo_narrate.json";
import type {
  DirectResponse,
  DirectToolName,
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
  ToolResult,
  TraceStep,
} from "./types";
import { ApiError } from "./types";

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
  const asOf = body.as_of ?? DEMO_SITUATION.as_of;
  const convert = (amount: number, period: ManualSetupRequest["essentials"]["period"]) =>
    period === "week" ? Math.ceil(amount / 7) : period === "month" ? Math.ceil(amount / 30) : amount;
  const draft: SituationDraft = {
    as_of: asOf,
    balance: { value: body.balance, grounded: true, source_text: null },
    essentials_per_day: {
      value: convert(body.essentials.amount, body.essentials.period),
      grounded: true,
      source_text: null,
      converted_from:
        body.essentials.period === "day"
          ? null
          : { amount: body.essentials.amount, period: body.essentials.period },
    },
    inflows: body.inflows.map((i, idx) => ({
      id: `inflow_${idx + 1}`,
      label: i.label,
      expected_amount: { value: i.expected_amount, grounded: true, source_text: null },
      expected_date: {
        value: resolveDateExpr(i.date_expr, asOf),
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
        value: resolveDateExpr(c.date_expr, asOf),
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
  for (const i of situation.inflows) {
    if (daysBetween(situation.as_of, i.expected_date) < 0) {
      throw new ApiError(422, { code: "invalid_date", message: `inflow ${i.id} is before as_of`, fallback: null });
    }
  }
  for (const c of situation.commitments) {
    if (daysBetween(situation.as_of, c.due_date) < 0) {
      throw new ApiError(422, { code: "invalid_date", message: `commitment ${c.id} is before as_of`, fallback: null });
    }
  }
  stored = { ...situation, synthetic: situation.synthetic ?? false };
  return stored;
}

async function getSituation(): Promise<Situation> {
  return structuredClone(requireSituation());
}

async function loadDemo(): Promise<Situation> {
  stored = structuredClone(DEMO_SITUATION);
  return structuredClone(stored);
}

async function scenarios(): Promise<ScenariosResponse> {
  const sit = requireSituation();
  const presets = presetScenarios();
  return {
    results: presets.map((scenario) => ({ scenario, result: runway(sit, scenario) })),
    safe_spend: safeSpend(sit, presets[0]),
    reserve: essentialsReserve(sit, presets[0]),
    assumptions: [
      "Presets are labelled defaults, not predictions of when money will arrive.",
      "Essentials are subtracted every day, starting today.",
      "Amounts are whole currency units.",
    ],
  };
}

async function askPlan(_question: string): Promise<PlanResponse> {
  return structuredClone(askDemoPlan) as PlanResponse;
}

async function askExecute(plan: Plan): Promise<ExecuteResponse> {
  const fixture = structuredClone(askDemoExecute) as ExecuteResponse;
  if ("tool_calls" in plan) {
    for (const tc of plan.tool_calls) {
      if (!fixture.results.some((r: ToolResult) => r.tool === tc.tool)) {
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
  const sit = requireSituation();
  const scenario = presetScenarios()[0];
  let result: object | null = null;
  try {
    if (tool === "compute_runway") result = runway(sit, scenario);
    else if (tool === "safe_daily_spend") result = safeSpend(sit, scenario);
    else if (tool === "essentials_reserve") result = essentialsReserve(sit, scenario);
    else if (tool === "check_affordability") {
      const a = args as { label?: string; amount?: number };
      if (typeof a.amount !== "number" || a.amount <= 0) {
        throw new ApiError(422, { code: "out_of_bounds", message: "amount must be a positive integer", fallback: null });
      }
      result = affordability(sit, scenario, {
        label: a.label ?? "expense",
        amount: Math.floor(a.amount),
        date_expr: null,
      });
    } else {
      throw new ApiError(422, { code: "invalid_request", message: `unknown tool: ${tool}`, fallback: null });
    }
  } catch (e) {
    if (e instanceof ApiError) throw e;
    const code = e instanceof EngineError ? e.code : "internal";
    throw new ApiError(422, { code, message: e instanceof Error ? e.message : "engine error", fallback: null });
  }
  return {
    results: [{ tool, args, ok: true, error: null, result, numbers: numberRegistry(tool, result) }],
  };
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
