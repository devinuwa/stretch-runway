"""T5 API endpoint tests (non-LLM-dependent).

Uses FastAPI TestClient. The store is accessed via the app's module-level
_store. We reset it via DELETE /api/data between tests.
"""
import json
import os
import pytest

# Force env BEFORE importing the app so module-level config is correct
os.environ["STRETCH_PERSIST"] = "0"
os.environ["STRETCH_PROFILE"] = "demo"
os.environ["STRETCH_LLM"] = "off"
os.environ["STRETCH_HANDOVER"] = "0"

import sys
# Remove any cached main module so env above is picked up fresh
for key in list(sys.modules.keys()):
    if key in ("main",):
        del sys.modules[key]

import main as app_module  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app_module.app, raise_server_exceptions=True)

DEMO_SITUATION_BODY = {
    "as_of": "2026-10-05",
    "currency": "NGN",
    "balance": 26000,
    "essentials_per_day": 1500,
    "horizon_days": 60,
    "buffer_days": 3,
    "inflows": [
        {
            "id": "inflow_1",
            "label": "Aunt",
            "expected_amount": 20000,
            "expected_date": "2026-10-15",
            "uncertainty_note": None,
        }
    ],
    "commitments": [
        {
            "id": "commit_1",
            "label": "Outfit",
            "amount": 12000,
            "due_date": "2026-10-21",
            "flexible": True,
        }
    ],
}


@pytest.fixture(autouse=True)
def reset_store():
    """Wipe store before every test via the DELETE endpoint."""
    app_module._store.delete()
    yield
    app_module._store.delete()


def _seed_demo():
    r = client.post("/api/situation/demo")
    assert r.status_code == 200, f"seed_demo failed: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "llm" in data
    assert "mode" in data
    assert "version" in data
    assert data["version"] == "0.1.0"


def test_health_has_situation_false_initially():
    r = client.get("/api/health")
    assert r.json()["has_situation"] is False


def test_health_has_situation_true_after_put():
    client.put("/api/situation", json=DEMO_SITUATION_BODY)
    r = client.get("/api/health")
    assert r.json()["has_situation"] is True


# ---------------------------------------------------------------------------
# POST /api/setup/manual
# ---------------------------------------------------------------------------

def test_setup_manual_basic():
    body = {
        "as_of": "2026-10-05",
        "balance": 26000,
        "essentials": {"amount": 1500, "period": "day"},
        "inflows": [
            {
                "label": "Aunt",
                "expected_amount": 20000,
                "date_expr": {"kind": "iso", "value": "2026-10-15"},
            }
        ],
        "commitments": [],
    }
    r = client.post("/api/setup/manual", json=body)
    assert r.status_code == 200
    draft = r.json()
    assert draft["balance"]["value"] == 26000
    assert draft["balance"]["grounded"] is True
    assert len(draft["inflows"]) == 1
    assert draft["inflows"][0]["expected_amount"]["value"] == 20000


def test_setup_manual_weekly_essentials():
    body = {
        "balance": 10000,
        "essentials": {"amount": 7000, "period": "week"},
        "inflows": [],
        "commitments": [],
    }
    r = client.post("/api/setup/manual", json=body)
    assert r.status_code == 200
    assert r.json()["essentials_per_day"]["value"] == 1000


def test_setup_manual_monthly_essentials():
    body = {
        "balance": 10000,
        "essentials": {"amount": 30000, "period": "month"},
        "inflows": [],
        "commitments": [],
    }
    r = client.post("/api/setup/manual", json=body)
    assert r.status_code == 200
    assert r.json()["essentials_per_day"]["value"] == 1000


def test_setup_manual_in_days_expr():
    body = {
        "as_of": "2026-10-05",
        "balance": 5000,
        "essentials": {"amount": 500, "period": "day"},
        "inflows": [
            {
                "label": "Loan",
                "expected_amount": 3000,
                "date_expr": {"kind": "in_days", "n": 10},
            }
        ],
        "commitments": [],
    }
    r = client.post("/api/setup/manual", json=body)
    assert r.status_code == 200
    assert r.json()["inflows"][0]["expected_date"]["value"] == "2026-10-15"


def test_setup_manual_assigns_ids():
    body = {
        "balance": 5000,
        "essentials": {"amount": 500, "period": "day"},
        "inflows": [
            {"label": "A", "expected_amount": 1000, "date_expr": {"kind": "in_days", "n": 5}},
            {"label": "B", "expected_amount": 2000, "date_expr": {"kind": "in_days", "n": 10}},
        ],
        "commitments": [],
    }
    r = client.post("/api/setup/manual", json=body)
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["inflows"]]
    assert ids == ["inflow_1", "inflow_2"]


# ---------------------------------------------------------------------------
# PUT / GET /api/situation
# ---------------------------------------------------------------------------

def test_put_situation_get_roundtrip():
    r = client.put("/api/situation", json=DEMO_SITUATION_BODY)
    assert r.status_code == 200
    data = r.json()
    assert data["balance"] == 26000
    assert data["as_of"] == "2026-10-05"

    r2 = client.get("/api/situation")
    assert r2.status_code == 200
    assert r2.json()["balance"] == 26000


def test_get_situation_no_situation_409():
    r = client.get("/api/situation")
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "no_situation"


def test_put_situation_validates_balance_nonneg():
    body = dict(DEMO_SITUATION_BODY)
    body["balance"] = -1
    r = client.put("/api/situation", json=body)
    assert r.status_code == 422


def test_put_situation_validates_essentials_pos():
    body = dict(DEMO_SITUATION_BODY)
    body["essentials_per_day"] = 0
    r = client.put("/api/situation", json=body)
    assert r.status_code == 422


def test_put_situation_date_before_as_of():
    body = json.loads(json.dumps(DEMO_SITUATION_BODY))
    body["inflows"][0]["expected_date"] = "2026-10-01"
    r = client.put("/api/situation", json=body)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/situation/demo
# ---------------------------------------------------------------------------

def test_situation_demo_loads_fixture():
    r = client.post("/api/situation/demo")
    assert r.status_code == 200
    data = r.json()
    assert data["balance"] == 26000
    assert data["as_of"] == "2026-10-05"
    assert len(data["inflows"]) >= 1


def test_situation_demo_sets_store():
    _seed_demo()
    r = client.get("/api/situation")
    assert r.status_code == 200
    assert r.json()["balance"] == 26000


# ---------------------------------------------------------------------------
# POST /api/runway/scenarios
# ---------------------------------------------------------------------------

def test_runway_scenarios_default_presets():
    _seed_demo()
    r = client.post("/api/runway/scenarios", json={})
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 5
    assert "safe_spend" in data
    assert "reserve" in data
    assert "assumptions" in data


def test_runway_scenarios_custom():
    _seed_demo()
    body = {
        "scenarios": [
            {"label": "on time", "adjustments": [], "extra_expenses": []},
            {"label": "late", "adjustments": [
                {"inflow_id": "*", "delay_days": 7, "new_date_expr": None,
                 "amount_factor": None, "new_amount": None, "cancelled": False}
            ], "extra_expenses": []},
        ]
    }
    r = client.post("/api/runway/scenarios", json=body)
    assert r.status_code == 200
    assert len(r.json()["results"]) == 2


def test_runway_scenarios_no_situation():
    r = client.post("/api/runway/scenarios", json={})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/ask/direct
# ---------------------------------------------------------------------------

def test_ask_direct_compute_runway():
    _seed_demo()
    r = client.post("/api/ask/direct", json={"tool": "compute_runway", "args": {}})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["ok"] is True
    assert "runway_days" in results[0]["result"]


def test_ask_direct_unknown_tool():
    _seed_demo()
    r = client.post("/api/ask/direct", json={"tool": "hack_planet", "args": {}})
    assert r.status_code == 422


def test_ask_direct_no_situation():
    r = client.post("/api/ask/direct", json={"tool": "compute_runway", "args": {}})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/ask/execute
# ---------------------------------------------------------------------------

def test_ask_execute_compare_scenarios():
    _seed_demo()
    plan = {
        "tool_calls": [
            {
                "tool": "compare_scenarios",
                "args": {
                    "scenarios": [
                        {"label": "on time", "adjustments": [], "extra_expenses": []},
                        {"label": "late+half", "adjustments": [
                            {"inflow_id": "*", "delay_days": 5, "new_date_expr": None,
                             "amount_factor": 0.5, "new_amount": None, "cancelled": False}
                        ], "extra_expenses": []},
                    ]
                },
            }
        ]
    }
    r = client.post("/api/ask/execute", json={"plan": plan})
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "trace" in data
    assert data["results"][0]["ok"] is True


def test_ask_execute_unknown_tool_422():
    _seed_demo()
    plan = {"tool_calls": [{"tool": "hack", "args": {}}]}
    r = client.post("/api/ask/execute", json={"plan": plan})
    assert r.status_code == 422


def test_ask_execute_no_tool_calls_422():
    _seed_demo()
    r = client.post("/api/ask/execute", json={"plan": {"clarify": "huh?"}})
    assert r.status_code == 422


def test_ask_execute_no_situation_409():
    plan = {"tool_calls": [{"tool": "compute_runway", "args": {}}]}
    r = client.post("/api/ask/execute", json={"plan": plan})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/ask/narrate  (template mode)
# ---------------------------------------------------------------------------

def test_ask_narrate_template_mode():
    results = [
        {
            "tool": "compute_runway",
            "args": {},
            "ok": True,
            "error": None,
            "result": {"runway_days": 22, "runs_out_on": "2026-10-27",
                       "covered_through_horizon": False, "shortfall_amount": 500,
                       "next_money_after_shortfall": None, "gap_days": None,
                       "inflows_applied": [], "horizon_days": 60, "series": []},
            "numbers": [{"path": "runway.runway_days", "value": 22, "type": "days"}],
        }
    ]
    r = client.post("/api/ask/narrate", json={"question": "How long will my money last?", "results": results})
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "template"
    assert "narration" in data
    assert data["verification"]["status"] == "verified"
    assert data["verification"]["badge"] == "numbers verified against the engine"
    assert data["model"] is None


def test_ask_narrate_failed_tool_handled():
    results = [{"tool": "compute_runway", "ok": False, "error": "no_situation",
                "result": None, "numbers": [], "args": {}}]
    r = client.post("/api/ask/narrate", json={"question": "?", "results": results})
    assert r.status_code == 200
    narration = r.json()["narration"].lower()
    assert "failed" in narration or "error" in narration


# ---------------------------------------------------------------------------
# DELETE /api/data
# ---------------------------------------------------------------------------

def test_delete_data():
    _seed_demo()
    assert app_module._store.has_situation() is True
    r = client.delete("/api/data")
    assert r.status_code == 204
    assert app_module._store.has_situation() is False


def test_delete_data_idempotent():
    r = client.delete("/api/data")
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------

def test_cors_allows_localhost_3000():
    r = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
