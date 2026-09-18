"""Paraphrase robustness helpers — structured expectations for LLM integration tests."""

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
]


@pytest.mark.parametrize("case", PARAPHRASE_CASES, ids=lambda c: c["id"])
def test_llm_paraphrase_solar(case: dict) -> None:
    base = load_samples()[0]["input"]
    payload = {**base, "operator_notes": case["notes"], "scenario_id": case["id"]}
    req = OptimizeEnergyRequest.model_validate(payload)
    raw = interpret_operator_notes(req)
    normalized = validate_and_normalize_interpretation(raw, req)
    assert interpretation_core(normalized) == case["expected"]
