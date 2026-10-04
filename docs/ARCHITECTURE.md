# ARCHITECTURE — Stretch

Status: approved direction (Strategy C, minimal hybrid). Nothing here is built yet. Items marked **VERIFY** must be checked by the agent against current docs before use.

## 0. Refinements since the chat version (these supersede it)

1. `InflowAdjustment` gains `new_amount` (absolute) and `new_date_expr` (absolute date) so the model never computes a factor or a delay. `amount_factor` and `new_amount` are mutually exclusive; `delay_days` and `new_date_expr` are mutually exclusive.
2. Essentials are extracted as `{amount, period: day|week|month}`; **code** converts: week -> `ceil(amount/7)`, month -> `ceil(amount/30)`.
3. `RunwayResult` no longer reports `min_balance` (it is dominated by the horizon end). It reports `runs_out_on`, `shortfall_amount` (deficit on that first day), `next_money_after_shortfall`, `gap_days`, `inflows_applied`, plus the daily series.
4. Affordability verdicts are exactly: `fits`, `shortens_runway`, `breaks_before_next_money`, `already_short`.
5. Plan schema is a union: `{tool_calls:[...]}` | `{clarify:"..."}` | `{refuse:"out_of_scope"}`.
6. The **manual fallback path** and **handover/session mode** are first-class (sections 9 and 12).
7. Persisted traces are **metadata-only** outside the `demo` profile.

## 1. Principles

1. **The model refers, code computes.**
2. **The engine is a pure library** (no I/O, no LLM, no network).
3. **The UI works without the LLM.**
4. **Scenarios, not forecasts.** No probabilities, no predictions of arrival.
5. **Sponsor pieces are optional adapters.** Removing them changes nothing structurally.
6. **Honest badges.** "numbers verified against the engine" means the numbers in the text match engine output. Nothing more.

## 2. Component diagram

```
Browser (Next.js, localhost:3000)
  Setup(text | manual form) -> Confirmation card -> Dashboard -> Ask bar -> Trace panel
        | HTTP, loopback only
FastAPI (127.0.0.1:8000)
  api/        routes, error mapping, mode flags
  pipeline/   extract (S1) | plan (S2) | narrate (S3)   orchestration only
     |            |              |
  llm/        tools/          verify/
  ModelAdapter  registry,       V1 grounding
  (replaceable) executor,       V2 plan validation
                numbers reg.    V3 narration check
                   |
                engine/   PURE: dates, scenarios, runway, safe_spend, reserve, affordability
  store/  SQLite or in-memory (session mode)       trace/  Tracer -> LocalJsonlTracer (default)
  adapters/  (optional) sentry                                        |  optional adapter
        | loopback
Ollama (127.0.0.1:11434): local open-weight model
```

**Import rule:** `engine` imports nothing from the project. `tools` -> `engine`. `pipeline` -> `llm, tools, verify, store, trace`. `adapters` -> `trace` only, loaded lazily.

## 3. The AI -> tools -> engine -> verification -> response boundary

| # | Layer | Owner | Does | Must not |
|---|---|---|---|---|
| 1 | Interpretation | LLM | text -> structured plan (`tool_calls` with ids and raw expressions) | compute, resolve dates, invent amounts or ids |
| 2 | Validation | code (V1/V2) | schema, allowlist, bounds, id existence, number grounding | trust the model |
| 3 | Tool execution | tool registry | model-agnostic dispatch, resolves `date_expr` against `as_of` | call the LLM or network |
| 4 | Calculation | engine | all arithmetic, deterministic | any I/O |
| 5 | Verification | code (V3) | every number in the narration must be in the numbers registry / inputs / question | judge advice quality |
| 6 | Explanation | template (P0) or LLM composer (P1) | plain-language answer | introduce numbers |
| 7 | Presentation | UI | result cards + chart from engine output, narration with honest badge | show unverified numbers as verified |

The demo transformation, shown live in the trace panel:

```
"What if the money comes 5 days late and is only half the amount?"
  -> [1] LLM interpretation -> plan JSON (compare_scenarios: on time vs {delay_days:5, amount_factor:0.5})
  -> [2] validation checks (schema, allowlist, bounds, ids, grounding)
  -> [3] tool registry call
  -> [4] engine: inputs, outputs, numbers registry
  -> [5] verification (V3) -> verified | regenerated | template
  -> [6] explanation
```

Fixtures for this exact path: `fixtures/ask_demo_plan.json`, `ask_demo_execute.json`, `ask_demo_narrate.json`.

## 4. Data flow

**Setup (LLM path)**
```
text -> S1 extract (LLM, constrained JSON) -> ExtractionOutput
     -> code: resolve date_expr against as_of, convert essentials to per-day, V1 grounding flags
     -> SituationDraft -> Confirmation card (editable; ungrounded values highlighted)
     -> PUT /api/situation -> store
```

**Setup (manual fallback path, no LLM at all)**
```
manual form -> POST /api/setup/manual -> SituationDraft (same shape) -> Confirmation card -> PUT /api/situation
```

**Question path**
```
question -> S2 plan (LLM) -> V2 -> executor -> engine -> ToolResult[] (+ numbers registry)
         -> UI renders cards + chart from ToolResult (always, no LLM needed)
         -> S3 narrate: template (P0) | LLM composer (P1) -> V3 -> verified | regenerate once | template
```

Presets (`/api/runway/scenarios`) never touch the LLM.

## 5. Model layer

```python
class ModelAdapter(Protocol):
    def health(self) -> HealthInfo
    def generate_structured(self, system, user, json_schema, *, max_tokens, temperature=0.0) -> StructuredResult
    def generate_text(self, system, user, *, max_tokens, temperature=0.0) -> TextResult
# Results: raw, parsed, prompt_tokens, completion_tokens, ttft_ms, total_ms
```

- **One concrete adapter: Ollama** over plain HTTP (httpx), schema-constrained output. **VERIFY** the structured-output API on the installed Ollama version. Also provide a `StubModelAdapter` (scripted responses) used by tests and CI.
- `backend/eval/models.yaml` lists candidate models: id, runtime tag, family, params, quantization, digest, license link. **Gemma is one row.** Candidate set (**VERIFY** current tags/sizes/licenses on the Ollama library; do not trust this list): a Gemma small variant (e.g. `gemma3:4b`), a Llama small variant (e.g. `llama3.2:3b`), and a third family (e.g. a Qwen small instruct). Prefer three different families at roughly 2-4B parameters. Larger models will be too slow on this CPU.
- Pipeline stages S1 extract, S2 plan, S3 compose. One default model for all stages is preferred (model swap = load time on CPU). Per-stage override allowed in config.
- This is a **constrained tool-calling pipeline, not an open-ended agent loop**: one planning step, at most 3 validated tool calls, then explanation. Say this honestly in the README/article.
- CPU rules: compact prompts (planner gets ids and labels, not full data), few-shot examples **disjoint from eval cases** (a test enforces it), warm the model at startup (`keep_alive`), default timeout 90 s per call (configurable).

## 6. Deterministic engine

**Day semantics (exact).** Day 0 is `as_of`. For each day `n = 0..horizon-1`: apply inflows dated that day, subtract commitments (and scenario `extra_expenses`) dated that day, subtract `essentials_per_day`; record the end-of-day balance. A day is *covered* if its end-of-day balance >= 0. `runway_days` = consecutive covered days from day 0 (capped at `horizon_days` when never short). `runs_out_on` = first uncovered day or null.

**Inputs.** `as_of`, `balance`, `essentials_per_day`, `commitments[]{id,label,amount,due_date,flexible}`, `inflows[]{id,label,expected_amount,expected_date,uncertainty_note}`, `horizon_days` (default 60), `buffer_days` (default 3, user-editable, a display setting not advice). Integer currency units only; currency is a label (`NGN` in the synthetic demo).

**Date expressions** (`DateExpr`): `{kind:"iso",value}` | `{kind:"in_days",n}` | `{kind:"day_of_month",day,month_offset}`. Resolution against `as_of`:
- `day_of_month` with `month_offset: null`: this month if `day >= as_of.day`, else next month (year rollover handled).
- `month_offset: 0|1`: this month / next month.
- Invalid dates (e.g. day 31 in a 30-day month) raise `invalid_date`. Dates before `as_of` are invalid.
- Expense `date_expr: null` means `as_of`.

**Scenario spec.**
```
InflowAdjustment { inflow_id: str|"*", delay_days:int|null, new_date_expr:DateExpr|null,
                   amount_factor:number|null, new_amount:int|null, cancelled:bool }
ScenarioSpec { label, adjustments[], extra_expenses[{label, amount, date_expr|null}] }
```
Order inside one adjustment: cancel > (delay or new_date) > (amount_factor or new_amount). `amount_factor` result is **floored**. Bounds: `delay_days` 0..365, `amount_factor` 0..2, amounts >= 0. Adjustments with `"*"` apply to all inflows; later adjustments for a specific id apply on top.

**Presets (labelled defaults, not predictions):** on time; 7 days late; half the amount; 7 days late and half; never arrives.

**Queries.**
- `runway(scenario)` -> `{runway_days, covered_through_horizon, runs_out_on, shortfall_amount, next_money_after_shortfall, gap_days, inflows_applied[], horizon_days, series[]}`. `next_money_after_shortfall` = first applied inflow strictly after `runs_out_on`; `gap_days` = days from `runs_out_on` to it.
- `safe_spend(scenario)`: `N` = days until the first non-cancelled inflow arriving on/after `as_of` (or `horizon_days` if none). If `N == 0` -> `inflow_today: true`, no limit. Else `max_daily_total = floor(min over i in 0..N-1 of (balance - C_i)/(i+1))`, where `C_i` = commitments and extra expenses due on days `0..i`; negative values clamp to 0 with `already_short: true`. `headroom = max(0, max_daily_total - essentials)`; `covers_essentials = max_daily_total >= essentials`. It protects only the time until the next money arrives (state this in the UI).
- `essentials_reserve(scenario, buffer_days)`: `N` as above; `reserve = essentials*(N+buffer_days) + sum(non-flexible commitments due on days 0..N-1)`; returns `covered` and signed `surplus_or_gap`.
- `affordability(expense, scenario)`: `before = runway(S)`, `after = runway(S + expense)`, `days_lost = before.runway_days - after.runway_days`, `next_money` = first applied inflow on/after `as_of`. `breaks(r)` = `r.runs_out_on` exists and (`next_money` is null or `r.runs_out_on < next_money`). Verdict: `already_short` if `breaks(before)`; else `breaks_before_next_money` if `breaks(after)`; else `shortens_runway` if `days_lost > 0`; else `fits`.

Golden cases and hand-checkable examples: `fixtures/engine_golden.json`. Property tests: delaying an inflow never extends runway; shrinking one never extends it; adding an expense never extends it; cancelling never extends it.

## 7. Tool definitions (model-agnostic registry)

| Tool | Args | Returns |
|---|---|---|
| `compute_runway` | `scenario?` | RunwayResult |
| `compare_scenarios` | `scenarios[1..5]` | list of RunwayResult + deltas vs first |
| `safe_daily_spend` | `scenario?` | SafeSpendResult |
| `check_affordability` | `expense{label,amount,date_expr?}`, `scenario?` | AffordabilityResult |
| `essentials_reserve` | `scenario?`, `buffer_days?` | ReserveResult |
| `propose_update` (P1) | `kind: log_spend|log_inflow`, fields | staged change; **never auto-applied**, needs UI confirmation |

Every `ToolResult` = `{tool, args, ok, error, result, numbers[]}` where `numbers` is a flat registry `[{path, value, type: money|days|date|int}]` that is the allowlist for V3.

## 8. Verification layer

| Gate | Checks | On failure |
|---|---|---|
| **V1 extraction grounding** | every extracted amount appears in the user's text after normalizing `k`/`m`/commas/currency signs; flags `grounded` | confirmation card highlights it; never silently accepted |
| **V2 plan validation** | schema, tool allowlist, bounds, known `inflow_id`s, amounts grounded in the question or stored situation, mutual exclusivity | one repair attempt with the error fed back; then a templated clarifying question |
| **V3 narration** | every integer/date token in the narration exists in the numbers registry, the situation, or the question (k/commas normalized); advice-pattern denylist (loan, invest, crypto, borrow) | regenerate once with violations listed; then **template narration** labelled "template answer" |

V3 limitation (state it in docs): it checks numbers, not reasoning quality or advice appropriateness.

## 9. Fallback architecture (mandatory)

`GET /api/health` reports `llm.state: up|down|disabled`. When not `up`: setup uses the manual form, the ask bar is replaced by preset-scenario buttons plus a "can I afford X?" **form** (amount, date) calling tools directly, and narration is template-only. The result is **identical engine output** to the LLM path. `STRETCH_LLM=off` forces this mode. An automated test runs the full fallback flow with the model adapter disabled.

## 10. Local storage and privacy

- **Profiles:** `demo` (synthetic seed, full traces allowed) and `user`. Env: `STRETCH_PROFILE`, `STRETCH_PERSIST` (0 = in-memory, nothing written), `STRETCH_HANDOVER=1` (forces `user` profile, `PERSIST=0`, metadata-only traces, session banner).
- **SQLite** (stdlib) holds the current situation and an append-only events table, only when persisting. JSONL traces/eval results under `data/` (gitignored).
- **Trace policy:** `demo` profile may store full prompt/plan/result content. Any other profile stores metadata only: stage, tool name, status, latency, token counts, validity flags. No text, no amounts, no arguments.
- "Delete all data" button -> `DELETE /api/data` wipes the user profile.
- Backend binds 127.0.0.1; CORS limited to `http://localhost:3000`; no telemetry; no remote assets. A pytest fixture blocks non-loopback sockets during the full pipeline test.
- The browser must not persist financial data (no localStorage/IndexedDB).

## 11. Evaluation architecture

Detailed in `TEST_PLAN.md`. Summary: the harness calls the **same** `extract`, `plan`, `execute`, `narrate` functions as production against 25 synthetic cases (`eval/cases.jsonl`), pins model digests, runs at temperature 0, and writes `eval/results/<run>/{results.json,results.md,raw/}` and a generated `docs/DECISION.md`. Metrics: tool-call correctness, scenario interpretation accuracy, numerical consistency, latency, CPU/memory, failure cases. Eval **ladder** (L0..L3) lets us cut scope safely.

## 12. Real-user handover (evidence capture)

Handover mode (`STRETCH_HANDOVER=1` or `?handover=1`): start screen offers **"Use sample data"** or **"Enter my own numbers"** (his choice). Banner: "Session mode: nothing is saved." A "Clear session" button wipes memory. No in-app feedback storage; the human records observations manually per `handover/HANDOVER_PROTOCOL.md`. His real numbers never reach Git, screenshots, logs, traces, Sentry, README, the article, or any agent prompt. Only his consented reaction may be reported, verbatim, and the article must not claim the tool "solved" anything.

## 13. Optional adapters

- **Gemma:** only a `models.yaml` row plus eval results. Claim rule is in `ACCEPTANCE_CRITERIA.md` section 6.
- **Sentry (P2, time-gated):** implements the `Tracer` interface in `adapters/sentry/`; optional extra; activates only if `STRETCH_ENV=eval` and a DSN are set **and** profile is `demo`; refuses to start otherwise; PII off; synthetic content only; **never** a dependency of the shipped app. Attempt only if every P0 item is green; hard stop at the time-box in `IMPLEMENTATION_PLAN.md`. Fallback is `LocalJsonlTracer` (the default). **VERIFY** Sentry's agent-tracing docs first; the integration route for a local model is unknown.

## 14. Frontend / backend boundary

**Frontend** (Next.js App Router, TypeScript, Tailwind, recharts; talks only to FastAPI):
1. Setup: paste-text box + "or enter manually" form + (demo profile only) "Load sample data".
2. **Confirmation card:** editable fields, `grounded` flags, unresolved/missing fields highlighted, "must pay?" toggle per commitment, resolved dates shown.
3. **Dashboard:** one chart (balance over time, a line per scenario, shortfall markers), five preset scenario cards (runs out on / days / gap), a safe-spend card, a reserve card. Always from engine output.
4. **Ask bar** with a visible 6-step ribbon (driven by the real staged endpoint responses).
5. **Trace panel** (basic is P0, polish is P1): collapsible JSON per step: question, model plan, validation checks, engine calls (inputs/outputs), numbers registry, narration + verification status.
6. Banners: LLM down (manual mode), session mode, synthetic data label.

**Backend** endpoints are staged so the UI can show real progress without SSE. See `API_CONTRACT.md`.

## 15. Recommended stack

Python 3.11+, FastAPI, pydantic v2, uvicorn, httpx, pytest, hypothesis, psutil, pyyaml. Next.js + TypeScript + Tailwind + recharts. SQLite (stdlib). Ollama. Docker optional (not required for MVP). **No LangGraph** (not needed for a one-step plan; do not add it).

## 16. Failure handling

| Failure | Behaviour |
|---|---|
| Model server down / `STRETCH_LLM=off` | banner, manual path, presets, template narration |
| Invalid JSON / schema violation | one repair attempt, then templated clarifying question |
| Timeout | cancel; fall back to presets/forms; show why |
| Ungrounded amount | highlighted on confirmation card, never silently accepted |
| V3 fails twice | template narration labelled as such |
| Engine error | shown as an error; never narrated by the LLM |
| Out-of-scope question | fixed refusal from code |
| Corrupt DB | back up the file, reinitialise |

## 17. MVP boundary

**P0:** engine + tests; manual path; text extraction + confirmation card; scenario calculations; dashboard; model -> plan -> tools -> engine pipeline with basic trace panel; V1-V3 + template narration; demo seed; fallback test; README + working demo.
**P1:** 3-model benchmark; 25-case eval; LLM narration; `propose_update` logging; polished trace panel; CI.
**P2:** Sentry; SSE; UI polish.
**Cut order if behind:** P2 -> polished trace -> logging -> LLM composer -> 3-model benchmark -> reduce eval cases -> chart polish. **Never cut:** engine and tests, confirmation card, V1-V3, the manual fallback.

## 17b. Risks

| Risk | Mitigation |
|---|---|
| Small models give unreliable plans | constrained JSON, one repair, L0 checkpoint, manual path as the fallback |
| CPU latency | compact prompts, warm-up, staged endpoints, template narration |
| Extraction errors | grounding + human confirmation card |
| Eval competes with dev for CPU | run final benchmark on an idle machine only |
| Quota exhaustion | slice prompts; frontend work goes to Freebuff |
| Over-claiming | fixed badge wording; claims limited to measured/tested facts |
