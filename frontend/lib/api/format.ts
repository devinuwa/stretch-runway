/**
 * Display helpers. Tone rule (AGENTS.md §2.2 / user constraints): never present
 * results as predictions. Phrase as "if the money arrives ..., your money runs
 * out on ...". Also honest badges per ACCEPTANCE_CRITERIA §3.
 */
import type { ScenarioSpec } from "./types";

export function money(n: number | null | undefined, currency: string): string {
  if (n === null || n === undefined) return "—";
  const sign = n < 0 ? "−" : "";
  return `${sign}${currency} ${Math.abs(Math.round(n)).toLocaleString("en-US")}`;
}

export function dayLabel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

/** "7 days late and half" style description of a scenario, for honest labels. */
export function scenarioLabel(s: ScenarioSpec): string {
  return s.label;
}

/** UI badge text comes only from the API's verification.badge field. */
export const BADGE_VERIFIED = "numbers verified against the engine";
export const BADGE_TEMPLATE = "template answer";
