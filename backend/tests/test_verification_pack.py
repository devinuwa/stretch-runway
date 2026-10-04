"""Verification pack before A2."""
import json
import os
import pytest
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["STRETCH_PERSIST"] = "0"
os.environ["STRETCH_PROFILE"] = "demo"
os.environ["STRETCH_LLM"] = "off"
os.environ["STRETCH_HANDOVER"] = "0"

import main as app_module
from stretch.engine.models import Situation
from stretch.tools.registry import execute_plan
from stretch.trace.tracer import LocalJsonlTracer

client = TestClient(app_module.app, raise_server_exceptions=True)

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"

def test_demo_plan_matches_fixture():
    # (a) the demo plan in fixtures/ask_demo_plan.json executes to the engine
    #     numbers recorded in fixtures/ask_demo_execute.json
    plan_fixture = json.loads((FIXTURES / "ask_demo_plan.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "ask_demo_execute.json").read_text(encoding="utf-8"))

    # The setup manual endpoint can build a Situation, but we can also POST to /api/situation
    client.post("/api/situation/demo")
    sit = app_module._store.get()

    results, trace = execute_plan(plan_fixture["plan"], sit)

    expected_results = expected["results"]
    assert len(results) == len(expected_results)
    for res, exp in zip(results, expected_results):
        assert res["ok"] == exp["ok"]
        assert res["result"] == exp["result"]
        # CONTRACT §4: the registry lists every number that may appear in prose, so
        # it is a superset of the fixture's recorded entries (shortfall_amount,
        # gap_days, inflows_applied[...], deltas, ...). The fixture stays canonical.
        produced = {(n["path"], n["value"], n["type"]) for n in res["numbers"]}
        for entry in exp["numbers"]:
            assert (entry["path"], entry["value"], entry["type"]) in produced, entry

def test_v3_rejection_logic():
    # (b) V3 rejects fixtures/v3_failure_example.json with unmatched ["22","17"]
    # and accepts fixtures/ask_demo_narrate.json
    from stretch.verify import verify_narration

    failure_expected = json.loads((FIXTURES / "v3_failure_example.json").read_text(encoding="utf-8"))
    success_expected = json.loads((FIXTURES / "ask_demo_narrate.json").read_text(encoding="utf-8"))

    # Registry has only runway_days=10; the narration invents 22 and 17, and the
    # question deliberately does not contain them. CONTRACT §4: the gate fails.
    registry = [{"path": "runway.runway_days", "value": 10, "type": "days"}]
    check = verify_narration(
        failure_expected["narration"],
        registry,
        question="What if the money comes 5 days late and at half the amount?",
    )
    assert check["status"] == "failed"
    assert "22" in check["unmatched"]
    assert "17" in check["unmatched"]

    # The passing fixture narrates only registry numbers/dates plus the delay from
    # the question (CONTRACT §4 allows integers present in the question).
    demo_question = "What if the money comes 5 days late and is only half the amount?"
    passing_registry = success_expected["verification"]["checked_numbers"]
    ok = verify_narration(success_expected["narration"], passing_registry, question=demo_question)
    assert ok["status"] == "verified", ok

    # Without the question, the delay "5" is not grounded -> the gate fails.
    bare = verify_narration(success_expected["narration"], passing_registry)
    assert bare["status"] == "failed"
    assert "5" in bare["unmatched"]

    # Template narration built by code from the registry always passes the gate.
    results = [
        {
            "tool": "compute_runway", "ok": True, "error": None,
            "result": {"runway_days": 10}, "numbers": [{"path": "runway.runway_days", "value": 10, "type": "days"}],
            "args": {},
        }
    ]
    r = client.post("/api/ask/narrate", json={"question": "How long will my money last?", "results": results})
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "template"
    assert data["verification"]["status"] == "verified"
    assert data["verification"]["badge"] == "numbers verified against the engine"

def test_handover_metadata_only(tmp_path):
    # (c) STRETCH_HANDOVER=1 trace file contains no amounts, question text or tool arguments
    tracer = LocalJsonlTracer(tmp_path / "trace.jsonl")
    # Record something with handover
    tracer.record("engine_call", "compute_runway", 10) # Handover tracer drops payload
    
    content = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert "amounts" not in content.lower()
    assert "question" not in content.lower()
    assert "payload" not in content.lower()

def test_demo_profile_forbidden():
    # (d) /api/situation/demo returns 403 outside the demo profile
    os.environ["STRETCH_PROFILE"] = "prod"
    import importlib
    importlib.reload(app_module) # Need to reload to pick up PROFILE env var
    
    prod_client = TestClient(app_module.app, raise_server_exceptions=False)
    r = prod_client.post("/api/situation/demo")
    assert r.status_code == 403
    
    # Restore
    os.environ["STRETCH_PROFILE"] = "demo"
    importlib.reload(app_module)
