"""Verify — V1/V2/V3 verification gates (ARCHITECTURE.md §8).

V1 (extraction grounding) is in `v1.py`; V3 (narration) is in `v3.py`. V2
(plan validation) lives with the planner that consumes it.
"""
from .v1 import (
    ground_amount,
    ground_date,
    ground_day,
    run_v1,
)
from .v3 import (
    ADVICE_DENYLIST,
    allowed_tokens,
    normalize,
    payload_number_values,
    situation_number_values,
    tokens_in,
    verify_narration,
)

__all__ = [
    "ADVICE_DENYLIST",
    "allowed_tokens",
    "ground_amount",
    "ground_date",
    "ground_day",
    "normalize",
    "payload_number_values",
    "run_v1",
    "situation_number_values",
    "tokens_in",
    "verify_narration",
]
