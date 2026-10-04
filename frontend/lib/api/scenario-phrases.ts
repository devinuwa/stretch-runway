/**
 * Tone rule: never present results as predictions. Each preset maps to a
 * conditional phrase that states the assumption instead of predicting arrival.
 */
import type { ScenarioSpec } from "./types";

const PHRASES: Record<string, string> = {
  "on time": "if the money arrives on time",
  "7 days late": "if the money arrives 7 days late",
  "half the amount": "if the money arrives at half the amount",
  "7 days late and half": "if the money arrives 7 days late and at half the amount",
  "never arrives": "if the money never arrives",
};

export function scenarioPhrase(s: ScenarioSpec): string {
  return PHRASES[s.label] ?? `if the money arrives per “${s.label}”`;
}
