# CODING_AGENT_PROMPT — Stretch

How to use: copy the package into the new repo (see s1), then paste **Prompt A0** into Antigravity. After each reply, bring me (Claude) the agent's report block and the key output; I review and write the next slice. Slice prompts below are pre-written so you do not have to wait for me, but I still review every gate. **Never paste real personal data into any agent.**

## 1. Repo setup (human, 3 minutes)

```powershell
mkdir stretch-runway; cd stretch-runway
mkdir docs, fixtures, handover, backend, frontend
# copy files from the package:
#   AGENTS.md                       -> repo root
#   ARCHITECTURE.md, API_CONTRACT.md, IMPLEMENTATION_PLAN.md,
#   ACCEPTANCE_CRITERIA.md, TEST_PLAN.md, CODING_AGENT_PROMPT.md -> docs/
#   fixtures/*                      -> fixtures/
#   eval/*                          -> backend/eval/
#   handover/*                      -> handover/
```
Do **not** `git init` yourself if you want Antigravity to do T0; either is fine, but the **first commit must happen now, inside the challenge window**. Do not run `git config --global`.

## 2. Prompt A0 (Antigravity) — kickoff: T0 + T1 + T2

```
You are the implementation agent for "Stretch", a local-first financial runway tool for a student with
irregular income. Read these files in order and obey them: AGENTS.md, docs/ARCHITECTURE.md,
docs/API_CONTRACT.md, docs/IMPLEMENTATION_PLAN.md, docs/ACCEPTANCE_CRITERIA.md, docs/TEST_PLAN.md.
AGENTS.md overrides everything except my explicit instructions in this session.

Environment: Windows + PowerShell, CPU-only laptop. Python 3.11+, Node LTS.

TASK T0 (scaffold, keep it fast):
1. GitHub identity check, READ-ONLY: run `git config --global user.name`, `git config --global user.email`,
   `gh auth status`. The account must be `devinuwa`. If it is not, STOP and tell me. Do not change global
   git config or any credentials.
2. Create the layout from ARCHITECTURE.md/AGENTS.md: backend/stretch/{engine,tools,verify,llm,pipeline,store,trace,adapters,api},
   backend/tests, backend/eval (already has cases.jsonl, situations.json), frontend (leave empty; another agent builds it),
   docs/, fixtures/, handover/. Add .gitignore (must cover .env, data/, handover/private/, *.db, *.log, .venv, node_modules, .next, model files),
   LICENSE (MIT), README.md stub, THIRD_PARTY.md stub, docs/PROVENANCE.md.
3. Create backend/.venv, a pinned requirements file (fastapi, uvicorn, pydantic>=2, httpx, pytest, hypothesis, psutil, pyyaml).
   Check current versions; do not guess.
4. `git init` if needed, make the first commit, and write its UTC timestamp into docs/PROVENANCE.md.
5. Do NOT create the remote or push. Ask me first.

TASK T1 (engine): implement backend/stretch/engine per ARCHITECTURE.md section 6, stdlib only. Files: dates.py,
models.py (dataclasses), scenario.py, runway.py, safe_spend.py, reserve.py, affordability.py. Expose a small public API.

TASK T2 (engine tests): write backend/tests/test_engine_*.py: golden tests from fixtures/engine_golden.json,
hypothesis property tests, validation-error tests, and an AST purity test (TEST_PLAN.md section 1). Run pytest.
If a golden case disagrees with your engine, derive it by hand day by day, show me both numbers, and do not edit
the fixture until I say so.

Rules: small steps, run the tests, paste the real output. Do not implement anything beyond T0-T2. Do not add
features or dependencies not listed. Report in the AGENTS.md section 8 format.
```

## 3. Prompt F0 (Freebuff) — start at the same time: T6 frontend against fixtures

Give Freebuff **only** `docs/API_CONTRACT.md`, `docs/ARCHITECTURE.md` section 14, and the `fixtures/` folder. No backend code. No real data.

```
Build the frontend for "Stretch" in /frontend using Next.js (App Router), TypeScript, Tailwind and recharts.
It talks only to a FastAPI backend at http://127.0.0.1:8000 as specified in docs/API_CONTRACT.md. The backend does not
exist yet: implement a typed API client plus a MOCK layer (switch via NEXT_PUBLIC_MOCK=1) that serves the JSON files in
/fixtures. Copy the fixtures you need into frontend/mocks/ (they are synthetic).

Constraints: no localStorage/IndexedDB or any browser persistence of financial data; no CDN assets, remote fonts or
analytics (set NEXT_TELEMETRY_DISABLED=1); no auth; no extra libraries beyond next, react, tailwind, recharts.
Windows/PowerShell instructions only.

Build in this order, one step per commit-sized chunk, running `npm run build` after each:
1. Scaffold + typed client for every endpoint + mock layer. Types mirror API_CONTRACT.md "Shared types".
2. Setup screen: paste-text box, "or enter manually" form, "Load sample data" button (visible only if /api/health reports profile demo).
3. Confirmation card: editable fields from SituationDraft, highlight grounded:false and missing fields, per-commitment "must pay?" toggle, resolved dates, Confirm button -> PUT /api/situation.
4. Dashboard: one recharts line chart (balance series per scenario, a marker where the balance first goes below zero), five preset scenario cards (runs out on / runway days / gap), a safe-spend card and a reserve card. Label "SAMPLE DATA" when situation.synthetic is true.
5. Ask bar with a 6-step ribbon: interpretation -> tool call -> validation -> engine -> verification -> explanation. The ribbon must advance from REAL staged responses (/api/ask/plan, /execute, /narrate), not a fake timer. Show the narration with the badge exactly as the API returns it ("numbers verified against the engine", or "template answer").
6. Basic trace panel: collapsible JSON per TraceStep.
7. Banners: LLM unavailable (health.llm.state != "up") -> hide the ask bar and show preset buttons + a "Can I afford X?" form calling /api/ask/direct; session mode (mode.handover) -> "Session mode: nothing is saved" + a "Clear session" button calling DELETE /api/data.

Tone/UX rules: never present results as predictions ("you will run out"); phrase as "if the money arrives ..., your money runs out on ...".
Do not implement features not listed. Report what you built, `npm run build` output, and any contract deviation you need.
```

## 4. Slice prompts for Antigravity (after A0 is green and I have confirmed G1)

**A1 — T3 + T4 + T5 (deterministic API, no LLM):**
```
Read AGENTS.md and docs/API_CONTRACT.md. Implement T3 (tool registry, executor, numbers registry; the demo plan in
fixtures/ask_demo_plan.json must produce fixtures/ask_demo_execute.json), T4 (store: SQLite or in-memory per STRETCH_PERSIST;
modes per API_CONTRACT section 2; Tracer + LocalJsonlTracer, metadata-only outside the demo profile), and T5 (endpoints:
/api/health, /setup/manual, /situation GET+PUT, /situation/demo, /runway/scenarios, /ask/direct, /ask/execute, template
/ask/narrate with the V3 check, DELETE /api/data). The server binds 127.0.0.1 and allows CORS only for http://localhost:3000.
Write the tests in TEST_PLAN.md sections 2 and 3 (except LLM-dependent ones). Do not touch the engine; if it must change, tell me why first.
Report with the AGENTS.md section 8 format and paste pytest output.
```

**A2 — T7 + T8 + T9 (model layer, extraction, planning):**
```
Read AGENTS.md, docs/ARCHITECTURE.md sections 3-5 and 8, docs/API_CONTRACT.md. First VERIFY against current Ollama docs
(a) the structured-output (JSON schema "format") API of the installed Ollama version, (b) the exact model tags I have pulled
(`ollama list`). Implement T7: ModelAdapter protocol, OllamaAdapter over httpx with timeouts and warm-up, StubModelAdapter,
backend/eval/models.yaml (candidate rows only; Gemma is just a row), /api/health llm state. Then T8: extractor S1 (constrained
JSON, ExtractionOutput exactly as in API_CONTRACT), V1 grounding, date resolution and essentials conversion in code,
/api/setup/extract. Then T9: planner S2 with compact context (as_of, inflow ids+labels, commitment ids+labels), the Plan union,
V2 with ONE repair attempt, clarify/refuse handling (refusal text fixed in code), /api/ask/plan. Prompts live in
backend/stretch/pipeline/prompts/ as versioned files; few-shot examples must NOT be copied from backend/eval/cases.jsonl
(a test enforces it). The model must never output computed values. Run the L0 smoke cases (E01, Q01, Q02, X02) against the
real local model and paste raw outputs and timings, including failures. Do not start the eval harness yet.
```

**A3 — T12 + T13 (fallback test, README):**
```
Implement the fallback E2E test (TEST_PLAN s3) and the socket-block test, then write README.md per ACCEPTANCE_CRITERIA P0-13
(PowerShell commands; privacy model; limits; model + license placeholders to be filled from docs/DECISION.md or marked
"not yet measured"; THIRD_PARTY.md; AI-assistance disclosure: built with Antigravity (and Freebuff where used); a
"Post-deadline commits" section that is empty for now). Do not claim any accuracy or latency number that is not in
eval/results. State plainly that the pipeline is a constrained tool-calling pipeline, not an open-ended agent loop.
Verify by running the README steps from a fresh clone in a temp folder.
```

**A4 — P1 only after I confirm P0 is green: T20 eval harness (L0 -> L1 -> L2), then T21 composer:**
```
Read docs/TEST_PLAN.md sections 6-8. Implement `python -m eval.run` and `python -m eval.decide` exactly as specified:
same production functions, temperature 0, pinned digests, results.json/results.md/raw, the scoring and normalization rules,
psutil sampling on the Ollama process tree (verify process detection on Windows; fall back to system-wide numbers and say so).
Run L1 for the default model first and paste results.md. Run L2 only when I say the machine is idle. Never edit numbers by hand.
```

## 5. Reporting protocol

Every agent reply must end with the AGENTS.md section 8 block. When you bring results to me, paste: the block, the exact commands run, and key output lines (test summary, health JSON, trace JSON for `Q01`). I will tell you whether to proceed, fix, or cut.

## 6. If an agent runs out of quota

Antigravity first, Freebuff second. Freebuff may take over **frontend, README and docs**. Engine, verification and eval code stay with the strongest available agent, and I review any engine diff against the golden cases. Never hand either agent private data.
