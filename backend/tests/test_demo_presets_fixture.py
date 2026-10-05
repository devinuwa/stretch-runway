"""Regression: demo fixtures and the engine agree on the CANONICAL numbers.

Canonical demo situation (fixtures/situation_demo.json) includes commit_2
(data bundle, 2500, due 2026-10-09, flexible false). With it:
  * on time          -> 21 days / 2026-10-26
  * 5 days late+half -> 16 days / 2026-10-21

A demo fixture/seed that yields 22 days / Oct 27 has lost commit_2 — that is a
fixture bug, not an engine bug. These tests fail loudly if either side drifts.
"""
import json
from datetime import date
from pathlib import Path

from stretch.engine import Commitment, Inflow, Situation
from stretch.tools.registry import execute_plan

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def _demo_situation() -> Situation:
    raw = json.loads((FIXTURES / "situation_demo.json").read_text(encoding="utf-8"))
    return Situation(
        as_of=date.fromisoformat(raw["as_of"]),
        currency=raw.get("currency", "NGN"),
        balance=int(raw["balance"]),
        essentials_per_day=int(raw["essentials_per_day"]),
        horizon_days=int(raw.get("horizon_days", 60)),
        buffer_days=int(raw.get("buffer_days", 3)),
        inflows=tuple(
            Inflow(
                id=i["id"],
                label=i["label"],
                expected_amount=int(i["expected_amount"]),
                expected_date=date.fromisoformat(i["expected_date"]),
                uncertainty_note=i.get("uncertainty_note"),
            )
            for i in raw.get("inflows", [])
        ),
        commitments=tuple(
            Commitment(
                id=c["id"],
                label=c["label"],
                amount=int(c["amount"]),
                due_date=date.fromisoformat(c["due_date"]),
                flexible=bool(c.get("flexible", False)),
            )
            for c in raw.get("commitments", [])
        ),
    )


def _fixture() -> dict:
    return json.loads((FIXTURES / "runway_presets_demo.json").read_text(encoding="utf-8"))


def test_demo_situation_includes_commit_2():
    """Root-cause guard: the demo situation must keep the 2500 data-bundle item."""
    raw = json.loads((FIXTURES / "situation_demo.json").read_text(encoding="utf-8"))
    commit_2 = next((c for c in raw["commitments"] if c["id"] == "commit_2"), None)
    assert commit_2 is not None, "commit_2 (data bundle) is missing from situation_demo.json"
    assert commit_2["amount"] == 2500
    assert commit_2["due_date"] == "2026-10-09"
    assert commit_2["flexible"] is False


def test_engine_gives_canonical_demo_numbers():
    situation = _demo_situation()
    scenarios = [
        {"label": "on time", "adjustments": [], "extra_expenses": []},
        {"label": "5 days late + half", "adjustments": [
            {"inflow_id": "*", "delay_days": 5, "new_date_expr": None,
             "amount_factor": 0.5, "new_amount": None, "cancelled": False}],
         "extra_expenses": []},
    ]
    produced, _ = execute_plan(
        {"tool_calls": [{"tool": "compare_scenarios", "args": {"scenarios": scenarios}}]}, situation
    )
    on_time, late_half = produced[0]["result"]["scenarios"]
    assert (on_time["result"]["runway_days"], on_time["result"]["runs_out_on"]) == (21, "2026-10-26")
    assert (late_half["result"]["runway_days"], late_half["result"]["runs_out_on"]) == (16, "2026-10-21")


def test_fixture_scenarios_reproduced_by_engine():
    fixture = _fixture()
    situation = _demo_situation()
    scenarios = [r["scenario"] for r in fixture["results"]]
    produced, _ = execute_plan(
        {"tool_calls": [{"tool": "compare_scenarios", "args": {"scenarios": scenarios}}]}, situation
    )
    got = produced[0]["result"]["scenarios"]
    assert len(got) == len(fixture["results"])
    for expected, actual in zip(fixture["results"], got):
        assert actual["scenario"]["label"] == expected["scenario"]["label"]
        assert actual["result"] == expected["result"]


def test_fixture_safe_spend_and_reserve_reproduced_by_engine():
    fixture = _fixture()
    situation = _demo_situation()
    ss, _ = execute_plan({"tool_calls": [{"tool": "safe_daily_spend", "args": {}}]}, situation)
    rs, _ = execute_plan({"tool_calls": [{"tool": "essentials_reserve", "args": {}}]}, situation)
    assert ss[0]["result"] == fixture["safe_spend"]
    assert rs[0]["result"] == fixture["reserve"]


def test_fixture_encodes_canonical_on_time_value():
    first = _fixture()["results"][0]
    assert first["scenario"]["label"] == "As planned"
    assert first["result"]["runway_days"] == 21
    assert first["result"]["runs_out_on"] == "2026-10-26"
