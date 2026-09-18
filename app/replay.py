"""Replay verifier: validate hourly plan against GridWise + directive rules."""

from __future__ import annotations

from typing import Any

from app.schemas import HourlyPlanEntry, OptimizeEnergyRequest, OptimizeEnergyResponse

TOLERANCE = 0.01


class ReplayError(ValueError):
    """Raised when returned schedule fails independent replay checks."""


def replay_and_aggregate(
    request: OptimizeEnergyRequest,
    interpretations: list[dict[str, Any]],
    params: dict[str, Any],
    plan: list[HourlyPlanEntry],
) -> OptimizeEnergyResponse:
    """Verify plan and return full response with recomputed aggregates."""
    if len(plan) != 24:
        raise ReplayError("hourly_plan must have 24 entries")
    hours_seen = [p.hour for p in plan]
    if sorted(hours_seen) != list(range(24)):
        raise ReplayError("hourly_plan hours must be unique 0..23")

    ordered = sorted(plan, key=lambda p: p.hour)
    demand = params["demand"]
    solar = params["effective_solar"]
    tariff = params["tariff"]
    energy_min = params["energy_min"]
    max_charge = params["max_charge"]
    max_discharge = params["max_discharge"]
    max_grid = params["max_grid"]
    capacity = params["capacity"]
    energy = params["initial_energy"]

    total_cost = 0.0
    total_grid = 0.0
    peak_grid = 0.0

    for h, entry in enumerate(ordered):
        if entry.hour != h:
            raise ReplayError("hourly_plan must be ordered 0..23 after sort")

        for name, val in (
            ("grid_kwh", entry.grid_kwh),
            ("solar_used_kwh", entry.solar_used_kwh),
            ("battery_kwh", entry.battery_kwh),
            ("battery_energy_after_kwh", entry.battery_energy_after_kwh),
        ):
            if val != val or val < -TOLERANCE:
                raise ReplayError(f"invalid {name} at hour {h}")

        grid = entry.grid_kwh
        solar_used = entry.solar_used_kwh
        action = entry.battery_action
        bkwh = entry.battery_kwh

        if action == "idle":
            if bkwh > TOLERANCE:
                raise ReplayError(f"idle requires battery_kwh=0 at hour {h}")
            charge = 0.0
            discharge = 0.0
        elif action == "charge":
            charge = bkwh
            discharge = 0.0
            if charge > max_charge[h] + TOLERANCE:
                raise ReplayError(f"charge exceeds limit at hour {h}")
        elif action == "discharge":
            discharge = bkwh
            charge = 0.0
            if discharge > max_discharge[h] + TOLERANCE:
                raise ReplayError(f"discharge exceeds limit at hour {h}")
        else:
            raise ReplayError(f"invalid battery_action at hour {h}")

        if solar_used > solar[h] + TOLERANCE:
            raise ReplayError(f"solar overuse at hour {h}")

        # Energy balance
        lhs = grid + solar_used + discharge
        rhs = demand[h] + charge
        if abs(lhs - rhs) > TOLERANCE:
            raise ReplayError(
                f"energy balance fail hour {h}: {lhs} != {rhs}"
            )

        if max_grid[h] is not None and grid > max_grid[h] + TOLERANCE:
            raise ReplayError(f"max_grid_window violated at hour {h}")

        energy_after = energy + charge - discharge
        if abs(energy_after - entry.battery_energy_after_kwh) > TOLERANCE:
            raise ReplayError(
                f"battery energy mismatch hour {h}: "
                f"expected {energy_after}, got {entry.battery_energy_after_kwh}"
            )
        if energy_after < energy_min[h] - TOLERANCE:
            raise ReplayError(f"battery below minimum at hour {h}")
        if energy_after > capacity + TOLERANCE:
            raise ReplayError(f"battery above capacity at hour {h}")

        energy = entry.battery_energy_after_kwh
        total_grid += grid
        total_cost += grid * tariff[h]
        peak_grid = max(peak_grid, grid)

    if abs(energy - params["initial_energy"]) > TOLERANCE:
        raise ReplayError("end-of-day battery neutrality violated")

    # Explicit directive re-check (redundant with params but mirrors judge)
    _verify_directives(interpretations, ordered, params)

    summary = _build_summary(interpretations, total_cost, peak_grid)

    return OptimizeEnergyResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=interpretations,  # type: ignore[arg-type]
        hourly_plan=ordered,
        total_grid_kwh=_clean(total_grid),
        total_cost_bdt=_clean(total_cost),
        peak_grid_kwh=_clean(peak_grid),
        plan_summary=summary,
    )


def _verify_directives(
    interpretations: list[dict[str, Any]],
    plan: list[HourlyPlanEntry],
    params: dict[str, Any],
) -> None:
    for entry in interpretations:
        if not entry.get("applies") or entry["directive_type"] == "no_op":
            continue
        dtype = entry["directive_type"]
        adj = entry["structured_adjustment"]
        hs = adj["hours"]

        if dtype == "solar_reduction":
            # Already baked into effective solar; solar_used checked earlier
            continue
        if dtype == "minimum_battery_reserve":
            reserve = adj["minimum_energy_kwh"]
            for h in hs:
                if plan[h].battery_energy_after_kwh < reserve - TOLERANCE:
                    raise ReplayError(f"reserve violated at hour {h}")
        elif dtype == "no_charge_window":
            for h in hs:
                if plan[h].battery_action == "charge" and plan[h].battery_kwh > TOLERANCE:
                    raise ReplayError(f"no_charge_window violated at hour {h}")
        elif dtype == "no_discharge_window":
            for h in hs:
                if (
                    plan[h].battery_action == "discharge"
                    and plan[h].battery_kwh > TOLERANCE
                ):
                    raise ReplayError(f"no_discharge_window violated at hour {h}")
        elif dtype == "max_grid_window":
            cap = adj["max_grid_kwh"]
            for h in hs:
                if plan[h].grid_kwh > cap + TOLERANCE:
                    raise ReplayError(f"max_grid_window violated at hour {h}")


def _build_summary(
    interpretations: list[dict[str, Any]], total_cost: float, peak_grid: float
) -> str:
    applied = [
        e["directive_type"]
        for e in interpretations
        if e.get("applies") and e["directive_type"] != "no_op"
    ]
    if applied:
        directives = ", ".join(applied)
        return (
            f"Applied directives [{directives}]; minimized grid cost to "
            f"{total_cost:.2f} BDT with peak grid {peak_grid:.2f} kWh "
            f"while respecting battery neutrality and energy balance."
        )
    return (
        f"No operational directives applied; minimized grid cost to "
        f"{total_cost:.2f} BDT with peak grid {peak_grid:.2f} kWh."
    )


def _clean(x: float) -> float:
    if abs(x) < 1e-9:
        return 0.0
    return round(x, 6)
