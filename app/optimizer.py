"""PuLP/CBC 24-hour battery energy optimizer."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pulp

from app.schemas import HourlyPlanEntry, OptimizeEnergyRequest

EPS = 1e-6


class OptimizationError(RuntimeError):
    """Raised when the LP is infeasible or solver fails."""


def optimize_schedule(
    request: OptimizeEnergyRequest,
    params: dict[str, Any],
) -> tuple[list[HourlyPlanEntry], dict[str, Any]]:
    """Solve min grid cost; on infeasibility, relax caps/reserves.

    Returns (plan, params_used) so replay matches the solved model.
    """
    attempts = [
        params,
        _relax_max_grid(params),
        _relax_directive_reserves(params),
        _relax_max_grid(_relax_directive_reserves(params)),
    ]
    last_error: Exception | None = None
    seen: set[str] = set()
    for attempt in attempts:
        key = _params_fingerprint(attempt)
        if key in seen:
            continue
        seen.add(key)
        try:
            return _solve_once(attempt), attempt
        except OptimizationError as exc:
            last_error = exc
    raise OptimizationError(str(last_error) if last_error else "optimizer failed")


def _relax_max_grid(params: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(params)
    out["max_grid"] = [None] * 24
    return out


def _relax_directive_reserves(params: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(params)
    base = float(params.get("base_minimum", min(params["energy_min"])))
    out["energy_min"] = [base] * 24
    return out

def _params_fingerprint(params: dict[str, Any]) -> str:
    return repr(
        (
            params["max_grid"],
            params["energy_min"],
            params["max_charge"],
            params["max_discharge"],
        )
    )


def _solve_once(params: dict[str, Any]) -> list[HourlyPlanEntry]:
    demand = params["demand"]
    solar = params["effective_solar"]
    tariff = params["tariff"]
    energy_min = params["energy_min"]
    max_charge = params["max_charge"]
    max_discharge = params["max_discharge"]
    max_grid = params["max_grid"]
    capacity = params["capacity"]
    initial = params["initial_energy"]

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

    # Tiny throughput penalty reduces pointless charge↔discharge cycling.
    prob += pulp.lpSum(
        g[h] * tariff[h] + 1e-7 * (c[h] + d[h]) for h in range(24)
    )

    for h in range(24):
        prob += g[h] + s[h] + d[h] == demand[h] + c[h], f"balance_{h}"
        prob += s[h] <= solar[h], f"solar_{h}"
        prob += c[h] <= max_charge[h], f"charge_cap_{h}"
        prob += d[h] <= max_discharge[h], f"discharge_cap_{h}"
        prob += e[h] >= energy_min[h], f"emin_{h}"
        prob += e[h] <= capacity, f"emax_{h}"
        if max_grid[h] is not None:
            prob += g[h] <= max_grid[h], f"gmax_{h}"
        else:
            prob += g[h] <= big_grid, f"gsoft_{h}"

        prev = initial if h == 0 else e[h - 1]
        prob += e[h] == prev + c[h] - d[h], f"dyn_{h}"

    prob += e[23] == initial, "eod_neutrality"

    z = [pulp.LpVariable(f"z_{h}", cat="Binary") for h in range(24)]
    for h in range(24):
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
    return round(x, 6)
