"""Hosted-preview smoke check (NOT a pytest module — the name avoids collection).

Usage:
    python smoke_hosted.py <API_URL> <FRONTEND_ORIGIN>

Checks a deployed ``STRETCH_HOSTED=1`` backend: health flags, the sample-data
path, the canonical scenario numbers, the profile guards, and the CORS
preflight. Prints PASS/FAIL per check and exits non-zero if any check fails.
"""
from __future__ import annotations

import sys

import httpx

# Allow cold starts on a free/idle host.
TIMEOUT = 120.0

# Canonical demo numbers (fixtures/situation_demo.json -> runway_presets_demo.json).
ON_TIME = (21, "2026-10-26")
FIVE_DAYS_LATE_HALF = (16, "2026-10-21")


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" | {detail}" if detail else ""))
    return ok


def _error_code(response: httpx.Response) -> str | None:
    try:
        return response.json()["detail"]["error"]["code"]
    except Exception:
        return None


def _error_fallback(response: httpx.Response) -> str | None:
    try:
        return response.json()["detail"]["error"]["fallback"]
    except Exception:
        return None


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python smoke_hosted.py <API_URL> <FRONTEND_ORIGIN>")
        return 2
    api = argv[1].rstrip("/")
    origin = argv[2].rstrip("/")

    results: list[bool] = []
    with httpx.Client(base_url=api, timeout=TIMEOUT, follow_redirects=True) as client:
        # --- health -----------------------------------------------------
        r = client.get("/api/health")
        health = r.json() if r.status_code == 200 else {}
        results.append(check("GET /api/health -> 200", r.status_code == 200, f"status={r.status_code}"))
        results.append(check("health.hosted is true", health.get("hosted") is True, f"hosted={health.get('hosted')!r}"))
        llm_state = (health.get("llm") or {}).get("state")
        results.append(check("llm.state is disabled", llm_state == "disabled", f"state={llm_state!r}"))
        mode = health.get("mode") or {}
        results.append(
            check(
                "profile=demo and persist=false",
                mode.get("profile") == "demo" and mode.get("persist") is False,
                f"mode={mode!r}",
            )
        )

        # --- sample data -------------------------------------------------
        r = client.post("/api/situation/demo")
        results.append(check("POST /api/situation/demo -> 200", r.status_code == 200, f"status={r.status_code}"))

        # --- scenarios (canonical numbers) ------------------------------
        r = client.post("/api/runway/scenarios", json={})
        scenarios: dict[str, dict] = {}
        if r.status_code == 200:
            for item in r.json().get("results", []):
                label = (item.get("scenario") or {}).get("label", "")
                scenarios[label] = item.get("result") or {}
        results.append(check("POST /api/runway/scenarios -> 200", r.status_code == 200, f"status={r.status_code}"))

        on_time_labels = [
            label
            for label, res in scenarios.items()
            if (res.get("runway_days"), res.get("runs_out_on")) == ON_TIME
        ]
        results.append(
            check(
                f"On time = {ON_TIME[0]} days / {ON_TIME[1]}",
                bool(on_time_labels),
                f"labels={on_time_labels}",
            )
        )
        late_half_labels = [
            label
            for label, res in scenarios.items()
            if (res.get("runway_days"), res.get("runs_out_on")) == FIVE_DAYS_LATE_HALF
        ]
        results.append(
            check(
                f"5 days late + half = {FIVE_DAYS_LATE_HALF[0]} days / {FIVE_DAYS_LATE_HALF[1]}",
                bool(late_half_labels),
                f"labels={late_half_labels}",
            )
        )

        # --- profile setup is forbidden ---------------------------------
        r = client.post("/api/setup/extract", json={"text": "I have 26000 naira"})
        results.append(
            check(
                "POST /api/setup/extract -> 403 profile_forbidden",
                r.status_code == 403 and _error_code(r) == "profile_forbidden",
                f"status={r.status_code} code={_error_code(r)!r}",
            )
        )
        r = client.post(
            "/api/setup/manual",
            json={"balance": 1, "essentials": {"amount": 1, "period": "day"}, "inflows": [], "commitments": []},
        )
        results.append(
            check(
                "POST /api/setup/manual -> 403 profile_forbidden",
                r.status_code == 403 and _error_code(r) == "profile_forbidden",
                f"status={r.status_code}",
            )
        )

        # --- plan is unavailable (model off) ----------------------------
        r = client.post("/api/ask/plan", json={"question": "how long will my money last?"})
        results.append(
            check(
                "POST /api/ask/plan -> 503 llm_unavailable fallback=manual",
                r.status_code == 503 and _error_code(r) == "llm_unavailable" and _error_fallback(r) == "manual",
                f"status={r.status_code} fallback={_error_fallback(r)!r}",
            )
        )

        # --- CORS preflight from the frontend origin --------------------
        r = client.options(
            "/api/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        allow = r.headers.get("access-control-allow-origin")
        results.append(
            check(
                "OPTIONS preflight reflects frontend origin",
                allow == origin,
                f"allow-origin={allow!r} origin={origin!r}",
            )
        )

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 1 if passed != len(results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
