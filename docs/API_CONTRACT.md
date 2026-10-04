# API_CONTRACT — Stretch

Backend: FastAPI on `127.0.0.1:8000`. JSON only. All amounts are integers. All dates are ISO `YYYY-MM-DD`. Concrete examples live in `fixtures/*.json` (all synthetic). If you must deviate from this contract, **flag it to the human instead of changing it silently**; the frontend (a different agent) builds against it.

## 1. Shared types

```ts
DateExpr = {kind:"iso", value:string} | {kind:"in_days", n:number}
         | {kind:"day_of_month", day:number, month_offset:0|1|null}

Situation = { synthetic?:boolean, as_of:string, currency:string, balance:number,
  essentials_per_day:number,
  inflows:[{id,label,expected_amount,expected_date,uncertainty_note:string|null}],
  commitments:[{id,label,amount,due_date,flexible:boolean}],
  horizon_days:number /*default 60*/, buffer_days:number /*default 3*/ }

InflowAdjustment = { inflow_id:string|"*", delay_days:number|null, new_date_expr:DateExpr|null,
  amount_factor:number|null, new_amount:number|null, cancelled:boolean }
Expense = { label:string, amount:number, date_expr:DateExpr|null }   // null = as_of
ScenarioSpec = { label:string, adjustments:InflowAdjustment[], extra_expenses:Expense[] }

RunwayResult = { runway_days:number, covered_through_horizon:boolean, runs_out_on:string|null,
  shortfall_amount:number|null, next_money_after_shortfall:string|null, gap_days:number|null,
  inflows_applied:[{id,date,amount}], horizon_days:number, series:number[] }
SafeSpendResult = { inflow_today:boolean, target_date:string|null, days_to_cover:number,
  max_daily_total:number|null, headroom:number|null, covers_essentials:boolean, already_short:boolean }
ReserveResult = { days_to_next_money:number, buffer_days:number, essentials_part:number,
  must_pay_part:number, reserve:number, covered:boolean, surplus_or_gap:number }
AffordabilityResult = { verdict:"fits"|"shortens_runway"|"breaks_before_next_money"|"already_short",
  runway_before:number, runway_after:number, days_lost:number,
  runs_out_before:string|null, runs_out_after:string|null, next_money_date:string|null }

NumberEntry = { path:string, value:number|string, type:"money"|"days"|"date"|"int" }
ToolResult = { tool:string, args:object, ok:boolean, error:string|null, result:object|null, numbers:NumberEntry[] }
TraceStep = { step:"interpretation"|"tool_plan"|"validation"|"engine_call"|"verification"|"explanation"|"extraction",
  label:string, ms:number, payload:object }   // payload content is returned to the browser only; never persisted outside the demo profile

Plan = { tool_calls:[{tool:string,args:object}] } | { clarify:string } | { refuse:"out_of_scope" }
```

**Tool names (allowlist):** `compute_runway`, `compare_scenarios`, `safe_daily_spend`, `check_affordability`, `essentials_reserve`, `propose_update` (P1).

**Error shape (all non-2xx):** `{ "error": { "code": string, "message": string, "fallback": "manual"|null } }`.
Codes: `llm_unavailable` (503, `fallback:"manual"`), `llm_timeout` (504, `fallback:"manual"`), `invalid_request` (422), `invalid_date`, `conflicting_adjustment`, `unknown_inflow`, `out_of_bounds` (422), `no_situation` (409), `profile_forbidden` (403), `internal` (500).

## 2. Modes (env)

| Env | Values | Effect |
|---|---|---|
| `STRETCH_PROFILE` | `demo` (default in dev) / `user` | `demo` allows the sample-data endpoint and full-content traces |
| `STRETCH_PERSIST` | `1` / `0` | `0` = in-memory only, nothing written |
| `STRETCH_HANDOVER` | `1` | forces profile `user`, `PERSIST=0`, metadata-only traces, session banner |
| `STRETCH_LLM` | `on` (default) / `off` | `off` forces manual fallback mode |
| `STRETCH_MODEL` | model id from `models.yaml` | default model for all stages |
| `STRETCH_ENV` | `dev` / `eval` | only `eval` + `demo` may activate the optional Sentry adapter |

## 3. Endpoints

### `GET /api/health`
```json
{ "status":"ok",
  "llm":{"state":"up|down|disabled","runtime":"ollama","model":"<id>|null","detail":"<short reason or null>"},
  "mode":{"profile":"demo|user","persist":true,"handover":false},
  "has_situation":false, "version":"0.1.0" }
```

### `POST /api/setup/extract` (LLM path)
Request `{ "text": string, "as_of"?: string }` (default `as_of` = server today; fixtures pin `2026-10-05`).
Response `SituationDraft` + `trace[]`. See `fixtures/extract_demo.json`.
```ts
SituationDraft = { as_of, balance:{value:number|null,grounded:boolean,source_text:string|null},
  essentials_per_day:{value:number|null,grounded:boolean,source_text:string|null,
                      converted_from:{amount:number,period:"week"|"month"}|null},
  inflows:[{id, label, expected_amount:{value:number|null,grounded,source_text},
            expected_date:{value:string|null,date_expr:DateExpr|null,grounded,source_text},
            uncertainty_note:string|null}],
  commitments:[{id, label, amount:{...}, due_date:{...}, flexible:boolean|null}],
  missing:string[],   // e.g. "essentials","inflow[0].amount","inflow[0].date","commitment[1].date"
  warnings:string[] }
```
Model output contract (S1, constrained JSON; **no computed values**):
```json
{ "balance": 26000, "essentials": {"amount":1500,"period":"day"},
  "inflows":[{"label":"","expected_amount":20000,"date_expr":{"kind":"day_of_month","day":15,"month_offset":null},"uncertainty_note":null}],
  "commitments":[{"label":"","amount":12000,"date_expr":{...},"flexible":null}] }
```
Unknown values are `null`, never guessed. IDs are assigned by code in order of appearance (`inflow_1..`, `commit_1..`).
Failure: 503 `llm_unavailable` / 504 `llm_timeout` with `fallback:"manual"`.

### `POST /api/setup/manual` (no-LLM path)
Request:
```json
{ "as_of":"2026-10-05"?, "balance":26000, "essentials":{"amount":1500,"period":"day"},
  "inflows":[{"label":"Aunt","expected_amount":20000,"date_expr":{"kind":"iso","value":"2026-10-15"},"uncertainty_note":null}],
  "commitments":[{"label":"Outfit","amount":12000,"date_expr":{"kind":"iso","value":"2026-10-21"},"flexible":true}] }
```
Response: `SituationDraft` (all `grounded:true`, `source_text:null`) so the **same confirmation card** is used.

### `PUT /api/situation` / `GET /api/situation`
`PUT` body = confirmed `Situation` (validated: dates >= `as_of`, amounts >= 0, essentials > 0). Returns the stored `Situation`. `GET` returns it or 409 `no_situation`.

### `POST /api/situation/demo`
Loads `fixtures/situation_demo.json` (synthetic). Profile `demo` only, else 403 `profile_forbidden`. The UI labels it "SAMPLE DATA".

### `POST /api/runway/scenarios` (never calls the LLM)
Request `{ "scenarios"?: ScenarioSpec[], "buffer_days"?: number }` (default = five presets). Response:
```json
{ "results":[{"scenario":ScenarioSpec,"result":RunwayResult}],
  "safe_spend":SafeSpendResult, "reserve":ReserveResult, "assumptions":["..."] }
```
See `fixtures/runway_presets_demo.json`.

### `POST /api/ask/plan`
Request `{ "question": string }`. Response:
```json
{ "plan":Plan,
  "validation":{"ok":true,"checks":["schema","tool_allowlist","bounds","inflow_ids","grounding"],"errors":[],"repaired":false},
  "model":{"id":"...","prompt_tokens":0,"completion_tokens":0,"total_ms":0},
  "trace":[TraceStep] }
```
`{clarify}` and `{refuse}` plans are returned as-is (refusal text is a fixed string from code, returned in `trace` and by the UI). Failure: 503/504 as above (`fallback:"manual"`). See `fixtures/ask_demo_plan.json`.

### `POST /api/ask/execute` (never calls the LLM)
Request `{ "plan": Plan }` (only `tool_calls` plans executable). Response `{ "results": ToolResult[], "trace": TraceStep[] }`. Calls the registry only; unknown tools -> 422. See `fixtures/ask_demo_execute.json`.

### `POST /api/ask/narrate`
Request `{ "question": string, "results": ToolResult[] }`. Response:
```json
{ "mode":"template|llm", "narration":"...",
  "verification":{"status":"verified|failed","checked_numbers":[],"unmatched":[],"badge":"numbers verified against the engine"|null},
  "regenerated":false, "model":{...}|null, "trace":[TraceStep] }
```
P0 always returns `mode:"template"`. P1 adds the LLM composer, V3 gate, one regeneration, then template fallback. The `badge` text is fixed; UI shows "template answer" when `mode:"template"`. See `fixtures/ask_demo_narrate.json` and `fixtures/v3_failure_example.json`.

### `POST /api/ask/direct` (fallback path, no LLM)
Request `{ "tool": "compute_runway|safe_daily_spend|check_affordability|essentials_reserve", "args": object }` using the same args as the plan. Response `{ "results": ToolResult[] }`. Powers preset buttons and the manual "can I afford X?" form when the LLM is down.

### `DELETE /api/data`
Wipes the stored situation and (user profile) any stored events. `204`.

## 4. Numbers registry rules (for V3)

Each tool adds entries for every number or date it returns that may appear in prose (`runway_days`, `runs_out_on`, `shortfall_amount`, `gap_days`, each `inflows_applied[k].date/amount`, deltas, `max_daily_total`, `headroom`, `reserve`, `surplus_or_gap`, `days_lost`, `runs_out_before/after`). V3 allows a token if it matches: a registry value, any integer or day/month of a registry date, any integer in the situation or question. Normalize `1,500`, `1.5k`, `₦`, `Oct 21` forms before comparing. Digits-only tokens are checked; spelled-out numbers are discouraged by the composer prompt.

## 5. Fixtures index

`situation_demo.json`, `situation_two_inflows.json` (inputs) · `extract_demo.json` · `runway_presets_demo.json` · `ask_demo_plan.json` · `ask_demo_execute.json` · `ask_demo_narrate.json` · `v3_failure_example.json` · `engine_golden.json` (runway, safe-spend, reserve, affordability, date resolution, essentials conversion, validation errors). **Fixtures were generated by a throwaway script that followed `ARCHITECTURE.md` section 6.** The real engine must reproduce them; investigate disagreements by hand.
