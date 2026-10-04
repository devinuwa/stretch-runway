import pytest
from datetime import date
from stretch.engine import (
    compute_runway,
    compute_safe_spend,
    compute_reserve,
    check_affordability,
    resolve_date,
    convert_essentials,
    EngineError,
    Situation,
    Inflow,
    ScenarioSpec,
    InflowAdjustment,
)
from tests.helpers import (
    load_situation,
    load_scenario,
    load_date_expr,
    load_expense,
)


# ---------------------------------------------------------------------------
# Count guards – a vacuous pass (0 cases) is a test failure
# ---------------------------------------------------------------------------
def test_golden_case_counts(engine_golden):
    assert len(engine_golden["runway_cases"]) == 11, "runway_cases count mismatch"
    assert len(engine_golden["safe_spend_cases"]) == 3, "safe_spend_cases count mismatch"
    assert len(engine_golden["reserve_cases"]) == 2, "reserve_cases count mismatch"
    assert len(engine_golden["affordability_cases"]) == 2, "affordability_cases count mismatch"
    assert len(engine_golden["date_resolution_cases"]) == 7, "date_resolution_cases count mismatch"
    assert len(engine_golden["essentials_conversion_cases"]) == 3, "essentials_conversion_cases count mismatch"
    assert len(engine_golden["validation_error_cases"]) == 4, "validation_error_cases count mismatch"


# ---------------------------------------------------------------------------
# Runway
# ---------------------------------------------------------------------------
def test_runway_golden(engine_golden):
    cases = engine_golden["runway_cases"]
    for case in cases:
        situation = load_situation(case["situation"])
        scenario = load_scenario(case["scenario"]) if case.get("scenario") else None
        expected = case["expected_runway"]

        res = compute_runway(situation, scenario)

        assert res.runway_days == expected["runway_days"], f"Failed case {case['id']}"

        expected_out = date.fromisoformat(expected["runs_out_on"]) if expected["runs_out_on"] else None
        assert res.runs_out_on == expected_out, f"Failed case {case['id']}"

        assert res.shortfall_amount == expected["shortfall_amount"], f"Failed case {case['id']}"

        expected_next = (
            date.fromisoformat(expected["next_money_after_shortfall"])
            if expected["next_money_after_shortfall"]
            else None
        )
        assert res.next_money_after_shortfall == expected_next, f"Failed case {case['id']}"

        assert res.gap_days == expected["gap_days"], f"Failed case {case['id']}"
        assert res.covered_through_horizon == expected["covered_through_horizon"], f"Failed case {case['id']}"


# ---------------------------------------------------------------------------
# Safe spend
# ---------------------------------------------------------------------------
def test_safe_spend_golden(engine_golden):
    cases = engine_golden["safe_spend_cases"]
    for case in cases:
        situation = load_situation(case["situation"])
        scenario = load_scenario(case["scenario"]) if case.get("scenario") else None
        expected = case["expected"]

        res = compute_safe_spend(situation, scenario)

        assert res.inflow_today == expected["inflow_today"], f"Failed case {case['id']}"

        expected_date = date.fromisoformat(expected["target_date"]) if expected["target_date"] else None
        assert res.target_date == expected_date, f"Failed case {case['id']}"

        assert res.days_to_cover == expected["days_to_cover"], f"Failed case {case['id']}"
        assert res.max_daily_total == expected["max_daily_total"], f"Failed case {case['id']}"
        assert res.headroom == expected["headroom"], f"Failed case {case['id']}"
        assert res.covers_essentials == expected["covers_essentials"], f"Failed case {case['id']}"
        assert res.already_short == expected["already_short"], f"Failed case {case['id']}"


# ---------------------------------------------------------------------------
# Reserve
# ---------------------------------------------------------------------------
def test_reserve_golden(engine_golden):
    cases = engine_golden["reserve_cases"]
    for case in cases:
        situation = load_situation(case["situation"])
        scenario = load_scenario(case["scenario"]) if case.get("scenario") else None
        expected = case["expected"]
        buffer_days = case.get("buffer_days")

        res = compute_reserve(situation, buffer_days, scenario)

        assert res.days_to_next_money == expected["days_to_next_money"], f"Failed case {case['id']}"
        assert res.buffer_days == expected["buffer_days"], f"Failed case {case['id']}"
        assert res.essentials_part == expected["essentials_part"], f"Failed case {case['id']}"
        assert res.must_pay_part == expected["must_pay_part"], f"Failed case {case['id']}"
        assert res.reserve == expected["reserve"], f"Failed case {case['id']}"
        assert res.covered == expected["covered"], f"Failed case {case['id']}"
        assert res.surplus_or_gap == expected["surplus_or_gap"], f"Failed case {case['id']}"


# ---------------------------------------------------------------------------
# Affordability
# ---------------------------------------------------------------------------
def test_affordability_golden(engine_golden):
    cases = engine_golden["affordability_cases"]
    for case in cases:
        situation = load_situation(case["situation"])
        scenario = load_scenario(case["scenario"]) if case.get("scenario") else None
        expense = load_expense(case["expense"])
        expected = case["expected"]

        res = check_affordability(expense, situation, scenario)

        assert res.verdict == expected["verdict"], f"Failed case {case['id']}"
        assert res.runway_before == expected["runway_before"], f"Failed case {case['id']}"
        assert res.runway_after == expected["runway_after"], f"Failed case {case['id']}"
        assert res.days_lost == expected["days_lost"], f"Failed case {case['id']}"


# ---------------------------------------------------------------------------
# Date resolution
# ---------------------------------------------------------------------------
def test_date_resolution_golden(engine_golden):
    cases = engine_golden["date_resolution_cases"]
    for i, case in enumerate(cases):
        as_of = date.fromisoformat(case["as_of"])
        expr = load_date_expr(case["expr"])

        if "expected" in case:
            expected = date.fromisoformat(case["expected"])
            assert resolve_date(expr, as_of) == expected, f"Failed case {i}"
        else:
            with pytest.raises(EngineError) as exc:
                resolve_date(expr, as_of)
            assert exc.value.code == case["expected_error"], f"Failed case {i}"


# ---------------------------------------------------------------------------
# Essentials conversion
# ---------------------------------------------------------------------------
def test_essentials_conversion_golden(engine_golden):
    cases = engine_golden["essentials_conversion_cases"]
    for i, case in enumerate(cases):
        assert convert_essentials(case["amount"], case["period"]) == case["expected_per_day"], f"Failed case {i}"


# ---------------------------------------------------------------------------
# Validation errors
# Each required error code must be raised by at least one case.
# Required codes: invalid_date, conflicting_adjustment, unknown_inflow, out_of_bounds
# invalid_date covers: new_date earlier than as_of, new_date_expr resolving before as_of,
#                      and day 31 in a 30-day month.
# ---------------------------------------------------------------------------
def test_validation_error_cases(engine_golden):
    cases = engine_golden["validation_error_cases"]
    observed_codes: set[str] = set()

    for case in cases:
        situation = Situation(
            as_of=date(2026, 10, 5),
            balance=10000,
            essentials_per_day=1000,
            inflows=(Inflow(id="inf1", expected_amount=5000, expected_date=date(2026, 10, 10), label="x"),),
        )

        scenario = None
        what = case["what"]

        if what == "new_date earlier than as_of":
            scenario = ScenarioSpec(
                label="err",
                adjustments=(InflowAdjustment(inflow_id="inf1", new_date=date(2026, 10, 1)),),
            )
        elif what == "amount_factor and new_amount both set":
            scenario = ScenarioSpec(
                label="err",
                adjustments=(InflowAdjustment(inflow_id="inf1", amount_factor=0.5, new_amount=2000),),
            )
        elif what == "unknown inflow_id":
            scenario = ScenarioSpec(
                label="err",
                adjustments=(InflowAdjustment(inflow_id="unknown_inf", delay_days=5),),
            )
        elif what == "delay_days outside 0..365":
            scenario = ScenarioSpec(
                label="err",
                adjustments=(InflowAdjustment(inflow_id="inf1", delay_days=-5),),
            )

        assert scenario is not None, f"Case {case['id']} has unrecognised 'what': {what!r}"

        with pytest.raises(EngineError) as exc:
            compute_runway(situation, scenario)

        assert exc.value.code == case["expected_error"], (
            f"Case {case['id']}: expected code {case['expected_error']!r}, got {exc.value.code!r}"
        )
        observed_codes.add(exc.value.code)

    # Every required error code must appear at least once
    required = {"invalid_date", "conflicting_adjustment", "unknown_inflow", "out_of_bounds"}
    missing = required - observed_codes
    assert not missing, (
        f"These error codes were never raised by any validation case: {missing}. "
        "Add fixture cases or check 'what' strings."
    )
