"""Pydantic models for the LLM extraction (S1) and planning (S2) stages.

All models that are sent to the LLM as a JSON schema use
``model_config = ConfigDict(extra="forbid")`` so that the generated
JSON Schema includes ``"additionalProperties": false``.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal


# ---------------------------------------------------------------------------
# S1  Extractor
#
# `FlatExtraction` is the FLAT, closed shape sent to the model: no nested date
# objects, only scalar fields (date_kind/date_day/date_in_days/date_value).
# Code maps it to the nested `ExtractorOutput` consumed by the API layer, so the
# model never names an internal key and can never compute a date or amount.
# ---------------------------------------------------------------------------

class ExtractorDateExpr(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["iso", "in_days", "day_of_month"]
    value: Optional[str] = None
    n: Optional[int] = None
    day: Optional[int] = None
    month_offset: Optional[int] = None


class ExtractorEssentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Optional[int] = None
    period: Literal["day", "week", "month"] = "day"


class ExtractorInflow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    expected_amount: Optional[int] = None
    date_expr: Optional[ExtractorDateExpr] = None
    uncertainty_note: Optional[str] = None


class ExtractorCommitment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    amount: Optional[int] = None
    date_expr: Optional[ExtractorDateExpr] = None
    flexible: Optional[bool] = None


class ExtractorOutput(BaseModel):
    """Internal (nested) extraction result. `grounding` is V1 output, not model output."""
    model_config = ConfigDict(extra="forbid")
    balance: Optional[int] = None
    essentials: Optional[ExtractorEssentials] = None
    inflows: list[ExtractorInflow] = []
    commitments: list[ExtractorCommitment] = []
    grounding: Optional[dict] = None


DATE_KIND_ENUM = Literal["iso", "in_days", "day_of_month"]


class FlatInflow(BaseModel):
    """What the model emits for one inflow: scalar date fields, no nesting."""
    model_config = ConfigDict(extra="forbid")
    label: str
    amount: Optional[int] = None
    date_kind: Optional[DATE_KIND_ENUM] = None
    date_value: Optional[str] = None          # iso: "2026-10-15"
    date_day: Optional[int] = None            # day_of_month: 15
    date_in_days: Optional[int] = None        # in_days: 3
    date_month_offset: Optional[int] = None
    uncertainty_note: Optional[str] = None


class FlatCommitment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    amount: Optional[int] = None
    date_kind: Optional[DATE_KIND_ENUM] = None
    date_value: Optional[str] = None
    date_day: Optional[int] = None
    date_in_days: Optional[int] = None
    date_month_offset: Optional[int] = None
    flexible: Optional[bool] = None


class FlatExtraction(BaseModel):
    """The flat object the model emits for S1. Unknown values are null, never guessed."""
    model_config = ConfigDict(extra="forbid")
    balance: Optional[int] = None
    essentials_amount: Optional[int] = None
    essentials_period: Literal["day", "week", "month"] = "day"
    inflows: list[FlatInflow] = []
    commitments: list[FlatCommitment] = []


# ---------------------------------------------------------------------------
# S2  Planner — FLAT, constrained schema sent to the model
#
# The model emits one flat object (action + tool + scenarios + expense +
# clarify_question). Code maps it to the API_CONTRACT Plan; the model never
# names contract arg keys, so it cannot invent them. extra="forbid" makes the
# JSON schema carry "additionalProperties": false.
# ---------------------------------------------------------------------------

TOOL_ENUM = Literal[
    "compute_runway",
    "compare_scenarios",
    "safe_daily_spend",
    "check_affordability",
    "essentials_reserve",
]

ACTION_ENUM = Literal["run", "clarify", "refuse"]


class PlannerAdjustment(BaseModel):
    """One inflow adjustment.  Flat: no nested date objects, no factor+amount pair."""
    model_config = ConfigDict(extra="forbid")
    inflow_id: str
    delay_days: Optional[int] = None
    amount_factor: Optional[float] = None
    new_amount: Optional[int] = None
    cancelled: bool = False


class PlannerScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    adjustments: list[PlannerAdjustment] = []


class PlannerExpense(BaseModel):
    """A purchase to test.  Exactly one of day_of_month / in_days (or neither)."""
    model_config = ConfigDict(extra="forbid")
    label: str
    amount: int
    day_of_month: Optional[int] = None
    in_days: Optional[int] = None


class PlannerOutput(BaseModel):
    """The flat object the model emits for S2."""
    model_config = ConfigDict(extra="forbid")
    action: ACTION_ENUM
    tool: Optional[TOOL_ENUM] = None
    scenarios: Optional[list[PlannerScenario]] = Field(default=None, max_length=5)
    expense: Optional[PlannerExpense] = None
    clarify_question: Optional[str] = None
