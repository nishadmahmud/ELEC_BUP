"""GridWise LLM Energy Optimization API."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.pipeline import PipelineError, run_optimize_energy
from app.schemas import HealthResponse, OptimizeEnergyRequest, OptimizeEnergyResponse

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(
    title="GridWise LLM Energy Optimizer",
    version="1.0.0",
    description="BUP CSE Fest 2026 — LLM-assisted campus energy optimization",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/optimize-energy", response_model=OptimizeEnergyResponse)
def optimize_energy(body: OptimizeEnergyRequest) -> OptimizeEnergyResponse:
    return run_optimize_energy(body)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "detail": "malformed_or_invalid_request",
            "errors": _json_safe_errors(exc.errors()),
        },
    )


def _json_safe_errors(errors: list) -> list:
    """RequestValidationError.ctx may contain non-JSON-serializable exceptions."""
    safe: list = []
    for err in errors:
        item = dict(err)
        ctx = item.get("ctx")
        if isinstance(ctx, dict):
            item["ctx"] = {
                k: (str(v) if isinstance(v, BaseException) else v)
                for k, v in ctx.items()
            }
        safe.append(item)
    return safe


@app.exception_handler(PipelineError)
async def pipeline_exception_handler(
    request: Request, exc: PipelineError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never expose stack traces or secrets
    return JSONResponse(
        status_code=500,
        content={"detail": "internal_error"},
    )


def create_app() -> FastAPI:
    return app


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
