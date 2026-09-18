"""Extra edge-case optimization tests (hand-injected directives, no LLM)."""

from __future__ import annotations

from copy import deepcopy

from app.pipeline import run_optimize_with_directives
from app.schemas import OptimizeEnergyRequest
from tests.conftest import load_samples, nearly_equal


def _sample_input(idx: int = 0) -> dict:
    return deepcopy(load_samples()[idx]["input"])


def test_pure_no_op_optimizes() -> None:
    payload = _sample_input(0)
    payload["operator_notes"] = ["Library hours posted on the notice board."]
    payload["scenario_id"] = "EXTRA-NOOP"
    req = OptimizeEnergyRequest.model_validate(payload)
    interps = [
        {
            "note_index": 0,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "distractor",
        }
    ]
    result = run_optimize_with_directives(req, interps)
    assert result.total_cost_bdt >= 0
    assert len(result.hourly_plan) == 24
    assert nearly_equal(
        result.hourly_plan[-1].battery_energy_after_kwh,
        req.battery.initial_energy_kwh,
    )


def test_single_hour_no_charge_window() -> None:
    payload = _sample_input(1)
    payload["operator_notes"] = ["Do not charge from 7 PM until 8 PM."]
    payload["scenario_id"] = "EXTRA-SINGLE"
    req = OptimizeEnergyRequest.model_validate(payload)
    interps = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": [19]},
            "explanation": "single hour",
        }
    ]
    result = run_optimize_with_directives(req, interps)
    assert result.hourly_plan[19].battery_action != "charge" or result.hourly_plan[
        19
    ].battery_kwh == 0


def test_solar_factor_zero() -> None:
    payload = _sample_input(0)
    payload["operator_notes"] = ["Solar unavailable (0% usable) from noon to 2 PM."]
    payload["scenario_id"] = "EXTRA-FACTOR0"
    req = OptimizeEnergyRequest.model_validate(payload)
    interps = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": [12, 13], "factor": 0.0},
            "explanation": "full outage",
        }
    ]
    result = run_optimize_with_directives(req, interps)
    assert result.hourly_plan[12].solar_used_kwh == 0
    assert result.hourly_plan[13].solar_used_kwh == 0


def test_distractor_first_then_real_directive() -> None:
    payload = _sample_input(0)
    payload["operator_notes"] = [
        "Sports office registration deadline is Friday.",
        "Do not discharge the battery between 6 PM and 8 PM.",
    ]
    payload["scenario_id"] = "EXTRA-ORDER"
    req = OptimizeEnergyRequest.model_validate(payload)
    interps = [
        {
            "note_index": 0,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "distractor",
        },
        {
            "note_index": 1,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {"hours": [18, 19]},
            "explanation": "no discharge",
        },
    ]
    result = run_optimize_with_directives(req, interps)
    assert result.directive_interpretation[0].directive_type == "no_op"
    assert result.directive_interpretation[1].directive_type == "no_discharge_window"
    for h in (18, 19):
        assert not (
            result.hourly_plan[h].battery_action == "discharge"
            and result.hourly_plan[h].battery_kwh > 0.01
        )
