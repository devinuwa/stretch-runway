"""Affordability check calculation — stdlib only.

ARCHITECTURE.md §6:
  before = runway(S)
  after = runway(S + expense)
  days_lost = before.runway_days - after.runway_days
  next_money = first applied inflow on/after as_of

  breaks(r) = r.runs_out_on exists and (next_money is null or r.runs_out_on < next_money)

  Verdict:
    already_short if breaks(before)
    else breaks_before_next_money if breaks(after)
    else shortens_runway if days_lost > 0
    else fits
"""
from __future__ import annotations

from typing import Optional

from stretch.engine.models import (
    AffordabilityResult,
    ExtraExpense,
    Situation,
    ScenarioSpec,
    RunwayResult,
)
from stretch.engine.runway import compute_runway
from stretch.engine.scenario import apply_scenario


def check_affordability(
    expense: ExtraExpense,
    situation: Situation,
    scenario: Optional[ScenarioSpec] = None,
) -> AffordabilityResult:
    """Check if an expense is affordable under a scenario."""
    
    # Compute before
    before = compute_runway(situation, scenario)
    
    # Create an augmented scenario that includes the expense
    if scenario is None:
        after_scenario = ScenarioSpec(
            label="With Expense",
            extra_expenses=(expense,)
        )
    else:
        after_scenario = ScenarioSpec(
            label=scenario.label,
            adjustments=scenario.adjustments,
            extra_expenses=scenario.extra_expenses + (expense,)
        )
        
    # Compute after
    after = compute_runway(situation, after_scenario)
    
    days_lost = before.runway_days - after.runway_days
    
    # Find next_money
    applied_inflows, _ = apply_scenario(situation, scenario)
    inflow_dates = [inf.date for inf in applied_inflows if inf.date >= situation.as_of]
    next_money = min(inflow_dates) if inflow_dates else None
    
    def breaks(r: RunwayResult) -> bool:
        if r.runs_out_on is None:
            return False
        if next_money is None:
            return True
        return r.runs_out_on < next_money
        
    if breaks(before):
        verdict = "already_short"
    elif breaks(after):
        verdict = "breaks_before_next_money"
    elif days_lost > 0:
        verdict = "shortens_runway"
    else:
        verdict = "fits"
        
    return AffordabilityResult(
        verdict=verdict,
        runway_before=before.runway_days,
        runway_after=after.runway_days,
        days_lost=days_lost,
        runs_out_before=before.runs_out_on,
        runs_out_after=after.runs_out_on,
        next_money_date=next_money,
    )
