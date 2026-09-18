"""Full public-sample pipeline tests using the live OpenAI interpreter."""

from __future__ import annotations

import os

import pytest

from app.pipeline import run_optimize_energy
from app.schemas import OptimizeEnergyRequest
from tests.conftest import interpretation_core, load_samples, nearly_equal

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


@pytest.mark.parametrize("case", load_samples(), ids=lambda c: c["id"])
def test_full_pipeline_public_samples(case: dict) -> None:
    req = OptimizeEnergyRequest.model_validate(case["input"])
    expected = case["expected_output"]
    result = run_optimize_energy(req)

    assert interpretation_core(
        [e.model_dump() for e in result.directive_interpretation]
    ) == interpretation_core(expected["directive_interpretation"])
    assert nearly_equal(result.total_cost_bdt, expected["total_cost_bdt"])
    assert nearly_equal(result.total_grid_kwh, expected["total_grid_kwh"])
    assert nearly_equal(result.peak_grid_kwh, expected["peak_grid_kwh"])
