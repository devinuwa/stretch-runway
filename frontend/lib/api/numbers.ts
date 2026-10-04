/**
 * Numbers registry helper for the mock direct path.
 * Mirrors API_CONTRACT.md §4: each tool adds entries for every number or date
 * it returns that may appear in prose.
 */
import type { NumberEntry, NumberType } from "./types";

function entries(prefix: string, obj: object | null, types: Record<string, NumberType>): NumberEntry[] {
  if (!obj) return [];
  const out: NumberEntry[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const t = types[key];
    if (t === undefined) continue;
    if (typeof value === "number" || typeof value === "string") {
      out.push({ path: `${prefix}${key}`, value, type: t });
    }
  }
  return out;
}

const runwayTypes: Record<string, NumberType> = {
  runway_days: "days",
  runs_out_on: "date",
  shortfall_amount: "money",
  next_money_after_shortfall: "date",
  gap_days: "days",
  horizon_days: "days",
};

const safeSpendTypes: Record<string, NumberType> = {
  target_date: "date",
  days_to_cover: "days",
  max_daily_total: "money",
  headroom: "money",
};

const reserveTypes: Record<string, NumberType> = {
  days_to_next_money: "days",
  buffer_days: "days",
  essentials_part: "money",
  must_pay_part: "money",
  reserve: "money",
  surplus_or_gap: "money",
};

const affordTypes: Record<string, NumberType> = {
  runway_before: "days",
  runway_after: "days",
  days_lost: "days",
  runs_out_before: "date",
  runs_out_after: "date",
  next_money_date: "date",
};

export function numberRegistry(tool: string, result: object | null): NumberEntry[] {
  switch (tool) {
    case "compute_runway":
      return entries("runway.", result, runwayTypes);
    case "safe_daily_spend":
      return entries("safe_spend.", result, safeSpendTypes);
    case "essentials_reserve":
      return entries("reserve.", result, reserveTypes);
    case "check_affordability":
      return entries("afford.", result, affordTypes);
    default:
      return [];
  }
}
