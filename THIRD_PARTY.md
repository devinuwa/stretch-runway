# Third-Party Software Credits

This project includes or uses the following open-source software, services and assets.

## Backend

- **Python** (PSF License)
- **FastAPI** (MIT License) — Copyright (c) 2018 Sebastián Ramírez
- **Uvicorn** (BSD License)
- **Pydantic** (MIT License)
- **HTTPX** (BSD License)
- **PyYAML** (MIT License)
- **pytest** and **Hypothesis** (MIT / MPL) — development and tests only (`requirements-dev.txt`)
- **psutil** (BSD License) — development and tests only (`requirements-dev.txt`)

## Frontend

- **React** (MIT License)
- **Next.js** (MIT License)
- **Tailwind CSS** (MIT License)
- **Recharts** (MIT License)

## Models

- **Gemma 3 (4B)** — Google LLC. Released under Google's own Gemma Terms of Use, not an OSI-approved licence: https://ai.google.dev/gemma/terms

## Tools

- **Ollama** (MIT License) — runs the local model on `127.0.0.1:11434`

## Hosting (hosted preview only)

Used only to host the public sample-data preview. No custom domain, no paid third-party service in the core app.

- **Render** — backend hosting for the hosted preview
- **Vercel** — frontend hosting for the hosted preview

The hosted preview holds only synthetic sample data and runs the deterministic engine only; the local model does not run on the host.
