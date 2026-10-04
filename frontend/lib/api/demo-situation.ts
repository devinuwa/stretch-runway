/**
 * Synthetic demo situation (SYNTHETIC DATA ONLY — `synthetic: true` is mandatory).
 *
 * These are the numbers the backend fixtures pin (`as_of: 2026-10-05` in
 * docs/API_CONTRACT.md §3). AGENTS.md §4: synthetic data only for development,
 * fixtures and demos.
 */
import type { Situation } from "./types";

export const DEMO_SITUATION: Situation = {
  synthetic: true,
  as_of: "2026-10-05",
  currency: "NGN",
  balance: 26000,
  essentials_per_day: 1500,
  inflows: [
    {
      id: "inflow_1",
      label: "Aunt",
      expected_amount: 20000,
      expected_date: "2026-10-15",
      uncertainty_note: null,
    },
  ],
  commitments: [
    {
      id: "commit_1",
      label: "Outfit",
      amount: 12000,
      due_date: "2026-10-21",
      flexible: true,
    },
  ],
  horizon_days: 60,
  buffer_days: 3,
};
