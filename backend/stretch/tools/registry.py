"""Tool registry and executor (T3).

The registry holds the five P0 tools. The executor takes a Plan (tool_calls list)
and runs each call against the current Situation stored in the session store.

Architecture rule: this module imports engine and store, never llm or pipeline.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from stretch.engine import (
    EngineError,
    Situation,
    ScenarioSpec,
    InflowAdjustment,
    ExtraExpense,
    DateExpr,
    DateExprKind,
    compute_runway,
    compute_safe_spend,
    compute_reserve,
    check_affordability,
    resolve_date,
    convert_essentials,
)
from stretch.engine.models import AffordabilityResult, RunwayResult

# ---------------------------------------------------------------------------
# Numbers registry helpers
# ---------------------------------------------------------------------------

@dataclass
class NumberEntry:
    path: str
    value: Any
    type: str  # "money" | "days" | "date" | "int"


def _date_str(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _registry_from_runway(prefix: str, r: RunwayResult) -> list[NumberEntry]:
    entries: list[NumberEntry] = [
        NumberEntry(f"{prefix}.runway_days", r.runway_days, "days"),
    ]
    if r.runs_out_on:
        entries.append(NumberEntry(f"{prefix}.runs_out_on", _date_str(r.runs_out_on), "date"))
    if r.shortfall_amount is not None:
        entries.append(NumberEntry(f"{prefix}.shortfall_amount", r.shortfall_amount, "money"))
    if r.gap_days is not None:
        entries.append(NumberEntry(f"{prefix}.gap_days", r.gap_days, "days"))
    if r.next_money_after_shortfall:
        entries.append(NumberEntry(f"{prefix}.next_money_after_shortfall", _date_str(r.next_money_after_shortfall), "date"))
    for k, inf in enumerate(r.inflows_applied):
        entries.append(NumberEntry(f"{prefix}.inflows_applied[{k}].date", _date_str(inf.date), "date"))
        entries.append(NumberEntry(f"{prefix}.inflows_applied[{k}].amount", inf.amount, "money"))
    return entries


# ---------------------------------------------------------------------------
# Argument coercion helpers
# ---------------------------------------------------------------------------

def _coerce_date_expr(raw: dict | None) -> DateExpr | None:
    if raw is None:
        return None
    kind_str = raw.get("kind", "")
    try:
        kind = DateExprKind(kind_str)
    except ValueError:
        raise EngineError("invalid_request", f"Unknown date expr kind: {kind_str!r}")
    return DateExpr(
        kind=kind,
        value=raw.get("value"),
        n=raw.get("n"),
        day=raw.get("day"),
        month_offset=raw.get("month_offset"),
    )


def _coerce_adjustment(raw: dict, situation: Situation) -> InflowAdjustment:
    """Build an InflowAdjustment from API JSON. Resolves new_date_expr -> new_date."""
    new_date_expr = _coerce_date_expr(raw.get("new_date_expr"))
    new_date = None
    if new_date_expr is not None:
        new_date = resolve_date(new_date_expr, situation.as_of)
    return InflowAdjustment(
        inflow_id=raw["inflow_id"],
        delay_days=raw.get("delay_days"),
        new_date=new_date,
        amount_factor=raw.get("amount_factor"),
        new_amount=raw.get("new_amount"),
        cancelled=raw.get("cancelled", False),
    )


def _coerce_expense(raw: dict, situation: Situation) -> ExtraExpense:
    date_expr = _coerce_date_expr(raw.get("date_expr"))
    exp_date = resolve_date(date_expr, situation.as_of) if date_expr else situation.as_of
    return ExtraExpense(label=raw["label"], amount=int(raw["amount"]), date=exp_date)


def _coerce_scenario(raw: dict, situation: Situation) -> ScenarioSpec:
    adjs = tuple(_coerce_adjustment(a, situation) for a in raw.get("adjustments", []))
    exps = tuple(_coerce_expense(e, situation) for e in raw.get("extra_expenses", []))
    return ScenarioSpec(label=raw.get("label", ""), adjustments=adjs, extra_expenses=exps)


# ---------------------------------------------------------------------------
# Individual tool implementations
# ---------------------------------------------------------------------------

def _tool_compute_runway(args: dict, situation: Situation) -> tuple[dict, list[NumberEntry]]:
    scenario = _coerce_scenario(args.get("scenario", {}), situation) if args.get("scenario") else None
    r = compute_runway(situation, scenario)
    numbers = _registry_from_runway("runway", r)
    result = {
        "runway_days": r.runway_days,
        "covered_through_horizon": r.covered_through_horizon,
        "runs_out_on": _date_str(r.runs_out_on),
        "shortfall_amount": r.shortfall_amount,
        "next_money_after_shortfall": _date_str(r.next_money_after_shortfall),
        "gap_days": r.gap_days,
        "inflows_applied": [{"id": i.id, "date": _date_str(i.date), "amount": i.amount} for i in r.inflows_applied],
        "horizon_days": r.horizon_days,
        "series": list(r.series),
    }
    return result, numbers


def _tool_compare_scenarios(args: dict, situation: Situation) -> tuple[dict, list[NumberEntry]]:
    raw_scenarios = args.get("scenarios", [])
    scenario_objects = [_coerce_scenario(s, situation) for s in raw_scenarios]
    results = []
    numbers: list[NumberEntry] = []
    for i, (raw, spec) in enumerate(zip(raw_scenarios, scenario_objects)):
        r = compute_runway(situation, spec)
        numbers.extend(_registry_from_runway(f"runway[{i}]", r))
        results.append({
            "scenario": raw,
            "result": {
                "runway_days": r.runway_days,
                "covered_through_horizon": r.covered_through_horizon,
                "runs_out_on": _date_str(r.runs_out_on),
                "shortfall_amount": r.shortfall_amount,
                "next_money_after_shortfall": _date_str(r.next_money_after_shortfall),
                "gap_days": r.gap_days,
                "inflows_applied": [{"id": i.id, "date": _date_str(i.date), "amount": i.amount} for i in r.inflows_applied],
                "horizon_days": r.horizon_days,
                "series": list(r.series),
            },
        })
    # deltas between first two scenarios
    deltas: dict = {}
    if len(results) >= 2:
        a = results[0]["result"]
        b = results[1]["result"]
        deltas["runway_days"] = b["runway_days"] - a["runway_days"]
        if a["runs_out_on"] and b["runs_out_on"]:
            d_a = date.fromisoformat(a["runs_out_on"])
            d_b = date.fromisoformat(b["runs_out_on"])
            deltas["runs_out_on_days"] = (d_b - d_a).days
        numbers.append(NumberEntry("deltas.runway_days", deltas.get("runway_days"), "days"))
    return {"scenarios": results, "deltas": deltas}, numbers


def _tool_safe_daily_spend(args: dict, situation: Situation) -> tuple[dict, list[NumberEntry]]:
    scenario = _coerce_scenario(args.get("scenario", {}), situation) if args.get("scenario") else None
    r = compute_safe_spend(situation, scenario)
    numbers = [
        NumberEntry("safe_spend.days_to_cover", r.days_to_cover, "days"),
    ]
    if r.max_daily_total is not None:
        numbers.append(NumberEntry("safe_spend.max_daily_total", r.max_daily_total, "money"))
    if r.headroom is not None:
        numbers.append(NumberEntry("safe_spend.headroom", r.headroom, "money"))
    result = {
        "inflow_today": r.inflow_today,
        "target_date": _date_str(r.target_date),
        "days_to_cover": r.days_to_cover,
        "max_daily_total": r.max_daily_total,
        "headroom": r.headroom,
        "covers_essentials": r.covers_essentials,
        "already_short": r.already_short,
    }
    return result, numbers


def _tool_check_affordability(args: dict, situation: Situation) -> tuple[dict, list[NumberEntry]]:
    expense_raw = args["expense"]
    date_expr = _coerce_date_expr(expense_raw.get("date_expr"))
    exp_date = resolve_date(date_expr, situation.as_of) if date_expr else situation.as_of
    expense = ExtraExpense(label=expense_raw["label"], amount=int(expense_raw["amount"]), date=exp_date)
    scenario = _coerce_scenario(args.get("scenario", {}), situation) if args.get("scenario") else None
    r = check_affordability(expense, situation, scenario)
    numbers = [
        NumberEntry("affordability.runway_before", r.runway_before, "days"),
        NumberEntry("affordability.runway_after", r.runway_after, "days"),
        NumberEntry("affordability.days_lost", r.days_lost, "days"),
    ]
    if r.runs_out_before:
        numbers.append(NumberEntry("affordability.runs_out_before", _date_str(r.runs_out_before), "date"))
    if r.runs_out_after:
        numbers.append(NumberEntry("affordability.runs_out_after", _date_str(r.runs_out_after), "date"))
    result = {
        "verdict": r.verdict,
        "runway_before": r.runway_before,
        "runway_after": r.runway_after,
        "days_lost": r.days_lost,
        "runs_out_before": _date_str(r.runs_out_before),
        "runs_out_after": _date_str(r.runs_out_after),
        "next_money_date": _date_str(r.next_money_date),
    }
    return result, numbers


def _tool_essentials_reserve(args: dict, situation: Situation) -> tuple[dict, list[NumberEntry]]:
    scenario = _coerce_scenario(args.get("scenario", {}), situation) if args.get("scenario") else None
    buffer_days = args.get("buffer_days")
    r = compute_reserve(situation, buffer_days, scenario)
    numbers = [
        NumberEntry("reserve.reserve", r.reserve, "money"),
        NumberEntry("reserve.surplus_or_gap", r.surplus_or_gap, "money"),
        NumberEntry("reserve.days_to_next_money", r.days_to_next_money, "days"),
    ]
    result = {
        "days_to_next_money": r.days_to_next_money,
        "buffer_days": r.buffer_days,
        "essentials_part": r.essentials_part,
        "must_pay_part": r.must_pay_part,
        "reserve": r.reserve,
        "covered": r.covered,
        "surplus_or_gap": r.surplus_or_gap,
    }
    return result, numbers


# ---------------------------------------------------------------------------
# Registry and executor
# ---------------------------------------------------------------------------

TOOL_ALLOWLIST = {
    "compute_runway",
    "compare_scenarios",
    "safe_daily_spend",
    "check_affordability",
    "essentials_reserve",
}

_TOOL_FN = {
    "compute_runway": _tool_compute_runway,
    "compare_scenarios": _tool_compare_scenarios,
    "safe_daily_spend": _tool_safe_daily_spend,
    "check_affordability": _tool_check_affordability,
    "essentials_reserve": _tool_essentials_reserve,
}


def execute_plan(plan: dict, situation: Situation) -> tuple[list[dict], list[dict]]:
    """Execute a tool_calls plan.  Returns (results, trace_steps)."""
    tool_calls = plan.get("tool_calls", [])
    results: list[dict] = []
    trace_steps: list[dict] = []

    for call in tool_calls:
        tool = call.get("tool", "")
        args = call.get("args", {})
        t0 = time.monotonic()

        if tool not in TOOL_ALLOWLIST:
            results.append({
                "tool": tool,
                "args": args,
                "ok": False,
                "error": f"unknown_tool: {tool!r}",
                "result": None,
                "numbers": [],
            })
            trace_steps.append({
                "step": "tool_plan",
                "label": f"unknown tool: {tool}",
                "ms": int((time.monotonic() - t0) * 1000),
                "payload": {"tool": tool, "error": "not in allowlist"},
            })
            continue

        trace_steps.append({
            "step": "tool_plan",
            "label": "tool registry",
            "ms": 0,
            "payload": {"tool": tool},
        })

        try:
            fn = _TOOL_FN[tool]
            result_dict, numbers = fn(args, situation)
            elapsed = int((time.monotonic() - t0) * 1000)
            results.append({
                "tool": tool,
                "args": args,
                "ok": True,
                "error": None,
                "result": result_dict,
                "numbers": [{"path": n.path, "value": n.value, "type": n.type} for n in numbers],
            })
            trace_steps.append({
                "step": "engine_call",
                "label": tool,
                "ms": elapsed,
                "payload": {"tool": tool},
            })
        except EngineError as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            results.append({
                "tool": tool,
                "args": args,
                "ok": False,
                "error": e.code,
                "result": None,
                "numbers": [],
            })
            trace_steps.append({
                "step": "engine_call",
                "label": f"{tool} error",
                "ms": elapsed,
                "payload": {"error": e.code, "message": str(e)},
            })

    return results, trace_steps
