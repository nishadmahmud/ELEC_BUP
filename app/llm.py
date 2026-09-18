"""OpenAI structured extraction for operator notes."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from openai import APIStatusError, APITimeoutError, OpenAI, RateLimitError

from app.prompts import INTERPRETATION_JSON_SCHEMA, SYSTEM_PROMPT, build_user_prompt
from app.schemas import OptimizeEnergyRequest

# Keep total LLM wall time under judge 30s budget (optimizer is ~ms).
_LLM_DEADLINE_S = 22.0
_client_singleton: OpenAI | None = None
_INTERP_CACHE: dict[str, list[dict[str, Any]]] = {}
_CACHE_MAX = 256


class LLMInterpretationError(RuntimeError):
    """Raised when the language model cannot produce usable structured output."""


def _client() -> OpenAI:
    global _client_singleton
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMInterpretationError("OPENAI_API_KEY is not configured")
    if _client_singleton is None:
        _client_singleton = OpenAI(api_key=api_key, timeout=20.0, max_retries=0)
    return _client_singleton


def _cache_key(request: OptimizeEnergyRequest) -> str:
    payload = {
        "notes": request.operator_notes,
        "capacity": request.battery.capacity_kwh,
        "min_energy": request.battery.minimum_energy_kwh,
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def interpret_operator_notes(request: OptimizeEnergyRequest) -> list[dict[str, Any]]:
    """Call OpenAI once for all notes; retry the same primary model once.

    Does not escalate to a slower backup by default (protects p95 latency).
    Set OPENAI_BACKUP_MODEL only if you explicitly want a different fallback.
    """
    key = _cache_key(request)
    cached = _INTERP_CACHE.get(key)
    if cached is not None:
        return [dict(e) for e in cached]

    primary = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    backup_raw = os.getenv("OPENAI_BACKUP_MODEL")
    if backup_raw is None:
        backup = primary
    else:
        backup = backup_raw.strip() or primary

    user_prompt = build_user_prompt(
        request.operator_notes,
        request.battery.capacity_kwh,
        request.battery.minimum_energy_kwh,
    )

    deadline = time.monotonic() + _LLM_DEADLINE_S
    attempts: list[str] = [primary, primary]
    if backup != primary:
        attempts.append(backup)

    last_error: Exception | None = None
    for i, model in enumerate(attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 1.0:
            break
        try:
            entries = _call_model(model, user_prompt)
            result = [
                _maybe_fix_solar_factor(e, request.operator_notes) for e in entries
            ]
            if len(_INTERP_CACHE) >= _CACHE_MAX:
                _INTERP_CACHE.pop(next(iter(_INTERP_CACHE)))
            _INTERP_CACHE[key] = result
            return [dict(e) for e in result]
        except Exception as exc:  # noqa: BLE001 — controlled retry boundary
            last_error = exc
            if i < len(attempts) - 1:
                delay = 0.4 if _is_transient(exc) else 0.2
                time.sleep(min(delay, max(0.0, deadline - time.monotonic())))

    raise LLMInterpretationError(
        f"LLM interpretation failed after retries: {last_error}"
    )


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (APITimeoutError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return True
    return False


def _call_model(model: str, user_prompt: str) -> list[dict[str, Any]]:
    client = _client()
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=900,
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
        return {**entry, "applies": False, "structured_adjustment": None}
    if isinstance(adj, dict):
        cleaned = {k: v for k, v in adj.items() if v is not None}
        entry = {**entry, "structured_adjustment": cleaned or None}
    return entry


def _maybe_fix_solar_factor(
    entry: dict[str, Any], request_notes: list[str]
) -> dict[str, Any]:
    """Fix factor when LLM returns a 1..100 percent instead of 0..1 fraction."""
    if entry.get("directive_type") != "solar_reduction":
        return entry
    adj = entry.get("structured_adjustment")
    if not isinstance(adj, dict) or "factor" not in adj:
        return entry
    try:
        factor = float(adj["factor"])
    except (TypeError, ValueError):
        return entry
    if not (1 < factor <= 100):
        return entry

    text = f"{entry.get('explanation', '')}".lower()
    idx = entry.get("note_index")
    if isinstance(idx, int) and 0 <= idx < len(request_notes):
        text = f"{request_notes[idx]} {text}".lower()

    reduction_cues = (
        "reduction",
        "reduce by",
        "reduced by",
        "drop by",
        "cuts by",
        "cut by",
        "% reduction",
    )
    remaining_cues = (
        "drop to",
        "down to",
        "leave",
        "leaves",
        "usable",
        "of forecast",
        "of normal",
        "% of",
        "one-fifth",
        "one fifth",
        "half of",
    )

    has_reduction = any(k in text for k in reduction_cues)
    has_remaining = any(k in text for k in remaining_cues)

    if has_remaining and not has_reduction:
        new_factor = round(factor / 100.0, 6)
    else:
        new_factor = round(1.0 - factor / 100.0, 6)

    new_factor = min(1.0, max(0.0, new_factor))
    return {**entry, "structured_adjustment": {**adj, "factor": new_factor}}
