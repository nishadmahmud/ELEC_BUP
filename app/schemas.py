"""Request and response schemas for GridWise API."""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


ALLOWED_DIRECTIVE_TYPES = (
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
)

BatteryAction = Literal["charge", "discharge", "idle"]
DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
]


class HourEntry(BaseModel):
    hour: int = Field(ge=0, le=23)
    demand_kwh: float = Field(ge=0)
    solar_kwh: float = Field(ge=0)
    tariff_bdt_per_kwh: float = Field(ge=0)


class BatteryConfig(BaseModel):
    capacity_kwh: float = Field(gt=0)
    initial_energy_kwh: float = Field(ge=0)
    minimum_energy_kwh: float = Field(ge=0)
    max_charge_kwh_per_hour: float = Field(ge=0)
    max_discharge_kwh_per_hour: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_battery_bounds(self) -> "BatteryConfig":
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError("initial_energy_kwh cannot exceed capacity_kwh")
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError("minimum_energy_kwh cannot exceed capacity_kwh")
        if self.initial_energy_kwh < self.minimum_energy_kwh:
            raise ValueError("initial_energy_kwh cannot be below minimum_energy_kwh")
        return self


class OptimizeEnergyRequest(BaseModel):
    scenario_id: str = Field(min_length=1)
    operator_notes: list[str] = Field(min_length=1, max_length=3)
    hours: list[HourEntry]
    battery: BatteryConfig

    @field_validator("operator_notes")
    @classmethod
    def notes_non_empty(cls, notes: list[str]) -> list[str]:
        if not notes or not (1 <= len(notes) <= 3):
            raise ValueError("operator_notes must contain 1-3 strings")
        for i, note in enumerate(notes):
            if not isinstance(note, str) or not note.strip():
                raise ValueError(f"operator_notes[{i}] must be a non-empty string")
        return notes

    @field_validator("hours")
    @classmethod
    def validate_hours(cls, hours: list[HourEntry]) -> list[HourEntry]:
        if len(hours) != 24:
            raise ValueError("hours must contain exactly 24 entries")
        seen = [h.hour for h in hours]
        if sorted(seen) != list(range(24)):
            raise ValueError("hours must contain unique hours 0 through 23")
        return sorted(hours, key=lambda h: h.hour)


class SolarReductionAdjustment(BaseModel):
    hours: list[int]
    factor: float = Field(ge=0, le=1)


class MinimumBatteryReserveAdjustment(BaseModel):
    hours: list[int]
    minimum_energy_kwh: float = Field(ge=0)


class HoursOnlyAdjustment(BaseModel):
    hours: list[int]


class MaxGridWindowAdjustment(BaseModel):
    hours: list[int]
    max_grid_kwh: float = Field(ge=0)


StructuredAdjustment = Optional[
    Union[
        SolarReductionAdjustment,
        MinimumBatteryReserveAdjustment,
        HoursOnlyAdjustment,
        MaxGridWindowAdjustment,
        dict[str, Any],
    ]
]


class DirectiveInterpretation(BaseModel):
    note_index: int = Field(ge=0)
    applies: bool
    directive_type: DirectiveType
    structured_adjustment: Optional[dict[str, Any]] = None
    explanation: str = ""


class HourlyPlanEntry(BaseModel):
    hour: int = Field(ge=0, le=23)
    grid_kwh: float = Field(ge=0)
    solar_used_kwh: float = Field(ge=0)
    battery_action: BatteryAction
    battery_kwh: float = Field(ge=0)
    battery_energy_after_kwh: float = Field(ge=0)


class OptimizeEnergyResponse(BaseModel):
    scenario_id: str
    directive_interpretation: list[DirectiveInterpretation]
    hourly_plan: list[HourlyPlanEntry]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
