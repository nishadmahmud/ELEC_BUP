#!/usr/bin/env python3
"""Run all public sample cases against a live API or local pipeline.

Usage:
  # Local pipeline with LLM (needs OPENAI_API_KEY):
  python scripts/run_samples.py

  # Against a deployed/base URL:
  python scripts/run_samples.py --base-url http://127.0.0.1:8000

  # Skip LLM: use expected interpretations to validate optimizer only:
  python scripts/run_samples.py --optimizer-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

SAMPLES = ROOT / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
TOL = 0.01


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--optimizer-only", action="store_true")
    args = parser.parse_args()

    cases = json.loads(SAMPLES.read_text(encoding="utf-8"))["cases"]
    failed = 0

    if args.base_url:
        import httpx

        health = httpx.get(f"{args.base_url.rstrip('/')}/health", timeout=30)
        print("HEALTH", health.status_code, health.text)
        if health.status_code != 200:
            return 1

    for case in cases:
        cid = case["id"]
        expected = case["expected_output"]
        t0 = time.perf_counter()
        try:
            if args.optimizer_only:
                from app.pipeline import run_optimize_with_directives
                from app.schemas import OptimizeEnergyRequest

                req = OptimizeEnergyRequest.model_validate(case["input"])
                result = run_optimize_with_directives(
                    req, expected["directive_interpretation"]
                )
                body = result.model_dump()
            elif args.base_url:
                import httpx

                r = httpx.post(
                    f"{args.base_url.rstrip('/')}/optimize-energy",
                    json=case["input"],
                    timeout=60,
                )
                r.raise_for_status()
                body = r.json()
            else:
                from app.pipeline import run_optimize_energy
                from app.schemas import OptimizeEnergyRequest

                req = OptimizeEnergyRequest.model_validate(case["input"])
                body = run_optimize_energy(req).model_dump()

            elapsed = time.perf_counter() - t0
            ok_interp = _interp_ok(
                body["directive_interpretation"],
                expected["directive_interpretation"],
            )
            ok_cost = abs(body["total_cost_bdt"] - expected["total_cost_bdt"]) <= TOL
            status = "PASS" if ok_interp and ok_cost else "FAIL"
            if status == "FAIL":
                failed += 1
            print(
                f"{status} {cid} cost={body['total_cost_bdt']} "
                f"expected={expected['total_cost_bdt']} "
                f"interp={'ok' if ok_interp else 'BAD'} {elapsed:.2f}s"
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {cid} ERROR {exc}")

    print(f"\nDone. failed={failed}/{len(cases)}")
    return 1 if failed else 0


def _interp_ok(got, expected) -> bool:
    def core(entries):
        return [
            {
                "note_index": e["note_index"],
                "applies": e["applies"],
                "directive_type": e["directive_type"],
                "structured_adjustment": e["structured_adjustment"],
            }
            for e in sorted(entries, key=lambda x: x["note_index"])
        ]

    return core(got) == core(expected)


if __name__ == "__main__":
    raise SystemExit(main())
