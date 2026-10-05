/**
 * Shared types mirroring docs/API_CONTRACT.md §1 "Shared types" and the
 * per-endpoint request/response shapes from §3.
 *
 * Do not change these without flagging a contract deviation to the human.
 */

// ---------- Shared types (API_CONTRACT.md §1) ----------

export type DateExpr =
  | { kind: "iso"; value: string }
  | { kind: "in_days"; n: number }
  | { kind: "day_of_month"; day: number; month_offset: 0 | 1 | null };

export interface Inflow {
  id: string;
  label: string;
  expected_amount: number;
  expected_date: string;
  uncertainty_note: string | null;
}

export interface Commitment {
  id: string;
  label: string;
  amount: number;
  due_date: string;
  flexible: boolean;
}

export interface Situation {
  synthetic?: boolean;
  as_of: string;
  currency: string;
  balance: number;
  essentials_per_day: number;
  inflows: Inflow[];
  commitments: Commitment[];
  /** default 60 */
  horizon_days: number;
  /** default 3 */
  buffer_days: number;
}

export interface InflowAdjustment {
  inflow_id: string | "*";
  delay_days: number | null;
  new_date_expr: DateExpr | null;
  amount_factor: number | null;
  new_amount: number | null;
  cancelled: boolean;
}

export interface Expense {
  label: string;
  amount: number;
  /** null = as_of */
  date_expr: DateExpr | null;
}

export interface ScenarioSpec {
  label: string;
  adjustments: InflowAdjustment[];
  extra_expenses: Expense[];
}

export interface InflowApplied {
  id: string;
  date: string;
  amount: number;
}

export interface RunwayResult {
  runway_days: number;
  covered_through_horizon: boolean;
  runs_out_on: string | null;
  shortfall_amount: number | null;
  next_money_after_shortfall: string | null;
  gap_days: number | null;
  inflows_applied: InflowApplied[];
  horizon_days: number;
  series: number[];
}

export interface SafeSpendResult {
  inflow_today: boolean;
  target_date: string | null;
  days_to_cover: number;
  max_daily_total: number | null;
  headroom: number | null;
  covers_essentials: boolean;
  already_short: boolean;
}

export interface ReserveResult {
  days_to_next_money: number;
  buffer_days: number;
  essentials_part: number;
  must_pay_part: number;
  reserve: number;
  covered: boolean;
  surplus_or_gap: number;
}

export type AffordabilityVerdict =
  | "fits"
  | "shortens_runway"
  | "breaks_before_next_money"
  | "already_short";

export interface AffordabilityResult {
  verdict: AffordabilityVerdict;
  runway_before: number;
  runway_after: number;
  days_lost: number;
  runs_out_before: string | null;
  runs_out_after: string | null;
  next_money_date: string | null;
}

export type NumberType = "money" | "days" | "date" | "int";

export interface NumberEntry {
  path: string;
  value: number | string;
  type: NumberType;
}

export interface ToolResult {
  tool: string;
  args: object;
  ok: boolean;
  error: string | null;
  result: object | null;
  numbers: NumberEntry[];
}

export type TraceStepName =
  | "interpretation"
  | "tool_plan"
  | "validation"
  | "engine_call"
  | "verification"
  | "explanation"
  | "extraction";

export interface TraceStep {
  step: TraceStepName;
  label: string;
  ms: number;
  /** payload content is returned to the browser only; never persisted outside the demo profile */
  payload: object;
}

export type Plan =
  | { tool_calls: { tool: string; args: object }[] }
  | { clarify: string }
  | { refuse: "out_of_scope" };

// ---------- Situation draft (extract + manual responses) ----------

export interface GroundedValue<T> {
  value: T;
  grounded: boolean;
  source_text: string | null;
}

export interface GroundedDateValue {
  value: string | null;
  date_expr: DateExpr | null;
  grounded: boolean;
  source_text: string | null;
}

export interface EssentialsDraftValue {
  value: number | null;
  grounded: boolean;
  source_text: string | null;
  converted_from: { amount: number; period: "week" | "month" } | null;
}

export interface InflowDraft {
  id: string;
  label: string;
  expected_amount: GroundedValue<number | null>;
  expected_date: GroundedDateValue;
  uncertainty_note: string | null;
}

export interface CommitmentDraft {
  id: string;
  label: string;
  amount: GroundedValue<number | null>;
  due_date: GroundedDateValue;
  flexible: boolean | null;
}

export interface SituationDraft {
  as_of: string;
  balance: GroundedValue<number | null>;
  essentials_per_day: EssentialsDraftValue;
  inflows: InflowDraft[];
  commitments: CommitmentDraft[];
  /** e.g. "essentials", "inflow[0].amount", "inflow[0].date", "commitment[1].date" */
  missing: string[];
  warnings: string[];
}

/** POST /api/setup/extract and POST /api/setup/manual both return the draft plus a trace. */
export type ExtractResponse = SituationDraft & { trace: TraceStep[] };

// ---------- Health ----------

export interface HealthLlm {
  state: "up" | "down" | "disabled";
  runtime: string;
  model: string | null;
  detail: string | null;
}

export interface HealthMode {
  profile: "demo" | "user";
  persist: boolean;
  handover: boolean;
}

export interface HealthResponse {
  status: string;
  llm: HealthLlm;
  mode: HealthMode;
  /** true when the backend runs the free public "hosted preview" (STRETCH_HOSTED=1) */
  hosted: boolean;
  has_situation: boolean;
  version: string;
}

// ---------- Manual setup request (POST /api/setup/manual) ----------

export type EssentialsPeriod = "day" | "week" | "month";

export interface ManualSetupRequest {
  as_of?: string;
  balance: number;
  essentials: { amount: number; period: EssentialsPeriod };
  inflows: {
    label: string;
    expected_amount: number;
    date_expr: DateExpr;
    uncertainty_note: string | null;
  }[];
  commitments: {
    label: string;
    amount: number;
    date_expr: DateExpr;
    flexible: boolean | null;
  }[];
}

// ---------- Runway scenarios (POST /api/runway/scenarios) ----------

export interface ScenarioRun {
  scenario: ScenarioSpec;
  result: RunwayResult;
}

export interface ScenariosResponse {
  results: ScenarioRun[];
  safe_spend: SafeSpendResult;
  reserve: ReserveResult;
  assumptions: string[];
}

// ---------- Ask endpoints ----------

export interface PlanValidation {
  ok: boolean;
  checks: string[];
  errors: string[];
  repaired: boolean;
}

export interface ModelInfo {
  id: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_ms: number;
}

export interface PlanResponse {
  plan: Plan;
  validation: PlanValidation;
  model: ModelInfo | null;
  trace: TraceStep[];
}

export interface ExecuteResponse {
  results: ToolResult[];
  trace: TraceStep[];
}

export interface NarrationVerification {
  status: "verified" | "failed";
  checked_numbers: NumberEntry[];
  unmatched: (number | string)[];
  /** exactly "numbers verified against the engine" or null */
  badge: string | null;
}

export interface NarrateResponse {
  mode: "template" | "llm";
  narration: string;
  verification: NarrationVerification;
  regenerated: boolean;
  model: ModelInfo | null;
  trace: TraceStep[];
}

export type DirectToolName =
  | "compute_runway"
  | "safe_daily_spend"
  | "check_affordability"
  | "essentials_reserve";

export interface DirectRequest {
  tool: DirectToolName;
  args: object;
}

export interface DirectResponse {
  results: ToolResult[];
}

// ---------- compare_scenarios result shape ----------
// The contract leaves `ToolResult.result` as `object`; the UI assumes this shape
// for compare_scenarios results (scenario/result pairs plus deltas vs the first).
// FLAGGED ASSUMPTION — see README "Contract deviations".
export interface CompareScenariosResult {
  scenarios: ScenarioRun[];
  deltas: { runway_days: number; runs_out_on_days: number | null };
}

// ---------- Errors (API_CONTRACT.md §1) ----------

export type ApiErrorCode =
  | "llm_unavailable"
  | "llm_timeout"
  | "invalid_request"
  | "invalid_date"
  | "conflicting_adjustment"
  | "unknown_inflow"
  | "out_of_bounds"
  | "no_situation"
  | "profile_forbidden"
  | "internal";

export class ApiError extends Error {
  readonly code: ApiErrorCode | string;
  readonly status: number;
  readonly fallback: "manual" | null;

  constructor(status: number, body: { code: string; message: string; fallback: "manual" | null }) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.fallback = body.fallback;
  }
}

// ---------- Client interface ----------

export interface StretchApi {
  health(): Promise<HealthResponse>;
  extract(text: string, as_of?: string): Promise<ExtractResponse>;
  manual(body: ManualSetupRequest): Promise<ExtractResponse>;
  putSituation(situation: Situation): Promise<Situation>;
  getSituation(): Promise<Situation>;
  loadDemo(): Promise<Situation>;
  scenarios(body?: { scenarios?: ScenarioSpec[]; buffer_days?: number }): Promise<ScenariosResponse>;
  askPlan(question: string): Promise<PlanResponse>;
  askExecute(plan: Plan): Promise<ExecuteResponse>;
  askNarrate(question: string, results: ToolResult[]): Promise<NarrateResponse>;
  askDirect(tool: DirectToolName, args: object): Promise<DirectResponse>;
  deleteData(): Promise<void>;
}
