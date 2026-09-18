"""Shared helpers for loading public sample cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
SAMPLES_PATH = ROOT / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"

TOLERANCE = 0.01


def load_samples() -> list[dict[str, Any]]:
    with SAMPLES_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


def interpretation_core(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare machine-checkable fields only (ignore explanation wording)."""
    out = []
    for e in sorted(entries, key=lambda x: x["note_index"]):
        out.append(
            {
                "note_index": e["note_index"],
                "applies": e["applies"],
                "directive_type": e["directive_type"],
                "structured_adjustment": e["structured_adjustment"],
            }
        )
    return out


def nearly_equal(a: float, b: float, tol: float = TOLERANCE) -> bool:
    return abs(float(a) - float(b)) <= tol
