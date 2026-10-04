"""Safe daily spend calculation — stdlib only.

ARCHITECTURE.md §6:
  N = days until the first non-cancelled inflow arriving on/after as_of
      (or horizon_days if none).
  If N == 0 -> inflow_today: true, no limit.
  Else: max_daily_total = floor(min over i in 0..N-1 of (balance - C_i)/(i+1)),
         where C_i = commitments and extra expenses due on days 0..i.
  Negative values clamp to 0 with already_short: true.
  headroom = max(0, max_daily_total - essentials).
  covers_essentials = max_daily_total >= essentials.
  It protects only the time until the next money arrives.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

from stretch.engine.models import (
    AppliedInflow,
    Commitment,
    ExtraExpense,
    SafeSpendResult,
    Situation,
    ScenarioSpec,
)
from stretch.engine.scenario import apply_scenario


def compute_safe_spend(
    situation: Situation,
    scenario: Optional[ScenarioSpec] = None,
) -> SafeSpendResult:
    """Compute the safe daily spend for a situation under an optional scenario."""
    applied_inflows, extra_expenses = apply_scenario(situation, scenario)

    # Find N: days until the first non-cancelled inflow on/after as_of
    inflow_dates = [inf.date for inf in applied_inflows if inf.date >= situation.as_of]
    if inflow_dates:
        first_inflow_date = min(inflow_dates)
        n = (first_inflow_date - situation.as_of).days
        target_date = first_inflow_date
    else:
        n = situation.horizon_days
        target_date = None

    if n == 0:
        return SafeSpendResult(
            inflow_today=True,
            target_date=target_date,
            days_to_cover=0,
            max_daily_total=None,
            headroom=None,
            covers_essentials=True,
            already_short=False,
        )

    # Build outflow lookup: date -> commitments + extra expenses
    outflow_by_date: dict[date, int] = {}
    for c in situation.commitments:
        outflow_by_date[c.due_date] = outflow_by_date.get(c.due_date, 0) + c.amount
    for e in extra_expenses:
        outflow_by_date[e.date] = outflow_by_date.get(e.date, 0) + e.amount

    # Compute max_daily_total = floor(min over i in 0..N-1 of (balance - C_i)/(i+1))
    # where C_i = cumulative commitments+extra_expenses due on days 0..i
    cumulative_outflow = 0
    min_val: Optional[float] = None

    for i in range(n):
        current_date = situation.as_of + timedelta(days=i)
        cumulative_outflow += outflow_by_date.get(current_date, 0)
        numerator = situation.balance - cumulative_outflow
        denominator = i + 1
        val = numerator / denominator

        if min_val is None or val < min_val:
            min_val = val

    assert min_val is not None
    max_daily_total = math.floor(min_val)

    already_short = max_daily_total < 0
    if already_short:
        max_daily_total = 0

    headroom = max(0, max_daily_total - situation.essentials_per_day)
    covers_essentials = max_daily_total >= situation.essentials_per_day

    return SafeSpendResult(
        inflow_today=False,
        target_date=target_date,
        days_to_cover=n,
        max_daily_total=max_daily_total,
        headroom=headroom,
        covers_essentials=covers_essentials,
        already_short=already_short,
    )
