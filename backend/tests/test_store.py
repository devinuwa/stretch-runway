"""T4 tests: store and tracer.

Tests TEST_PLAN.md section 3 (non-LLM-dependent, non-endpoint items).
"""
import pytest
from datetime import date
from pathlib import Path
import tempfile

from stretch.engine.models import Situation, Inflow, Commitment
from stretch.store.session import MemoryStore, SqliteStore, make_store


DEMO_SITUATION = Situation(
    as_of=date(2026, 10, 5),
    currency="NGN",
    balance=26000,
    essentials_per_day=1500,
    inflows=(Inflow(id="inflow_1", label="Aunt", expected_amount=20000,
                    expected_date=date(2026, 10, 15)),),
    commitments=(Commitment(id="commit_1", label="Outfit", amount=12000,
                            due_date=date(2026, 10, 21), flexible=True),),
)


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

def test_memory_store_empty():
    store = MemoryStore()
    assert store.has_situation() is False
    assert store.get() is None


def test_memory_store_put_get():
    store = MemoryStore()
    store.put(DEMO_SITUATION)
    assert store.has_situation() is True
    s = store.get()
    assert s is not None
    assert s.balance == 26000
    assert s.essentials_per_day == 1500
    assert len(s.inflows) == 1
    assert s.inflows[0].id == "inflow_1"


def test_memory_store_delete():
    store = MemoryStore()
    store.put(DEMO_SITUATION)
    store.delete()
    assert store.has_situation() is False
    assert store.get() is None


def test_memory_store_overwrite():
    store = MemoryStore()
    store.put(DEMO_SITUATION)
    new_sit = Situation(
        as_of=date(2026, 10, 6), balance=1000, essentials_per_day=500,
    )
    store.put(new_sit)
    assert store.get().balance == 1000


# ---------------------------------------------------------------------------
# SqliteStore
# ---------------------------------------------------------------------------

def test_sqlite_store_put_get():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        store = SqliteStore(path)
        try:
            store.put(DEMO_SITUATION)
            assert store.has_situation() is True
            s = store.get()
            assert s.balance == 26000
            assert s.as_of == date(2026, 10, 5)
            assert len(s.inflows) == 1
            assert s.inflows[0].expected_amount == 20000
            assert len(s.commitments) == 1
        finally:
            store.close()


def test_sqlite_store_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        store = SqliteStore(path)
        try:
            store.put(DEMO_SITUATION)
            store.delete()
            assert store.has_situation() is False
        finally:
            store.close()


def test_sqlite_store_overwrite():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        store = SqliteStore(path)
        try:
            store.put(DEMO_SITUATION)
            new_sit = Situation(as_of=date(2026, 10, 6), balance=999, essentials_per_day=100)
            store.put(new_sit)
            assert store.get().balance == 999
        finally:
            store.close()


def test_sqlite_store_roundtrip_commitments():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        store = SqliteStore(path)
        try:
            store.put(DEMO_SITUATION)
            s = store.get()
            assert s.commitments[0].due_date == date(2026, 10, 21)
            assert s.commitments[0].flexible is True
        finally:
            store.close()


# ---------------------------------------------------------------------------
# make_store factory
# ---------------------------------------------------------------------------

def test_make_store_memory_default():
    store = make_store(persist=False)
    assert isinstance(store, MemoryStore)


def test_make_store_handover_forces_memory():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        store = make_store(persist=True, handover=True, db_path=path)
        assert isinstance(store, MemoryStore)


def test_make_store_persist_sqlite():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        store = make_store(persist=True, handover=False, db_path=path)
        try:
            assert isinstance(store, SqliteStore)
        finally:
            store.close()


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------

def test_tracer_demo_profile_keeps_payload():
    from stretch.trace.tracer import Tracer
    t = Tracer(demo_profile=True)
    t.add("engine_call", "compute_runway", 10, payload={"runway_days": 22})
    steps = t.steps()
    assert len(steps) == 1
    assert steps[0]["payload"] == {"runway_days": 22}


def test_tracer_non_demo_drops_payload():
    from stretch.trace.tracer import Tracer
    t = Tracer(demo_profile=False)
    t.add("engine_call", "compute_runway", 10, payload={"runway_days": 22})
    steps = t.steps()
    assert steps[0]["payload"] == {}


def test_tracer_multiple_steps():
    from stretch.trace.tracer import Tracer
    t = Tracer(demo_profile=True)
    t.add("interpretation", "LLM", 500, payload={"x": 1})
    t.add("engine_call", "compute_runway", 3, payload={"y": 2})
    steps = t.steps()
    assert len(steps) == 2
    assert steps[0]["step"] == "interpretation"
    assert steps[1]["step"] == "engine_call"


def test_local_jsonl_tracer_writes_metadata_only():
    from stretch.trace.tracer import LocalJsonlTracer
    import json
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "trace.jsonl"
        tracer = LocalJsonlTracer(path)
        tracer.record("engine_call", "compute_runway", 5)
        lines = path.read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record == {"step": "engine_call", "label": "compute_runway", "ms": 5}
        # No payload field written
        assert "payload" not in record
