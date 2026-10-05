"""V1 verification: ground extracted monetary/date facts in the user's text.

The extractor never computes values, and the model must not invent them either.
V1 re-checks every number the model reported by looking for the matching token
in the original text.  A value whose token is absent (after normalising forms
like ``26k`` -> ``26000`` and ``20,000`` -> ``20000``) is ``grounded: false``
with ``source_text: null``, so a fabricated amount can never be shown as fact.

No arithmetic beyond unit normalisation (``k`` = thousands) happens here.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from stretch.pipeline.models import (
    ExtractorDateExpr,
    ExtractorOutput,
)

# A number, optionally comma-grouped, optionally suffixed k/K (thousands).
_AMOUNT = re.compile(r"(?<![\d.])(\d[\d,]*(?:\.\d+)?)\s*([kK])?")


def _as_int(digits: str, suffix: Optional[str]) -> int:
    value = float(digits.replace(",", ""))
    if suffix:
        value *= 1000
    return int(round(value))


def _snippet(text: str, start: int, end: int, radius: int = 16) -> str:
    """A short, word-trimmed window around ``text[start:end]``."""
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    frag = text[lo:hi]
    if lo > 0 and " " in frag:
        frag = frag.split(" ", 1)[1]
    if hi < len(text) and " " in frag:
        frag = frag.rsplit(" ", 1)[0]
    return frag.strip()


def ground_amount(value: Optional[int], text: str) -> tuple[bool, Optional[str]]:
    """(grounded, source_text) for an integer amount stated in ``text``."""
    if value is None:
        return (False, None)
    for m in _AMOUNT.finditer(text or ""):
        if _as_int(m.group(1), m.group(2)) == value:
            return (True, _snippet(text, *m.span()))
    return (False, None)


def ground_day(day: Optional[int], text: str) -> tuple[bool, Optional[str]]:
    """Ground a bare day-of-month / in-days number (no date arithmetic)."""
    if day is None:
        return (False, None)
    for m in _AMOUNT.finditer(text or ""):
        if not m.group(2) and _as_int(m.group(1), None) == day:
            return (True, _snippet(text, *m.span()))
    return (False, None)


def ground_date(date_expr: Optional[ExtractorDateExpr], text: str) -> tuple[bool, Optional[str]]:
    """Ground a date expression against the text's tokens."""
    if date_expr is None:
        return (False, None)
    if date_expr.kind == "day_of_month" and date_expr.day is not None:
        return ground_day(date_expr.day, text)
    if date_expr.kind == "in_days" and date_expr.n is not None:
        return ground_day(date_expr.n, text)
    if date_expr.kind == "iso" and date_expr.value:
        idx = (text or "").find(date_expr.value)
        if idx >= 0:
            return (True, _snippet(text, idx, idx + len(date_expr.value)))
    return (False, None)


def _fact(value: Any, grounded: bool, source_text: Optional[str]) -> dict:
    return {"value": value, "grounded": grounded, "source_text": source_text}


def run_v1(output: ExtractorOutput, text: str) -> dict:
    """Return the per-field V1 grounding map for an extraction."""
    g, s = ground_amount(output.balance, text)
    grounding: dict[str, Any] = {
        "balance": _fact(output.balance, g, s),
        "essentials": _fact(
            output.essentials.amount if output.essentials else None,
            *ground_amount(output.essentials.amount if output.essentials else None, text),
        ),
        "inflows": [],
        "commitments": [],
    }

    for inf in output.inflows:
        ag, asx = ground_amount(inf.expected_amount, text)
        dg, dsx = ground_date(inf.date_expr, text)
        grounding["inflows"].append({
            "amount": _fact(inf.expected_amount, ag, asx),
            "date": _fact(
                inf.date_expr.value if inf.date_expr and inf.date_expr.kind == "iso"
                else (inf.date_expr.day if inf.date_expr and inf.date_expr.kind == "day_of_month"
                      else (inf.date_expr.n if inf.date_expr else None)),
                dg, dsx,
            ),
        })

    for com in output.commitments:
        ag, asx = ground_amount(com.amount, text)
        dg, dsx = ground_date(com.date_expr, text)
        grounding["commitments"].append({
            "amount": _fact(com.amount, ag, asx),
            "date": _fact(
                com.date_expr.value if com.date_expr and com.date_expr.kind == "iso"
                else (com.date_expr.day if com.date_expr and com.date_expr.kind == "day_of_month"
                      else (com.date_expr.n if com.date_expr else None)),
                dg, dsx,
            ),
        })

    return grounding
