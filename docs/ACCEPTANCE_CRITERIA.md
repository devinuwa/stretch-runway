# ACCEPTANCE_CRITERIA — Stretch

Every item is checkable by running something or looking at something. "Evidence" means pasted command output, a file in the repo, or a screenshot of **synthetic** data.

## 1. P0 (all required)

| # | Criterion | Evidence |
|---|---|---|
| P0-1 | **Engine** implements `ARCHITECTURE.md` s6 exactly (day semantics, date resolution, floor on factors, safe-spend, reserve, affordability verdicts) | engine tests |
| P0-2 | **Engine tests** pass: all cases in `fixtures/engine_golden.json`, property tests (delay/shrink/cancel/expense never extend runway), validation-error cases, import-purity test | `pytest` output |
| P0-3 | **Setup/extraction**: demo paragraph (`fixtures/extract_demo.json`) produces the expected draft with `grounded:true` on all values; unknown values are `null` and listed in `missing`; weekly/monthly essentials converted by **code** | test + live run |
| P0-4 | **Confirmation card**: every extracted field editable; ungrounded or missing fields visibly highlighted; resolved dates shown; per-commitment "must pay?" toggle; nothing reaches the engine until the user confirms | screenshot (synthetic) |
| P0-5 | **Scenario calculations**: five presets plus custom scenarios match golden values; results shown as "runs out on / days / gap", never as predictions | API test + screenshot |
| P0-6 | **Dashboard**: one chart with a line per scenario and shortfall markers, safe-spend card, reserve card, labelled "SAMPLE DATA" when synthetic; works with no LLM | screenshot |
| P0-7 | **Pipeline**: question -> model plan JSON -> V2 -> tool registry -> engine -> result, using a local model; the demo question `What if the money comes 5 days late and is only half the amount?` yields a valid plan (`compare_scenarios` or `compute_runway` with `delay_days:5, amount_factor:0.5`) and the exact engine numbers in `fixtures/ask_demo_execute.json` (runs out Oct 21 after 16 days vs Oct 26 after 21 days) | live run + trace |
| P0-8 | **Basic trace panel** shows all 6 steps with real payloads: interpretation (model plan), tool plan, validation checks, engine call inputs/outputs, verification, explanation | screenshot |
| P0-9 | **Verification**: V1 flags ungrounded amounts; V2 rejects bad plans (bounds, unknown ids, tool not in allowlist, conflicting adjustments) with one repair attempt; V3 rejects narration containing numbers not in the registry (`fixtures/v3_failure_example.json` fails; `ask_demo_narrate.json` passes); template narration always passes | tests |
| P0-10 | **Out-of-scope** questions (e.g. loans/crypto) get the fixed refusal from code; ambiguous ones (`a bit late`) get a clarifying question, not a guess | tests |
| P0-11 | **Manual fallback**: with `STRETCH_LLM=off` (and with Ollama stopped), manual form -> confirmation -> dashboard -> presets -> direct "can I afford X?" form works end to end, with identical engine output | automated E2E test |
| P0-12 | **Demo seed**: one click loads the synthetic situation; labelled synthetic | screenshot |
| P0-13 | **README** lets a fresh clone run it (PowerShell commands), documents privacy model, limits, model + license, third-party credits, AI-assistance disclosure, "Post-deadline commits" section, and does not overclaim | fresh-clone run |
| P0-14 | **Working demo** executes the 30-second story below, live, on the CPU laptop | recording |

## 2. Privacy and data (all required)

| # | Criterion | Evidence |
|---|---|---|
| PR-1 | Backend binds `127.0.0.1` only; CORS only `http://localhost:3000` | config + test |
| PR-2 | Socket-block test: full pipeline (LLM stubbed or loopback Ollama) makes **zero non-loopback connections** | pytest |
| PR-3 | No telemetry, no CDN assets or fonts, no analytics; `NEXT_TELEMETRY_DISABLED=1` documented | build output / grep |
| PR-4 | `.gitignore` covers `.env`, `data/`, `handover/private/`, `*.db`, `*.log`, model files; `git ls-files` shows none of them | command output |
| PR-5 | All fixtures contain `"synthetic": true` where applicable; a test fails if a fixture lacks it | pytest |
| PR-6 | In handover/user profile: in-memory only, metadata-only traces (a test asserts no amounts/text in the trace file) | pytest |
| PR-7 | No browser persistence of financial data (no localStorage/IndexedDB usage) | grep + review |
| PR-8 | No real personal data in any agent prompt, commit, screenshot, README or article | human + Claude review |

## 3. Honest-claims criteria

- The UI badge text is exactly **"numbers verified against the engine"** and only appears when V3 passed; template answers say **"template answer"**.
- No probability, no "you will", no financial advice in any narration template.
- README/article claims about accuracy, latency, CPU/memory come **only** from `eval/results/*` files. If L1/L2/L3 were not run, the README says so.
- The README states the pipeline is a **constrained tool-calling pipeline**, not an open-ended agent loop.

## 4. P1 (only after all P0 is green)

| # | Criterion |
|---|---|
| P1-1 | Eval L1 completes: `results.json` + `results.md` with the metrics in `TEST_PLAN.md` s6 |
| P1-2 | Eval L2 completes with pinned model digests; `docs/DECISION.md` generated by the harness applying the pre-registered rule |
| P1-3 | LLM composer passes V3 (or falls back) and reports its raw V3 pass rate |
| P1-4 | `propose_update` stages a change that **only** applies after UI confirmation |
| P1-5 | Trace panel is readable in a 30-second screen recording |
| P1-6 | CI runs `pytest` and `npm run build` |

## 5. P2 (only if the human asks)

Sentry (dev/eval only, demo profile only, never a dependency), SSE, UI polish. If Sentry is not done by its time-box, the criterion is "local JSONL trace shown instead" and nothing else changes.

## 6. Gemma category claim (all must hold, otherwise **do not claim**)

1. The Gemma row exists in `models.yaml` with pinned tag/digest and license link.
2. Gemma was run on the same cases as at least two other families (L2, or a reduced L2 of >= 12 cases stated up front).
3. `docs/DECISION.md` (generated by the harness) selects Gemma for at least one shipped stage, **or** documents a concrete shipped role for it that the final app really uses.
4. The README/article state the Gemma license terms accurately and report Gemma's actual scores, including where it lost.
5. If any condition fails: Gemma is still reported in the eval table, but the Prize Categories section lists nothing for Gemma.

## 7. The 30-second demo story (acceptance script)

Synthetic data, labelled on screen.

| Time | On screen | Must be true |
|---|---|---|
| 0-5 s | Title + one line: "For my roommate, money comes in bits. The scary part is not knowing when the next bit lands." | no numbers about him |
| 5-12 s | Messy paragraph pasted -> **confirmation card** shows what the local model understood | all values grounded; he/you confirm |
| 12-20 s | Dashboard: runway under on time / late / half / late+half / never, outfit date visible | numbers equal `runway_presets_demo.json` |
| 20-26 s | Ask: "What if the money comes 5 days late and is only half the amount?" -> **ribbon** steps through interpretation -> structured tool call -> deterministic engine -> result -> verified numbers; trace panel shows the real plan JSON | numbers equal `ask_demo_execute.json` (Oct 21 / 16 days vs Oct 26 / 21 days) |
| 26-30 s | "Runs offline on a laptop CPU. Nothing leaves the machine." | the claim is tested (PR-2) |

If the roommate really tried it and reacted, a cut to his genuine reaction may follow **only if it happened and he consented**. Latency: show the real wait or label the recording as sped up.
