# AGENTS.md — Stretch (repo: `stretch-runway`)

Read this file first, every session. It overrides anything in a prompt that conflicts with it, except explicit instructions from the human operator in the current session.

## 0. What we are building

**Stretch** is a local-first, privacy-first tool for a student whose money arrives in unpredictable bits. He describes his situation in plain language; a small **open-weight model running locally** turns it into structured scenarios and tool calls; a **deterministic engine** computes how long his money lasts if the next money is on time, late, smaller, or never arrives. Every number shown is checked against engine output.

It is **not**: a budgeting app, an expense tracker, a bank app, an investment/debt assistant, or an "AI financial advisor". Never add those. No bank connection, ever.

It is built for one real person (the human's roommate) for the Hacktoberfest 2026 DEV Weekend Challenge "Build for a Friend". Deadline logic: the human's **hard personal cutoff is 3:00 AM WAT**; treat it as the real deadline.

## 1. Priority order (hard)

**P0 — must work, in this order:** (1) deterministic runway engine, (2) engine tests, (3) setup/extraction flow, (4) confirmation card, (5) scenario calculations, (6) dashboard, (7) local model -> structured plan -> tools -> engine pipeline (with a basic trace panel), (8) verification of model outputs, (9) demo seed, (10) README + working demo. Also P0: the **manual fallback path** (§3 rule 5).

**P1 — only if every P0 item is green:** 3-model benchmark, 25-case eval, LLM narration, natural-language spend/inflow logging (`propose_update`), polished trace panel, CI.

**P2 — optional:** Sentry adapter, SSE, extra UI polish, anything not improving the core demo.

If the eval harness threatens a P0 item, **reduce eval scope, never ship an unfinished application.** See `IMPLEMENTATION_PLAN.md` for the eval ladder and cut rules.

## 2. Product rules

1. **The model refers, code computes.** The LLM never does arithmetic, date math, unit conversion, or invents amounts. Absolute amounts use `new_amount`; weekly/monthly essentials are sent as `{amount, period}` and converted by code.
2. **Scenarios, not forecasts.** Never predict when money will arrive. Never attach probabilities. Defaults are labelled presets.
3. **No advice.** The tool reports what happens under assumptions. Out-of-scope questions (loans, investing, "what should I do with my life") get a fixed refusal produced by code.
4. **Every number the user sees comes from the engine** (or is the user's own input echoed back). The badge "numbers verified against the engine" means only that. Never claim more.
5. **The UI must work without the LLM** (manual path -> confirmation -> engine -> dashboard -> presets).

## 3. Architecture rules (see `docs/ARCHITECTURE.md`)

1. `stretch/engine/` is **pure**: stdlib only (`datetime, math, dataclasses, typing, enum, functools`), no I/O, no LLM, no network. A test enforces this.
2. Import direction: `engine` <- `tools` <- `pipeline`; `pipeline` uses `llm`, `verify`, `store`, `trace`. `adapters/*` import `trace`/`llm` and load **only when configured**.
3. The model layer is replaceable (`ModelAdapter` protocol). Gemma is **one row in `models.yaml`**, not special code.
4. The tool interface is model-agnostic: the model emits constrained JSON; our executor runs it. No model-specific tool-calling formats.
5. **Fallback is mandatory:** with Ollama stopped or `STRETCH_LLM=off`, the manual form -> confirmation -> dashboard -> presets flow must work end to end. A test covers this.
6. Sponsor tech is optional adapters only. **No sponsor SDK in `requirements.txt`/`package.json` of the core app.** Sentry, if ever attempted, lives in `backend/stretch/adapters/sentry/` with its own optional extra and refuses to start unless `STRETCH_ENV=eval` **and** profile `demo`.

## 4. Privacy and data rules (non-negotiable)

- **Synthetic data only** for development, tests, evals, screenshots, fixtures, prompts to any coding agent, and the demo seed. All fixtures carry `"synthetic": true`.
- The roommate's real numbers (if he enters any during handover) must **never** appear in: Git, screenshots, logs, traces, Sentry, README, the article, or any agent prompt. Handover runs in **session mode** (`STRETCH_HANDOVER=1`: in-memory only, metadata-only traces).
- Do **not** paste real personal data into Antigravity, Freebuff, or any hosted tool. If you need to illustrate, use the fixtures.
- Backend binds `127.0.0.1` only. No telemetry, no CDN assets/fonts, no analytics. Set `NEXT_TELEMETRY_DISABLED=1`. The only allowed network use is pulling models/packages at setup time.
- A test blocks all non-loopback sockets while the full pipeline test runs. Keep it green.
- Never commit `.env`, `data/`, `handover/private/`, model files, or logs containing user content. Never print secrets.

## 5. Git and GitHub

- GitHub account: **`devinuwa`**. The human has already authenticated git/gh in their terminal. **Verify, do not reconfigure:**
  - Run read-only checks: `git config --global user.name`, `git config --global user.email`, `gh auth status`.
  - If the identity or logged-in account is not `devinuwa` (or checks fail), **stop and tell the human**. Do not run `git config --global`, `gh auth login`, or touch credentials, tokens, SSH keys or credential helpers.
  - Set nothing globally. If a repo-local setting is genuinely needed, set it with `git config --local` and tell the human.
- Repository: `devinuwa/stretch-runway` (human confirms the name). **Ask the human before** creating the remote, the first push, or flipping visibility. Target visibility is **public** before submission. Command once approved: `gh repo create devinuwa/stretch-runway --public --source . --remote origin` (human approves; do not add `--push` until told).
- This project must be **new and started inside the challenge window**. Do not copy or fork any older repo. Create the repo fresh. **Record the first commit's UTC timestamp** in `docs/PROVENANCE.md` (`git log --reverse --format=%cI | head -1`).
- Commit early and often with clear messages (`feat(engine): ...`, `test(engine): ...`, `docs: ...`). One logical change per commit. Commit after each green gate. Never commit failing code to `main` without saying so; use short-lived branches only if useful.
- **Any commit made after the submission deadline must be listed in the README** under "Post-deadline commits" (empty section is fine until then).
- Credit all third-party code/models/datasets in `README.md` and `THIRD_PARTY.md` with licenses. State model licenses accurately (Gemma/Llama licenses are custom, not OSI).
- Add an LICENSE (MIT) for our code; it does not relicense models.

## 6. Environment (assume Windows 10/11 + PowerShell)

- Machine: i7-8650U (4C/8T), 16 GB RAM, Intel UHD 620. **CPU-only.** No GPU, no hardware.
- Use cross-platform Python scripts. No bash-only scripts. Commands in docs must work in PowerShell.
- Python 3.11+, virtualenv in `backend/.venv`. Node LTS for the frontend. Check versions before installing.
- Ollama on `127.0.0.1:11434`. **Verify** the current structured-output API (JSON schema `format`) and model tags against Ollama docs/library before coding against them; do not rely on memory.

## 7. Workflow rules

- Work in **small, runnable, tested steps**. At each step: state assumptions, make the change, run the tests, report real output.
- **Tests first for the engine.** Golden cases are in `fixtures/engine_golden.json`; they were produced by a throwaway script, so if the real engine disagrees, **derive by hand before editing a fixture** and tell the human.
- Conserve quota: do not scan the whole repo repeatedly; do not regenerate files you were not asked to change; prefer targeted edits; no speculative refactors; no unrequested features.
- Never claim something works without running it. Paste the command and the key lines of output. If you could not run it, say so.
- Never fabricate results, metrics, screenshots, benchmark numbers, or test output. Eval numbers come only from `python -m eval.run` output files.
- If blocked, ask **one** specific question and continue with whatever is unblocked.
- Do not start P1 until the human confirms P0 is green. Do not start P2 unless the human says so.
- **Feature freeze:** when the human says "freeze", only bug fixes, README, demo-data fixes. No new features, no dependency additions.

## 8. Definition of done (per task)

1. Code + tests written, **tests pass** (paste output).
2. Matches `docs/API_CONTRACT.md` and `docs/ARCHITECTURE.md` (flag any deviation instead of silently changing a contract).
3. No secrets, no real data, no new network calls.
4. Committed with a clear message.
5. Report in this format:

```
TASK: <id>
DONE: <1-3 lines>
EVIDENCE: <commands + key output>
DEVIATIONS: <none | list>
NEXT: <suggested next task>
```

## 9. Never do

- Add an LLM-computed number anywhere. Add bank/SMS integrations. Add accounts/auth. Add cloud databases. Add analytics.
- Add a sponsor SDK to the core. Claim a sponsor category in docs unless `docs/DECISION.md` supports it.
- Use localStorage/IndexedDB for financial data (server session store or in-memory only; the UI must not persist his numbers in the browser).
- Pretend a simulated or synthetic thing is real. Label synthetic data in the UI.
- Make the demo faster by faking the model. If the UI is sped up in a recording, it must be labelled.
