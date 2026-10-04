import traceback
from stretch.llm.adapters import OllamaAdapter
from stretch.pipeline.planner import run_planner
from stretch.trace.tracer import Tracer
from stretch.engine.models import Situation
from datetime import date

def test():
    adapter = OllamaAdapter("gemma3:4b")
    sit = Situation(as_of=date.today(), balance=0, essentials_per_day=0, inflows=[], commitments=[])
    tracer = Tracer()
    try:
        plan, val, stats = run_planner("hello", sit, adapter, tracer)
        print(plan)
    except Exception as e:
        traceback.print_exc()

test()
