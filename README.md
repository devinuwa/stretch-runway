# Stretch

**Local-first financial runway tool.** Stretch helps a student whose money arrives in unpredictable bits see how long their money will last under different scenarios — without predictions, without advice, without anything leaving the machine.

> Built for the Hacktoberfest 2026 DEV Weekend Challenge "Build for a Friend".

## Status

🚧 Under construction.

## Quick Start

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest

# Frontend (coming soon)
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

This is a **constrained tool-calling pipeline**, not an open-ended agent loop: one planning step, at most 3 validated tool calls, then explanation.

## Privacy

- Runs entirely on `127.0.0.1`. No telemetry, no CDN, no analytics.
- The LLM runs locally via Ollama. Nothing leaves the machine.
- All demo data is synthetic.

## Limits

- Scenarios, not forecasts. No probabilities, no predictions of when money will arrive.
- No financial advice. The tool reports what happens under assumptions.
- "Numbers verified against the engine" means the numbers in the text match engine output. Nothing more.

## Third-Party Credits

See [THIRD_PARTY.md](THIRD_PARTY.md).

## AI-Assistance Disclosure

This project was built with AI coding assistance (Google Antigravity / Freebuff).

## Post-deadline commits

_(none yet)_

## License

[MIT](LICENSE) for the application code. Models are subject to their own licenses.
