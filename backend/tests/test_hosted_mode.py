"""Hosted preview (STRETCH_HOSTED=1) tests.

Hosted preview is the free public deploy: local model forced off, demo profile,
nothing persisted, and only the sample situation may be used. These tests load
``backend/main.py`` under a distinct module name with the hosted env so the
local-mode tests that import ``main`` directly are unaffected.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).parent.parent
FIXTURE = BACKEND_DIR.parent / "fixtures" / "situation_demo.json"
HOSTED_ORIGIN = "https://stretch.example"


def _load_hosted_app():
    """Execute main.py fresh with hosted env, then restore the environment."""
    env = {
        # A hostile starting point: user profile + LLM "on" + persist on. Hosted
        # mode must override all three.
        "STRETCH_HOSTED": "1",
        "STRETCH_PROFILE": "user",
        "STRETCH_LLM": "on",
        "STRETCH_PERSIST": "1",
        "STRETCH_HANDOVER": "0",
        "STRETCH_CORS_ORIGINS": f"http://localhost:3000,{HOSTED_ORIGIN}",
    }
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        spec = importlib.util.spec_from_file_location("main_hosted", BACKEND_DIR / "main.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["main_hosted"] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return module


hosted = _load_hosted_app()
client = TestClient(hosted.app, raise_server_exceptions=True)


def _fixture_body() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def reset_store():
    hosted._store.delete()
    yield
    hosted._store.delete()


# ---------------------------------------------------------------------------
# Health + forced mode
# ---------------------------------------------------------------------------

def test_health_reports_hosted_and_forced_mode():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["hosted"] is True
    assert data["llm"]["state"] == "disabled"
    assert data["mode"]["profile"] == "demo"
    assert data["mode"]["persist"] is False


# ---------------------------------------------------------------------------
# Profile setup is forbidden
# ---------------------------------------------------------------------------

def test_setup_extract_forbidden():
    r = client.post("/api/setup/extract", json={"text": "I have 26000 naira"})
    assert r.status_code == 403
    err = r.json()["detail"]["error"]
    assert err["code"] == "profile_forbidden"
    assert "sample-data only" in err["message"]


def test_setup_manual_forbidden():
    body = {
        "balance": 26000,
        "essentials": {"amount": 1500, "period": "day"},
        "inflows": [],
        "commitments": [],
    }
    r = client.post("/api/setup/manual", json=body)
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "profile_forbidden"


# ---------------------------------------------------------------------------
# PUT /api/situation: only the exact demo situation is accepted
# ---------------------------------------------------------------------------

def test_demo_situation_allowed():
    r = client.post("/api/situation/demo")
    assert r.status_code == 200
    assert r.json()["balance"] == 26000


def test_put_demo_body_accepted():
    body = _fixture_body()
    body.pop("synthetic", None)
    r = client.put("/api/situation", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["balance"] == 26000
    assert len(r.json()["commitments"]) == 2


def test_put_accepts_reordered_keys():
    raw = _fixture_body()
    # Reverse key order to prove comparison ignores key order, and keep the
    # extra "synthetic" field (pydantic drops it).
    reordered = {k: raw[k] for k in reversed(list(raw.keys()))}
    r = client.put("/api/situation", json=reordered)
    assert r.status_code == 200, r.text


def test_put_other_body_forbidden():
    body = _fixture_body()
    body.pop("synthetic", None)
    body["balance"] = 999_999
    r = client.put("/api/situation", json=body)
    assert r.status_code == 403
    err = r.json()["detail"]["error"]
    assert err["code"] == "profile_forbidden"
    assert "sample-data only" in err["message"]


def test_put_dropped_commitment_forbidden():
    body = _fixture_body()
    body.pop("synthetic", None)
    body["commitments"] = body["commitments"][:1]
    r = client.put("/api/situation", json=body)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Allowed no-LLM paths
# ---------------------------------------------------------------------------

def test_delete_data_resets_to_none():
    client.post("/api/situation/demo")
    assert hosted._store.has_situation() is True
    assert client.delete("/api/data").status_code == 204
    assert hosted._store.has_situation() is False


def test_scenarios_and_direct_still_work():
    client.post("/api/situation/demo")
    r = client.post("/api/runway/scenarios", json={})
    assert r.status_code == 200
    assert len(r.json()["results"]) == 5
    r2 = client.post("/api/ask/direct", json={"tool": "compute_runway", "args": {}})
    assert r2.status_code == 200
    assert r2.json()["results"][0]["ok"] is True


def test_ask_plan_reports_llm_unavailable():
    client.post("/api/situation/demo")
    r = client.post("/api/ask/plan", json={"question": "how long will my money last?"})
    assert r.status_code == 503
    assert r.json()["detail"]["error"]["code"] == "llm_unavailable"


# ---------------------------------------------------------------------------
# CORS comes from STRETCH_CORS_ORIGINS
# ---------------------------------------------------------------------------

def test_cors_allows_configured_origin():
    r = client.options(
        "/api/health",
        headers={"Origin": HOSTED_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == HOSTED_ORIGIN


def test_cors_default_origin_still_allowed():
    r = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
