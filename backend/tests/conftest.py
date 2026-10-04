import json
import pytest
from pathlib import Path

@pytest.fixture(scope="session")
def engine_golden():
    golden_path = Path(__file__).parent.parent.parent / "fixtures" / "engine_golden.json"
    with open(golden_path, "r", encoding="utf-8") as f:
        return json.load(f)
