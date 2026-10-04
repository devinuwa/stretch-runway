"""T3 tests: tool registry + executor.

Tests TEST_PLAN.md section 2 (non-LLM-dependent items).
"""
import pytest
from datetime import date

from stretch.engine.models import Situation, Inflow, Commitment
from stretch.tools.registry import execute_plan, TOOL_ALLOWLIST


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def demo_situation():
    """Matches situation_demo.json (synthetic)."""
    return Situation(
        as_of=date(2026, 10, 5),
        currency="NGN",
        balance=26000,
        essentials_per_day=1500,
        inflows=(
            Inflow(id="inflow_1", label="Aunt", expected_amount=20000,
                   expected_date=date(2026, 10, 15)),
        ),
        commitments=(
            Commitment(id="commit_1", label="Outfit", amount=12000,
                       due_date=date(2026, 10, 21), flexible=True),
        ),
        horizon_days=60,
        buffer_days=3,
    )


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

def test_allowlist_contents():
    assert "compute_runway" in TOOL_ALLOWLIST
    assert "compare_scenarios" in TOOL_ALLOWLIST
    assert "safe_daily_spend" in TOOL_ALLOWLIST
    assert "check_affordability" in TOOL_ALLOWLIST
    assert "essentials_reserve" in TOOL_ALLOWLIST
    assert "propose_update" not in TOOL_ALLOWLIST  # P1 only


# ---------------------------------------------------------------------------
# compute_runway
# ---------------------------------------------------------------------------

def test_compute_runway_basic(demo_situation):
    plan = {"tool_calls": [{"tool": "compute_runway", "args": {}}]}
    results, trace = execute_plan(plan, demo_situation)
    assert len(results) == 1
    r = results[0]
    assert r["ok"] is True
    assert r["tool"] == "compute_runway"
    assert isinstance(r["result"]["runway_days"], int)
    assert r["result"]["runway_days"] >= 0
    assert len(r["numbers"]) > 0
    assert any(n["type"] == "days" for n in r["numbers"])


# ---------------------------------------------------------------------------
# compare_scenarios
# ---------------------------------------------------------------------------

def test_compare_scenarios_fixture(demo_situation):
    """Executes the demo plan from ask_demo_plan.json and checks structure."""
    plan = {
        "tool_calls": [
            {
                "tool": "compare_scenarios",
                "args": {
                    "scenarios": [
                        {"label": "on time", "adjustments": [], "extra_expenses": []},
                        {
                            "label": "5 days late, half the amount",
                            "adjustments": [
                                {
                                    "inflow_id": "*",
                                    "delay_days": 5,
                                    "new_date_expr": None,
                                    "amount_factor": 0.5,
                                    "new_amount": None,
                                    "cancelled": False,
                                }
                            ],
                            "extra_expenses": [],
                        },
                    ]
                },
            }
        ]
    }
    results, trace = execute_plan(plan, demo_situation)
    assert results[0]["ok"] is True
    result = results[0]["result"]
    assert len(result["scenarios"]) == 2
    # First scenario: on time
    s0 = result["scenarios"][0]["result"]
    # Second scenario: late + half
    s1 = result["scenarios"][1]["result"]
    # Late + half must be worse (fewer runway days)
    assert s1["runway_days"] <= s0["runway_days"]
    # Deltas present
    assert "deltas" in result
    assert result["deltas"]["runway_days"] == s1["runway_days"] - s0["runway_days"]


def test_compare_scenarios_numbers_registry(demo_situation):
    plan = {
        "tool_calls": [
            {
                "tool": "compare_scenarios",
                "args": {
                    "scenarios": [
                        {"label": "A", "adjustments": [], "extra_expenses": []},
                        {"label": "B", "adjustments": [
                            {"inflow_id": "*", "delay_days": 3, "new_date_expr": None,
                             "amount_factor": None, "new_amount": None, "cancelled": False}
                        ], "extra_expenses": []},
                    ]
                },
            }
        ]
    }
    results, _ = execute_plan(plan, demo_situation)
    nums = results[0]["numbers"]
    paths = {n["path"] for n in nums}
    assert "runway[0].runway_days" in paths
    assert "runway[1].runway_days" in paths
    assert "deltas.runway_days" in paths


# ---------------------------------------------------------------------------
# safe_daily_spend
# ---------------------------------------------------------------------------

def test_safe_daily_spend_basic(demo_situation):
    plan = {"tool_calls": [{"tool": "safe_daily_spend", "args": {}}]}
    results, _ = execute_plan(plan, demo_situation)
    r = results[0]
    assert r["ok"] is True
    result = r["result"]
    assert "days_to_cover" in result
    assert "covers_essentials" in result
    assert "already_short" in result


# ---------------------------------------------------------------------------
# essentials_reserve
# ---------------------------------------------------------------------------

def test_essentials_reserve_basic(demo_situation):
    plan = {"tool_calls": [{"tool": "essentials_reserve", "args": {}}]}
    results, _ = execute_plan(plan, demo_situation)
    r = results[0]
    assert r["ok"] is True
    result = r["result"]
    assert "reserve" in result
    assert "covered" in result
    assert "surplus_or_gap" in result
    assert any(n["path"].startswith("reserve.") for n in r["numbers"])


# ---------------------------------------------------------------------------
# check_affordability
# ---------------------------------------------------------------------------

def test_check_affordability_basic(demo_situation):
    plan = {
        "tool_calls": [
            {
                "tool": "check_affordability",
                "args": {
                    "expense": {"label": "Party", "amount": 5000, "date_expr": None}
                },
            }
        ]
    }
    results, _ = execute_plan(plan, demo_situation)
    r = results[0]
    assert r["ok"] is True
    assert r["result"]["verdict"] in {"fits", "shortens_runway", "breaks_before_next_money", "already_short"}


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------

def test_unknown_tool_returns_error(demo_situation):
    plan = {"tool_calls": [{"tool": "hack_the_planet", "args": {}}]}
    results, _ = execute_plan(plan, demo_situation)
    assert results[0]["ok"] is False
    assert "unknown_tool" in results[0]["error"]


# ---------------------------------------------------------------------------
# Engine error propagation
# ---------------------------------------------------------------------------

def test_invalid_adjustment_propagated(demo_situation):
    plan = {
        "tool_calls": [
            {
                "tool": "compute_runway",
                "args": {
                    "scenario": {
                        "label": "bad",
                        "adjustments": [
                            {
                                "inflow_id": "inflow_1",
                                "delay_days": None,
                                "new_date_expr": None,
                                "amount_factor": 0.5,
                                "new_amount": 999,
                                "cancelled": False,
                            }
                        ],
                        "extra_expenses": [],
                    }
                },
            }
        ]
    }
    results, _ = execute_plan(plan, demo_situation)
    assert results[0]["ok"] is False
    assert results[0]["error"] == "conflicting_adjustment"


# ---------------------------------------------------------------------------
# Trace shape
# ---------------------------------------------------------------------------

def test_trace_shape(demo_situation):
    plan = {"tool_calls": [{"tool": "essentials_reserve", "args": {}}]}
    _, trace = execute_plan(plan, demo_situation)
    for step in trace:
        assert "step" in step
        assert "label" in step
        assert "ms" in step
        assert isinstance(step["ms"], int)
