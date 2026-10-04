"""Scenario application — applies adjustments to inflows, stdlib only.

ARCHITECTURE.md §6 rules:
- "*" adjustments apply to all inflows first
- Specific id adjustments apply on top
- Order inside one adjustment: cancel > (delay or new_date) > (amount_factor or new_amount)
- amount_factor result is floored
- Bounds: delay_days 0..365, amount_factor 0..2, amounts >= 0
- delay_days and new_date are mutually exclusive
- amount_factor and new_amount are mutually exclusive
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Optional

from stretch.engine.dates import EngineError
from stretch.engine.models import (
    AppliedInflow,
    ExtraExpense,
    Inflow,
    InflowAdjustment,
    ScenarioSpec,
    Situation,
)


def validate_adjustment(adj: InflowAdjustment, situation: Situation) -> None:
    """Validate an adjustment against bounds and the situation.

    Raises EngineError for violations.
    """
    # Check mutual exclusivity
    if adj.delay_days is not None and adj.new_date is not None:
        raise EngineError(
            "conflicting_adjustment",
            f"delay_days and new_date_expr are mutually exclusive for inflow_id={adj.inflow_id}",
        )
    if adj.amount_factor is not None and adj.new_amount is not None:
        raise EngineError(
            "conflicting_adjustment",
            f"amount_factor and new_amount are mutually exclusive for inflow_id={adj.inflow_id}",
        )
    
    if adj.new_date is not None and adj.new_date < situation.as_of:
        raise EngineError(
            "invalid_date",
            f"new_date {adj.new_date} is earlier than as_of {situation.as_of}",
        )

    # Bounds checks
    if adj.delay_days is not None:
        if adj.delay_days < 0 or adj.delay_days > 365:
            raise EngineError(
                "out_of_bounds",
                f"delay_days must be 0..365, got {adj.delay_days}",
            )
    if adj.amount_factor is not None:
        if adj.amount_factor < 0 or adj.amount_factor > 2:
            raise EngineError(
                "out_of_bounds",
                f"amount_factor must be 0..2, got {adj.amount_factor}",
            )
    if adj.new_amount is not None:
        if adj.new_amount < 0:
            raise EngineError(
                "out_of_bounds",
                f"new_amount must be >= 0, got {adj.new_amount}",
            )

    # Check inflow_id exists (unless wildcard)
    if adj.inflow_id != "*":
        known_ids = {inf.id for inf in situation.inflows}
        if adj.inflow_id not in known_ids:
            raise EngineError(
                "unknown_inflow",
                f"inflow_id '{adj.inflow_id}' not found in situation",
            )


def validate_scenario(scenario: ScenarioSpec, situation: Situation) -> None:
    """Validate all adjustments in a scenario."""
    for adj in scenario.adjustments:
        validate_adjustment(adj, situation)


def apply_scenario(
    situation: Situation,
    scenario: Optional[ScenarioSpec] = None,
) -> tuple[tuple[AppliedInflow, ...], tuple[ExtraExpense, ...]]:
    """Apply a scenario's adjustments to the situation's inflows.

    Returns (applied_inflows, extra_expenses).
    Applied inflows have their dates and amounts adjusted per the scenario.
    Cancelled inflows are excluded.
    """
    if scenario is None:
        # No adjustments — return inflows as-is
        applied = tuple(
            AppliedInflow(id=inf.id, date=inf.expected_date, amount=inf.expected_amount)
            for inf in situation.inflows
        )
        return applied, ()

    validate_scenario(scenario, situation)

    # Build a mutable working copy per inflow
    working: dict[str, dict] = {}
    for inf in situation.inflows:
        working[inf.id] = {
            "id": inf.id,
            "date": inf.expected_date,
            "amount": inf.expected_amount,
            "cancelled": False,
        }

    # Apply wildcard adjustments first, then specific ones
    wildcard_adjs = [a for a in scenario.adjustments if a.inflow_id == "*"]
    specific_adjs = [a for a in scenario.adjustments if a.inflow_id != "*"]

    for adj in wildcard_adjs:
        for iid in working:
            _apply_one_adjustment(working[iid], adj)

    for adj in specific_adjs:
        if adj.inflow_id in working:
            _apply_one_adjustment(working[adj.inflow_id], adj)

    # Build results, excluding cancelled
    applied = tuple(
        AppliedInflow(id=w["id"], date=w["date"], amount=w["amount"])
        for w in working.values()
        if not w["cancelled"]
    )

    return applied, scenario.extra_expenses


def _apply_one_adjustment(working: dict, adj: InflowAdjustment) -> None:
    """Apply a single adjustment to a working inflow dict.

    Order: cancel > (delay or new_date) > (amount_factor or new_amount).
    """
    if adj.cancelled:
        working["cancelled"] = True
        return

    # Date adjustments
    if adj.delay_days is not None:
        working["date"] = working["date"] + timedelta(days=adj.delay_days)
    elif adj.new_date is not None:
        working["date"] = adj.new_date

    # Amount adjustments (amount_factor result is floored)
    if adj.amount_factor is not None:
        working["amount"] = math.floor(working["amount"] * adj.amount_factor)
    elif adj.new_amount is not None:
        working["amount"] = adj.new_amount
