"""S2 flat schema + mapping + V2 (no network: StubModelAdapter only)."""
import json
from datetime import date

from stretch.engine.models import Commitment, Inflow, Situation
from stretch.llm.adapters import StubModelAdapter
from stretch.pipeline.models import PlannerOutput
from stretch.pipeline.planner import (
    PROMPT_PATH,
    REFUSAL_CODE,
    map_flat_plan,
    planner_schema,
    run_planner,
    validate_plan,
)
from stretch.trace.tracer import Tracer


def _situation() -> Situation:
    return Situation(
        as_of=date(2026, 10, 5),
        balance=26000,
        essentials_per_day=1500,
        inflows=[Inflow(id="inflow_1", label="Aunt", expected_amount=20000,
                        expected_date=date(2026, 10, 15), uncertainty_note=None)],
        commitments=[Commitment(id="commit_1", label="Outfit", amount=12000,
                                due_date=date(2026, 10, 21), flexible=True)],
    )


def _object_schema(node: dict) -> dict:
    """Return the object branch of a schema node (unwrapping anyOf[obj, null])."""
    if node.get("type") == "object":
        return node
    return next(branch for branch in node["anyOf"] if branch.get("type") == "object")


def test_schema_is_flat_and_closed():
    schema = planner_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"action"}
    assert "$defs" not in schema  # refs inlined for Ollama's `format`
    props = schema["properties"]
    assert set(props) == {"action", "tool", "scenarios", "expense", "clarify_question"}
    assert "run" in json.dumps(props["action"])
    # Optional fields render as anyOf[<object>, {"type": "null"}]
    expense = next(branch for branch in props["expense"]["anyOf"] if branch.get("type") == "object")
    assert set(expense["properties"]) == {"label", "amount", "day_of_month", "in_days"}
    assert expense["additionalProperties"] is False
    scenario = next(branch for branch in props["scenarios"]["anyOf"] if branch.get("type") == "array")
    adjustment = _object_schema(scenario["items"])["properties"]["adjustments"]["items"]
    adjustment = _object_schema(adjustment)
    assert set(adjustment["properties"]) == {"inflow_id", "delay_days", "amount_factor", "new_amount", "cancelled"}
    assert "new_date_expr" not in adjustment["properties"]  # flat: no invented date arg


def test_run_planner_maps_flat_to_contract_plan():
    flat = {
        "action": "run",
        "tool": "compare_scenarios",
        "scenarios": [
            {"label": "on time", "adjustments": []},
            {"label": "5 days late, half",
             "adjustments": [{"inflow_id": "*", "delay_days": 5,
                              "amount_factor": 0.5, "new_amount": None, "cancelled": False}]},
        ],
        "expense": None,
        "clarify_question": None,
    }
    adapter = StubModelAdapter(json.dumps(flat))
    plan, validation, stats = run_planner("What if it comes 5 days late and half?", _situation(), adapter, Tracer())

    assert validation["ok"] is True, validation["errors"]
    assert plan["tool_calls"][0]["tool"] == "compare_scenarios"
    args = plan["tool_calls"][0]["args"]
    assert [s["label"] for s in args["scenarios"]] == ["on time", "5 days late, half"]
    adj = args["scenarios"][1]["adjustments"][0]
    # mapped to the contract adjustment shape (new_date_expr present, model never named it)
    assert adj == {"inflow_id": "*", "delay_days": 5, "new_date_expr": None,
                   "amount_factor": 0.5, "new_amount": None, "cancelled": False}
    assert stats["id"] == "unknown"  # StubModelAdapter has no model_id


def test_refusal_is_fixed_in_code():
    flat = {"action": "refuse", "tool": None, "scenarios": [], "expense": None,
            "clarify_question": "You should buy crypto."}
    mapped = map_flat_plan(flat)
    assert mapped == {"refuse": REFUSAL_CODE}
    assert "crypto" not in json.dumps(mapped)  # model text never reaches the plan


def test_clarify_maps_question():
    mapped = map_flat_plan({"action": "clarify", "clarify_question": "How much smaller?"})
    assert mapped == {"clarify": "How much smaller?"}


def test_affordability_date_mapping():
    day = map_flat_plan({"action": "run", "tool": "check_affordability",
                         "expense": {"label": "meal", "amount": 3000, "day_of_month": 8, "in_days": None}})
    exp = day["tool_calls"][0]["args"]["expense"]
    assert exp["date_expr"] == {"kind": "day_of_month", "day": 8, "month_offset": None}

    soon = map_flat_plan({"action": "run", "tool": "check_affordability",
                          "expense": {"label": "data", "amount": 2500, "day_of_month": None, "in_days": 3}})
    assert soon["tool_calls"][0]["args"]["expense"]["date_expr"] == {"kind": "in_days", "n": 3}

    undated = map_flat_plan({"action": "run", "tool": "check_affordability",
                             "expense": {"label": "book", "amount": 1000, "day_of_month": None, "in_days": None}})
    assert undated["tool_calls"][0]["args"]["expense"]["date_expr"] is None


def test_v2_rejects_bad_mapped_plans():
    sit = _situation()

    unknown_id = {"tool_calls": [{"tool": "compute_runway", "args": {"scenario": {
        "label": "x", "adjustments": [{"inflow_id": "inflow_9"}], "extra_expenses": []}}}]}
    assert validate_plan(unknown_id, sit)["ok"] is False

    both = {"tool_calls": [{"tool": "compute_runway", "args": {"scenario": {
        "label": "x", "adjustments": [{"inflow_id": "*", "amount_factor": 0.5, "new_amount": 9000}],
        "extra_expenses": []}}}]}
    assert validate_plan(both, sit)["ok"] is False

    factor_out_of_bounds = {"tool_calls": [{"tool": "compute_runway", "args": {"scenario": {
        "label": "x", "adjustments": [{"inflow_id": "*", "amount_factor": 3}], "extra_expenses": []}}}]}
    assert validate_plan(factor_out_of_bounds, sit)["ok"] is False

    unknown_tool = {"tool_calls": [{"tool": "delete_everything", "args": {}}]}
    assert validate_plan(unknown_tool, sit)["ok"] is False

    # run with no tool at all -> empty plan -> V2 reports it
    assert map_flat_plan({"action": "run", "tool": None}) == {}


def test_run_planner_repairs_once_then_reports_failure():
    adapter = StubModelAdapter("no json here")
    plan, validation, _ = run_planner("?", _situation(), adapter, Tracer())
    assert validation["ok"] is False
    assert validation["repaired"] is False
    assert len(adapter.calls) == 2  # exactly one repair attempt
    assert plan == {}


def test_planner_output_model_is_closed():
    assert PlannerOutput.model_config["extra"] == "forbid"


def test_week_late_maps_to_delay_days_seven():
    flat = {
        "action": "run",
        "tool": "compute_runway",
        "scenarios": [{"label": "a week late", "adjustments": [
            {"inflow_id": "*", "delay_days": 7, "amount_factor": None,
             "new_amount": None, "cancelled": False}]}],
        "expense": None,
        "clarify_question": None,
    }
    plan = map_flat_plan(flat)
    assert plan["tool_calls"][0]["tool"] == "compute_runway"
    adj = plan["tool_calls"][0]["args"]["scenario"]["adjustments"][0]
    assert adj["delay_days"] == 7
    assert validate_plan(plan, _situation())["ok"] is True


def test_prompt_teaches_week_equals_seven_days():
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "a week" in prompt and "=7" in prompt
    assert '\"delay_days\":7' in prompt  # the week-late few-shot
