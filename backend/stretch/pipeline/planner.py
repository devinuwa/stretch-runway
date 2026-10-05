"""S2 Planner: question -> FLAT constrained JSON -> API_CONTRACT Plan.

The model emits the flat `PlannerOutput` shape (action/tool/scenarios/expense/
clarify_question). Code maps it to the contract Plan, so the model can never
name a contract key or invent an argument name. The refusal text and code come
from this module, never from the model.
"""

import json
from pathlib import Path
from typing import Any

from stretch.llm.adapters import ModelAdapter
from stretch.pipeline.models import PlannerOutput
from stretch.trace.tracer import Tracer
from stretch.engine.models import Situation

PROMPT_PATH = Path(__file__).parent / "prompts" / "planner_s2.txt"

# Fixed out-of-scope handling (AGENTS.md §2.3): code produces both the code and
# the text. The model never supplies the refusal string.
REFUSAL_CODE = "out_of_scope"
REFUSAL_TEXT = (
    "I can only help you calculate how long your money will last under "
    "different assumptions. I cannot give financial advice, recommend "
    "investments, or help with loans."
)

_FALLBACK_CLARIFY = "Can you give me a number (or a date) for that?"

_LAST_MODEL_OUTPUT: str | None = None


def last_model_output() -> str | None:
    """Raw text of the most recent planner call (smoke scripts / traces)."""
    return _LAST_MODEL_OUTPUT


# ---------------------------------------------------------------------------
# JSON schema (inlined: Ollama's `format` is happiest without $ref indirection)
# ---------------------------------------------------------------------------

def planner_schema() -> dict[str, Any]:
    return inline_refs(PlannerOutput.model_json_schema())


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Replace {"$ref": "#/$defs/X"} with the definition and drop `$defs`."""
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                target = defs.get(ref.split("/")[-1], {})
                merged = {k: resolve(v) for k, v in target.items()}
                for key, value in node.items():
                    if key != "$ref":
                        merged[key] = resolve(value)
                return merged
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


# ---------------------------------------------------------------------------
# flat -> contract Plan mapping
# ---------------------------------------------------------------------------

def _adjustment(raw: dict) -> dict:
    return {
        "inflow_id": raw.get("inflow_id") or "*",
        "delay_days": raw.get("delay_days"),
        "new_date_expr": None,  # the flat schema has no date expressions
        "amount_factor": raw.get("amount_factor"),
        "new_amount": raw.get("new_amount"),
        "cancelled": bool(raw.get("cancelled", False)),
    }


def _scenario(raw: dict | None) -> dict:
    raw = raw or {}
    return {
        "label": raw.get("label") or "scenario",
        "adjustments": [_adjustment(a) for a in raw.get("adjustments") or []],
        "extra_expenses": [],
    }


def _expense(raw: dict | None) -> dict | None:
    if not raw:
        return None
    date_expr = None
    if raw.get("day_of_month") is not None:
        date_expr = {"kind": "day_of_month", "day": raw["day_of_month"], "month_offset": None}
    elif raw.get("in_days") is not None:
        date_expr = {"kind": "in_days", "n": raw["in_days"]}
    return {
        "label": raw.get("label") or "expense",
        "amount": raw.get("amount"),
        "date_expr": date_expr,
    }


def map_flat_plan(flat: dict) -> dict:
    """Map the flat model output to the API_CONTRACT Plan. Never raises."""
    if not isinstance(flat, dict):
        return {}

    action = flat.get("action")
    if action == "refuse":
        return {"refuse": REFUSAL_CODE}
    if action == "clarify":
        return {"clarify": flat.get("clarify_question") or _FALLBACK_CLARIFY}

    tool = flat.get("tool")
    scenarios = flat.get("scenarios") or []
    scenario = scenarios[0] if scenarios else None

    if tool == "compute_runway":
        return {"tool_calls": [{"tool": tool, "args": {"scenario": _scenario(scenario)}}]}
    if tool == "compare_scenarios":
        return {
            "tool_calls": [
                {"tool": tool, "args": {"scenarios": [_scenario(s) for s in scenarios]}}
            ]
        }
    if tool in ("safe_daily_spend", "essentials_reserve"):
        return {"tool_calls": [{"tool": tool, "args": {"scenario": _scenario(scenario)}}]}
    if tool == "check_affordability":
        return {
            "tool_calls": [
                {"tool": tool, "args": {"expense": _expense(flat.get("expense")), "scenario": _scenario(scenario)}}
            ]
        }
    # action == "run" with no/unknown tool: leave empty so V2 reports it.
    return {}


# ---------------------------------------------------------------------------
# S2 runner
# ---------------------------------------------------------------------------

def run_planner(
    question: str,
    situation: Situation,
    adapter: ModelAdapter,
    tracer: Tracer,
) -> tuple[dict, dict, dict]:
    global _LAST_MODEL_OUTPUT

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    inflows_ctx = ", ".join(f"{i.id} ({i.label})" for i in situation.inflows)
    commitments_ctx = ", ".join(f"{c.id} ({c.label})" for c in situation.commitments)

    # Identical system-prompt prefix across attempts and calls (prefix caching).
    sys_prompt = (
        prompt_template
        .replace("{as_of}", situation.as_of.isoformat())
        .replace("{inflows}", inflows_ctx or "none")
        .replace("{commitments}", commitments_ctx or "none")
    )
    messages: list[dict] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": question},
    ]

    schema = planner_schema()

    result = adapter.generate(messages, schema=schema)
    _LAST_MODEL_OUTPUT = result.get("content")
    tracer.add(
        "llm_call",
        "planner_s2",
        result["total_ms"],
        payload={
            "attempt": 1,
            "raw": result.get("content"),
            "prompt_tokens": result.get("prompt_tokens"),
            "completion_tokens": result.get("completion_tokens"),
        },
    )

    flat, plan_dict, validation = _parse_and_map(result["content"], situation)

    if not validation["ok"]:
        repair_msg = (
            "Your previous output failed validation. Errors:\n"
            + "\n".join(validation["errors"])
            + "\nReply with the corrected flat JSON only."
        )
        messages.extend([
            {"role": "assistant", "content": result.get("content") or "{}"},
            {"role": "user", "content": repair_msg},
        ])
        result = adapter.generate(messages, schema=schema)
        _LAST_MODEL_OUTPUT = result.get("content")
        tracer.add(
            "llm_call",
            "planner_s2_repair",
            result["total_ms"],
            payload={
                "attempt": 2,
                "raw": result.get("content"),
                "prompt_tokens": result.get("prompt_tokens"),
                "completion_tokens": result.get("completion_tokens"),
            },
        )
        flat, plan_dict, validation = _parse_and_map(result["content"], situation)
        validation["repaired"] = validation["ok"]
    else:
        validation["repaired"] = False

    # Observable, code-owned refusal text (never model output).
    if plan_dict.get("refuse"):
        tracer.add(
            "validation",
            "out-of-scope refusal (fixed string from code)",
            0,
            payload={"refuse": REFUSAL_CODE, "text": REFUSAL_TEXT},
        )

    model_stats = {
        "id": getattr(adapter, "model_id", "unknown"),
        "prompt_tokens": result.get("prompt_tokens", 0),
        "completion_tokens": result.get("completion_tokens", 0),
        "total_ms": result.get("total_ms", 0),
    }
    return plan_dict, validation, model_stats


def _parse_and_map(raw: str | None, situation: Situation) -> tuple[dict, dict, dict]:
    """Parse the flat JSON, map it to a contract Plan, and run V2 over it."""
    if not raw:
        return {}, {}, {"ok": False, "checks": ["schema"], "errors": ["Empty model output"], "repaired": False}

    try:
        flat = json.loads(raw)
    except Exception as e:  # noqa: BLE001 - any parse failure is a validation failure
        return {}, {}, {"ok": False, "checks": ["schema"], "errors": [f"Parse error: {e}"], "repaired": False}

    if not isinstance(flat, dict) or flat.get("action") not in ("run", "clarify", "refuse"):
        return flat if isinstance(flat, dict) else {}, {}, {
            "ok": False,
            "checks": ["schema"],
            "errors": ["Missing or invalid 'action' (run|clarify|refuse)"],
            "repaired": False,
        }

    plan_dict = map_flat_plan(flat)
    validation = validate_plan(plan_dict, situation)
    return flat, plan_dict, validation


# ---------------------------------------------------------------------------
# V2 validation (on the mapped contract plan)
# ---------------------------------------------------------------------------

def validate_plan(plan_dict: dict, situation: Situation | None = None) -> dict:
    checks = ["schema", "tool_allowlist", "bounds", "inflow_ids", "grounding"]
    errors: list[str] = []

    if not isinstance(plan_dict, dict):
        return {"ok": False, "checks": checks, "errors": ["Plan must be an object"]}

    # clarify / refuse pass through
    if plan_dict.get("refuse") is not None or plan_dict.get("clarify") is not None:
        return {"ok": True, "checks": checks, "errors": []}

    tool_calls = plan_dict.get("tool_calls")
    if not isinstance(tool_calls, list) or len(tool_calls) == 0:
        return {"ok": False, "checks": checks, "errors": ["Missing or empty tool_calls"]}

    from stretch.tools.registry import TOOL_ALLOWLIST

    known_inflow_ids: set[str] = set()
    if situation:
        known_inflow_ids = {i.id for i in situation.inflows} | {"*"}

    for i, call in enumerate(tool_calls):
        prefix = f"tool_calls[{i}]"

        tool = call.get("tool")
        if not tool:
            errors.append(f"{prefix}: missing 'tool'")
            continue
        if tool not in TOOL_ALLOWLIST:
            errors.append(f"{prefix}: tool '{tool}' not in allowlist")

        args = call.get("args", {})
        if not isinstance(args, dict):
            errors.append(f"{prefix}: 'args' must be an object")
            continue

        for adj in args.get("adjustments", []) or []:
            _validate_adjustment(adj, known_inflow_ids, errors, prefix)

        for sc in args.get("scenarios", []) or []:
            for adj in sc.get("adjustments", []) or []:
                _validate_adjustment(adj, known_inflow_ids, errors,
                                     f"{prefix}.scenario[{sc.get('label', '')}]")

        sc = args.get("scenario")
        if sc and isinstance(sc, dict):
            for adj in sc.get("adjustments", []) or []:
                _validate_adjustment(adj, known_inflow_ids, errors, f"{prefix}.scenario")

    return {"ok": len(errors) == 0, "checks": checks, "errors": errors}


def _validate_adjustment(adj: dict, known_ids: set[str], errors: list[str], prefix: str):
    if not isinstance(adj, dict):
        errors.append(f"{prefix}: adjustment must be an object")
        return

    iid = adj.get("inflow_id")
    if iid and known_ids and iid not in known_ids:
        errors.append(f"{prefix}: unknown inflow_id '{iid}'")

    if adj.get("delay_days") is not None and adj.get("new_date_expr") is not None:
        errors.append(f"{prefix}: conflicting delay_days + new_date_expr")

    if adj.get("amount_factor") is not None and adj.get("new_amount") is not None:
        errors.append(f"{prefix}: conflicting amount_factor + new_amount")

    dd = adj.get("delay_days")
    if dd is not None and (not isinstance(dd, int) or dd < 0 or dd > 365):
        errors.append(f"{prefix}: delay_days out of bounds: {dd}")

    af = adj.get("amount_factor")
    if af is not None and (not isinstance(af, (int, float)) or af < 0 or af > 2):
        errors.append(f"{prefix}: amount_factor out of bounds: {af}")

    na = adj.get("new_amount")
    if na is not None and (not isinstance(na, int) or na < 0):
        errors.append(f"{prefix}: new_amount out of bounds: {na}")
