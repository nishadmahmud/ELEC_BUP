# GridWise

GridWise is a FastAPI service for the BUP CSE Fest 2026 online preliminary. It uses a language-capable model to convert every operator note into a typed directive, validates the result deterministically, applies the constraints to a SciPy/HiGHS mixed-integer program, independently replays the returned schedule, and only then serializes the response.

## Architecture

`request -> LLM structured output -> Pydantic guardrails -> effective constraints -> SciPy MILP -> independent replay -> exact response`

The service exposes only `GET /health` and `POST /optimize-energy`. The judged request path is bounded: one structured model call (with the provider SDK's configured retry), one MILP solve, one replay. The LLM directly produces the `directive_interpretation` consumed by the optimizer; it is not used merely for prose.

The MILP has continuous grid, solar, charge, discharge, and battery-state variables plus one binary charge/discharge mode variable per hour. It minimizes `sum(grid[h] * tariff[h])` subject to hourly balance, battery transitions and bounds, rate limits, charge/discharge exclusivity, solar availability, no export, all validated directives, and final energy equal to initial energy. No efficiency loss, degradation cost, export revenue, or peak objective is added.

## Clean local quickstart

Python 3.11+ is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
copy .env.example .env  # Windows; use cp on Linux/macOS
```

The verified provider configuration is OpenRouter at `https://openrouter.ai/api/v1` with `openai/gpt-4.1-mini`, selected for structured-output support, correctness, and measured latency. Put the rotated key in the ignored `.env` copied above; the service loads that file from its working directory without overriding process variables. Never put a real key in `.env.example` or commit `.env`.

```bash
uvicorn gridwise.service:app --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/health
python -m gridwise.sample_runner --base-url http://127.0.0.1:8000
pytest
python -m scripts.benchmark_optimizer --rounds 10
```

`requirements-lock.txt` records the complete dependency set used for the reported verification run; the shorter requirements files pin every direct runtime and test dependency.

The sample runner sends only each case's `input` to production. Expected outputs remain in the test/runner process and are never passed to the interpreter or optimizer.

## API examples

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/optimize-energy \
  -H "Content-Type: application/json" \
  --data-binary @sample-request.json
```

`GET /health` returns `{"status":"ok"}` without making a billable model call when an interpreter/provider is configured; otherwise it returns 503 with `{"status":"not_ready"}`. `POST /optimize-energy` requires the exact schema in the problem statement. Malformed or structurally invalid JSON returns 400. Model, solver, replay, and deadline failures return a controlled 500 without a raw stack trace or secret.

## Configuration

| Variable | Required | Purpose |
|---|---:|---|
| `OPENAI_API_KEY` | yes | Provider credential |
| `OPENAI_MODEL` | yes | Exact deployed model identifier with structured-output support |
| `OPENAI_BASE_URL` | no | OpenAI-compatible provider base URL |
| `LLM_TIMEOUT_SECONDS` | no | Per-model-call timeout; default 8 |
| `LLM_MAX_RETRIES` | no | SDK retries; default 1 |
| `LLM_MAX_OUTPUT_TOKENS` | no | Compact structured-response ceiling; default 1024 |
| `REQUEST_TIMEOUT_SECONDS` | no | Whole application deadline; default 28 |
| `PORT` | no | Container listen port; default 8000 |

## Guardrails and failure behavior

Pydantic discriminated unions enforce exact adjustment shapes and reject extra fields. Deterministic checks enforce note coverage/order, applies semantics, unique sorted 0-23 hours, finite numeric values, factors in `[0,1]`, reserves within capacity, and nonnegative grid caps. Invalid model output is never converted to `no_op` or clamped. Operator notes are explicitly treated as untrusted content in the model prompt.

The replay module is separate from the optimizer construction. It recalculates effective constraints and validates coverage, finite/nonnegative flows, solar limits, balance, transitions, state/rate bounds, action consistency, every directive, final neutrality, and totals.

## Tests

`pytest` runs contract validation, a mocked full HTTP pipeline for all ten official samples, official-directive optimizer regression tests against all reference costs, deliberate replay corruption, and deterministic optimizer timing. Live interpreter/paraphrase and real end-to-end tests are opt-in and clearly marked:

```bash
RUN_LIVE_LLM=1 pytest -m live_llm
```

The full ten-case live run uses the sample runner against the running service; live tests are intentionally not disguised as unit tests.

## Docker

Build and run locally:

```bash
docker build -t gridwise:1.0.0 .
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY \
  -e OPENAI_MODEL \
  gridwise:1.0.0
curl http://127.0.0.1:8000/health
```

For submission, push this exact tested image to Docker Hub, GHCR, or an equivalent registry, then replace the placeholder in `SUBMISSION_CHECKLIST.md` with an exact public tag or digest and verify the documented pull/run command from a clean host. No registry reference is claimed until that has happened.

## Deployment

Deploy the same container as one public service, inject secrets at runtime, bind `0.0.0.0:$PORT`, and expose the base URL without authentication, VPN, or manual approval. Configure health checks for `/health`. Test both endpoints from outside the platform network and keep provider quota available for repeated calls. Do not publish the repository before the competition rule permits it.

## Four-person ownership and handoff

These are review/ownership areas, not claims about completed human contributions:

1. Backend/API: `service.py`, `schemas.py`, configuration, error/status behavior, integration.
2. LLM/guardrails: `llm.py`, prompt-injection boundary, typed extraction, live paraphrase evaluation.
3. Optimization: `effective.py`, `optimizer.py`, `replay.py`, mathematical review and official costs.
4. QA/deployment: tests, sample runner, Docker, external checks, documentation and submission artifacts.

Each owner should review the shared Pydantic contracts before changing an interface. Optimization changes must pass official-directive tests and replay; LLM changes must pass live samples and paraphrase cases; API changes must preserve exact response fields.

## Known limitations and unresolved specification questions

- The supplied specification does not define overlapping `solar_reduction` semantics. This implementation treats each directive as an upper bound and uses the strongest restriction (lowest remaining factor). The policy is isolated in `build_effective_constraints`.
- Live-model evidence covers the six synthetic paraphrase checks and all ten public samples, not hidden-test correctness or long-duration production reliability.
- A model/provider outage is a controlled 500, not a fabricated successful schedule. There is no rule-based fallback because hard-coded interpretation would violate the mandatory LLM path.
- The official rulebook was not supplied and is not claimed as reviewed.

## Dependencies and credits

Python, FastAPI, Uvicorn, Pydantic, OpenAI's Python SDK (also usable with compatible endpoints), NumPy, SciPy `optimize.milp` with HiGHS, HTTPX, and pytest are credited. AI assistance was used to implement this submission; the four human team members remain responsible for reviewing the architecture, mathematics, tests, and final submission.
