"""Date expression resolution — stdlib only.

DateExpr types:
  - iso: {kind: "iso", value: "YYYY-MM-DD"}
  - in_days: {kind: "in_days", n: int}
  - day_of_month: {kind: "day_of_month", day: int, month_offset: 0|1|None}

Resolution rules (ARCHITECTURE.md §6):
  - day_of_month with month_offset None: this month if day >= as_of.day, else next month
  - month_offset 0: this month; 1: next month
  - Invalid dates (e.g. day 31 in 30-day month) raise EngineError("invalid_date")
  - Dates before as_of raise EngineError("invalid_date")
  - Expense date_expr None means as_of
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Optional


class EngineError(Exception):
    """Base error for engine validation failures."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class DateExprKind(Enum):
    ISO = "iso"
    IN_DAYS = "in_days"
    DAY_OF_MONTH = "day_of_month"


@dataclass(frozen=True)
class DateExpr:
    """A date expression that can be resolved against an as_of date."""

    kind: DateExprKind
    # For ISO: the date string "YYYY-MM-DD"
    value: Optional[str] = None
    # For IN_DAYS: number of days from as_of
    n: Optional[int] = None
    # For DAY_OF_MONTH: the day number (1-31)
    day: Optional[int] = None
    # For DAY_OF_MONTH: 0 = this month, 1 = next month, None = auto
    month_offset: Optional[int] = None


def resolve_date(expr: DateExpr, as_of: date) -> date:
    """Resolve a DateExpr to a concrete date.

    Raises EngineError("invalid_date") for invalid or past dates.
    """
    if expr.kind == DateExprKind.ISO:
        assert expr.value is not None
        try:
            resolved = date.fromisoformat(expr.value)
        except ValueError:
            raise EngineError("invalid_date", f"invalid ISO date: {expr.value}")
        if resolved < as_of:
            raise EngineError("invalid_date", f"date {resolved} is before as_of {as_of}")
        return resolved

    elif expr.kind == DateExprKind.IN_DAYS:
        assert expr.n is not None
        if expr.n < 0:
            raise EngineError("invalid_date", f"in_days cannot be negative: {expr.n}")
        return as_of + timedelta(days=expr.n)

    elif expr.kind == DateExprKind.DAY_OF_MONTH:
        assert expr.day is not None
        return _resolve_day_of_month(expr.day, expr.month_offset, as_of)

    raise EngineError("invalid_date", f"unknown DateExpr kind: {expr.kind}")


def _resolve_day_of_month(day: int, month_offset: Optional[int], as_of: date) -> date:
    """Resolve a day_of_month expression.

    month_offset=None: this month if day >= as_of.day, else next month.
    month_offset=0: this month.
    month_offset=1: next month.
    """
    if day < 1 or day > 31:
        raise EngineError("invalid_date", f"day must be 1-31, got {day}")

    if month_offset is None:
        # Auto: this month if day >= as_of.day, else next month
        if day >= as_of.day:
            target_month_offset = 0
        else:
            target_month_offset = 1
    else:
        if month_offset not in (0, 1):
            raise EngineError("invalid_date", f"month_offset must be 0, 1, or null, got {month_offset}")
        target_month_offset = month_offset

    year = as_of.year
    month = as_of.month + target_month_offset
    if month > 12:
        month -= 12
        year += 1

    # Check if the day is valid for the target month
    max_day = calendar.monthrange(year, month)[1]
    if day > max_day:
        raise EngineError(
            "invalid_date",
            f"day {day} is invalid for {year}-{month:02d} (max {max_day})",
        )

    resolved = date(year, month, day)
    if resolved < as_of:
        raise EngineError("invalid_date", f"date {resolved} is before as_of {as_of}")
    return resolved


def convert_essentials(amount: int, period: str) -> int:
    """Convert essentials to per-day amount.

    ARCHITECTURE.md §0.2: week -> ceil(amount/7), month -> ceil(amount/30).
    day -> amount unchanged.

    Returns integer (all currency units are integers).
    """
    import math

    if period == "day":
        return amount
    elif period == "week":
        return math.ceil(amount / 7)
    elif period == "month":
        return math.ceil(amount / 30)
    else:
        raise EngineError("invalid_request", f"unknown essentials period: {period}")
