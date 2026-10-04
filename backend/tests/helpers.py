import json
from datetime import date
from typing import Any

from stretch.engine.dates import DateExpr, DateExprKind
from stretch.engine.models import (
    Commitment,
    ExtraExpense,
    Inflow,
    InflowAdjustment,
    ScenarioSpec,
    Situation,
)


def load_date_expr(data: dict) -> DateExpr:
    kind = data["kind"]
    if kind == "iso":
        return DateExpr(kind=DateExprKind.ISO, value=data["value"])
    elif kind == "in_days":
        return DateExpr(kind=DateExprKind.IN_DAYS, n=data["n"])
    elif kind == "day_of_month":
        return DateExpr(kind=DateExprKind.DAY_OF_MONTH, day=data["day"], month_offset=data.get("month_offset"))
    raise ValueError(f"Unknown kind {kind}")


def load_inflow(data: dict) -> Inflow:
    return Inflow(
        id=data["id"],
        label=data["label"],
        expected_amount=data["expected_amount"],
        expected_date=date.fromisoformat(data["expected_date"]),
        uncertainty_note=data.get("uncertainty_note"),
    )


def load_commitment(data: dict) -> Commitment:
    return Commitment(
        id=data["id"],
        label=data["label"],
        amount=data["amount"],
        due_date=date.fromisoformat(data["due_date"]),
        flexible=data["flexible"],
    )


def load_situation(data: dict) -> Situation:
    return Situation(
        as_of=date.fromisoformat(data["as_of"]),
        balance=data["balance"],
        essentials_per_day=data["essentials_per_day"],
        commitments=tuple(load_commitment(c) for c in data.get("commitments", [])),
        inflows=tuple(load_inflow(i) for i in data.get("inflows", [])),
        horizon_days=data.get("horizon_days", 60),
        buffer_days=data.get("buffer_days", 3),
        currency=data.get("currency", "NGN"),
    )


def load_adjustment(data: dict) -> InflowAdjustment:
    return InflowAdjustment(
        inflow_id=data["inflow_id"],
        delay_days=data.get("delay_days"),
        new_date=date.fromisoformat(data["new_date"]) if data.get("new_date") else None,
        amount_factor=data.get("amount_factor"),
        new_amount=data.get("new_amount"),
        cancelled=data.get("cancelled", False),
    )


def load_expense(data: dict) -> ExtraExpense:
    return ExtraExpense(
        label=data["label"],
        amount=data["amount"],
        date=date.fromisoformat(data["date"]) if data.get("date") else None,
    )


def load_scenario(data: dict) -> ScenarioSpec:
    return ScenarioSpec(
        label=data["label"],
        adjustments=tuple(load_adjustment(a) for a in data.get("adjustments", [])),
        extra_expenses=tuple(load_expense(e) for e in data.get("extra_expenses", [])),
    )
