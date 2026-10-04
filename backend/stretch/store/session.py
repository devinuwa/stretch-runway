"""Session store (T4).

Two backends selected by STRETCH_PERSIST:
  0 (default): in-memory only — nothing written to disk.
  1: SQLite at data/stretch.db — stores the Situation row only.

API_CONTRACT section 2 modes are enforced by the FastAPI app; the store
is agnostic to profile.  It holds at most one Situation per session.

Privacy rules (AGENTS.md §4):
  - STRETCH_HANDOVER=1 forces in-memory regardless of PERSIST.
  - No financial data is stored in the browser (handled by the API layer).
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

from stretch.engine.models import Commitment, Inflow, Situation


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _situation_to_dict(s: Situation) -> dict:
    return {
        "as_of": s.as_of.isoformat(),
        "currency": s.currency,
        "balance": s.balance,
        "essentials_per_day": s.essentials_per_day,
        "horizon_days": s.horizon_days,
        "buffer_days": s.buffer_days,
        "inflows": [
            {
                "id": i.id,
                "label": i.label,
                "expected_amount": i.expected_amount,
                "expected_date": i.expected_date.isoformat(),
                "uncertainty_note": i.uncertainty_note,
            }
            for i in s.inflows
        ],
        "commitments": [
            {
                "id": c.id,
                "label": c.label,
                "amount": c.amount,
                "due_date": c.due_date.isoformat(),
                "flexible": c.flexible,
            }
            for c in s.commitments
        ],
    }


def _situation_from_dict(d: dict) -> Situation:
    inflows = tuple(
        Inflow(
            id=i["id"],
            label=i["label"],
            expected_amount=int(i["expected_amount"]),
            expected_date=date.fromisoformat(i["expected_date"]),
            uncertainty_note=i.get("uncertainty_note"),
        )
        for i in d.get("inflows", [])
    )
    commitments = tuple(
        Commitment(
            id=c["id"],
            label=c["label"],
            amount=int(c["amount"]),
            due_date=date.fromisoformat(c["due_date"]),
            flexible=bool(c["flexible"]),
        )
        for c in d.get("commitments", [])
    )
    return Situation(
        as_of=date.fromisoformat(d["as_of"]),
        currency=d.get("currency", "NGN"),
        balance=int(d["balance"]),
        essentials_per_day=int(d["essentials_per_day"]),
        horizon_days=int(d.get("horizon_days", 60)),
        buffer_days=int(d.get("buffer_days", 3)),
        inflows=inflows,
        commitments=commitments,
    )


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

class MemoryStore:
    """Single-slot in-memory situation store. Thread-unsafe (single-process dev only)."""

    def __init__(self) -> None:
        self._situation: Optional[Situation] = None

    def get(self) -> Optional[Situation]:
        return self._situation

    def put(self, s: Situation) -> None:
        self._situation = s

    def delete(self) -> None:
        self._situation = None

    def has_situation(self) -> bool:
        return self._situation is not None


# ---------------------------------------------------------------------------
# SQLite store
# ---------------------------------------------------------------------------

class SqliteStore:
    """Persists one Situation row in SQLite (data/stretch.db)."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS situation
               (id INTEGER PRIMARY KEY, data TEXT NOT NULL)"""
        )
        self._conn.commit()

    def get(self) -> Optional[Situation]:
        row = self._conn.execute("SELECT data FROM situation WHERE id=1").fetchone()
        if row is None:
            return None
        return _situation_from_dict(json.loads(row[0]))

    def put(self, s: Situation) -> None:
        data = json.dumps(_situation_to_dict(s))
        self._conn.execute(
            "INSERT OR REPLACE INTO situation (id, data) VALUES (1, ?)", (data,)
        )
        self._conn.commit()

    def delete(self) -> None:
        self._conn.execute("DELETE FROM situation WHERE id=1")
        self._conn.commit()

    def has_situation(self) -> bool:
        return self._conn.execute(
            "SELECT COUNT(*) FROM situation WHERE id=1"
        ).fetchone()[0] > 0

    def close(self) -> None:
        """Close the SQLite connection. Required on Windows before temp-dir cleanup."""
        self._conn.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_store(persist: bool = False, handover: bool = False,
               db_path: Path | None = None) -> MemoryStore | SqliteStore:
    """Return the appropriate store.

    handover=True always returns MemoryStore (AGENTS.md §4).
    persist=True returns SqliteStore unless handover is set.
    """
    if handover or not persist:
        return MemoryStore()
    path = db_path or Path("data") / "stretch.db"
    return SqliteStore(path)
