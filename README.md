# GridWise LLM Energy Optimizer

BUP CSE Fest 2026 Preliminary — LLM-assisted campus energy scheduling API.

Interprets natural-language operator notes with OpenAI, validates them with deterministic guardrails, then solves a 24-hour battery/solar/grid LP (PuLP + CBC) that minimizes grid electricity cost while obeying GridWise energy rules and every applicable directive.

## Architecture

```
operator_notes
    -> OpenAI gpt-4o-mini (structured JSON interpretation)   [mandatory LLM step]
    -> deterministic guardrails (type/hours/factor/applies)
    -> directive application (effective solar, reserves, windows, grid caps)
    -> PuLP/CBC optimizer (min sum grid_kwh * tariff)
    -> replay verifier (balance, battery, directives, EOD neutrality)
    -> JSON response
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Readiness: `{"status":"ok"}` |
| `POST` | `/optimize-energy` | Interpret notes + return 24h plan |

## Local quickstart (clean environment)

### 1. Prerequisites

- Python 3.11+ (3.12/3.13 also work)
- An OpenAI API key
- (Optional) Docker for the fallback image path

### 2. Clone and configure

```bash
git clone <YOUR_REPO_URL>
cd BUP_HACKATHON
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Edit `.env` (do **not** commit this file):

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
PORT=8000
```

### 3. Start the service

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Health check

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

### 5. Public sample test

Optimizer-only (no LLM, uses sample expected directives — validates physics):

```bash
python scripts/run_samples.py --optimizer-only
```

Full pipeline against local API (requires `OPENAI_API_KEY`):

```bash
# terminal 1
uvicorn app.main:app --host 0.0.0.0 --port 8000

# terminal 2
python scripts/run_samples.py --base-url http://127.0.0.1:8000
```

Or call one sample with curl (replace body with a case from `BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json`):

```bash
curl -X POST http://127.0.0.1:8000/optimize-energy ^
  -H "Content-Type: application/json" ^
  -d "@sample_request.json"
```

### 6. Unit tests

```bash
python -m pytest tests/test_guardrails.py tests/test_samples.py tests/test_extra_cases.py tests/test_failures.py -q
```

LLM paraphrase tests (optional, uses API credits):

```bash
python -m pytest tests/test_paraphrase.py -q
```

## Environment variables

| Name | Required | Default | Meaning |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes (for live interpretation) | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Primary chat model |
| `OPENAI_BACKUP_MODEL` | No | `gpt-4o` | Fallback after retries |
| `PORT` | No | `8000` | HTTP listen port |

Never commit secrets. Never bake keys into the Docker image.

## Docker fallback

Build:

```bash
docker build -t gridwise-llm:latest .
```

Run (pass the key at runtime):

```bash
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=sk-... -e OPENAI_MODEL=gpt-4o-mini gridwise-llm:latest
```

Then:

```bash
curl http://127.0.0.1:8000/health
python scripts/run_samples.py --base-url http://127.0.0.1:8000
```

Published image reference (fill after push):

```
docker pull <REGISTRY>/<IMAGE>:<TAG>
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=$OPENAI_API_KEY <REGISTRY>/<IMAGE>:<TAG>
```

## Deployment notes

- **Live API base URL:** `https://elec-bup.onrender.com`
- **Primary host: Render free Web Service** (Docker). See [`DEPLOY.md`](DEPLOY.md).
- Bind `0.0.0.0` (already in Dockerfile / uvicorn command).
- Set `OPENAI_API_KEY` in the Render dashboard env (never bake into the image).
- Public base URL must expose `/health` and `/optimize-energy` without login/VPN.
- Per-request budget: complete within 30 seconds (target p95 ≤ 5s with `gpt-4o-mini`).
- Render free spins down when idle — ping `https://elec-bup.onrender.com/health` every ~10 minutes during judging (e.g. cron-job.org).
- Docker fallback commands: [`scripts/docker_publish.ps1`](scripts/docker_publish.ps1) (requires Docker Desktop).

## LLM role, guardrails, optimizer

- **LLM:** Interprets 1–3 `operator_notes` into `directive_interpretation` (structured JSON). This is on the critical path — not used only for `plan_summary`.
- **Guardrails:** Whitelist directive types; enforce `applies` / `no_op` semantics; unique ascending hours 0–23; solar `factor` in [0,1]; reserve ≤ capacity; reject invented types.
- **Optimizer:** Linear program via PuLP + CBC. Objective `min Σ grid_kwh[h] * tariff[h]`. Constraints: energy balance, effective solar, battery dynamics/bounds/rates, directive windows/caps, end-of-day battery neutrality (`E_final = E_initial`).
- **Replay:** Independently re-checks the returned `hourly_plan` and recomputes totals.

## Supported directives

| Type | Adjustment |
| --- | --- |
| `solar_reduction` | `{hours, factor}` — factor = remaining usable fraction |
| `minimum_battery_reserve` | `{hours, minimum_energy_kwh}` |
| `no_charge_window` | `{hours}` |
| `no_discharge_window` | `{hours}` |
| `max_grid_window` | `{hours, max_grid_kwh}` |
| `no_op` | `null` with `applies=false` |

Time windows are half-open: start inclusive, end exclusive (`1 PM to 3 PM` → `[13,14]`).

## Dependencies / credits

- FastAPI, Uvicorn, Pydantic — HTTP API
- OpenAI Python SDK — operator-note interpretation
- PuLP (+ bundled CBC) — energy LP
- httpx, pytest — testing harness

AI coding assistants may have been used during development; core architecture and logic are team-owned for the hackathon submission.

## Known limitations

- Requires OpenAI API availability/quota during judging; configure a valid key and monitor rate limits.
- Organizer scoring scenarios are assumed feasible; contradictory hard directives return a controlled 500 rather than inventing constraints.
- Equivalent optimal schedules may differ from public sample `hourly_plan` byte-for-byte; scoring uses validity, directive application, and recalculated cost (tolerance 0.01).
- `plan_summary` is a short template string and is not judged for wording.

## Secret handling

- Do not commit `.env`, keys, or tokens.
- API error responses never include stack traces or secret values.
- Docker image contains no baked-in credentials — inject `OPENAI_API_KEY` at runtime only.
