"""Deterministic guardrails for LLM directive interpretations."""

from __future__ import annotations

from typing import Any

from app.schemas import ALLOWED_DIRECTIVE_TYPES, BatteryConfig, OptimizeEnergyRequest

TOLERANCE = 0.01


class GuardrailError(ValueError):
    """Raised when LLM output fails deterministic validation."""


def _normalize_hours(hours: Any) -> list[int]:
    if not isinstance(hours, list) or not hours:
        raise GuardrailError("hours must be a non-empty list")
    cleaned: list[int] = []
    for h in hours:
        if isinstance(h, bool) or not isinstance(h, (int, float)):
            raise GuardrailError(f"invalid hour value: {h!r}")
        hi = int(h)
        if hi != h:
            raise GuardrailError(f"hour must be integer: {h!r}")
        if hi < 0 or hi > 23:
            raise GuardrailError(f"hour out of range: {hi}")
        cleaned.append(hi)
    unique_sorted = sorted(set(cleaned))
    if len(unique_sorted) != len(cleaned):
        # Deduplicate but keep ascending unique — duplicates are invalid per spec
        raise GuardrailError("hours must contain unique integers")
    if unique_sorted != cleaned and cleaned != sorted(cleaned):
        # Allow unsorted input by normalizing to ascending unique
        pass
    return unique_sorted


def _as_float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GuardrailError(f"{name} must be a number")
    f = float(value)
    if f != f or f in (float("inf"), float("-inf")):
        raise GuardrailError(f"{name} must be finite")
    return f


def validate_and_normalize_interpretation(
    raw_entries: list[dict[str, Any]],
    request: OptimizeEnergyRequest,
) -> list[dict[str, Any]]:
    """Validate LLM output and return normalized directive_interpretation list."""
    n = len(request.operator_notes)
    if not isinstance(raw_entries, list):
        raise GuardrailError("directive_interpretation must be a list")
    if len(raw_entries) != n:
        raise GuardrailError(
            f"expected {n} interpretation entries, got {len(raw_entries)}"
        )

    by_index: dict[int, dict[str, Any]] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict):
            raise GuardrailError("each interpretation entry must be an object")
        if "note_index" not in entry:
            raise GuardrailError("missing note_index")
        idx = entry["note_index"]
        if isinstance(idx, bool) or not isinstance(idx, (int, float)) or int(idx) != idx:
            raise GuardrailError(f"invalid note_index: {idx!r}")
        idx = int(idx)
        if idx < 0 or idx >= n:
            raise GuardrailError(f"note_index out of range: {idx}")
        if idx in by_index:
            raise GuardrailError(f"duplicate note_index: {idx}")
        by_index[idx] = entry

    if set(by_index.keys()) != set(range(n)):
        raise GuardrailError("note_index mapping incomplete")

    battery = request.battery
    normalized: list[dict[str, Any]] = []

    for i in range(n):
        entry = by_index[i]
        dtype = entry.get("directive_type")
        if dtype not in ALLOWED_DIRECTIVE_TYPES:
            raise GuardrailError(f"unsupported directive_type: {dtype!r}")

        applies = entry.get("applies")
        explanation = entry.get("explanation") or ""
        if not isinstance(explanation, str):
            explanation = str(explanation)

        adj = entry.get("structured_adjustment", None)

        # Coerce applies from directive_type when the model mismatches.
        if dtype == "no_op":
            applies = False
            adj = None
        else:
            applies = True
            if not isinstance(adj, dict):
                raise GuardrailError(f"{dtype} requires structured_adjustment object")

        if dtype == "no_op":
            normalized.append(
                {
                    "note_index": i,
                    "applies": False,
                    "directive_type": "no_op",
                    "structured_adjustment": None,
                    "explanation": explanation
                    or "Note does not affect today's energy schedule.",
                }
            )
            continue

        structured = _normalize_adjustment(dtype, adj, battery)
        normalized.append(
            {
                "note_index": i,
                "applies": True,
                "directive_type": dtype,
                "structured_adjustment": structured,
                "explanation": explanation or f"Applied {dtype} directive.",
            }
        )

    return normalized


def _normalize_adjustment(
    dtype: str, adj: dict[str, Any], battery: BatteryConfig
) -> dict[str, Any]:
    if "hours" not in adj:
        raise GuardrailError(f"{dtype} requires hours")
    hours = _normalize_hours(adj["hours"])

    if dtype == "solar_reduction":
        if "factor" not in adj:
            raise GuardrailError("solar_reduction requires factor")
        factor = _as_float(adj["factor"], "factor")
        if factor < 0 or factor > 1:
            raise GuardrailError("solar_reduction factor must be in [0, 1]")
        return {"hours": hours, "factor": factor}

    if dtype == "minimum_battery_reserve":
        if "minimum_energy_kwh" not in adj:
            raise GuardrailError("minimum_battery_reserve requires minimum_energy_kwh")
        reserve = _as_float(adj["minimum_energy_kwh"], "minimum_energy_kwh")
        if reserve < 0:
            raise GuardrailError("minimum_energy_kwh must be non-negative")
        if reserve > battery.capacity_kwh + TOLERANCE:
            raise GuardrailError("minimum_energy_kwh exceeds battery capacity")
        # Clamp tiny float overshoot into capacity
        reserve = min(reserve, battery.capacity_kwh)
        return {"hours": hours, "minimum_energy_kwh": reserve}

    if dtype in ("no_charge_window", "no_discharge_window"):
        extra = set(adj.keys()) - {"hours"}
        # Ignore unknown keys but require hours only shape
        return {"hours": hours}

    if dtype == "max_grid_window":
        if "max_grid_kwh" not in adj:
            raise GuardrailError("max_grid_window requires max_grid_kwh")
        cap = _as_float(adj["max_grid_kwh"], "max_grid_kwh")
        if cap < 0:
            raise GuardrailError("max_grid_kwh must be non-negative")
        return {"hours": hours, "max_grid_kwh": cap}

    raise GuardrailError(f"unsupported directive_type: {dtype}")


def apply_directives_to_params(
    request: OptimizeEnergyRequest,
    interpretations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build effective solar, per-hour battery mins, charge/discharge caps, grid caps."""
    hours = request.hours
    battery = request.battery

    effective_solar = [h.solar_kwh for h in hours]
    energy_min = [battery.minimum_energy_kwh] * 24
    max_charge = [battery.max_charge_kwh_per_hour] * 24
    max_discharge = [battery.max_discharge_kwh_per_hour] * 24
    max_grid: list[float | None] = [None] * 24

    for entry in interpretations:
        if not entry.get("applies") or entry["directive_type"] == "no_op":
            continue
        dtype = entry["directive_type"]
        adj = entry["structured_adjustment"]
        hs = adj["hours"]

        if dtype == "solar_reduction":
            factor = adj["factor"]
            for h in hs:
                # Compose multiple reductions on the same hour (defensive).
                effective_solar[h] = effective_solar[h] * factor
        elif dtype == "minimum_battery_reserve":
            reserve = adj["minimum_energy_kwh"]
            for h in hs:
                energy_min[h] = max(energy_min[h], reserve)
        elif dtype == "no_charge_window":
            for h in hs:
                max_charge[h] = 0.0
        elif dtype == "no_discharge_window":
            for h in hs:
                max_discharge[h] = 0.0
        elif dtype == "max_grid_window":
            cap = adj["max_grid_kwh"]
            for h in hs:
                if max_grid[h] is None:
                    max_grid[h] = cap
                else:
                    max_grid[h] = min(max_grid[h], cap)

    return {
        "effective_solar": effective_solar,
        "energy_min": energy_min,
        "max_charge": max_charge,
        "max_discharge": max_discharge,
        "max_grid": max_grid,
        "demand": [h.demand_kwh for h in hours],
        "tariff": [h.tariff_bdt_per_kwh for h in hours],
        "capacity": battery.capacity_kwh,
        "initial_energy": battery.initial_energy_kwh,
    }
