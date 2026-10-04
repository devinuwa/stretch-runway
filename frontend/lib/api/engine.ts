/**
 * Deterministic runway engine — TypeScript port of ARCHITECTURE.md §6.
 *
 * The backend owns the real engine; this file exists ONLY so the frontend mock
 * layer can serve fixture-faithful numbers while the backend does not exist yet.
 * It is pure: no I/O, no network, no LLM. Day semantics follow the doc exactly:
 * Day 0 is as_of; for each day n = 0..horizon-1 apply inflows dated that day,
 * subtract commitments (and extra expenses) dated that day and essentials_per_day;
 * record the end-of-day balance. A day is covered if end-of-day balance >= 0.
 * runway_days = consecutive covered days from day 0 (capped at horizon when never short).
 */
import type {
  AffordabilityResult,
  Commitment,
  DateExpr,
  Inflow,
  InflowAdjustment,
  RunwayResult,
  SafeSpendResult,
  ReserveResult,
  ScenarioSpec,
  Situation,
} from "./types";

// ---------- date helpers (ISO YYYY-MM-DD only; UTC arithmetic, no tz drift) ----------

export function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function parseISO(s: string): Date {
  return new Date(`${s}T00:00:00Z`);
}

export function addDays(s: string, n: number): string {
  const d = parseISO(s);
  d.setUTCDate(d.getUTCDate() + n);
  return iso(d);
}

export function daysBetween(from: string, to: string): number {
  return Math.round((parseISO(to).getTime() - parseISO(from).getTime()) / 86_400_000);
}

export function isISODate(s: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const [y, m, d] = s.split("-").map(Number);
  return (
    m >= 1 && m <= 12 && d >= 1 && d <= daysInMonth(y, m)
  );
}

function daysInMonth(y: number, m: number): number {
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

/** Resolve a DateExpr against as_of (ARCHITECTURE.md §6). Dates before as_of are invalid. */
export function resolveDateExpr(expr: DateExpr | null, as_of: string): string {
  if (expr === null) return as_of;
  if (expr.kind === "iso") {
    if (!isISODate(expr.value)) throw new EngineError("invalid_date", `bad ISO date: ${expr.value}`);
    return expr.value;
  }
  if (expr.kind === "in_days") return addDays(as_of, expr.n);
  // day_of_month
  const [y, m] = as_of.split("-").map(Number);
  const monthOffset = expr.month_offset === null ? (expr.day >= Number(as_of.slice(8, 10)) ? 0 : 1) : expr.month_offset;
  let ty = y;
  let tm = m + monthOffset;
  while (tm > 12) { tm -= 12; ty += 1; }
  if (!isISODate(`${ty}-${String(tm).padStart(2, "0")}-${String(expr.day).padStart(2, "0")}`)) {
    throw new EngineError("invalid_date", `day ${expr.day} does not exist in that month`);
  }
  return `${ty}-${String(tm).padStart(2, "0")}-${String(expr.day).padStart(2, "0")}`;
}

export class EngineError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = "EngineError";
    this.code = code;
  }
}

// ---------- scenario application ----------

function floorInt(x: number): number {
  return Math.floor(x);
}

export function applyAdjustments(
  inflow: Inflow,
  adjustments: InflowAdjustment[],
  as_of: string,
): { date: string; amount: number; cancelled: boolean } {
  // '*' adjustments first, then id-specific on top (order inside one adjustment:
  // cancel > (delay or new_date) > (amount_factor or new_amount))
  const matched = adjustments.filter((a) => a.inflow_id === "*" || a.inflow_id === inflow.id);
  let amount = inflow.expected_amount;
  let date = inflow.expected_date;
  let cancelled = false;
  for (const a of matched) {
    if (a.cancelled) cancelled = true;
    if (a.delay_days !== null && a.new_date_expr !== null) {
      throw new EngineError("conflicting_adjustment", "delay_days and new_date_expr are mutually exclusive");
    }
    if (a.amount_factor !== null && a.new_amount !== null) {
      throw new EngineError("conflicting_adjustment", "amount_factor and new_amount are mutually exclusive");
    }
    if (a.delay_days !== null) date = addDays(date, a.delay_days);
    // date_exprs resolve against as_of (ARCHITECTURE.md §3: the executor resolves date_expr against as_of)
    if (a.new_date_expr !== null) date = resolveDateExpr(a.new_date_expr, as_of);
    if (a.amount_factor !== null) amount = floorInt(amount * a.amount_factor);
    if (a.new_amount !== null) amount = a.new_amount;
  }
  return { date, amount, cancelled };
}

// ---------- runway ----------

export function runway(situation: Situation, scenario: ScenarioSpec): RunwayResult {
  const horizon = situation.horizon_days;
  const series: number[] = new Array(horizon);
  let balance = situation.balance;
  let runwayDays = 0;
  let coveredThroughHorizon = true;
  let runsOutOn: string | null = null;
  let shortfallAmount: number | null = null;

  const inflows = situation.inflows.map((i) => ({ ...applyAdjustments(i, scenario.adjustments, situation.as_of), id: i.id }));
  const commitments = situation.commitments.map((c) => ({ ...c, due: c.due_date }));
  const extras = scenario.extra_expenses.map((e) => ({
    label: e.label,
    amount: e.amount,
    date: resolveDateExpr(e.date_expr, situation.as_of),
  }));

  for (let n = 0; n < horizon; n++) {
    const day = addDays(situation.as_of, n);
    for (const i of inflows) if (i.date === day && !i.cancelled) balance += i.amount;
    for (const c of commitments) if (c.due === day) balance -= c.amount;
    for (const e of extras) if (e.date === day) balance -= e.amount;
    balance -= situation.essentials_per_day;
    series[n] = balance;
    if (balance >= 0) {
      if (runsOutOn === null) runwayDays += 1;
    } else {
      coveredThroughHorizon = false;
      if (runsOutOn === null) {
        runsOutOn = day;
        shortfallAmount = -balance;
      }
    }
  }

  let nextMoneyAfterShortfall: string | null = null;
  let gapDays: number | null = null;
  if (runsOutOn !== null) {
    const first = inflows
      .filter((i) => !i.cancelled && i.amount > 0 && daysBetween(runsOutOn as string, i.date) > 0)
      .sort((a, b) => (a.date < b.date ? -1 : 1))[0];
    if (first) {
      nextMoneyAfterShortfall = first.date;
      gapDays = daysBetween(runsOutOn, first.date);
    }
  }

  const inflowsApplied = inflows
    .filter((i) => !i.cancelled && i.amount > 0 && daysBetween(situation.as_of, i.date) >= 0 && daysBetween(situation.as_of, i.date) < horizon)
    .sort((a, b) => (a.date < b.date ? -1 : 1))
    .map((i) => ({ id: i.id, date: i.date, amount: i.amount }));

  return {
    runway_days: runwayDays,
    covered_through_horizon: coveredThroughHorizon,
    runs_out_on: runsOutOn,
    shortfall_amount: shortfallAmount,
    next_money_after_shortfall: nextMoneyAfterShortfall,
    gap_days: gapDays,
    inflows_applied: inflowsApplied,
    horizon_days: horizon,
    series,
  };
}

// ---------- safe spend ----------

export function safeSpend(situation: Situation, scenario: ScenarioSpec): SafeSpendResult {
  const inflows = situation.inflows.map((i) => ({ ...applyAdjustments(i, scenario.adjustments, situation.as_of), id: i.id }));
  const first = inflows
    .filter((i) => !i.cancelled && i.amount > 0 && daysBetween(situation.as_of, i.date) >= 0)
    .sort((a, b) => (a.date < b.date ? -1 : 1))[0];
  const N = first ? daysBetween(situation.as_of, first.date) : situation.horizon_days;

  if (N === 0) {
    return {
      inflow_today: true,
      target_date: null,
      days_to_cover: 0,
      max_daily_total: null,
      headroom: null,
      covers_essentials: false,
      already_short: false,
    };
  }

  const commitments = situation.commitments.map((c) => ({ amount: c.amount, due: c.due_date }));
  const extras = scenario.extra_expenses.map((e) => ({
    amount: e.amount,
    date: resolveDateExpr(e.date_expr, situation.as_of),
  }));

  let maxDailyTotal = Infinity;
  for (let i = 0; i < N; i++) {
    const day = addDays(situation.as_of, i);
    let ci = 0;
    for (const c of commitments) if (daysBetween(situation.as_of, c.due) <= i) ci += c.amount;
    for (const e of extras) if (daysBetween(situation.as_of, e.date) <= i) ci += e.amount;
    const allowed = floorInt((situation.balance - ci) / (i + 1));
    if (allowed < maxDailyTotal) maxDailyTotal = allowed;
  }
  const alreadyShort = maxDailyTotal < 0;
  if (alreadyShort) maxDailyTotal = 0;
  const headroom = Math.max(0, maxDailyTotal - situation.essentials_per_day);

  return {
    inflow_today: false,
    target_date: first ? first.date : null,
    days_to_cover: N,
    max_daily_total: maxDailyTotal,
    headroom: headroom,
    covers_essentials: maxDailyTotal >= situation.essentials_per_day,
    already_short: alreadyShort,
  };
}

// ---------- essentials reserve ----------

export function essentialsReserve(
  situation: Situation,
  scenario: ScenarioSpec,
  bufferDays?: number,
): ReserveResult {
  const buffer = bufferDays ?? situation.buffer_days;
  const inflows = situation.inflows.map((i) => ({ ...applyAdjustments(i, scenario.adjustments, situation.as_of), id: i.id }));
  const first = inflows
    .filter((i) => !i.cancelled && i.amount > 0 && daysBetween(situation.as_of, i.date) >= 0)
    .sort((a, b) => (a.date < b.date ? -1 : 1))[0];
  const N = first ? daysBetween(situation.as_of, first.date) : situation.horizon_days;

  const essentialsPart = situation.essentials_per_day * (N + buffer);
  let mustPayPart = 0;
  for (const c of situation.commitments) {
    if (!c.flexible) {
      const d = daysBetween(situation.as_of, c.due_date);
      if (d >= 0 && d < N) mustPayPart += c.amount;
    }
  }
  const reserve = essentialsPart + mustPayPart;
  const covered = situation.balance >= reserve;
  return {
    days_to_next_money: N,
    buffer_days: buffer,
    essentials_part: essentialsPart,
    must_pay_part: mustPayPart,
    reserve,
    covered,
    surplus_or_gap: situation.balance - reserve,
  };
}

// ---------- affordability ----------

function breaks(r: RunwayResult, nextMoney: string | null): boolean {
  if (r.runs_out_on === null) return false;
  return nextMoney === null || daysBetween(nextMoney, r.runs_out_on) > 0;
}

export function affordability(
  situation: Situation,
  scenario: ScenarioSpec,
  expense: { label: string; amount: number; date_expr: DateExpr | null },
): AffordabilityResult {
  const before = runway(situation, scenario);
  const withExpense: ScenarioSpec = {
    ...scenario,
    extra_expenses: [...scenario.extra_expenses, expense],
  };
  const after = runway(situation, withExpense);

  const applied = scenario.adjustments.length
    ? situation.inflows.map((i) => ({ ...applyAdjustments(i, scenario.adjustments, situation.as_of), id: i.id }))
    : situation.inflows.map((i) => ({ id: i.id, date: i.expected_date, amount: i.expected_amount, cancelled: false }));
  const nextMoney =
    applied
      .filter((i) => !i.cancelled && i.amount > 0 && daysBetween(situation.as_of, i.date) >= 0)
      .sort((a, b) => (a.date < b.date ? -1 : 1))[0]?.date ?? null;

  const daysLost = before.runway_days - after.runway_days;

  let verdict: AffordabilityResult["verdict"];
  if (breaks(before, nextMoney)) verdict = "already_short";
  else if (breaks(after, nextMoney)) verdict = "breaks_before_next_money";
  else if (daysLost > 0) verdict = "shortens_runway";
  else verdict = "fits";

  return {
    verdict,
    runway_before: before.runway_days,
    runway_after: after.runway_days,
    days_lost: daysLost,
    runs_out_before: before.runs_out_on,
    runs_out_after: after.runs_out_on,
    next_money_date: nextMoney,
  };
}

// ---------- presets (labelled defaults, not predictions) ----------

const emptyAdj: InflowAdjustment = {
  inflow_id: "*",
  delay_days: null,
  new_date_expr: null,
  amount_factor: null,
  new_amount: null,
  cancelled: false,
};

export function presetScenarios(): ScenarioSpec[] {
  return [
    { label: "on time", adjustments: [{ ...emptyAdj }], extra_expenses: [] },
    { label: "7 days late", adjustments: [{ ...emptyAdj, delay_days: 7 }], extra_expenses: [] },
    { label: "half the amount", adjustments: [{ ...emptyAdj, amount_factor: 0.5 }], extra_expenses: [] },
    {
      label: "7 days late and half",
      adjustments: [{ ...emptyAdj, delay_days: 7, amount_factor: 0.5 }],
      extra_expenses: [],
    },
    { label: "never arrives", adjustments: [{ ...emptyAdj, cancelled: true }], extra_expenses: [] },
  ];
}

export { floorInt };
