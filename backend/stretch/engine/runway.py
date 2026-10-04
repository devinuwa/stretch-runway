"""Runway calculation — the core engine, stdlib only.

ARCHITECTURE.md §6 day semantics (exact):
  Day 0 is as_of. For each day n = 0..horizon-1:
    - apply inflows dated that day
    - subtract commitments (and scenario extra_expenses) dated that day
    - subtract essentials_per_day
    - record the end-of-day balance

  A day is *covered* if its end-of-day balance >= 0.
  runway_days = consecutive covered days from day 0 (capped at horizon_days).
  runs_out_on = first uncovered day or None.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from stretch.engine.models import (
    AppliedInflow,
    Commitment,
    ExtraExpense,
    RunwayResult,
    Situation,
    ScenarioSpec,
)
from stretch.engine.scenario import apply_scenario


def compute_runway(
    situation: Situation,
    scenario: Optional[ScenarioSpec] = None,
) -> RunwayResult:
    """Compute the runway for a situation under an optional scenario.

    Returns a RunwayResult with the daily balance series, runway_days,
    runs_out_on date, shortfall info, and applied inflows.
    """
    applied_inflows, extra_expenses = apply_scenario(situation, scenario)

    # Build lookup: date -> total inflow on that date
    inflow_by_date: dict[date, int] = {}
    for inf in applied_inflows:
        inflow_by_date[inf.date] = inflow_by_date.get(inf.date, 0) + inf.amount

    # Build lookup: date -> total outflow (commitments + extra expenses)
    outflow_by_date: dict[date, int] = {}
    for c in situation.commitments:
        outflow_by_date[c.due_date] = outflow_by_date.get(c.due_date, 0) + c.amount
    for e in extra_expenses:
        outflow_by_date[e.date] = outflow_by_date.get(e.date, 0) + e.amount

    # Simulate day by day
    balance = situation.balance
    series: list[int] = []
    runway_days: Optional[int] = None  # will be set when we find first uncovered
    runs_out_on: Optional[date] = None
    shortfall_amount: Optional[int] = None

    for day_n in range(situation.horizon_days):
        current_date = situation.as_of + timedelta(days=day_n)

        # Apply inflows for this day
        balance += inflow_by_date.get(current_date, 0)

        # Subtract commitments and extra expenses for this day
        balance -= outflow_by_date.get(current_date, 0)

        # Subtract daily essentials
        balance -= situation.essentials_per_day

        # Record end-of-day balance
        series.append(balance)

        # Check if this is the first uncovered day
        if balance < 0 and runway_days is None:
            runway_days = day_n
            runs_out_on = current_date
            shortfall_amount = abs(balance)

    # If we never went negative, runway = horizon_days
    if runway_days is None:
        runway_days = situation.horizon_days

    covered_through_horizon = runs_out_on is None

    # Find next_money_after_shortfall
    next_money_after_shortfall: Optional[date] = None
    gap_days: Optional[int] = None
    if runs_out_on is not None:
        # First applied inflow strictly after runs_out_on
        candidates = [inf.date for inf in applied_inflows if inf.date > runs_out_on]
        if candidates:
            next_money_after_shortfall = min(candidates)
            gap_days = (next_money_after_shortfall - runs_out_on).days

    return RunwayResult(
        runway_days=runway_days,
        covered_through_horizon=covered_through_horizon,
        runs_out_on=runs_out_on,
        shortfall_amount=shortfall_amount,
        next_money_after_shortfall=next_money_after_shortfall,
        gap_days=gap_days,
        inflows_applied=applied_inflows,
        horizon_days=situation.horizon_days,
        series=tuple(series),
    )
