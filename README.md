# Stretch

**A local-first, uncertainty-first runway tool for students whose money arrives in unpredictable bits.**

You describe your situation in plain language. A small open-weight model running on your own machine (Gemma 3 4B via Ollama) turns it into structured fields. You confirm them. A deterministic Python engine then shows how long your money lasts if the next money is **on time, late, smaller, or never arrives**. You can also ask "what if" questions, and every number in the answer is checked against the engine.

Stretch does not predict when money will arrive, gives no financial advice, and never connects to a bank. It was built for one real person: my roommate.

Built for the DEV / MLH Hacktoberfest 2026 Weekend Challenge, "Build for a Friend".

## Status

| Component | Status |
|---|---|
| Deterministic engine (runway, safe daily spend, essentials reserve, affordability) | Done, tested |
| Setup: paste text or manual form, then a confirmation card | Done |
| Dashboard (chart, scenario cards, safe-spend and reserve cards) | Done |
| Ask flow (plan, execute, narrate) with a visible trace panel | Done |
| Verification of model output (grounding, plan validation, number check) | Done |
| LLM-off fallback (manual form, presets, "can I afford X?") | Done, tested |
| Session/handover mode (nothing saved) | Done |
| Frontend (Next.js) | Done, works against the real backend |
| Model comparison and accuracy benchmark | **Not done** |
| LLM-written narration | **Not done** (answers use fixed templates) |
| Natural-language spend logging | **Not done** |

## How it works

```
natural language -> local model (Gemma 3 4B) -> structured plan
  -> validation -> tool registry -> deterministic engine -> number check -> answer
```

- **The model interprets; code computes.** The model never does arithmetic or date math.
- **Every number shown comes from the engine.** The badge "numbers verified against the engine" means only that the numbers in the text match the engine's output. It does not mean any advice is correct, and Stretch gives none.
- This is a constrained tool-calling pipeline, not an open-ended agent loop.
- Amounts the model cannot find in your text are flagged on the confirmation card instead of being accepted.

## Requirements

- Windows 10/11 and PowerShell (commands below), Python 3.11+, Node.js LTS, Git
- [Ollama](https://ollama.com) with the `gemma3:4b` model
- CPU-only is fine. It was developed on an i7-8650U with 16 GB RAM and no GPU.

## Run it

**1. Clone and pull the model**

```powershell
git clone https://github.com/devinuwa/stretch-runway.git
cd stretch-runway
ollama pull gemma3:4b
```

**2. Start the backend** (first terminal)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:STRETCH_PROFILE = "demo"
$env:STRETCH_PERSIST = "0"
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

**3. Start the frontend** (second terminal)

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_MOCK = "0"
$env:NEXT_TELEMETRY_DISABLED = "1"
npm run dev
```

**4. Open** http://localhost:3000, click **Load sample data** (or paste your own description), confirm the card, then use the dashboard and the Ask bar.

Try: `What if the money comes 5 days late and is only half the amount?`

Make sure Ollama is running (`ollama list` should show `gemma3:4b`). On a CPU laptop each model call takes several seconds; first load is slower.

### Modes

| Variable | Values | Effect |
|---|---|---|
| `STRETCH_LLM` | `on` (default) / `off` | `off` forces the manual path: manual form, presets, direct "can I afford X?" |
| `STRETCH_PROFILE` | `demo` / `user` | `demo` enables the sample-data button |
| `STRETCH_PERSIST` | `0` / `1` | `0` keeps everything in memory, nothing written to disk |
| `STRETCH_HANDOVER` | `1` | session mode: in-memory only, metadata-only traces, "nothing is saved" banner |

LLM-off example:

```powershell
$env:STRETCH_LLM = "off"
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

The suite does not call a live model. It includes golden cases (cross-checked against an independently written reference), property tests (for example, delaying money never extends the runway), verification tests, a no-LLM fallback test, and a test that fails on any non-loopback network connection.

## Privacy

- The backend binds to `127.0.0.1` only. CORS allows only `http://localhost:3000`.
- No telemetry, no analytics, no CDN assets or fonts.
- No bank connection, no accounts. The browser stores no financial data.
- All sample data and fixtures are synthetic.
- In session mode nothing is written to disk and traces contain metadata only.

## Known limits

- Scenarios are assumptions, not forecasts.
- Model calls are slow on a CPU. Early runs on an i7-8650U took roughly 17 to 35 seconds per call. I have not run a controlled benchmark, so I quote no other timing.
- Only Gemma 3 4B was used. **No models were compared**, so nothing here claims it beats any other model.
- The confirmation card treats a commitment as skippable unless you tick "must pay". This affects the essentials-reserve card.
- Safe daily spend only protects the time until the next money arrives.
- Gemma is released under Google's own terms, not an OSI-approved licence. Check the current terms before reuse.

## Post-deadline commits

None.

## Credits and licence

Code: MIT. See [THIRD_PARTY.md](THIRD_PARTY.md) for dependencies and model terms.
Built with the Antigravity and Freebuff coding agents, with planning and drafting help from Claude.
