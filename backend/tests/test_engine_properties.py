from datetime import date, timedelta
from hypothesis import given, strategies as st
from stretch.engine import (
    compute_runway,
    Situation,
    Inflow,
    ScenarioSpec,
    InflowAdjustment,
    ExtraExpense,
)

# Generate simple valid situations
@st.composite
def situations(draw):
    balance = draw(st.integers(min_value=0, max_value=100000))
    essentials = draw(st.integers(min_value=1, max_value=5000))
    
    inflow_amount = draw(st.integers(min_value=1, max_value=50000))
    inflow_delay = draw(st.integers(min_value=0, max_value=30))
    
    as_of = date(2026, 1, 1)
    
    inflow = Inflow(
        id="i1",
        label="test",
        expected_amount=inflow_amount,
        expected_date=as_of + timedelta(days=inflow_delay)
    )
    
    return Situation(
        as_of=as_of,
        balance=balance,
        essentials_per_day=essentials,
        inflows=(inflow,),
        horizon_days=60
    )


@given(situations(), st.integers(min_value=1, max_value=365))
def test_delaying_never_extends_runway(situation, delay):
    base_res = compute_runway(situation)
    
    scenario = ScenarioSpec(
        label="Delay",
        adjustments=(InflowAdjustment(inflow_id="i1", delay_days=delay),)
    )
    delayed_res = compute_runway(situation, scenario)
    
    assert delayed_res.runway_days <= base_res.runway_days


@given(situations(), st.floats(min_value=0.0, max_value=0.999))
def test_shrinking_never_extends_runway(situation, factor):
    base_res = compute_runway(situation)
    
    scenario = ScenarioSpec(
        label="Shrink",
        adjustments=(InflowAdjustment(inflow_id="i1", amount_factor=factor),)
    )
    shrunk_res = compute_runway(situation, scenario)
    
    assert shrunk_res.runway_days <= base_res.runway_days


@given(situations())
def test_cancelling_never_extends_runway(situation):
    base_res = compute_runway(situation)
    
    scenario = ScenarioSpec(
        label="Cancel",
        adjustments=(InflowAdjustment(inflow_id="i1", cancelled=True),)
    )
    cancelled_res = compute_runway(situation, scenario)
    
    assert cancelled_res.runway_days <= base_res.runway_days


@given(situations(), st.integers(min_value=1, max_value=10000), st.integers(min_value=0, max_value=60))
def test_adding_expense_never_extends_runway(situation, amount, day_offset):
    base_res = compute_runway(situation)
    
    expense = ExtraExpense(
        label="Test",
        amount=amount,
        date=situation.as_of + timedelta(days=day_offset)
    )
    
    scenario = ScenarioSpec(
        label="Expense",
        extra_expenses=(expense,)
    )
    expense_res = compute_runway(situation, scenario)
    
    assert expense_res.runway_days <= base_res.runway_days


@given(situations())
def test_runway_bounds_and_determinism(situation):
    res1 = compute_runway(situation)
    res2 = compute_runway(situation)
    
    # Determinism
    assert res1 == res2
    
    # Bounds
    assert res1.runway_days <= situation.horizon_days
    assert len(res1.series) == situation.horizon_days
