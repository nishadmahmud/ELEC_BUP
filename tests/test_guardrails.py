"""Guardrail unit tests."""

from __future__ import annotations

import pytest

from app.guardrails import GuardrailError, validate_and_normalize_interpretation
from app.schemas import OptimizeEnergyRequest
from tests.conftest import load_samples


def _base_request(notes: list[str]) -> OptimizeEnergyRequest:
    sample = load_samples()[0]["input"]
    payload = {**sample, "operator_notes": notes}
    return OptimizeEnergyRequest.model_validate(payload)


def test_no_op_semantics() -> None:
    req = _base_request(["The cafeteria menu changes tomorrow."])
    out = validate_and_normalize_interpretation(
        [
            {
                "note_index": 0,
                "applies": False,
                "directive_type": "no_op",
                "structured_adjustment": None,
                "explanation": "distractor",
            }
        ],
        req,
    )
    assert out[0]["applies"] is False
    assert out[0]["structured_adjustment"] is None


def test_coerces_applies_mismatch_for_no_op() -> None:
    req = _base_request(["Library notice tomorrow."])
    out = validate_and_normalize_interpretation(
        [
            {
                "note_index": 0,
                "applies": True,  # wrong; should coerce to false for no_op
                "directive_type": "no_op",
                "structured_adjustment": {"hours": [1]},
                "explanation": "distractor",
            }
        ],
        req,
    )
    assert out[0]["applies"] is False
    assert out[0]["structured_adjustment"] is None


def test_rejects_unknown_directive() -> None:
    req = _base_request(["Do something weird."])
    with pytest.raises(GuardrailError):
        validate_and_normalize_interpretation(
            [
                {
                    "note_index": 0,
                    "applies": True,
                    "directive_type": "export_to_grid",
                    "structured_adjustment": {"hours": [1]},
                    "explanation": "bad",
                }
            ],
            req,
        )


def test_normalizes_unsorted_hours() -> None:
    req = _base_request(["Do not charge between 2 PM and 4 PM."])
    out = validate_and_normalize_interpretation(
        [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "no_charge_window",
                "structured_adjustment": {"hours": [15, 14]},
                "explanation": "ok",
            }
        ],
        req,
    )
    assert out[0]["structured_adjustment"]["hours"] == [14, 15]


def test_solar_factor_bounds() -> None:
    req = _base_request(["Solar drops."])
    with pytest.raises(GuardrailError):
        validate_and_normalize_interpretation(
            [
                {
                    "note_index": 0,
                    "applies": True,
                    "directive_type": "solar_reduction",
                    "structured_adjustment": {"hours": [12], "factor": 1.5},
                    "explanation": "bad",
                }
            ],
            req,
        )


def test_expands_start_end_window() -> None:
    req = _base_request(["Do not charge from 2 PM until 4 PM."])
    out = validate_and_normalize_interpretation(
        [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "no_charge_window",
                "structured_adjustment": {
                    "hours": [],
                    "start_hour": 14,
                    "end_hour": 16,
                },
                "explanation": "window",
            }
        ],
        req,
    )
    assert out[0]["structured_adjustment"]["hours"] == [14, 15]


def test_window_beats_empty_hours() -> None:
    req = _base_request(["Solar drop 1-3 PM to 20%."])
    out = validate_and_normalize_interpretation(
        [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "solar_reduction",
                "structured_adjustment": {
                    "start_hour": 13,
                    "end_hour": 15,
                    "factor": 0.2,
                },
                "explanation": "window",
            }
        ],
        req,
    )
    assert out[0]["structured_adjustment"]["hours"] == [13, 14]
    assert out[0]["structured_adjustment"]["factor"] == 0.2
