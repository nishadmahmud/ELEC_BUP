"""Paraphrase robustness — structured expectations for LLM integration tests."""

from __future__ import annotations

import os

import pytest

from app.guardrails import validate_and_normalize_interpretation
from app.llm import interpret_operator_notes
from app.schemas import OptimizeEnergyRequest
from tests.conftest import interpretation_core, load_samples

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


PARAPHRASE_CASES = [
    {
        "id": "solar_paraphrase_a",
        "notes": [
            "PV production will drop to about 20% between 13:00 and 15:00.",
        ],
        "expected": [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "solar_reduction",
                "structured_adjustment": {"hours": [13, 14], "factor": 0.2},
            }
        ],
    },
    {
        "id": "solar_paraphrase_b",
        "notes": [
            "Expect an 80% reduction in rooftop solar during the 1-3 PM maintenance window.",
        ],
        "expected": [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "solar_reduction",
                "structured_adjustment": {"hours": [13, 14], "factor": 0.2},
            }
        ],
    },
    {
        "id": "solar_paraphrase_c",
        "notes": [
            "Panel washing from one until three will leave roughly one-fifth of normal solar output.",
        ],
        "expected": [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "solar_reduction",
                "structured_adjustment": {"hours": [13, 14], "factor": 0.2},
            }
        ],
    },
    {
        "id": "no_charge_am",
        "notes": [
            "Battery charger will be isolated from 2 AM until 5 AM for electrical work.",
        ],
        "expected": [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "no_charge_window",
                "structured_adjustment": {"hours": [2, 3, 4]},
            }
        ],
    },
    {
        "id": "reserve_pct",
        "notes": [
            "Hold at least 50% of battery capacity as emergency reserve from 6 PM to 9 PM.",
        ],
        "expected": [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "minimum_battery_reserve",
                "structured_adjustment": {
                    "hours": [18, 19, 20],
                    "minimum_energy_kwh": 100,
                },
            }
        ],
        # SAMPLE-01 battery capacity is 500 in first sample — need matching capacity.
        # Use sample index with capacity 200 (SAMPLE-03 style).
        "sample_index": 2,
    },
    {
        "id": "max_grid_feeder",
        "notes": [
            "Temporary feeder limit: grid import must stay at or below 155 kWh each hour from 6 PM until 9 PM.",
        ],
        "expected": [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "max_grid_window",
                "structured_adjustment": {"hours": [18, 19, 20], "max_grid_kwh": 155},
            }
        ],
    },
    {
        "id": "no_discharge",
        "notes": [
            "Do not discharge the battery between 6 PM and 8 PM during relay testing.",
        ],
        "expected": [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "no_discharge_window",
                "structured_adjustment": {"hours": [18, 19]},
            }
        ],
    },
    {
        "id": "distractor_noop",
        "notes": [
            "Library hours are posted on the notice board for tomorrow.",
        ],
        "expected": [
            {
                "note_index": 0,
                "applies": False,
                "directive_type": "no_op",
                "structured_adjustment": None,
            }
        ],
    },
]


@pytest.mark.parametrize("case", PARAPHRASE_CASES, ids=lambda c: c["id"])
def test_llm_paraphrase_directives(case: dict) -> None:
    idx = case.get("sample_index", 0)
    base = load_samples()[idx]["input"]
    # For reserve_pct, ensure capacity is 200 so 50% -> 100
    if case["id"] == "reserve_pct":
        assert base["battery"]["capacity_kwh"] == 200
    payload = {**base, "operator_notes": case["notes"], "scenario_id": case["id"]}
    req = OptimizeEnergyRequest.model_validate(payload)
    raw = interpret_operator_notes(req)
    normalized = validate_and_normalize_interpretation(raw, req)
    assert interpretation_core(normalized) == case["expected"]
