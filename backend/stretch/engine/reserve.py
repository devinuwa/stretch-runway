"""Essentials reserve calculation — stdlib only.

ARCHITECTURE.md §6:
  N = days until first non-cancelled inflow on/after as_of (or horizon_days if none).
  reserve = essentials * (N + buffer_days) + sum(non-flexible commitments due on days 0..N-1).
  Returns covered and signed surplus_or_gap.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from stretch.engine.models import (
    AppliedInflow,
    Commitment,
    ReserveResult,
    Situation,
    ScenarioSpec,
)
from stretch.engine.scenario import apply_scenario


def compute_reserve(
    situation: Situation,
    buffer_days: Optional[int] = None,
    scenario: Optional[ScenarioSpec] = None,
) -> ReserveResult:
    """Compute the essentials reserve for a situation under an optional scenario."""
    applied_inflows, extra_expenses = apply_scenario(situation, scenario)
    
    if buffer_days is None:
        buffer_days = situation.buffer_days

    # Find N: days until the first non-cancelled inflow on/after as_of
    inflow_dates = [inf.date for inf in applied_inflows if inf.date >= situation.as_of]
    if inflow_dates:
        first_inflow_date = min(inflow_dates)
        n = (first_inflow_date - situation.as_of).days
    else:
        n = situation.horizon_days

    # Calculate essentials part
    essentials_part = situation.essentials_per_day * (n + buffer_days)

    # Calculate must-pay part (non-flexible commitments due in 0..N-1)
    must_pay_part = 0
    cutoff_date = situation.as_of + timedelta(days=n)
    
    for c in situation.commitments:
        if not c.flexible and situation.as_of <= c.due_date < cutoff_date:
            must_pay_part += c.amount

    reserve = essentials_part + must_pay_part
    surplus_or_gap = situation.balance - reserve
    covered = surplus_or_gap >= 0

    return ReserveResult(
        days_to_next_money=n,
        buffer_days=buffer_days,
        essentials_part=essentials_part,
        must_pay_part=must_pay_part,
        reserve=reserve,
        covered=covered,
        surplus_or_gap=surplus_or_gap,
    )
