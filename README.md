# GridWise — Campus Energy Optimization API

BUP CSE Fest 2026 Preliminary (GridWise LLM)

This service receives a 24-hour campus energy scenario plus 1–3 natural-language operator notes, converts the notes into structured directives, and returns a feasible low-cost hourly schedule.

| Item | Value |
| --- | --- |
| Live base URL | https://elec-bup.onrender.com |
| Health | `GET /health` → `{"status":"ok"}` |
| Optimize | `POST /optimize-energy` |
| Repository | https://github.com/nishadmahmud/ELEC_BUP |
| Model | OpenAI `gpt-4o-mini` (structured JSON) |
| Solver | PuLP + CBC |

---

## Problem in one paragraph

Campus load is met by grid purchases, rooftop solar, and a battery. Tariffs vary by hour. Operators send short notes such as “do not charge between 2–4 PM” or “solar drops to 20% from 1–3 PM.” Some notes are distractors. The API must interpret every note, apply only the supported directive types, keep the physical energy rules intact, and minimize total grid cost:

`total_cost_bdt = Σ grid_kwh[h] × tariff_bdt_per_kwh[h]` for `h = 0..23`

---

## System architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Request    │────▶│  OpenAI gpt-4o-  │────▶│  Guardrails  │
│  JSON       │     │  mini (structured│     │  + note hour │
│             │     │   JSON extract)  │     │  expansion   │
└─────────────┘     └──────────────────┘     └──────┬───────┘
                                                    │
                                                    ▼
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Response   │◀────│  Replay verifier │◀────│  PuLP / CBC  │
│  JSON       │     │  (balance, EOD,  │     │  LP minimize │
│             │     │   directives)    │     │  grid cost   │
└─────────────┘     └──────────────────┘     └──────────────┘
```

Module map:

| Path | Role |
| --- | --- |
| `app/main.py` | FastAPI routes, latency logging, controlled errors |
| `app/llm.py` | OpenAI call, same-model retry, in-process note cache |
| `app/prompts.py` | System prompt + strict JSON schema |
| `app/guardrails.py` | Type/hours/factor validation; half-open window repair |
| `app/optimizer.py` | LP model + infeasibility relaxation ladder |
| `app/replay.py` | Independent schedule check + aggregate totals |
| `app/pipeline.py` | End-to-end orchestration |

The language model is on the interpretation path. It is not used only for `plan_summary`.

---

## Energy model

Each hour the campus must satisfy:

```
grid_kwh + solar_used_kwh + battery_discharge
    = demand_kwh + battery_charge
```

```
          ┌──────── solar_kwh (after solar_reduction factor)
          │
demand ◀──┼── solar_used  (≤ effective solar; unused solar is curtailed)
          │
          ├── grid import (priced by tariff)
          │
          └── battery ◀── charge / discharge / idle
                 │
                 └── SOC after hour: within [min_reserve, capacity]
                     Final SOC (hour 23) = initial SOC  (neutrality)
```

Battery rules:

- Charge: `E_after = E_before + battery_kwh`
- Discharge: `E_after = E_before − battery_kwh`
- Idle: `battery_kwh = 0`
- Rate limits: charge/discharge magnitudes ≤ per-hour maxima
- `no_charge_window` / `no_discharge_window` force the corresponding flow to zero
- `minimum_battery_reserve` can raise the SOC floor on listed hours
- `max_grid_window` caps `grid_kwh` on listed hours

Time windows are half-open. Example: “1 PM to 3 PM” → hours `[13, 14]`.  
Solar `factor` is the **remaining usable fraction**. “80% reduction” → `factor = 0.2`.

---

## Supported directives

| `directive_type` | `structured_adjustment` | Effect |
| --- | --- | --- |
| `solar_reduction` | `{hours, factor}` | `effective_solar[h] = solar[h] × factor` |
| `minimum_battery_reserve` | `{hours, minimum_energy_kwh}` | Raise SOC floor on those hours |
| `no_charge_window` | `{hours}` | Charge amount = 0 |
| `no_discharge_window` | `{hours}` | Discharge amount = 0 |
| `max_grid_window` | `{hours, max_grid_kwh}` | Cap grid import |
| `no_op` | `null` | Ignore note (`applies` must be `false`) |

One interpretation entry per note, in `note_index` order `0..N-1`.

---

## API contract

### `GET /health`

```json
{"status": "ok"}
```

### `POST /optimize-energy`

Request fields: `scenario_id`, `operator_notes` (1–3 strings), `hours` (exactly 24), `battery`.

Response fields: `scenario_id`, `directive_interpretation`, `hourly_plan` (24), `total_grid_kwh`, `total_cost_bdt`, `peak_grid_kwh`, `plan_summary`.

HTTP codes: `200` success, `400` malformed/invalid request, `500` controlled internal failure (no stack traces, no secrets).

---

## Local quickstart (fresh machine)

### Prerequisites

- Python 3.11 or newer
- OpenAI API key
- Optional: Docker Desktop (engine must be running) for container runs

### Install

```bash
git clone https://github.com/nishadmahmud/ELEC_BUP.git
cd ELEC_BUP

python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Create `.env` from the example (do not commit `.env`):

```bash
# macOS / Linux
cp .env.example .env

# Windows
# copy .env.example .env
```

Set at least:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
PORT=8000
```

### Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Health check

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

### Public sample validation

Physics-only (no LLM; injects sample expected directives):

```bash
python scripts/run_samples.py --optimizer-only
```

Expected last line: `Done. failed=0/10`

Full pipeline against a running server:

```bash
# terminal 1
uvicorn app.main:app --host 0.0.0.0 --port 8000

# terminal 2
python scripts/run_samples.py --base-url http://127.0.0.1:8000
```

Against the deployed service:

```bash
python scripts/run_samples.py --base-url https://elec-bup.onrender.com
```

Expected: each case prints `PASS`, interpretation fields match the public sample, `total_cost_bdt` within **0.01**, and `failed=0/10`.

### Automated tests

```bash
python -m pytest tests/test_guardrails.py tests/test_samples.py tests/test_extra_cases.py tests/test_failures.py -q
```

Optional paraphrase suite (calls OpenAI, uses credits):

```bash
python -m pytest tests/test_paraphrase.py -q
```

---

## Example request / response (live)

Public case **SAMPLE-01** from `BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json`, posted to the deployed API:

`POST https://elec-bup.onrender.com/optimize-energy`

The JSON below is the real request body and the real HTTP 200 response (captured from that URL). Equivalent schedules may differ hour-by-hour; cost must stay within 0.01 of the public sample (`38365.0`).

### Request

```json
{
  "scenario_id": "SAMPLE-01",
  "operator_notes": [
    "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
    "The sports office moved next month's registration deadline."
  ],
  "hours": [
    {"hour": 0, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 1, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 2, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
    {"hour": 3, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
    {"hour": 4, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
    {"hour": 5, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 6, "demand_kwh": 110, "solar_kwh": 5, "tariff_bdt_per_kwh": 8},
    {"hour": 7, "demand_kwh": 130, "solar_kwh": 20, "tariff_bdt_per_kwh": 10},
    {"hour": 8, "demand_kwh": 150, "solar_kwh": 50, "tariff_bdt_per_kwh": 12},
    {"hour": 9, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14},
    {"hour": 10, "demand_kwh": 175, "solar_kwh": 130, "tariff_bdt_per_kwh": 16},
    {"hour": 11, "demand_kwh": 180, "solar_kwh": 160, "tariff_bdt_per_kwh": 16},
    {"hour": 12, "demand_kwh": 185, "solar_kwh": 180, "tariff_bdt_per_kwh": 15},
    {"hour": 13, "demand_kwh": 180, "solar_kwh": 170, "tariff_bdt_per_kwh": 14},
    {"hour": 14, "demand_kwh": 170, "solar_kwh": 140, "tariff_bdt_per_kwh": 13},
    {"hour": 15, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14},
    {"hour": 16, "demand_kwh": 170, "solar_kwh": 45, "tariff_bdt_per_kwh": 18},
    {"hour": 17, "demand_kwh": 185, "solar_kwh": 10, "tariff_bdt_per_kwh": 22},
    {"hour": 18, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 28},
    {"hour": 19, "demand_kwh": 215, "solar_kwh": 0, "tariff_bdt_per_kwh": 30},
    {"hour": 20, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 26},
    {"hour": 21, "demand_kwh": 175, "solar_kwh": 0, "tariff_bdt_per_kwh": 18},
    {"hour": 22, "demand_kwh": 135, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
    {"hour": 23, "demand_kwh": 105, "solar_kwh": 0, "tariff_bdt_per_kwh": 7}
  ],
  "battery": {
    "capacity_kwh": 220,
    "initial_energy_kwh": 110,
    "minimum_energy_kwh": 40,
    "max_charge_kwh_per_hour": 50,
    "max_discharge_kwh_per_hour": 50
  }
}
```

### Response (actual)

```json
{
  "scenario_id": "SAMPLE-01",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "solar_reduction",
      "structured_adjustment": {
        "hours": [12, 13],
        "factor": 0.25
      },
      "explanation": "Solar output will drop to about 25% during panel washing."
    },
    {
      "note_index": 1,
      "applies": false,
      "directive_type": "no_op",
      "structured_adjustment": null,
      "explanation": "The note is about a registration deadline and does not affect energy scheduling."
    }
  ],
  "hourly_plan": [
    {"hour": 0, "grid_kwh": 50.0, "solar_used_kwh": 0.0, "battery_action": "discharge", "battery_kwh": 40.0, "battery_energy_after_kwh": 70.0},
    {"hour": 1, "grid_kwh": 85.0, "solar_used_kwh": 0.0, "battery_action": "idle", "battery_kwh": 0.0, "battery_energy_after_kwh": 70.0},
    {"hour": 2, "grid_kwh": 130.0, "solar_used_kwh": 0.0, "battery_action": "charge", "battery_kwh": 50.0, "battery_energy_after_kwh": 120.0},
    {"hour": 3, "grid_kwh": 130.0, "solar_used_kwh": 0.0, "battery_action": "charge", "battery_kwh": 50.0, "battery_energy_after_kwh": 170.0},
    {"hour": 4, "grid_kwh": 135.0, "solar_used_kwh": 0.0, "battery_action": "charge", "battery_kwh": 50.0, "battery_energy_after_kwh": 220.0},
    {"hour": 5, "grid_kwh": 95.0, "solar_used_kwh": 0.0, "battery_action": "idle", "battery_kwh": 0.0, "battery_energy_after_kwh": 220.0},
    {"hour": 6, "grid_kwh": 105.0, "solar_used_kwh": 5.0, "battery_action": "idle", "battery_kwh": 0.0, "battery_energy_after_kwh": 220.0},
    {"hour": 7, "grid_kwh": 110.0, "solar_used_kwh": 20.0, "battery_action": "idle", "battery_kwh": 0.0, "battery_energy_after_kwh": 220.0},
    {"hour": 8, "grid_kwh": 100.0, "solar_used_kwh": 50.0, "battery_action": "idle", "battery_kwh": 0.0, "battery_energy_after_kwh": 220.0},
    {"hour": 9, "grid_kwh": 75.0, "solar_used_kwh": 90.0, "battery_action": "idle", "battery_kwh": 0.0, "battery_energy_after_kwh": 220.0},
    {"hour": 10, "grid_kwh": 0.0, "solar_used_kwh": 130.0, "battery_action": "discharge", "battery_kwh": 45.0, "battery_energy_after_kwh": 175.0},
    {"hour": 11, "grid_kwh": 0.0, "solar_used_kwh": 160.0, "battery_action": "discharge", "battery_kwh": 20.0, "battery_energy_after_kwh": 155.0},
    {"hour": 12, "grid_kwh": 90.0, "solar_used_kwh": 45.0, "battery_action": "discharge", "battery_kwh": 50.0, "battery_energy_after_kwh": 105.0},
    {"hour": 13, "grid_kwh": 152.5, "solar_used_kwh": 42.5, "battery_action": "charge", "battery_kwh": 15.0, "battery_energy_after_kwh": 120.0},
    {"hour": 14, "grid_kwh": 80.0, "solar_used_kwh": 140.0, "battery_action": "charge", "battery_kwh": 50.0, "battery_energy_after_kwh": 170.0},
    {"hour": 15, "grid_kwh": 125.0, "solar_used_kwh": 90.0, "battery_action": "charge", "battery_kwh": 50.0, "battery_energy_after_kwh": 220.0},
    {"hour": 16, "grid_kwh": 125.0, "solar_used_kwh": 45.0, "battery_action": "idle", "battery_kwh": 0.0, "battery_energy_after_kwh": 220.0},
    {"hour": 17, "grid_kwh": 145.0, "solar_used_kwh": 10.0, "battery_action": "discharge", "battery_kwh": 30.0, "battery_energy_after_kwh": 190.0},
    {"hour": 18, "grid_kwh": 155.0, "solar_used_kwh": 0.0, "battery_action": "discharge", "battery_kwh": 50.0, "battery_energy_after_kwh": 140.0},
    {"hour": 19, "grid_kwh": 165.0, "solar_used_kwh": 0.0, "battery_action": "discharge", "battery_kwh": 50.0, "battery_energy_after_kwh": 90.0},
    {"hour": 20, "grid_kwh": 155.0, "solar_used_kwh": 0.0, "battery_action": "discharge", "battery_kwh": 50.0, "battery_energy_after_kwh": 40.0},
    {"hour": 21, "grid_kwh": 175.0, "solar_used_kwh": 0.0, "battery_action": "idle", "battery_kwh": 0.0, "battery_energy_after_kwh": 40.0},
    {"hour": 22, "grid_kwh": 155.0, "solar_used_kwh": 0.0, "battery_action": "charge", "battery_kwh": 20.0, "battery_energy_after_kwh": 60.0},
    {"hour": 23, "grid_kwh": 155.0, "solar_used_kwh": 0.0, "battery_action": "charge", "battery_kwh": 50.0, "battery_energy_after_kwh": 110.0}
  ],
  "total_grid_kwh": 2692.5,
  "total_cost_bdt": 38365.0,
  "peak_grid_kwh": 175.0,
  "plan_summary": "Applied directives [solar_reduction]; minimized grid cost to 38365.00 BDT with peak grid 175.00 kWh while respecting battery neutrality and energy balance."
}
```

Replay this yourself:

```bash
python scripts/run_samples.py --base-url https://elec-bup.onrender.com
```

Or POST the SAMPLE-01 body with curl / any HTTP client to `/optimize-energy`. All ten public samples should print `PASS` with `failed=0/10`.

## Environment variables

| Name | Required | Default | Purpose |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes for live interpretation | — | OpenAI credential |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Primary chat model |
| `OPENAI_BACKUP_MODEL` | No | same as primary | Optional alternate model; by default we retry the primary |
| `PORT` | No | `8000` | HTTP listen port |

Secrets stay in environment variables or `.env`. They are never committed and never baked into images.

---

## Docker (local build & run)

Docker Hub publishing is not required to evaluate the service. If Docker Desktop’s engine is running on your machine, build from this repository:

```bash
docker build -t elec-bup:local .
```

Run (pass the API key at runtime):

```bash
# macOS / Linux
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e OPENAI_MODEL=gpt-4o-mini \
  elec-bup:local
```

```powershell
# Windows PowerShell
docker run --rm -p 8000:8000 `
  -e OPENAI_API_KEY=$env:OPENAI_API_KEY `
  -e OPENAI_MODEL=gpt-4o-mini `
  elec-bup:local
```

Then:

```bash
curl http://127.0.0.1:8000/health
python scripts/run_samples.py --base-url http://127.0.0.1:8000
```

Notes:

- The container binds `0.0.0.0` and reads `PORT` (default 8000).
- No credentials are stored in the image layers.
- If Docker Desktop shows “Engine stopped” or “Virtualization support not detected,” enable virtualization / WSL2 first; the Python uvicorn path above does not need Docker.

Optional Hub publish (when the engine works and you are logged in):

```bash
docker tag elec-bup:local nishadmahmud/elec_bup:v1
docker login
docker push nishadmahmud/elec_bup:v1
```

Helper script: `scripts/docker_publish.ps1`.

---

## Deployment

- Hosted on Render as a Docker web service.
- Public base URL: `https://elec-bup.onrender.com`
- Set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`) in the Render dashboard.
- Free-tier instances sleep when idle. During judging, ping `/health` every ~10 minutes (see `KEEP_ALIVE.md`).
- Target: respond within 30 seconds per request; with `gpt-4o-mini` typical public samples complete in a few seconds when warm.

---

## Design choices

**Interpretation.** OpenAI structured outputs produce one directive object per note. Temperature is 0. The same primary model is retried once on transient failures. Identical note/battery contexts are cached in-process to reduce repeat latency.

**Guardrails.** LLM output is untrusted until validation. Unsupported types are rejected. `applies` is aligned with `directive_type`. Hours are unique integers `0..23`. When the note text states a clear clock window (“between 11 AM and 2 PM”), hours are expanded half-open in code so off-by-one lists from the model do not leak into the optimizer.

**Optimization.** Continuous LP (with charge/discharge mutual exclusion binaries) minimizes grid cost subject to balance, solar availability, battery dynamics, rate limits, directive caps, and end-of-day neutrality. If the model becomes infeasible under extracted caps, the solver retries with a short relaxation ladder (drop grid caps, then raised reserves) and still runs replay on the params that solved.

**Replay.** Before returning HTTP 200, the schedule is checked hour-by-hour. Totals and peak are recomputed from `hourly_plan`. Equivalent optimal schedules may differ hour-by-hour; scoring uses validity, directive application, and cost within 0.01.

---

## Dependencies

| Package | Use |
| --- | --- |
| FastAPI, Uvicorn, Pydantic | HTTP API and schemas |
| openai | Operator-note interpretation |
| PuLP (CBC) | Linear program |
| python-dotenv | Local `.env` loading |
| httpx, pytest | Sample harness and tests |

---

## Limitations

- Judging depends on OpenAI availability and quota for the deployed key.
- Organizer scoring scenarios are assumed feasible under ground-truth directives. Mutually impossible hard constraints are not invented away.
- `plan_summary` is a short generated sentence and is not scored for wording.
- Docker Hub may be unavailable from some machines if the local Docker engine cannot start; use the Render URL or local `docker build` / `uvicorn` instead.

---

## Security

- `.env` is gitignored.
- Error responses do not include stack traces or secret values.
- Runtime configuration uses environment variables only.

---

## Project layout

```
ELEC_BUP/
  app/                 # API + LLM + guardrails + optimizer + replay
  tests/               # Guardrail, sample, failure, paraphrase tests
  scripts/             # Sample runner, Docker helper, env helpers
  Dockerfile
  requirements.txt
  .env.example
  BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json
  README.md
```

---

## Tie-break video

Recording outline: `VIDEO_SCRIPT.md` (max 3 minutes). Demo against `https://elec-bup.onrender.com`.
