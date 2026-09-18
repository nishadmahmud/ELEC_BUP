"""PuLP/CBC 24-hour battery energy optimizer."""

from __future__ import annotations

from typing import Any

import pulp

from app.schemas import HourlyPlanEntry, OptimizeEnergyRequest

EPS = 1e-6


class OptimizationError(RuntimeError):
    """Raised when the LP is infeasible or solver fails."""


def optimize_schedule(
    request: OptimizeEnergyRequest,
    params: dict[str, Any],
) -> list[HourlyPlanEntry]:
    """Solve min grid cost subject to GridWise + directive constraints."""
    demand = params["demand"]
    solar = params["effective_solar"]
    tariff = params["tariff"]
    energy_min = params["energy_min"]
    max_charge = params["max_charge"]
    max_discharge = params["max_discharge"]
    max_grid = params["max_grid"]
    capacity = params["capacity"]
    initial = params["initial_energy"]

    # Upper bound for grid import (unconstrained hours)
    big_grid = max(
        max(d + mc for d, mc in zip(demand, max_charge)) + 1.0,
        1e6,
    )

    prob = pulp.LpProblem("gridwise_energy", pulp.LpMinimize)

    g = [pulp.LpVariable(f"g_{h}", lowBound=0) for h in range(24)]
    s = [pulp.LpVariable(f"s_{h}", lowBound=0) for h in range(24)]
    c = [pulp.LpVariable(f"c_{h}", lowBound=0) for h in range(24)]
    d = [pulp.LpVariable(f"d_{h}", lowBound=0) for h in range(24)]
    e = [pulp.LpVariable(f"e_{h}", lowBound=0) for h in range(24)]

    prob += pulp.lpSum(g[h] * tariff[h] for h in range(24))

    for h in range(24):
        # Energy balance
        prob += g[h] + s[h] + d[h] == demand[h] + c[h], f"balance_{h}"
        # Solar curtailment
        prob += s[h] <= solar[h], f"solar_{h}"
        # Rate limits
        prob += c[h] <= max_charge[h], f"charge_cap_{h}"
        prob += d[h] <= max_discharge[h], f"discharge_cap_{h}"
        # Battery bounds
        prob += e[h] >= energy_min[h], f"emin_{h}"
        prob += e[h] <= capacity, f"emax_{h}"
        # Grid cap
        if max_grid[h] is not None:
            prob += g[h] <= max_grid[h], f"gmax_{h}"
        else:
            prob += g[h] <= big_grid, f"gsoft_{h}"

        # Dynamics
        prev = initial if h == 0 else e[h - 1]
        prob += e[h] == prev + c[h] - d[h], f"dyn_{h}"

    # End-of-day neutrality
    prob += e[23] == initial, "eod_neutrality"

    # Discourage simultaneous charge+discharge (soft via tiny penalty not needed;
    # CBC with continuous vars may dual-use — we net in post-processing).
    # Add mutual exclusion with binary for cleaner plans when rates allow both.
    z = [pulp.LpVariable(f"z_{h}", cat="Binary") for h in range(24)]
    for h in range(24):
        # If max_charge is 0, force c=0 already; same for discharge
        if max_charge[h] > EPS:
            prob += c[h] <= max_charge[h] * z[h], f"z_c_{h}"
        if max_discharge[h] > EPS:
            prob += d[h] <= max_discharge[h] * (1 - z[h]), f"z_d_{h}"

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=10)
    status = prob.solve(solver)
    if status != pulp.LpStatusOptimal:
        raise OptimizationError(
            f"optimizer failed with status {pulp.LpStatus[status]}"
        )

    plan: list[HourlyPlanEntry] = []
    for h in range(24):
        gv = float(pulp.value(g[h]) or 0.0)
        sv = float(pulp.value(s[h]) or 0.0)
        cv = float(pulp.value(c[h]) or 0.0)
        dv = float(pulp.value(d[h]) or 0.0)
        ev = float(pulp.value(e[h]) or 0.0)

        # Net simultaneous charge/discharge (should be rare with binaries)
        if cv > EPS and dv > EPS:
            if cv >= dv:
                cv, dv = cv - dv, 0.0
            else:
                dv, cv = dv - cv, 0.0

        if cv > EPS and dv <= EPS:
            action = "charge"
            bkwh = cv
        elif dv > EPS and cv <= EPS:
            action = "discharge"
            bkwh = dv
        else:
            action = "idle"
            bkwh = 0.0
            # Recompute energy after from previous for consistency
            # Use solver e[h] which already accounts for net

        # Round lightly for JSON cleanliness while staying within 0.01 tolerance
        plan.append(
            HourlyPlanEntry(
                hour=h,
                grid_kwh=_clean(gv),
                solar_used_kwh=_clean(sv),
                battery_action=action,
                battery_kwh=_clean(bkwh),
                battery_energy_after_kwh=_clean(ev),
            )
        )

    return plan


def _clean(x: float) -> float:
    if abs(x) < 1e-9:
        return 0.0
    # Keep enough precision for 0.01 tolerance checks
    return round(x, 6)
