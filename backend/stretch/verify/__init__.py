"""Verify — V1/V2/V3 verification gates (ARCHITECTURE.md §8).

V3 (narration) is implemented in `v3.py`. V1 (extraction grounding) and V2
(plan validation) live with the pipeline that consumes them.
"""
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
    "normalize",
    "payload_number_values",
    "situation_number_values",
    "tokens_in",
    "verify_narration",
]
