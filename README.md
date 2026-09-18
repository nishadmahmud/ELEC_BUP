# GridWise LLM Energy Optimizer

BUP CSE Fest 2026 Preliminary — LLM-assisted campus energy scheduling API.

**Live API base URL:** `https://elec-bup.onrender.com`  
**GitHub:** https://github.com/nishadmahmud/ELEC_BUP  
**Docker fallback:** `nishadmahmud/elec_bup:v1`

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
git clone https://github.com/nishadmahmud/ELEC_BUP.git
cd ELEC_BUP
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # macOS/Linux
# copy .env.example .env      # Windows
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

Expected: `Done. failed=0/10`

Full pipeline against local or live API (requires `OPENAI_API_KEY`):

```bash
# local
uvicorn app.main:app --host 0.0.0.0 --port 8000
python scripts/run_samples.py --base-url http://127.0.0.1:8000

# deployed
python scripts/run_samples.py --base-url https://elec-bup.onrender.com
```

Expected: every sample `PASS`, interpretation fields match, `total_cost_bdt` within **0.01** of the public sample cost, script ends with `failed=0/10`.

Minimal curl (Windows PowerShell):

```powershell
curl.exe -X POST http://127.0.0.1:8000/optimize-energy `
  -H "Content-Type: application/json" `
  -d "@BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
```

Prefer `scripts/run_samples.py` (it posts each case `input` correctly).

Minimal single-note example body:

```json
{
  "scenario_id": "DEMO-1",
  "operator_notes": [
    "Do not charge the battery between 2 PM and 4 PM.",
    "The cafeteria menu changes tomorrow."
  ],
  "hours": [],
  "battery": {
    "capacity_kwh": 500,
    "initial_energy_kwh": 200,
    "minimum_energy_kwh": 50,
    "max_charge_kwh_per_hour": 100,
    "max_discharge_kwh_per_hour": 100
  }
}
```

Use a full 24-hour `hours` array from `BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json` (empty `hours` is invalid). Example success shape:

```json
{
  "scenario_id": "DEMO-1",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "no_charge_window",
      "structured_adjustment": {"hours": [14, 15]},
      "explanation": "..."
    },
    {
      "note_index": 1,
      "applies": false,
      "directive_type": "no_op",
      "structured_adjustment": null,
      "explanation": "..."
    }
  ],
  "hourly_plan": [],
  "total_grid_kwh": 0,
  "total_cost_bdt": 0,
  "peak_grid_kwh": 0,
  "plan_summary": "..."
}
```

### 6. Unit tests

```bash
python -m pytest tests/test_guardrails.py tests/test_samples.py tests/test_extra_cases.py tests/test_failures.py -q
```

LLM paraphrase tests (uses API credits):

```bash
python -m pytest tests/test_paraphrase.py -q
```

## Environment variables

| Name | Required | Default | Meaning |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes (for live interpretation) | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Primary chat model |
| `OPENAI_BACKUP_MODEL` | No | same as primary | Optional different fallback; default retries the same model |
| `PORT` | No | `8000` | HTTP listen port |

Never commit secrets. Never bake keys into the Docker image.

## Docker fallback (published image)

```bash
docker pull nishadmahmud/elec_bup:v1
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e OPENAI_MODEL=gpt-4o-mini \
  nishadmahmud/elec_bup:v1
```

Windows PowerShell:

```powershell
docker pull nishadmahmud/elec_bup:v1
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=$env:OPENAI_API_KEY -e OPENAI_MODEL=gpt-4o-mini nishadmahmud/elec_bup:v1
curl.exe http://127.0.0.1:8000/health
```

Expected health: `{"status":"ok"}`

Rebuild/push (maintainers):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\docker_publish.ps1
```

## Deployment notes

- **Live API base URL:** `https://elec-bup.onrender.com`
- **Primary host:** Render free Web Service (Docker). See [`DEPLOY.md`](DEPLOY.md).
- Bind `0.0.0.0` (Dockerfile / uvicorn).
- Set `OPENAI_API_KEY` in the Render dashboard (never bake into the image).
- Keep-alive during judging: GET `https://elec-bup.onrender.com/health` every 10 minutes (see [`KEEP_ALIVE.md`](KEEP_ALIVE.md)).
- Per-request budget: complete within 30 seconds (target p95 ≤ 5s with `gpt-4o-mini`).

## LLM role, guardrails, optimizer

- **LLM:** Interprets 1–3 `operator_notes` into `directive_interpretation` (structured JSON). On the critical path — not only for `plan_summary`.
- **Guardrails:** Whitelist directive types; coerce `applies` from type; unique ascending hours 0–23; solar `factor` in [0,1]; reserve ≤ capacity; reject invented types.
- **Optimizer:** PuLP + CBC LP. Objective `min Σ grid_kwh[h] * tariff[h]`. Energy balance, effective solar, battery dynamics/bounds/rates, directive windows/caps, end-of-day neutrality.
- **Replay:** Re-checks `hourly_plan` and recomputes totals.

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

- Requires OpenAI API availability/quota during judging.
- Organizer scoring scenarios are assumed feasible; contradictory hard directives return a controlled 500 rather than inventing constraints.
- Equivalent optimal schedules may differ from public sample `hourly_plan` byte-for-byte; scoring uses validity, directive application, and recalculated cost (tolerance 0.01).
- `plan_summary` is a short template string and is not judged for wording.

## Secret handling

- Do not commit `.env`, keys, or tokens.
- API error responses never include stack traces or secret values.
- Docker image contains no baked-in credentials — inject `OPENAI_API_KEY` at runtime only.

## Video (tie-break)

See [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) for a ≤3-minute recording outline against the live URL.
