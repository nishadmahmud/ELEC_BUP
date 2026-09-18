"""End-to-end optimize-energy pipeline."""

from __future__ import annotations

from app.guardrails import (
    GuardrailError,
    apply_directives_to_params,
    validate_and_normalize_interpretation,
)
from app.llm import LLMInterpretationError, interpret_operator_notes
from app.optimizer import OptimizationError, optimize_schedule
from app.replay import ReplayError, replay_and_aggregate
from app.schemas import OptimizeEnergyRequest, OptimizeEnergyResponse


class PipelineError(RuntimeError):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def run_optimize_energy(request: OptimizeEnergyRequest) -> OptimizeEnergyResponse:
    try:
        raw = interpret_operator_notes(request)
        interpretations = validate_and_normalize_interpretation(raw, request)
        params = apply_directives_to_params(request, interpretations)
        plan = optimize_schedule(request, params)
        return replay_and_aggregate(request, interpretations, params, plan)
    except GuardrailError as exc:
        raise PipelineError(f"interpretation_invalid: {exc}", status_code=500) from exc
    except LLMInterpretationError as exc:
        raise PipelineError(f"interpretation_failed: {exc}", status_code=500) from exc
    except OptimizationError as exc:
        raise PipelineError(f"optimization_infeasible: {exc}", status_code=500) from exc
    except ReplayError as exc:
        raise PipelineError(f"schedule_invalid: {exc}", status_code=500) from exc


def run_optimize_with_directives(
    request: OptimizeEnergyRequest,
    interpretations: list[dict],
) -> OptimizeEnergyResponse:
    """Test helper: skip LLM and optimize with provided interpretations."""
    normalized = validate_and_normalize_interpretation(interpretations, request)
    params = apply_directives_to_params(request, normalized)
    plan = optimize_schedule(request, params)
    return replay_and_aggregate(request, normalized, params, plan)
