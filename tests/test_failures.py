"""API failure / contract tests (no LLM required for most)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_malformed_json_returns_400() -> None:
    r = client.post(
        "/optimize-energy",
        content="{not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


def test_missing_fields_returns_400() -> None:
    r = client.post("/optimize-energy", json={"scenario_id": "x"})
    assert r.status_code == 400


def test_wrong_hour_count_returns_400() -> None:
    payload = {
        "scenario_id": "BAD",
        "operator_notes": ["The cafeteria menu changes tomorrow."],
        "hours": [
            {"hour": 0, "demand_kwh": 1, "solar_kwh": 0, "tariff_bdt_per_kwh": 1}
        ],
        "battery": {
            "capacity_kwh": 100,
            "initial_energy_kwh": 50,
            "minimum_energy_kwh": 10,
            "max_charge_kwh_per_hour": 20,
            "max_discharge_kwh_per_hour": 20,
        },
    }
    r = client.post("/optimize-energy", json=payload)
    assert r.status_code == 400
