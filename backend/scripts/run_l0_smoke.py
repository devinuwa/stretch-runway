"""L0 smoke tests — E01, Q01, Q02, X02 against live gemma3:4b.

Prints: input, raw model output, V1/V2 verdict, PASS/FAIL vs gold, ms.
"""
import json, time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stretch.llm.adapters import OllamaAdapter
from stretch.pipeline.extractor import run_extraction, last_model_output as last_extractor_output
from stretch.pipeline.planner import run_planner, REFUSAL_TEXT, REFUSAL_CODE, last_model_output
from stretch.trace.tracer import Tracer
from stretch.engine.models import (
    Situation, Inflow, Commitment,
)
from datetime import date
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"

adapter = OllamaAdapter("gemma3:4b")

# Demo situation (as_of 2026-10-05)
demo_sit = Situation(
    as_of=date(2026, 10, 5),
    balance=26000,
    essentials_per_day=1500,
    inflows=(
        Inflow(id="inflow_1", label="Aunt", expected_amount=20000,
               expected_date=date(2026, 10, 15), uncertainty_note=None),
    ),
    commitments=(
        Commitment(id="commit_1", label="Outfit", amount=12000,
                   due_date=date(2026, 10, 21), flexible=True),
    ),
    horizon_days=60,
    buffer_days=3,
)

sep = "=" * 70


def _walk(obj):
    """Yield every dict nested anywhere in obj (readjusts for contract shape)."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


# ── E01 ──────────────────────────────────────────────────────────────────
def run_e01():
    print(f"\n{sep}\n=== E01 (Extraction) ===\n{sep}")
    text = (
        "I have about 26k in my account. I spend like 1500 naira every day on "
        "food and transport. My aunt promised 20,000 around the 15th but I'm "
        "not sure. I also need to pay 12k for an outfit before the 21st, "
        "and there's a 2500 data sub due on the 9th."
    )
    print(f"INPUT: {text!r}\n")

    tracer = Tracer()
    t0 = time.perf_counter()
    ext = run_extraction(text, adapter, tracer)
    ms = int((time.perf_counter() - t0) * 1000)

    print(f"RAW MODEL OUTPUT:\n{last_extractor_output()}\n")
    print(f"MAPPED / V1:\n{ext.model_dump_json(indent=2)}\n")

    # Gold checks
    ok = True
    checks = []

    def chk(cond, msg):
        nonlocal ok
        checks.append(("PASS" if cond else "FAIL", msg))
        if not cond:
            ok = False

    chk(ext.balance == 26000, f"balance={ext.balance} expect 26000")
    if ext.essentials:
        epd = ext.essentials.amount
        if ext.essentials.period == "day":
            pass
        elif ext.essentials.period == "week":
            epd = ext.essentials.amount // 7 if ext.essentials.amount else None
        elif ext.essentials.period == "month":
            epd = ext.essentials.amount // 30 if ext.essentials.amount else None
        chk(epd == 1500, f"essentials/day={epd} expect 1500")
    else:
        chk(False, "essentials missing")

    chk(len(ext.inflows) >= 1, f"inflows count={len(ext.inflows)} expect >=1")
    if ext.inflows:
        i0 = ext.inflows[0]
        chk(i0.expected_amount == 20000, f"inflow[0].amount={i0.expected_amount} expect 20000")
        if i0.date_expr:
            chk(i0.date_expr.kind == "day_of_month" and i0.date_expr.day == 15,
                f"inflow[0].date={i0.date_expr} expect day_of_month 15")
        else:
            chk(False, "inflow[0].date_expr missing")

    chk(len(ext.commitments) >= 2, f"commitments count={len(ext.commitments)} expect >=2")
    if len(ext.commitments) >= 1:
        c0 = ext.commitments[0]
        chk(c0.amount == 12000, f"commit[0].amount={c0.amount} expect 12000")
    if len(ext.commitments) >= 2:
        c1 = ext.commitments[1]
        chk(c1.amount == 2500, f"commit[1].amount={c1.amount} expect 2500")

    for status, msg in checks:
        print(f"  [{status}] {msg}")

    verdict = "PASS" if ok else "FAIL"
    print(f"\nE01 verdict: {verdict}  ({ms} ms)")
    return verdict, ms


# ── Q01 ──────────────────────────────────────────────────────────────────
def run_q01():
    print(f"\n{sep}\n=== Q01 (In-scope plan: late+half) ===\n{sep}")
    question = "What if the money comes 5 days late and is only half the amount?"
    print(f"INPUT: {question!r}\n")

    tracer = Tracer()
    t0 = time.perf_counter()
    plan, val, stats = run_planner(question, demo_sit, adapter, tracer)
    ms = int((time.perf_counter() - t0) * 1000)

    print(f"RAW MODEL OUTPUT:\n{last_model_output()}\n")
    print(f"MAPPED PLAN:\n{json.dumps(plan, indent=2)}\n")
    print(f"V2 validation: {json.dumps(val, indent=2)}\n")

    ok = True
    checks = []

    def chk(cond, msg):
        nonlocal ok
        checks.append(("PASS" if cond else "FAIL", msg))
        if not cond:
            ok = False

    chk(val["ok"], f"V2 ok={val['ok']}")
    chk("tool_calls" in plan and plan["tool_calls"], "has tool_calls")

    if plan.get("tool_calls"):
        tools_used = [tc["tool"] for tc in plan["tool_calls"]]
        chk(any(t in ("compare_scenarios", "compute_runway") for t in tools_used),
            f"tools={tools_used}")
        # Check for delay_days=5 and amount_factor=0.5 anywhere in the plan
        found_delay = any(d.get("delay_days") == 5 for d in _walk(plan))
        found_factor = any(d.get("amount_factor") == 0.5 for d in _walk(plan))
        chk(found_delay, f"delay_days=5 found={found_delay}")
        chk(found_factor, f"amount_factor=0.5 found={found_factor}")

    for status, msg in checks:
        print(f"  [{status}] {msg}")

    verdict = "PASS" if ok else "FAIL"
    print(f"\nQ01 verdict: {verdict}  ({ms} ms)")
    return verdict, ms


# ── Q02 ──────────────────────────────────────────────────────────────────
def run_q02():
    print(f"\n{sep}\n=== Q02 (delay 7 days) ===\n{sep}")
    question = "What if the money is a week late?"
    print(f"INPUT: {question!r}\n")

    tracer = Tracer()
    t0 = time.perf_counter()
    plan, val, stats = run_planner(question, demo_sit, adapter, tracer)
    ms = int((time.perf_counter() - t0) * 1000)

    print(f"RAW MODEL OUTPUT:\n{last_model_output()}\n")
    print(f"MAPPED PLAN:\n{json.dumps(plan, indent=2)}\n")
    print(f"V2 validation: {json.dumps(val, indent=2)}\n")

    ok = True
    checks = []

    def chk(cond, msg):
        nonlocal ok
        checks.append(("PASS" if cond else "FAIL", msg))
        if not cond:
            ok = False

    chk(val["ok"], f"V2 ok={val['ok']}")
    # Should be compute_runway with delay_days=7 on "*" or "inflow_1"
    if plan.get("tool_calls"):
        found_delay7 = any(d.get("delay_days") == 7 for d in _walk(plan))
        chk(found_delay7, f"delay_days=7 found={found_delay7}")
    elif plan.get("clarify"):
        chk(False, f"got clarify instead of tool_calls: {plan['clarify']!r}")
    else:
        chk(False, "no tool_calls")

    for status, msg in checks:
        print(f"  [{status}] {msg}")

    verdict = "PASS" if ok else "FAIL"
    print(f"\nQ02 verdict: {verdict}  ({ms} ms)")
    return verdict, ms


# ── X02 ──────────────────────────────────────────────────────────────────
def run_x02():
    print(f"\n{sep}\n=== X02 (Out of scope — refuse) ===\n{sep}")
    question = "Should I invest in crypto or take out a loan?"
    print(f"INPUT: {question!r}\n")

    tracer = Tracer()
    t0 = time.perf_counter()
    plan, val, stats = run_planner(question, demo_sit, adapter, tracer)
    ms = int((time.perf_counter() - t0) * 1000)

    print(f"RAW MODEL OUTPUT:\n{last_model_output()}\n")
    print(f"MAPPED PLAN:\n{json.dumps(plan, indent=2)}\n")
    print(f"V2 validation: {json.dumps(val, indent=2)}\n")

    ok = True
    checks = []

    def chk(cond, msg):
        nonlocal ok
        checks.append(("PASS" if cond else "FAIL", msg))
        if not cond:
            ok = False

    chk(val["ok"], f"V2 ok={val['ok']}")
    chk(plan.get("refuse") == REFUSAL_CODE,
        f"refuse code is fixed-from-code: {plan.get('refuse')!r} (== {REFUSAL_CODE!r})")
    chk(bool(REFUSAL_TEXT), f"fixed refusal text present: {REFUSAL_TEXT!r}")

    for status, msg in checks:
        print(f"  [{status}] {msg}")

    verdict = "PASS" if ok else "FAIL"
    print(f"\nX02 verdict: {verdict}  ({ms} ms)")
    return verdict, ms


# ── Main ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    results = {}
    for case_id, fn in [("E01", run_e01), ("Q01", run_q01), ("Q02", run_q02), ("X02", run_x02)]:
        verdict, ms = fn()
        results[case_id] = (verdict, ms)

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    for cid, (v, ms) in results.items():
        print(f"  {cid}: {v}  ({ms} ms)")
    total_pass = sum(1 for v, _ in results.values() if v == "PASS")
    print(f"\n  {total_pass}/{len(results)} PASSED")
