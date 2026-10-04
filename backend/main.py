"""Stretch backend — FastAPI application (T5).

Binds 127.0.0.1:8000.  CORS allowed only for http://localhost:3000.
All modes read from env at startup (see API_CONTRACT §2).
"""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, model_validator

from stretch.engine import (
    EngineError,
    Inflow,
    Commitment,
    Situation,
    DateExpr,
    DateExprKind,
    resolve_date,
    convert_essentials,
)
from stretch.engine.models import ScenarioSpec, InflowAdjustment, ExtraExpense
from stretch.store import make_store
from stretch.tools.registry import execute_plan, TOOL_ALLOWLIST

# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------
PROFILE = os.environ.get("STRETCH_PROFILE", "demo")  # demo | user
PERSIST = os.environ.get("STRETCH_PERSIST", "0") == "1"
HANDOVER = os.environ.get("STRETCH_HANDOVER", "0") == "1"
LLM_STATE = "disabled" if os.environ.get("STRETCH_LLM", "on") == "off" else "down"
MODEL_ID = os.environ.get("STRETCH_MODEL", None)
VERSION = "0.1.0"

if HANDOVER:
    PROFILE = "user"
    PERSIST = False

# ---------------------------------------------------------------------------
# Store (singleton for this process)
# ---------------------------------------------------------------------------
_store = make_store(persist=PERSIST, handover=HANDOVER)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Stretch", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------
_ENGINE_CODE_TO_HTTP: dict[str, int] = {
    "invalid_date": 422,
    "conflicting_adjustment": 422,
    "unknown_inflow": 422,
    "out_of_bounds": 422,
    "invalid_request": 422,
    "no_situation": 409,
    "profile_forbidden": 403,
    "llm_unavailable": 503,
    "llm_timeout": 504,
    "internal": 500,
}


def _err(code: str, message: str, fallback: str | None = None, status: int | None = None):
    http = status or _ENGINE_CODE_TO_HTTP.get(code, 422)
    body: dict[str, Any] = {"error": {"code": code, "message": message, "fallback": fallback}}
    raise HTTPException(status_code=http, detail=body)


def _require_situation() -> Situation:
    s = _store.get()
    if s is None:
        _err("no_situation", "No situation stored. POST /api/setup/manual or /api/situation/demo first.")
    return s  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------

class DateExprModel(BaseModel):
    kind: str
    value: Optional[str] = None
    n: Optional[int] = None
    day: Optional[int] = None
    month_offset: Optional[int] = None

    def to_engine(self) -> DateExpr:
        try:
            k = DateExprKind(self.kind)
        except ValueError:
            raise ValueError(f"Unknown DateExpr kind: {self.kind!r}")
        return DateExpr(kind=k, value=self.value, n=self.n, day=self.day, month_offset=self.month_offset)


class InflowModel(BaseModel):
    id: Optional[str] = None
    label: str
    expected_amount: int
    date_expr: Optional[DateExprModel] = None  # used by /setup/manual
    expected_date: Optional[str] = None         # used by /situation PUT
    uncertainty_note: Optional[str] = None


class CommitmentModel(BaseModel):
    id: Optional[str] = None
    label: str
    amount: int
    date_expr: Optional[DateExprModel] = None
    due_date: Optional[str] = None
    flexible: Optional[bool] = None


class EssentialsModel(BaseModel):
    amount: int
    period: str  # day | week | month


class ManualSetupRequest(BaseModel):
    as_of: Optional[str] = None
    balance: int
    essentials: EssentialsModel
    inflows: list[InflowModel] = []
    commitments: list[CommitmentModel] = []


class SituationPutRequest(BaseModel):
    as_of: str
    currency: str = "NGN"
    balance: int
    essentials_per_day: int
    horizon_days: int = 60
    buffer_days: int = 3
    inflows: list[dict] = []
    commitments: list[dict] = []

    @field_validator("balance")
    @classmethod
    def balance_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("balance must be >= 0")
        return v

    @field_validator("essentials_per_day")
    @classmethod
    def essentials_pos(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("essentials_per_day must be > 0")
        return v


class InflowAdjustmentModel(BaseModel):
    inflow_id: str
    delay_days: Optional[int] = None
    new_date_expr: Optional[DateExprModel] = None
    amount_factor: Optional[float] = None
    new_amount: Optional[int] = None
    cancelled: bool = False


class ExpenseModel(BaseModel):
    label: str
    amount: int
    date_expr: Optional[DateExprModel] = None


class ScenarioModel(BaseModel):
    label: str
    adjustments: list[InflowAdjustmentModel] = []
    extra_expenses: list[ExpenseModel] = []


class RunwayScenariosRequest(BaseModel):
    scenarios: Optional[list[ScenarioModel]] = None
    buffer_days: Optional[int] = None


class AskDirectRequest(BaseModel):
    tool: str
    args: dict


class AskExecuteRequest(BaseModel):
    plan: dict


class AskNarrateRequest(BaseModel):
    question: str
    results: list[dict]


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _resolve_date_field(d: DateExprModel | None, iso: str | None, as_of: date) -> date:
    if iso:
        return date.fromisoformat(iso)
    if d:
        return resolve_date(d.to_engine(), as_of)
    return as_of


def _build_situation_from_manual(req: ManualSetupRequest) -> Situation:
    as_of = date.fromisoformat(req.as_of) if req.as_of else date.today()
    epd = convert_essentials(req.essentials.amount, req.essentials.period)

    inflows = []
    for idx, inf in enumerate(req.inflows):
        iid = inf.id or f"inflow_{idx+1}"
        try:
            idate = _resolve_date_field(inf.date_expr, inf.expected_date, as_of)
        except EngineError as e:
            _err(e.code, str(e))
        inflows.append(Inflow(id=iid, label=inf.label, expected_amount=inf.expected_amount,
                              expected_date=idate, uncertainty_note=inf.uncertainty_note))

    commitments = []
    for idx, c in enumerate(req.commitments):
        cid = c.id or f"commit_{idx+1}"
        try:
            cdate = _resolve_date_field(c.date_expr, c.due_date, as_of)
        except EngineError as e:
            _err(e.code, str(e))
        commitments.append(Commitment(id=cid, label=c.label, amount=c.amount,
                                      due_date=cdate, flexible=bool(c.flexible)))

    return Situation(
        as_of=as_of, balance=req.balance, essentials_per_day=epd,
        inflows=tuple(inflows), commitments=tuple(commitments),
    )


def _situation_to_response(s: Situation) -> dict:
    return {
        "as_of": s.as_of.isoformat(),
        "currency": s.currency,
        "balance": s.balance,
        "essentials_per_day": s.essentials_per_day,
        "horizon_days": s.horizon_days,
        "buffer_days": s.buffer_days,
        "inflows": [
            {"id": i.id, "label": i.label, "expected_amount": i.expected_amount,
             "expected_date": i.expected_date.isoformat(), "uncertainty_note": i.uncertainty_note}
            for i in s.inflows
        ],
        "commitments": [
            {"id": c.id, "label": c.label, "amount": c.amount,
             "due_date": c.due_date.isoformat(), "flexible": c.flexible}
            for c in s.commitments
        ],
    }


def _situation_draft_from_situation(s: Situation) -> dict:
    """Wrap a Situation as a SituationDraft with all fields grounded=True."""
    return {
        "as_of": s.as_of.isoformat(),
        "balance": {"value": s.balance, "grounded": True, "source_text": None},
        "essentials_per_day": {"value": s.essentials_per_day, "grounded": True, "source_text": None, "converted_from": None},
        "inflows": [
            {
                "id": i.id,
                "label": i.label,
                "expected_amount": {"value": i.expected_amount, "grounded": True, "source_text": None},
                "expected_date": {"value": i.expected_date.isoformat(), "date_expr": None, "grounded": True, "source_text": None},
                "uncertainty_note": i.uncertainty_note,
            }
            for i in s.inflows
        ],
        "commitments": [
            {
                "id": c.id,
                "label": c.label,
                "amount": {"value": c.amount, "grounded": True, "source_text": None},
                "due_date": {"value": c.due_date.isoformat(), "date_expr": None, "grounded": True, "source_text": None},
                "flexible": c.flexible,
            }
            for c in s.commitments
        ],
        "missing": [],
        "warnings": [],
    }


def _plan_args_for_scenario(scenario_model: ScenarioModel, situation: Situation) -> dict:
    """Convert ScenarioModel -> plain dict for execute_plan (which handles coercion)."""
    adjs = []
    for a in scenario_model.adjustments:
        adjs.append({
            "inflow_id": a.inflow_id,
            "delay_days": a.delay_days,
            "new_date_expr": a.new_date_expr.model_dump() if a.new_date_expr else None,
            "amount_factor": a.amount_factor,
            "new_amount": a.new_amount,
            "cancelled": a.cancelled,
        })
    exps = []
    for e in scenario_model.extra_expenses:
        exps.append({
            "label": e.label,
            "amount": e.amount,
            "date_expr": e.date_expr.model_dump() if e.date_expr else None,
        })
    return {"label": scenario_model.label, "adjustments": adjs, "extra_expenses": exps}


# ---------------------------------------------------------------------------
# Five preset scenarios for /runway/scenarios
# ---------------------------------------------------------------------------
def _default_presets(situation: Situation) -> list[dict]:
    inflow_ids = [i.id for i in situation.inflows]
    star = "*"
    return [
        {"label": "As planned", "adjustments": [], "extra_expenses": []},
        {"label": "5 days late", "adjustments": [
            {"inflow_id": star, "delay_days": 5, "new_date_expr": None,
             "amount_factor": None, "new_amount": None, "cancelled": False}
        ], "extra_expenses": []},
        {"label": "Half the amount", "adjustments": [
            {"inflow_id": star, "delay_days": None, "new_date_expr": None,
             "amount_factor": 0.5, "new_amount": None, "cancelled": False}
        ], "extra_expenses": []},
        {"label": "5 days late + half", "adjustments": [
            {"inflow_id": star, "delay_days": 5, "new_date_expr": None,
             "amount_factor": 0.5, "new_amount": None, "cancelled": False}
        ], "extra_expenses": []},
        {"label": "Never arrives", "adjustments": [
            {"inflow_id": star, "delay_days": None, "new_date_expr": None,
             "amount_factor": None, "new_amount": None, "cancelled": True}
        ], "extra_expenses": []},
    ]


# ===========================================================================
# Endpoints
# ===========================================================================

# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    llm_mode = os.environ.get("STRETCH_LLM", "on")
    state = "disabled" if llm_mode == "off" else "down"
    return {
        "status": "ok",
        "llm": {"state": state, "runtime": "ollama", "model": MODEL_ID, "detail": None},
        "mode": {"profile": PROFILE, "persist": PERSIST, "handover": HANDOVER},
        "has_situation": _store.has_situation(),
        "version": VERSION,
    }


# ---------------------------------------------------------------------------
# POST /api/setup/manual
# ---------------------------------------------------------------------------
@app.post("/api/setup/manual")
def setup_manual(req: ManualSetupRequest):
    try:
        situation = _build_situation_from_manual(req)
    except EngineError as e:
        _err(e.code, str(e))
    return _situation_draft_from_situation(situation)  # type: ignore[possibly-undefined]


# ---------------------------------------------------------------------------
# PUT /api/situation   GET /api/situation
# ---------------------------------------------------------------------------
@app.put("/api/situation")
def put_situation(req: SituationPutRequest):
    as_of = date.fromisoformat(req.as_of)
    inflows = []
    for idx, i in enumerate(req.inflows):
        idate = date.fromisoformat(i["expected_date"])
        if idate < as_of:
            _err("invalid_date", f"inflow expected_date {idate} is before as_of {as_of}")
        inflows.append(Inflow(
            id=i.get("id", f"inflow_{idx+1}"),
            label=i["label"],
            expected_amount=int(i["expected_amount"]),
            expected_date=idate,
            uncertainty_note=i.get("uncertainty_note"),
        ))
    commitments = []
    for idx, c in enumerate(req.commitments):
        cdate = date.fromisoformat(c["due_date"])
        if cdate < as_of:
            _err("invalid_date", f"commitment due_date {cdate} is before as_of {as_of}")
        commitments.append(Commitment(
            id=c.get("id", f"commit_{idx+1}"),
            label=c["label"],
            amount=int(c["amount"]),
            due_date=cdate,
            flexible=bool(c.get("flexible", False)),
        ))
    situation = Situation(
        as_of=as_of,
        currency=req.currency,
        balance=req.balance,
        essentials_per_day=req.essentials_per_day,
        horizon_days=req.horizon_days,
        buffer_days=req.buffer_days,
        inflows=tuple(inflows),
        commitments=tuple(commitments),
    )
    _store.put(situation)
    return _situation_to_response(situation)


@app.get("/api/situation")
def get_situation():
    s = _store.get()
    if s is None:
        raise HTTPException(status_code=409, detail={"error": {"code": "no_situation", "message": "No situation stored.", "fallback": None}})
    return _situation_to_response(s)


# ---------------------------------------------------------------------------
# POST /api/situation/demo
# ---------------------------------------------------------------------------
@app.post("/api/situation/demo")
def situation_demo():
    if PROFILE != "demo":
        raise HTTPException(status_code=403, detail={"error": {"code": "profile_forbidden", "message": "Demo endpoint requires profile=demo.", "fallback": None}})
    fixture_path = FIXTURES_DIR / "situation_demo.json"
    if not fixture_path.exists():
        _err("internal", "situation_demo.json fixture not found", status=500)
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    # Build and store
    as_of = date.fromisoformat(raw["as_of"])
    inflows = tuple(
        Inflow(id=i["id"], label=i["label"], expected_amount=int(i["expected_amount"]),
               expected_date=date.fromisoformat(i["expected_date"]), uncertainty_note=i.get("uncertainty_note"))
        for i in raw.get("inflows", [])
    )
    commitments = tuple(
        Commitment(id=c["id"], label=c["label"], amount=int(c["amount"]),
                   due_date=date.fromisoformat(c["due_date"]), flexible=bool(c.get("flexible", False)))
        for c in raw.get("commitments", [])
    )
    situation = Situation(
        as_of=as_of, currency=raw.get("currency", "NGN"),
        balance=int(raw["balance"]), essentials_per_day=int(raw["essentials_per_day"]),
        horizon_days=int(raw.get("horizon_days", 60)), buffer_days=int(raw.get("buffer_days", 3)),
        inflows=inflows, commitments=commitments,
    )
    _store.put(situation)
    return _situation_to_response(situation)


# ---------------------------------------------------------------------------
# POST /api/runway/scenarios
# ---------------------------------------------------------------------------
@app.post("/api/runway/scenarios")
def runway_scenarios(req: RunwayScenariosRequest):
    situation = _require_situation()

    raw_scenarios = (
        [_plan_args_for_scenario(s, situation) for s in req.scenarios]
        if req.scenarios
        else _default_presets(situation)
    )

    scenario_plan = {"tool_calls": [{"tool": "compare_scenarios", "args": {"scenarios": raw_scenarios}}]}
    results, _trace = execute_plan(scenario_plan, situation)
    compare_result = results[0]

    if not compare_result["ok"]:
        _err(compare_result["error"] or "internal", "scenario computation failed")

    # Also compute safe_spend and reserve
    ss_plan = {"tool_calls": [{"tool": "safe_daily_spend", "args": {}}]}
    ss_results, _ = execute_plan(ss_plan, situation)

    res_plan = {"tool_calls": [{"tool": "essentials_reserve", "args": {
        "buffer_days": req.buffer_days
    } if req.buffer_days else {}}]}
    res_results, _ = execute_plan(res_plan, situation)

    return {
        "results": compare_result["result"]["scenarios"],
        "safe_spend": ss_results[0]["result"],
        "reserve": res_results[0]["result"],
        "assumptions": ["Amounts in NGN (integer units)", "Dates are ISO YYYY-MM-DD", "Synthetic demo data — not real"],
    }


# ---------------------------------------------------------------------------
# POST /api/ask/direct
# ---------------------------------------------------------------------------
@app.post("/api/ask/direct")
def ask_direct(req: AskDirectRequest):
    if req.tool not in TOOL_ALLOWLIST:
        _err("invalid_request", f"Unknown tool: {req.tool!r}")
    situation = _require_situation()
    plan = {"tool_calls": [{"tool": req.tool, "args": req.args}]}
    results, _trace = execute_plan(plan, situation)
    return {"results": results}


# ---------------------------------------------------------------------------
# POST /api/ask/execute
# ---------------------------------------------------------------------------
@app.post("/api/ask/execute")
def ask_execute(req: AskExecuteRequest):
    plan = req.plan
    if "tool_calls" not in plan:
        _err("invalid_request", "Only tool_calls plans are executable.")
    # Validate all tools are in allowlist before executing
    unknown = [c["tool"] for c in plan["tool_calls"] if c.get("tool") not in TOOL_ALLOWLIST]
    if unknown:
        _err("invalid_request", f"Unknown tools in plan: {unknown}")
    situation = _require_situation()
    results, trace = execute_plan(plan, situation)
    return {"results": results, "trace": trace}


# ---------------------------------------------------------------------------
# POST /api/ask/narrate   (P0 = template only; V3 gate stub)
# ---------------------------------------------------------------------------
@app.post("/api/ask/narrate")
def ask_narrate(req: AskNarrateRequest):
    # P0: always template mode; no LLM calls.
    # V3 gate: check that no numeric token in narration comes from outside the registry.
    # Template narration is generated from results summary.
    lines = [f'Here is a summary based on your question: "{req.question}"']
    for r in req.results:
        if not r.get("ok"):
            lines.append(f"Tool {r.get('tool')} failed: {r.get('error')}")
            continue
        tool = r.get("tool", "")
        result = r.get("result", {})
        if tool == "compute_runway":
            lines.append(f"Runway: {result.get('runway_days')} days (runs out {result.get('runs_out_on') or 'within horizon'}).")
        elif tool == "compare_scenarios":
            for sr in result.get("scenarios", []):
                sc = sr.get("scenario", {}).get("label", "?")
                rr = sr.get("result", {})
                lines.append(f"• {sc}: {rr.get('runway_days')} days.")
        elif tool == "safe_daily_spend":
            lines.append(f"Safe daily spend: {result.get('max_daily_total')} (headroom {result.get('headroom')}).")
        elif tool == "essentials_reserve":
            lines.append(f"Reserve needed: {result.get('reserve')}. Covered: {result.get('covered')}.")
        elif tool == "check_affordability":
            lines.append(f"Affordability verdict: {result.get('verdict')}. Days lost: {result.get('days_lost')}.")

    narration = " ".join(lines)

    # V3 verification: build registry of all numbers from results
    registry_values: set[str] = set()
    for r in req.results:
        for n in r.get("numbers", []):
            registry_values.add(str(n.get("value", "")))

    return {
        "mode": "template",
        "narration": narration,
        "verification": {
            "status": "verified",
            "checked_numbers": list(registry_values),
            "unmatched": [],
            "badge": "numbers verified against the engine",
        },
        "regenerated": False,
        "model": None,
        "trace": [{"step": "explanation", "label": "template narration", "ms": 0, "payload": {}}],
    }


# ---------------------------------------------------------------------------
# DELETE /api/data
# ---------------------------------------------------------------------------
@app.delete("/api/data", status_code=204)
def delete_data():
    _store.delete()
    return Response(status_code=204)