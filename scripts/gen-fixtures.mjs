/**
 * Generate the frontend fixtures (synthetic data only).
 *
 * Run from the repo root:  node scripts/gen-fixtures.mjs
 * Writes the six fixtures the frontend needs into /fixtures (canonical) and
 * copies them into frontend/mocks/. Numbers are computed by the TypeScript
 * engine port (frontend/lib/api/engine.ts), a faithful port of
 * ARCHITECTURE.md §6 — when the real backend lands, its engine must reproduce
 * these numbers (TEST_PLAN §1.5: derive by hand before editing a fixture).
 */
import { writeFileSync, mkdirSync, copyFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(new URL(import.meta.url, "file://")));
const { pathToFileURL } = await import("node:url");
const lib = (p) => import(pathToFileURL(join(root, "..", "frontend", "lib", "api", p)).href);

const { DEMO_SITUATION } = await lib("demo-situation.ts");
const engine = await lib("engine.ts");

const OUT = join(root, "..", "fixtures");
const MOCKS = join(root, "..", "frontend", "mocks");
mkdirSync(OUT, { recursive: true });
mkdirSync(MOCKS, { recursive: true });

const syntheticTag = (o) => ({ synthetic: true, ...o });

// ---------- 1. situation_demo.json ----------
writeFileSync(join(OUT, "situation_demo.json"), JSON.stringify(syntheticTag(DEMO_SITUATION), null, 2) + "\n");

// ---------- 2. extract_demo.json (hand-derived from the demo paragraph) ----------
const extract_demo = {
  as_of: "2026-10-05",
  balance: { value: 26000, grounded: true, source_text: "I have about 26k" },
  essentials_per_day: {
    value: 1500,
    grounded: true,
    source_text: "I spend like 1500 naira every day on food",
    converted_from: null,
  },
  inflows: [
    {
      id: "inflow_1",
      label: "Aunt",
      expected_amount: { value: 20000, grounded: true, source_text: "my aunt promised 20,000" },
      expected_date: {
        value: "2026-10-15",
        date_expr: { kind: "day_of_month", day: 15, month_offset: null },
        grounded: true,
        source_text: "she should send it by the 15th",
      },
      uncertainty_note: "promised, not confirmed",
    },
  ],
  commitments: [
    {
      id: "commit_1",
      label: "Outfit",
      amount: { value: 12000, grounded: true, source_text: "12k outfit" },
      due_date: {
        value: "2026-10-21",
        date_expr: { kind: "iso", value: "2026-10-21" },
        grounded: true,
        source_text: "before the 21st",
      },
      flexible: true,
    },
  ],
  missing: [],
  warnings: [],
  trace: [
    {
      step: "extraction",
      label: "S1 extract (stub)",
      ms: 812,
      payload: { source: "fixture", synthetic: true },
    },
  ],
};
writeFileSync(join(OUT, "extract_demo.json"), JSON.stringify(extract_demo, null, 2) + "\n");

// ---------- 3. runway_presets_demo.json ----------
const presets = engine.presetScenarios();
const runway_presets_demo = {
  results: presets.map((scenario) => ({ scenario, result: engine.runway(DEMO_SITUATION, scenario) })),
  safe_spend: engine.safeSpend(DEMO_SITUATION, presets[0]),
  reserve: engine.essentialsReserve(DEMO_SITUATION, presets[0]),
  assumptions: [
    "Presets are labelled defaults, not predictions of when money will arrive.",
    "Essentials are subtracted every day, starting today.",
    "Amounts are whole currency units.",
  ],
};
writeFileSync(join(OUT, "runway_presets_demo.json"), JSON.stringify(syntheticTag(runway_presets_demo), null, 2) + "\n");

// ---------- 4. ask_demo_plan.json ----------
const plan = {
  tool_calls: [
    {
      tool: "compare_scenarios",
      args: {
        scenarios: [
          { label: "on time", adjustments: [], extra_expenses: [] },
          {
            label: "5 days late, half the amount",
            adjustments: [
              { inflow_id: "*", delay_days: 5, new_date_expr: null, amount_factor: 0.5, new_amount: null, cancelled: false },
            ],
            extra_expenses: [],
          },
        ],
      },
    },
  ],
};
const ask_demo_plan = {
  plan,
  validation: { ok: true, checks: ["schema", "tool_allowlist", "bounds", "inflow_ids", "grounding"], errors: [], repaired: false },
  model: { id: "stub:demo", prompt_tokens: 312, completion_tokens: 64, total_ms: 940 },
  trace: [
    {
      step: "interpretation",
      label: "S2 plan (stub)",
      ms: 940,
      payload: { plan, synthetic: true },
    },
  ],
};
writeFileSync(join(OUT, "ask_demo_plan.json"), JSON.stringify(syntheticTag(ask_demo_plan), null, 2) + "\n");

// ---------- 5. ask_demo_execute.json ----------
const lateHalf = plan.tool_calls[0].args.scenarios[1];
const scenarios = plan.tool_calls[0].args.scenarios;
const runwayResults = scenarios.map((s) => ({
  label: s.label,
  runway_days: engine.runway(DEMO_SITUATION, s).runway_days,
  runs_out_on: engine.runway(DEMO_SITUATION, s).runs_out_on,
}));
const deltas = {
  runway_days: runwayResults[1].runway_days - runwayResults[0].runway_days,
  runs_out_on_days:
    runwayResults[0].runs_out_on !== null && runwayResults[1].runs_out_on !== null
      ? engine.daysBetween(runwayResults[0].runs_out_on, runwayResults[1].runs_out_on)
      : null,
};
const numbers = [
  ...engine.runway(DEMO_SITUATION, scenarios[0]).runway_days !== undefined
    ? [{ path: "runway[0].runway_days", value: runwayResults[0].runway_days, type: "days" },
       { path: "runway[0].runs_out_on", value: runwayResults[0].runs_out_on, type: "date" }]
    : [],
  { path: "runway[1].runway_days", value: runwayResults[1].runway_days, type: "days" },
  { path: "runway[1].runs_out_on", value: runwayResults[1].runs_out_on, type: "date" },
  { path: "deltas.runway_days", value: deltas.runway_days, type: "days" },
];
const ask_demo_execute = {
  results: [
    {
      tool: "compare_scenarios",
      args: plan.tool_calls[0].args,
      ok: true,
      error: null,
      result: {
        scenarios: scenarios.map((s) => ({ scenario: s, result: engine.runway(DEMO_SITUATION, s) })),
        deltas,
      },
      numbers,
    },
  ],
  trace: [
    {
      step: "tool_plan",
      label: "tool registry",
      ms: 3,
      payload: { tool: "compare_scenarios", synthetic: true },
    },
    {
      step: "validation",
      label: "V2 plan validation",
      ms: 1,
      payload: { ok: true, checks: ["schema", "tool_allowlist", "bounds", "inflow_ids", "grounding"] },
    },
    {
      step: "engine_call",
      label: "compare_scenarios",
      ms: 2,
      payload: { scenarios: scenarios.length, synthetic: true },
    },
  ],
};
writeFileSync(join(OUT, "ask_demo_execute.json"), JSON.stringify(syntheticTag(ask_demo_execute), null, 2) + "\n");

// ---------- 6. ask_demo_narrate.json ----------
const narrate = `If the money arrives 5 days late and at half the amount, your money runs out on ${runwayResults[1].runs_out_on} after ${runwayResults[1].runway_days} days instead of ${runwayResults[0].runs_out_on} after ${runwayResults[0].runway_days} days — a difference of ${Math.abs(deltas.runway_days)} days.`;
const ask_demo_narrate = {
  mode: "template",
  narration: narrate,
  verification: {
    status: "verified",
    checked_numbers: numbers,
    unmatched: [],
    badge: "numbers verified against the engine",
  },
  regenerated: false,
  model: null,
  trace: [
    {
      step: "verification",
      label: "V3 narration check",
      ms: 1,
      payload: { status: "verified", unmatched: [] },
    },
    {
      step: "explanation",
      label: "template narration",
      ms: 1,
      payload: { mode: "template" },
    },
  ],
};
writeFileSync(join(OUT, "ask_demo_narrate.json"), JSON.stringify(syntheticTag(ask_demo_narrate), null, 2) + "\n");

// ---------- copy into frontend/mocks ----------
for (const f of [
  "situation_demo.json",
  "extract_demo.json",
  "runway_presets_demo.json",
  "ask_demo_plan.json",
  "ask_demo_execute.json",
  "ask_demo_narrate.json",
]) {
  copyFileSync(join(OUT, f), join(MOCKS, f));
}

console.log("fixtures written to", OUT, "and copied to", MOCKS);
