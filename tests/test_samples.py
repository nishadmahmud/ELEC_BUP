"""Optimizer + guardrail tests using public sample expected interpretations (no LLM)."""

from __future__ import annotations

import pytest

from app.pipeline import run_optimize_with_directives
from app.schemas import OptimizeEnergyRequest
from tests.conftest import interpretation_core, load_samples, nearly_equal


@pytest.mark.parametrize("case", load_samples(), ids=lambda c: c["id"])
def test_optimizer_matches_sample_with_expected_directives(case: dict) -> None:
    req = OptimizeEnergyRequest.model_validate(case["input"])
    expected = case["expected_output"]
    result = run_optimize_with_directives(req, expected["directive_interpretation"])

    assert interpretation_core(
        [e.model_dump() for e in result.directive_interpretation]
    ) == interpretation_core(expected["directive_interpretation"])

    assert nearly_equal(result.total_cost_bdt, expected["total_cost_bdt"])
    assert nearly_equal(result.total_grid_kwh, expected["total_grid_kwh"])
    assert nearly_equal(result.peak_grid_kwh, expected["peak_grid_kwh"])
    assert len(result.hourly_plan) == 24
    assert result.scenario_id == req.scenario_id
