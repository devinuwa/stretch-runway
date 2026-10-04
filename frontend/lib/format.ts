/**
 * Display helpers. Tone rule (AGENTS.md §2): never present results as
 * predictions — phrase as "if the money arrives ..., your money runs out on ...".
 * Badges are honest per ACCEPTANCE_CRITERIA §3 and come only from the API.
 */
import type { ScenarioSpec } from "@/lib/api/types";

export function money(n: number | null | undefined, currency: string): string {
  if (n === null || n === undefined) return "—";
  const sign = n < 0 ? "−" : "";
  return `${sign}${currency} ${Math.abs(Math.round(n)).toLocaleString("en-US")}`;
}

export function plainMoney(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  const sign = n < 0 ? "−" : "";
  return `${sign}${Math.abs(Math.round(n)).toLocaleString("en-US")}`;
}

export function dayLabel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Tone-compliant conditional phrase for a preset scenario. */
export function scenarioPhrase(s: { label: string }): string {
  const map: Record<string, string> = {
    "on time": "if the money arrives on time",
    "7 days late": "if the money arrives 7 days late",
    "half the amount": "if the money arrives at half the amount",
    "7 days late and half": "if the money arrives 7 days late and at half the amount",
    "never arrives": "if the money never arrives",
  };
  return map[s.label] ?? `if the money arrives per “${s.label}”`;
}

/** UI badge text comes only from the API's verification.badge field. */
export const BADGE_TEMPLATE = "template answer";

export function exprToText(e: {
  kind: string;
  value?: string;
  n?: number;
  day?: number;
  month_offset?: number | null;
}): string {
  if (e.kind === "iso") return `ISO ${e.value}`;
  if (e.kind === "in_days") return `${e.n} days from today`;
  return `day ${e.day} of ${e.month_offset === 0 ? "this" : e.month_offset === 1 ? "next" : "the nearest"} month`;
}
