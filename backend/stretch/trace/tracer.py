"""Tracer — lightweight, privacy-aware step recorder (T4).

Outside the demo profile only metadata (step name, ms) is kept; payload is
dropped.  Inside demo profile full payloads are retained for the trace panel.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class Tracer:
    """In-memory trace collector for one request."""

    def __init__(self, *, demo_profile: bool = False) -> None:
        self._demo = demo_profile
        self._steps: list[dict] = []

    def add(self, step: str, label: str, ms: int, payload: dict | None = None) -> None:
        record: dict[str, Any] = {"step": step, "label": label, "ms": ms}
        if self._demo and payload is not None:
            record["payload"] = payload
        else:
            record["payload"] = {}
        self._steps.append(record)

    def steps(self) -> list[dict]:
        return list(self._steps)


class LocalJsonlTracer:
    """Appends metadata-only trace records to a local JSONL file.

    Payload is NEVER written (privacy rule: only metadata outside demo profile).
    Used when STRETCH_PERSIST=1 and profile != demo.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, step: str, label: str, ms: int) -> None:
        line = json.dumps({"step": step, "label": label, "ms": ms})
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
