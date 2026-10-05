"""S1 flat schema + mapping + V1 grounding (no network: StubModelAdapter only)."""
import json

from stretch.llm.adapters import StubModelAdapter
from stretch.pipeline.models import ExtractorOutput, FlatExtraction
from stretch.pipeline.extractor import (
    extractor_schema,
    map_flat_extraction,
    run_extraction,
)
from stretch.trace.tracer import Tracer
from stretch.verify import ground_amount, run_v1

E01_TEXT = (
    "I have about 26k in my account. I spend like 1500 naira every day on "
    "food and transport. My aunt promised 20,000 around the 15th but I'm "
    "not sure. I also need to pay 12k for an outfit before the 21st, "
    "and there's a 2500 data sub due on the 9th."
)

E01_FLAT = {
    "balance": 26000,
    "essentials_amount": 1500,
    "essentials_period": "day",
    "inflows": [
        {"label": "Aunt", "amount": 20000, "date_kind": "day_of_month",
         "date_value": None, "date_day": 15, "date_in_days": None,
         "date_month_offset": None, "uncertainty_note": "promised, not confirmed"},
    ],
    "commitments": [
        {"label": "Outfit", "amount": 12000, "date_kind": "day_of_month",
         "date_value": None, "date_day": 21, "date_in_days": None,
         "date_month_offset": None, "flexible": None},
        {"label": "Data sub", "amount": 2500, "date_kind": "day_of_month",
         "date_value": None, "date_day": 9, "date_in_days": None,
         "date_month_offset": None, "flexible": None},
    ],
}


def test_schema_is_flat_and_closed():
    schema = extractor_schema()
    assert schema["additionalProperties"] is False
    assert "$defs" not in schema  # refs inlined for Ollama's `format`
    assert set(schema["properties"]) == {
        "balance", "essentials_amount", "essentials_period", "inflows", "commitments",
    }
    inflow = schema["properties"]["inflows"]["items"]
    assert set(inflow["properties"]) == {
        "label", "amount", "date_kind", "date_value", "date_day",
        "date_in_days", "date_month_offset", "uncertainty_note",
    }
    assert inflow["additionalProperties"] is False
    assert "date_expr" not in inflow["properties"]  # flat: no nested date object
    # date fields are scalar (no nested object)
    assert "properties" not in inflow["properties"]["date_day"]
    assert "integer" in json.dumps(inflow["properties"]["date_day"])
    assert "day_of_month" in json.dumps(inflow["properties"]["date_kind"])


def test_map_flat_maps_date_to_day_of_month():
    out = map_flat_extraction(E01_FLAT)
    assert isinstance(out, ExtractorOutput)
    assert out.balance == 26000
    assert out.essentials.amount == 1500 and out.essentials.period == "day"
    assert out.inflows[0].expected_amount == 20000
    assert out.inflows[0].date_expr.kind == "day_of_month"
    assert out.inflows[0].date_expr.day == 15
    assert out.inflows[0].uncertainty_note == "promised, not confirmed"
    assert out.commitments[0].date_expr.day == 21
    assert out.commitments[1].amount == 2500 and out.commitments[1].date_expr.day == 9


def test_run_extraction_with_stub_sets_grounding():
    adapter = StubModelAdapter(json.dumps(E01_FLAT))
    out = run_extraction(E01_TEXT, adapter, Tracer())
    assert out.balance == 26000
    assert out.inflows[0].date_expr.day == 15
    g = out.grounding
    assert g["balance"]["grounded"] is True
    assert "26k" in g["balance"]["source_text"]
    assert g["inflows"][0]["amount"]["grounded"] is True
    assert g["inflows"][0]["date"]["grounded"] is True
    assert g["commitments"][1]["amount"]["grounded"] is True


def test_v1_flags_fabricated_amount_ungrounded():
    text = "I have about 26k in my account."
    ok, src = ground_amount(26000, text)
    assert ok is True and "26k" in src
    assert ground_amount(999999, text) == (False, None)
    assert ground_amount(1500, text) == (False, None)  # not in this text

    out = ExtractorOutput(balance=999999)
    g = run_v1(out, text)
    assert g["balance"]["grounded"] is False
    assert g["balance"]["source_text"] is None


def test_flat_extraction_model_is_closed():
    assert FlatExtraction.model_config["extra"] == "forbid"
