"""Engine public API."""

from stretch.engine.affordability import check_affordability
from stretch.engine.dates import DateExpr, DateExprKind, EngineError, convert_essentials, resolve_date
from stretch.engine.models import (
    AffordabilityResult,
    AppliedInflow,
    Commitment,
    ExtraExpense,
    Inflow,
    InflowAdjustment,
    ReserveResult,
    RunwayResult,
    SafeSpendResult,
    ScenarioSpec,
    Situation,
)
from stretch.engine.reserve import compute_reserve
from stretch.engine.runway import compute_runway
from stretch.engine.safe_spend import compute_safe_spend
from stretch.engine.scenario import apply_scenario

__all__ = [
    "DateExpr",
    "DateExprKind",
    "EngineError",
    "convert_essentials",
    "resolve_date",
    "Commitment",
    "Inflow",
    "Situation",
    "InflowAdjustment",
    "ExtraExpense",
    "ScenarioSpec",
    "AppliedInflow",
    "RunwayResult",
    "SafeSpendResult",
    "ReserveResult",
    "AffordabilityResult",
    "check_affordability",
    "compute_reserve",
    "compute_runway",
    "compute_safe_spend",
    "apply_scenario",
]
