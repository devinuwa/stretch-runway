# Deploy — hosted preview (sample data, model off)

This deploys the **free public preview** of Stretch: the backend on Render and
the frontend on Vercel, both on their default URLs. No custom domain, no
backend on the public internet beyond this preview service.

The preview runs with `STRETCH_HOSTED=1`: sample data only, deterministic engine
only, the local model switched off. It is **not** the private local tool.

- Backend URL: `https://<service-name>.onrender.com` (Render assigns it)
- Frontend URL: `https://stretch-runway.vercel.app` (or whatever Vercel assigns)

## 0. Prerequisites

- Repo pushed to `https://github.com/devinuwa/stretch-runway`
- A Render account and a Vercel account
- No custom domain is required

## 1. Backend — Render Blueprint

1. Render dashboard -> **New** -> **Blueprint**.
2. Select the `devinuwa/stretch-runway` repository.
3. Render detects [`render.yaml`](../render.yaml). Click **Apply**.
4. Wait for the build and deploy to finish. The service is
   `stretch-runway-api`.
5. Open `https://<service-name>.onrender.com/api/health`. It must contain
   `"hosted": true`, `"llm": {"state": "disabled"}`, and
   `"mode": {"profile": "demo", "persist": false}`.

`render.yaml` sets `STRETCH_HOSTED=1`, `STRETCH_PROFILE=demo`,
`STRETCH_PERSIST=0`, `STRETCH_LLM=off`, `PYTHON_VERSION=3.12.7`, and leaves
`STRETCH_CORS_ORIGINS` unsynced for step 3. The plan is `starter` to avoid the
cold start; change `plan: starter` to `plan: free` to use the free instance
type instead.

## 2. Frontend — Vercel

1. Vercel dashboard -> **Add New** -> **Project** -> import
   `devinuwa/stretch-runway`.
2. **Root Directory**: `frontend`.
3. **Environment Variables**:
   - `NEXT_PUBLIC_MOCK` = `0`
   - `NEXT_PUBLIC_API_BASE` = `https://<service-name>.onrender.com`
   - `NEXT_TELEMETRY_DISABLED` = `1`
4. **Deploy**. Note the assigned URL (e.g. `https://stretch-runway.vercel.app`).

## 3. Point CORS at the frontend

The API only accepts browser calls from the origins in `STRETCH_CORS_ORIGINS`
(comma-separated, no trailing slash).

1. Render -> `stretch-runway-api` -> **Environment**.
2. Set `STRETCH_CORS_ORIGINS` = `https://stretch-runway.vercel.app`.
3. Save; Render redeploys automatically.

## 4. Verify

Run the hosted smoke check against the two live URLs:

```powershell
python backend/scripts/smoke_hosted.py https://<service-name>.onrender.com https://stretch-runway.vercel.app
```

It checks health, the sample-data path, the canonical scenario numbers
(`On time` = 2026-10-26 after 21 days), the 403/503 guards, and the CORS
preflight. Every line prints `PASS`/`FAIL` and the process exits non-zero on
failure.

## Cold start

On the free instance type Render sleeps an idle service. The first request can
take about a minute; open the link once yourself before sharing it. The
frontend shows "Waking the free server, this can take about a minute…" and
retries `/api/health` for up to 90 seconds. With the `starter` plan the service
stays warm.

## Cleaning up

1. Render -> `stretch-runway-api` -> **Settings** -> **Delete Web Service**.
2. Vercel -> the project -> **Settings** -> **Delete Project**.

Deleting both stops any billing. No custom domain is used, so there is nothing
else to release.
