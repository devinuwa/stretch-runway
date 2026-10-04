# IMPLEMENTATION_PLAN — Stretch

Clock times assume **T0 = 6:00 PM WAT**. If the real start differs, shift everything by the same offset. The human's **hard cutoff is 3:00 AM WAT**; the official 7:59 AM WAT deadline is an emergency buffer only. Prayer breaks (about 10 minutes each) are absorbed by the gate buffers.

## 1. Dependency graph

```
T0 repo+env ─────────────┬──────────────────────────────────────────────┐
(human: Ollama install,   │                                              │
 model pulls start now)   ▼                                              ▼
                         T1 ENGINE ──► T2 ENGINE TESTS [G1]          T6 FRONTEND vs FIXTURES (Freebuff)
                           │                │                            │
                           ▼                ▼                            │
                         T3 TOOLS+registry  T4 STORE+modes+tracer        │
                           │   │            │                            │
                           │   └────┬───────┘                            │
                           │        ▼                                    │
                           │      T5 API: manual setup, situation,       │
                           │         runway/scenarios, ask/direct,       │
                           │         template narration, V3  [G2]        │
                           │        │                                    │
 T7 MODEL LAYER (needs T0 Ollama) ──┤                                     │
   │                                │                                     │
   ▼                                ▼                                     │
 T8 EXTRACTOR S1 + V1 ──► T9 PLANNER S2 + V2 + executor                   │
        │                          │                                      │
        └──────────────┬───────────┘                                      │
                       ▼                                                  ▼
                     T10 INTEGRATION (frontend <-> real API, confirmation card, ask ribbon, basic trace) ◄─┘
                       │
                       ▼
        T11 DEMO SEED + sample-data button ─► T12 FALLBACK E2E TEST (LLM off) ─► T13 README + working demo [G3]
                                                             │
        ─────────── P0 COMPLETE ─────────────────────────────┘
        P1: T20 eval L0 -> L1 -> L2 -> L3 | T21 LLM composer | T22 propose_update | T23 trace polish | T24 CI
        P2: T30 Sentry | T31 SSE | T32 UI polish
```

**Critical path (P0):** T1 -> T2 -> T3 -> T5 -> T9 -> T10 -> T12 -> T13, with T7/T8 feeding T9. Anything on this path slipping moves the demo date.

**Parallel lanes:**
- Lane A (Antigravity): T0 scaffold -> T1 -> T2 -> T3 -> T4 -> T5 -> T7 -> T8 -> T9.
- Lane B (Freebuff): T6 frontend against fixtures (no backend needed). Starts at the same time as T1.
- Lane C (human, no agent): Ollama install and model pulls; roommate questions already done; handover scheduling; `handover/` prep; start a draft article skeleton with me (Claude) here.

**Cuttable (in this order, first to go first):** P2 everything -> trace polish -> `propose_update` -> LLM composer -> L3 resource sampling -> L2 (3-model run reduced to fewer cases) -> L1 (reduced case count) -> chart polish. **Never cut:** T1, T2, T3, T5 (incl. V3 + template narration), the confirmation card, T8/T9 V1/V2, T12 fallback, T13.

**First thing Antigravity implements:** T0 scaffold (10 minutes) then **T1 + T2 together: the engine and its golden/property tests**, in that order, before anything else.
**First thing Freebuff implements:** T6 step 1: Next.js scaffold + a typed API client that serves **fixtures** from a mock layer, then the confirmation card and dashboard against `fixtures/situation_demo.json`, `extract_demo.json`, `runway_presets_demo.json`.
**Human first actions (now):** install Ollama; ask Antigravity (T0) to verify current candidate model tags, then start the downloads; confirm the GitHub identity check passes.

## 2. Task list

| ID | Task | Owner | Depends on | Priority | Done when |
|---|---|---|---|---|---|
| T0 | Repo scaffold (in-window), `.gitignore`, venv, package files, `docs/` copy of this package, `docs/PROVENANCE.md` with first-commit UTC time, GitHub identity check (read-only) | Antigravity | none | P0 | `pytest` runs (even empty), `npm run dev` boots, first commit made |
| T1 | Engine: `dates`, `models` (dataclasses), `scenario`, `runway`, `safe_spend`, `reserve`, `affordability` per `ARCHITECTURE.md` s6 | Antigravity | T0 | P0 | importable, no non-stdlib imports |
| T2 | Engine tests: golden cases from `fixtures/engine_golden.json`, property tests (hypothesis), validation-error cases, purity test | Antigravity | T1 | P0 | all green **[G1]** |
| T3 | Tool registry + executor + numbers registry; arg models with bounds | Antigravity | T1 | P0 | each tool returns `ToolResult` matching `fixtures/ask_demo_execute.json` for the demo plan |
| T4 | Store (SQLite / in-memory), mode flags, `Tracer` + `LocalJsonlTracer` (metadata-only outside demo profile) | Antigravity | T0 | P0 | modes honoured by tests |
| T5 | API: `/health`, `/setup/manual`, `/situation`, `/situation/demo`, `/runway/scenarios`, `/ask/direct`, `/ask/execute`, template `narrate`, V3, `/data` | Antigravity | T3, T4 | P0 | contract tests green; the dashboard works with **no LLM** **[G2]** |
| T6 | Frontend vs fixtures: setup (text + manual), confirmation card, dashboard + chart, ask bar + 6-step ribbon (mocked), basic trace panel, banners (LLM down / session / sample data) | Freebuff | API_CONTRACT + fixtures | P0 | runs on mock layer, no backend |
| T7 | Model layer: `ModelAdapter`, Ollama adapter (verify structured-output API), `StubModelAdapter`, `models.yaml`, health, warm-up, timeouts | Antigravity | T0 + Ollama running | P0 | live health shows model; stub works in tests |
| T8 | Extractor S1 + V1 grounding + date resolution + essentials conversion; `/setup/extract` | Antigravity | T5, T7 | P0 | `E01` produces the fixture draft |
| T9 | Planner S2 + V2 + repair + clarify/refuse handling; `/ask/plan`; end-to-end ask path | Antigravity | T3, T7 | P0 | `Q01` yields the fixture plan **[L0 smoke]** |
| T10 | Integrate frontend with the real API; remove mocks behind a flag | Freebuff or Antigravity (human decides by quota) | T5, T6, T8, T9 | P0 | demo flow works live |
| T11 | Demo seed (synthetic) + sample-data button + handover mode screens | Freebuff | T10 | P0 | one-click demo |
| T12 | Fallback E2E test: adapter disabled, full manual flow | Antigravity | T5, T10 | P0 | green |
| T13 | README (setup, run, architecture, privacy, limits, THIRD_PARTY, post-deadline commits section), working demo, `docs/PROVENANCE.md` finalized | Antigravity + human review | all P0 | P0 | fresh clone runs per README **[G3]** |
| T20 | Eval harness: L0 (smoke) -> L1 (1 model x 25) -> L2 (3 models x 25) -> L3 (resource sampling, idle run) -> `DECISION.md` | Antigravity | T8, T9 | P1 | per ladder below |
| T21 | LLM composer (S3) + V3 regenerate/fallback | Antigravity | T9 | P1 | V3 pass rate measured |
| T22 | `propose_update` (log spend/inflow) with UI confirmation | Antigravity | T21 or T9 | P1 | confirm-only |
| T23 | Trace panel polish | Freebuff | T10 | P1 | readable demo |
| T24 | CI: `pytest` + `npm run build` on GitHub Actions (no Copilot claim) | Antigravity | P0 | P1 | green run |
| T30-32 | Sentry / SSE / UI polish | n/a | P0 complete | P2 | only if told |

## 3. Eval ladder (reduces scope safely)

| Level | Content | Required for |
|---|---|---|
| **L0 smoke** | 1 model x cases `E01, Q01, Q02, X02` (4 cases) | P0 item 7 (pipeline works) |
| **L1** | 1 model x all 25 cases | meaningful accuracy numbers |
| **L2** | 3 models x all 25 cases (same prompts, same run conditions) | any Gemma claim, `DECISION.md` |
| **L3** | L2 + CPU/RSS sampling + a clean idle-machine latency run | article's latency/resource claims |

If time is short, **drop levels, not the product.** A reduced L2 (3 models x >= 12 cases chosen up front and written in `DECISION.md`) is acceptable for model selection but must be stated as reduced.

## 4. Gates and clock (T0 = 6:00 PM)

| Time | Work | Gate |
|---|---|---|
| 6:00-6:30 | T0 scaffold; human installs Ollama; verify tags, start pulls | repo exists; downloads running |
| 6:30-8:30 | T1+T2 (Antigravity); T6 steps 1-3 (Freebuff) | **G1 8:30:** engine tests green |
| 8:30-9:30 | T3, T4, T5 | dashboard works with no LLM |
| 9:30-10:30 | T7, T8, T9; L0 smoke | **G2 10:30: P0 check** (see below) |
| 10:30-11:30 | T10, T11, T12; start L1 in the background only if CPU is idle enough; T21 if on schedule | integrated demo works |
| 11:30 | **Sentry hard stop** (it should not have started unless everything was green at 11:00) | |
| 11:30-12:00 | T13 README, bug fixes | |
| **12:00 AM** | **FEATURE FREEZE** | only bugs, README, demo data |
| 12:00-12:30 | **Handover** to the roommate (session mode), then record the demo | reaction captured, or honestly absent |
| 12:30-1:15 | L3 idle run (if L2 done), `DECISION.md`; article draft with Claude from real evidence | |
| 1:15-2:15 | Article finalised with screenshots/results | |
| 2:15-2:45 | JUDGE ME, SUBMISSION CHECK, publish | published with margin |
| 3:00 | hard personal cutoff | |

**G2 P0 check (10:30 PM):** if L0 smoke is not green, the **manual form path becomes the primary setup**, extraction is demoted to "experimental", all P1 is suspended, and the Gemma claim is dropped. Re-judge the Relevance score honestly with Claude before continuing.

## 5. Stop adding features

1. **12:00 AM freeze** (hard). After it, no new features and no new dependencies.
2. Earlier if P0 is not green at 10:30 PM: suspend P1 immediately.
3. P2 is never started unless the human says so after every P0 item is green.

## 6. Cut rules at a glance

- Behind at G1: cut chart polish and the trace panel to JSON dumps; everything else continues.
- Behind at G2: manual-first fallback plan (s4); P1 suspended.
- No handover possible before 12:30: the article states that plainly. No reaction is invented.
- Antigravity quota exhausted: switch to Freebuff for **frontend and README only**; engine and verification code stay with the agent that has the strongest allowance, and I review every engine diff against the golden cases.
