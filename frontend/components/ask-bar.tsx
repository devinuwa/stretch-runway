"use client";

/**
 * Ask bar (ARCHITECTURE.md §14.4, user constraint): a question box with a
 * 6-step ribbon — interpretation -> tool call -> validation -> engine ->
 * verification -> explanation — that advances only on real staged responses
 * (/api/ask/plan, /api/ask/execute, /api/ask/narrate), never a timer.
 *
 * When health.llm.state !== "up": the ask bar is replaced by preset buttons
 * + a "Can I afford X?" form calling /api/ask/direct (§9 fallback).
 */
import { useState } from "react";
import { api } from "@/lib/api/client";
import { money } from "@/lib/format";
import { TracePanel } from "@/components/trace-panel";
import type {
  ExecuteResponse,
  HealthResponse,
  NarrateResponse,
  PlanResponse,
  ToolResult,
  TraceStep,
} from "@/lib/api/types";

const RIBBON = [
  { key: "interpretation", label: "Interpretation" },
  { key: "tool_call", label: "Tool call" },
  { key: "validation", label: "Validation" },
  { key: "engine", label: "Engine" },
  { key: "verification", label: "Verification" },
  { key: "explanation", label: "Explanation" },
] as const;

type RibbonKey = (typeof RIBBON)[number]["key"];
type RibbonState = Record<RibbonKey, "idle" | "active" | "done">;

const freshRibbon = (): RibbonState =>
  Object.fromEntries(RIBBON.map((r) => [r.key, "idle"])) as RibbonState;

const cardCls =
  "rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900";
const btnPrimary =
  "rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50";
const inputCls =
  "w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-emerald-600 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100";

export function AskBar({
  health,
  llmUp,
}: {
  health: HealthResponse | null;
  llmUp: boolean;
}) {
  if (!llmUp) return <FallbackAsk health={health} />;

  return (
    <section className={cardCls}>
      <h2 className="text-sm font-semibold">Ask about your situation</h2>
      <AskFlow />
    </section>
  );
}

function AskFlow() {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ribbon, setRibbon] = useState<RibbonState>(freshRibbon);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [exec, setExec] = useState<ExecuteResponse | null>(null);
  const [narr, setNarr] = useState<NarrateResponse | null>(null);

  function reset() {
    setRibbon(freshRibbon());
    setPlan(null);
    setExec(null);
    setNarr(null);
    setError(null);
  }

  async function ask(q: string) {
    const question = q.trim();
    if (!question) return;
    reset();
    setBusy(true);
    try {
      // Step 1: interpretation -> the model plan is the interpretation.
      setRibbon((r) => ({ ...r, interpretation: "active" }));
      const planRes = await api.askPlan(question);
      setPlan(planRes);
      setRibbon((r) => ({ ...r, interpretation: "done" }));

      // Refusal / clarify plans stop the pipeline honestly.
      if (!("tool_calls" in planRes.plan)) {
        setRibbon((r) => ({ ...r, tool_call: "active" }));
        setNarr({
          mode: "template",
          narration:
            "clarify" in planRes.plan
              ? planRes.plan.clarify
              : "I can only answer questions about your own situation — not loans, investments, or anything like advice.",
          verification: { status: "verified", checked_numbers: [], unmatched: [], badge: null },
          regenerated: false,
          model: null,
          trace: planRes.trace,
        });
        setRibbon((r) => ({ ...r, tool_call: "done", validation: "done", engine: "done", verification: "done", explanation: "done" }));
        setBusy(false);
        return;
      }

      // Step 2: tool call staged; Step 3: validation from the same response.
      setRibbon((r) => ({ ...r, tool_call: "active" }));
      const planChecks = planRes.validation.checks.length > 0;
      setRibbon((r) => ({ ...r, tool_call: "done", validation: planChecks ? "active" : "done" }));

      // Step 4: engine (execute endpoint, never calls the LLM).
      const execRes = await api.askExecute(planRes.plan);
      setExec(execRes);
      setRibbon((r) => ({ ...r, validation: "done", engine: "done" }));

      // Steps 5-6: verification + explanation from the narrate response.
      setRibbon((r) => ({ ...r, verification: "active" }));
      const narrRes = await api.askNarrate(question, execRes.results);
      setNarr(narrRes);
      setRibbon((r) => ({ ...r, verification: "done", explanation: "done" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRibbon(freshRibbon());
    } finally {
      setBusy(false);
    }
  }

  const allSteps: TraceStep[] = [
    ...(plan?.trace ?? []),
    ...(exec?.trace ?? []),
    ...(narr?.trace ?? []),
  ];

  return (
    <div className="mt-3 space-y-4">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
      >
        <input
          className={inputCls}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What if the money comes 5 days late and is only half the amount?"
        />
        <button className={btnPrimary} disabled={busy || !question.trim()}>
          {busy ? "Thinking…" : "Ask"}
        </button>
      </form>

      <ol className="flex flex-wrap items-center gap-1 text-[11px]" aria-label="pipeline ribbon">
        {RIBBON.map(({ key, label }, i) => {
          const st = ribbon[key];
          return (
            <li key={key} className="flex items-center">
              {i > 0 && <span className="mx-1 text-zinc-400">→</span>}
              <span
                className={[
                  "rounded-full px-2 py-1 font-medium",
                  st === "done"
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200"
                    : st === "active"
                      ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
                      : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
                ].join(" ")}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>

      {error && (
        <p className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      )}

      {narr && (
        <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <p className="text-sm">{narr.narration}</p>
          {narr.verification.badge ? (
            <span className="mt-2 inline-block rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
              {narr.verification.badge}
            </span>
          ) : (
            <span className="mt-2 inline-block rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-semibold text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              template answer
            </span>
          )}
          {narr.verification.unmatched.length > 0 && (
            <p className="mt-1 text-[11px] text-amber-700 dark:text-amber-400">
              unverified tokens: {narr.verification.unmatched.join(", ")}
            </p>
          )}
        </div>
      )}

      {exec && <ResultCards results={exec.results} />}

      {allSteps.length > 0 && <TracePanel steps={allSteps} title="Ask trace" />}
    </div>
  );
}

function ResultCards({ results }: { results: ToolResult[] }) {
  return (
    <div className="space-y-2">
      {results.map((tr, i) =>
        tr.ok ? (
          <ResultCard key={i} tr={tr} />
        ) : (
          <p key={i} className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            {tr.tool}: {tr.error}
          </p>
        ),
      )}
    </div>
  );
}

function ResultCard({ tr }: { tr: ToolResult }) {
  const r = tr.result as {
    scenarios?: { scenario: { label: string }; result: { runway_days: number; runs_out_on: string | null } }[];
    deltas?: { runway_days: number };
    runway_days?: number;
    runs_out_on?: string | null;
    verdict?: string;
    runway_before?: number;
    runway_after?: number;
    max_daily_total?: number | null;
    reserve?: number;
  } | null;
  if (!r) return null;

  if (r.scenarios) {
    return (
      <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
        <p className="text-xs font-semibold text-zinc-600 dark:text-zinc-400">Scenario comparison</p>
        <ul className="mt-1 space-y-0.5">
          {r.scenarios.map((s) => (
            <li key={s.scenario.label}>
              If the money arrives {s.scenario.label}: runs out{" "}
              {s.result.runs_out_on ?? "never within the horizon"} after {s.result.runway_days} days
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (typeof r.runway_days === "number") {
    return (
      <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
        Runs out {r.runs_out_on ?? "never within the horizon"} after {r.runway_days} days.
      </div>
    );
  }
  if (r.verdict) {
    return (
      <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
        Verdict: {r.verdict} (runway {r.runway_before} → {r.runway_after} days).
      </div>
    );
  }
  if (typeof r.max_daily_total === "number") {
    return (
      <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
        Safe daily spend: {r.max_daily_total}.
      </div>
    );
  }
  if (typeof r.reserve === "number") {
    return (
      <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
        Reserve needed: {r.reserve}.
      </div>
    );
  }
  return null;
}

// ---------- fallback (LLM down / disabled) ----------

const DIRECT_TOOLS = [
  { tool: "compute_runway", label: "How long does my money last?" },
  { tool: "safe_daily_spend", label: "What can I spend per day?" },
  { tool: "essentials_reserve", label: "How much reserve do I need?" },
] as const;

function FallbackAsk({ health }: { health: HealthResponse | null }) {
  const [amount, setAmount] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ToolResult[] | null>(null);

  const reason =
    health?.llm.state === "disabled"
      ? "The local model is switched off."
      : "The local model is not reachable right now.";

  async function runDirect(tool: (typeof DIRECT_TOOLS)[number]["tool"]) {
    setBusy(true);
    setError(null);
    setResults(null);
    try {
      const res = await api.askDirect(tool, {});
      setResults(res.results);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function afford() {
    const amt = Math.floor(Number(amount.replace(/,/g, "")));
    if (!Number.isFinite(amt) || amt <= 0) {
      setError("Enter a positive amount.");
      return;
    }
    setBusy(true);
    setError(null);
    setResults(null);
    try {
      const res = await api.askDirect("check_affordability", {
        label: label.trim() || "expense",
        amount: amt,
        date_expr: null,
      });
      setResults(res.results);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={cardCls}>
      <h2 className="text-sm font-semibold">Ask without the model</h2>
      <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
        {reason} Use the preset buttons or the form below — the engine still gives the same numbers.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {DIRECT_TOOLS.map((t) => (
          <button
            key={t.tool}
            className="rounded-md border border-zinc-300 px-3 py-2 text-xs font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
            onClick={() => runDirect(t.tool)}
            disabled={busy}
          >
            {t.label}
          </button>
        ))}
      </div>
      <form
        className="mt-3 flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          afford();
        }}
      >
        <span className="text-xs text-zinc-600 dark:text-zinc-400">Can I afford</span>
        <input
          className="w-28 rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          placeholder="amount"
          inputMode="numeric"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          aria-label="expense amount"
        />
        <input
          className="w-40 rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          placeholder="what for (optional)"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          aria-label="expense label"
        />
        <span className="text-xs text-zinc-600 dark:text-zinc-400">?</span>
        <button className={btnPrimary} disabled={busy}>
          {busy ? "Checking…" : "Check"}
        </button>
      </form>

      {error && (
        <p className="mt-3 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      )}

      {results && (
        <div className="mt-3">
          <ResultCards results={results} />
          <TracePanel steps={resultsToTrace(results)} title="Direct trace" />
        </div>
      )}
    </section>
  );
}

function resultsToTrace(results: ToolResult[]): TraceStep[] {
  return [
    {
      step: "engine_call",
      label: "direct tool call",
      ms: 0,
      payload: { results },
    },
  ];
}
