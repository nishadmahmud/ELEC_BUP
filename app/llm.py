"""OpenAI structured extraction for operator notes."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from openai import OpenAI

from app.prompts import INTERPRETATION_JSON_SCHEMA, SYSTEM_PROMPT, build_user_prompt
from app.schemas import OptimizeEnergyRequest


class LLMInterpretationError(RuntimeError):
    """Raised when the language model cannot produce usable structured output."""


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMInterpretationError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=api_key, timeout=25.0)


def interpret_operator_notes(request: OptimizeEnergyRequest) -> list[dict[str, Any]]:
    """Call OpenAI once for all notes; retry once; optional backup model."""
    primary = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    backup = os.getenv("OPENAI_BACKUP_MODEL", "gpt-4o")
    user_prompt = build_user_prompt(
        request.operator_notes,
        request.battery.capacity_kwh,
        request.battery.minimum_energy_kwh,
    )

    last_error: Exception | None = None
    for model in (primary, primary, backup):
        try:
            return _call_model(model, user_prompt)
        except Exception as exc:  # noqa: BLE001 — controlled retry boundary
            last_error = exc
            time.sleep(0.35)

    raise LLMInterpretationError(
        f"LLM interpretation failed after retries: {last_error}"
    )


def _call_model(model: str, user_prompt: str) -> list[dict[str, Any]]:
    client = _client()
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=1200,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "gridwise_directive_interpretation",
                "strict": True,
                "schema": INTERPRETATION_JSON_SCHEMA,
            },
        },
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise LLMInterpretationError("empty LLM response")
    data = json.loads(content)
    entries = data.get("directive_interpretation")
    if not isinstance(entries, list):
        raise LLMInterpretationError("missing directive_interpretation array")
    return [_strip_null_adjustment_fields(e) for e in entries]


def _strip_null_adjustment_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Remove null optional keys from structured_adjustment (strict schema padding)."""
    adj = entry.get("structured_adjustment")
    dtype = entry.get("directive_type")
    if dtype == "no_op":
        entry = {**entry, "applies": False, "structured_adjustment": None}
        return entry
    if isinstance(adj, dict):
        cleaned = {k: v for k, v in adj.items() if v is not None}
        # hours-only leftover with no usable fields beyond empty hours → treat carefully
        entry = {**entry, "structured_adjustment": cleaned or None}
    return entry
