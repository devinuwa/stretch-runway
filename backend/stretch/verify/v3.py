"""V3 — narration verification (ARCHITECTURE.md §8, API_CONTRACT.md §4).

Pure: no I/O, no LLM, no network. A token is allowed when it matches
  * a numbers-registry value (money/day/date/int),
  * the day or month of a registry date,
  * any integer in the stored situation or the user's question,

after normalizing `1,500` / `1.5k` / `₦` forms. Advice-pattern words fail.

V3 checks numbers, not reasoning quality (state that in docs).
"""
from __future__ import annotations

import re
from typing import Any, Iterable

ADVICE_DENYLIST = ("loan", "invest", "crypto", "borrow")

_AMOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([km])?", re.IGNORECASE)


def normalize(text: str) -> str:
    """Lower-case, drop currency signs/separators so `1,500` and `1.5k` match."""
    return (
        str(text)
        .lower()
        .replace("\u20a6", "")
        .replace("ngn", "")
    )


def tokens_in(text: str) -> list[str]:
    """Digit tokens, with `1.5k` -> 1500 and `12,000` -> 12000, in order."""
    out: list[str] = []
    for raw, suffix in _AMOUNT_RE.findall(normalize(text)):
        value = float(raw)
        if suffix == "k":
            value *= 1_000
        elif suffix == "m":
            value *= 1_000_000
        out.append(str(int(value)) if value == int(value) else str(value))
    return out


def allowed_tokens(
    numbers: Iterable[dict[str, Any]],
    *,
    question: str = "",
    situation_values: Iterable[Any] = (),
) -> set[str]:
    """Build the allowlist from the registry, the question and the situation."""
    allowed: set[str] = set()
    for entry in numbers:
        value = entry.get("value") if isinstance(entry, dict) else entry
        if value is None:
            continue
        allowed.update(tokens_in(str(value)))
        # dates: allow the day and month numerals too (e.g. 2026-10-21 -> 10, 21)
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            year, month, day = value.split("-")
            allowed.update({year.lstrip("0") or "0", month.lstrip("0") or "0", day.lstrip("0") or "0"})
    for value in situation_values:
        if value is None:
            continue
        allowed.update(tokens_in(str(value)))
    allowed.update(tokens_in(question or ""))
    return allowed


def verify_narration(
    narration: str,
    numbers: Iterable[dict[str, Any]],
    *,
    question: str = "",
    situation_values: Iterable[Any] = (),
) -> dict[str, Any]:
    """Return {status, matched, unmatched, advice_hits}. `status` is verified|failed."""
    numbers = list(numbers)
    lowered = normalize(narration)
    advice_hits = [w for w in ADVICE_DENYLIST if w in lowered]
    allowed = allowed_tokens(numbers, question=question, situation_values=situation_values)

    matched: list[str] = []
    unmatched: list[str] = []
    for token in tokens_in(narration):
        if token in allowed:
            matched.append(token)
        else:
            unmatched.append(token)

    status = "failed" if (unmatched or advice_hits) else "verified"
    return {
        "status": status,
        "matched": matched,
        "unmatched": unmatched,
        "advice_hits": advice_hits,
    }


def payload_number_values(obj: Any) -> list[Any]:
    """Walk an engine payload and collect its numbers/date strings.

    The P0 template narration is built by code from tool results, so every value
    it may print is by construction an engine value; V3 still re-checks it.
    """
    out: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            out.append(node)
        elif isinstance(node, str):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", node):
                out.append(node)
            elif re.fullmatch(r"-?\d+(?:\.\d+)?", node):
                out.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(obj)
    return out


def situation_number_values(situation: Any) -> list[Any]:
    """Flatten the numbers/dates of a stored Situation for the allowlist."""
    if situation is None:
        return []
    values: list[Any] = [situation.balance, situation.essentials_per_day]
    for inflow in situation.inflows:
        values.extend([inflow.expected_amount, inflow.expected_date.isoformat()])
    for commitment in situation.commitments:
        values.extend([commitment.amount, commitment.due_date.isoformat()])
    return values
