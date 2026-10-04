"""Engine data models — pure dataclasses, stdlib only.

All amounts are integers (currency units). All dates are datetime.date.
These match the types in API_CONTRACT.md but are engine-internal (no pydantic).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Commitment:
    """A known future expense (e.g. rent, outfit)."""

    id: str
    label: str
    amount: int  # >= 0
    due_date: date
    flexible: bool  # True = can be skipped; False = must pay


@dataclass(frozen=True)
class Inflow:
    """An expected future income (e.g. money from aunt)."""

    id: str
    label: str
    expected_amount: int  # >= 0
    expected_date: date
    uncertainty_note: Optional[str] = None


@dataclass(frozen=True)
class Situation:
    """The user's current financial situation — all engine inputs."""

    as_of: date
    balance: int  # current balance (integer currency units)
    essentials_per_day: int  # daily essential spending (> 0)
    commitments: tuple[Commitment, ...] = ()
    inflows: tuple[Inflow, ...] = ()
    horizon_days: int = 60
    buffer_days: int = 3
    currency: str = "NGN"


@dataclass(frozen=True)
class InflowAdjustment:
    """Adjustment to an inflow in a scenario.

    Rules (ARCHITECTURE.md §6):
    - inflow_id "*" applies to all inflows
    - delay_days and new_date are mutually exclusive
    - amount_factor and new_amount are mutually exclusive
    - Order: cancel > (delay or new_date) > (amount_factor or new_amount)
    - amount_factor result is floored
    - Bounds: delay_days 0..365, amount_factor 0..2, amounts >= 0
    """

    inflow_id: str  # specific id or "*" for all
    delay_days: Optional[int] = None
    new_date: Optional[date] = None  # resolved from new_date_expr by caller
    amount_factor: Optional[float] = None
    new_amount: Optional[int] = None
    cancelled: bool = False


@dataclass(frozen=True)
class ExtraExpense:
    """An additional one-time expense in a scenario."""

    label: str
    amount: int  # >= 0
    date: date  # resolved from date_expr by caller (null -> as_of)


@dataclass(frozen=True)
class ScenarioSpec:
    """A scenario specification: adjustments to inflows + extra expenses."""

    label: str
    adjustments: tuple[InflowAdjustment, ...] = ()
    extra_expenses: tuple[ExtraExpense, ...] = ()


@dataclass(frozen=True)
class AppliedInflow:
    """An inflow after scenario adjustments have been applied."""

    id: str
    date: date
    amount: int


@dataclass(frozen=True)
class RunwayResult:
    """Result of a runway calculation.

    runway_days: consecutive covered days from day 0 (capped at horizon_days)
    covered_through_horizon: True if never short within the horizon
    runs_out_on: first uncovered day (date) or None
    shortfall_amount: deficit on the first uncovered day, or None
    next_money_after_shortfall: first applied inflow strictly after runs_out_on
    gap_days: days from runs_out_on to next_money_after_shortfall
    inflows_applied: list of inflows with their adjusted dates and amounts
    horizon_days: the horizon used
    series: end-of-day balance for each day [day 0 .. day horizon-1]
    """

    runway_days: int
    covered_through_horizon: bool
    runs_out_on: Optional[date]
    shortfall_amount: Optional[int]
    next_money_after_shortfall: Optional[date]
    gap_days: Optional[int]
    inflows_applied: tuple[AppliedInflow, ...]
    horizon_days: int
    series: tuple[int, ...]


@dataclass(frozen=True)
class SafeSpendResult:
    """Result of safe daily spend calculation."""

    inflow_today: bool
    target_date: Optional[date]  # the date of the next inflow
    days_to_cover: int  # N = days until first non-cancelled inflow
    max_daily_total: Optional[int]  # floor(min ...) or None if inflow_today
    headroom: Optional[int]  # max(0, max_daily_total - essentials)
    covers_essentials: bool
    already_short: bool


@dataclass(frozen=True)
class ReserveResult:
    """Result of essentials reserve calculation."""

    days_to_next_money: int
    buffer_days: int
    essentials_part: int  # essentials * (N + buffer_days)
    must_pay_part: int  # sum of non-flexible commitments due in 0..N-1
    reserve: int  # essentials_part + must_pay_part
    covered: bool  # balance >= reserve
    surplus_or_gap: int  # balance - reserve (signed)


@dataclass(frozen=True)
class AffordabilityResult:
    """Result of affordability check."""

    verdict: str  # fits | shortens_runway | breaks_before_next_money | already_short
    runway_before: int
    runway_after: int
    days_lost: int
    runs_out_before: Optional[date]
    runs_out_after: Optional[date]
    next_money_date: Optional[date]
