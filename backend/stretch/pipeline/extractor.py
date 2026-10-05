"""S1 Extractor: situation text -> FLAT constrained JSON -> ExtractorOutput.

The model emits the flat, closed `FlatExtraction` shape (scalar date fields,
no nested objects, no arithmetic).  Code maps it to the nested
`ExtractorOutput` and runs V1 grounding so every reported amount/date can be
checked against the user's original text.  The model never computes a date.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from stretch.llm.adapters import ModelAdapter
from stretch.pipeline.models import (
    ExtractorCommitment,
    ExtractorDateExpr,
    ExtractorEssentials,
    ExtractorInflow,
    ExtractorOutput,
    FlatExtraction,
)
from stretch.trace.tracer import Tracer
from stretch.verify import run_v1

PROMPT_PATH = Path(__file__).parent / "prompts" / "extractor_s1.txt"

# Last raw model text, for smoke scripts / traces.
_LAST_MODEL_OUTPUT: str | None = None


def last_model_output() -> str | None:
    return _LAST_MODEL_OUTPUT


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


def extractor_schema() -> dict[str, Any]:
    return inline_refs(FlatExtraction.model_json_schema())


def _date_expr(raw: dict) -> ExtractorDateExpr | None:
    kind = raw.get("date_kind")
    if kind not in ("iso", "in_days", "day_of_month"):
        return None
    return ExtractorDateExpr(
        kind=kind,
        value=raw.get("date_value") if kind == "iso" else None,
        day=raw.get("date_day") if kind == "day_of_month" else None,
        n=raw.get("date_in_days") if kind == "in_days" else None,
        month_offset=raw.get("date_month_offset"),
    )


def map_flat_extraction(flat: dict) -> ExtractorOutput:
    """Map the model's flat object to the nested ExtractorOutput. Never raises."""
    if not isinstance(flat, dict):
        return ExtractorOutput()

    essentials = None
    if flat.get("essentials_amount") is not None or flat.get("essentials_period"):
        essentials = ExtractorEssentials(
            amount=flat.get("essentials_amount"),
            period=flat.get("essentials_period") or "day",
        )

    inflows = [
        ExtractorInflow(
            label=i.get("label") or "",
            expected_amount=i.get("amount"),
            date_expr=_date_expr(i),
            uncertainty_note=i.get("uncertainty_note"),
        )
        for i in flat.get("inflows") or []
        if isinstance(i, dict)
    ]

    commitments = [
        ExtractorCommitment(
            label=c.get("label") or "",
            amount=c.get("amount"),
            date_expr=_date_expr(c),
            flexible=c.get("flexible"),
        )
        for c in flat.get("commitments") or []
        if isinstance(c, dict)
    ]

    return ExtractorOutput(
        balance=flat.get("balance"),
        essentials=essentials,
        inflows=inflows,
        commitments=commitments,
    )


def run_extraction(text: str, adapter: ModelAdapter, tracer: Tracer) -> ExtractorOutput:
    global _LAST_MODEL_OUTPUT

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]

    result = adapter.generate(messages, schema=extractor_schema())
    _LAST_MODEL_OUTPUT = result.get("content")
    tracer.add(
        "llm_call",
        "extractor_s1",
        result["total_ms"],
        payload={
            "raw": result.get("content"),
            "prompt_tokens": result.get("prompt_tokens"),
            "completion_tokens": result.get("completion_tokens"),
        },
    )

    flat = json.loads(result["content"])
    output = map_flat_extraction(flat)
    # V1: ground every amount/date in the original text.
    output.grounding = run_v1(output, text)
    return output
