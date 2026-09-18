# GridWise — Smart Campus Energy Optimization Engine

> **BUP CSE Fest 2026 Hackathon (Online Preliminary Round)**  
> *LLM-Assisted Operator Directive Interpretation & Mathematical Energy Dispatch*

---

## 1. Overview & Architecture

GridWise is an enterprise-grade campus energy management HTTP service built for the BUP CSE Fest 2026 Hackathon. The platform receives a 24-hour smart campus scenario (hourly demand, rooftop solar forecast, grid tariffs, battery storage parameters) alongside 1–3 natural language operator notes.

It orchestrates a robust 4-stage pipeline:

```
+------------------------+      +-------------------------------+
| Campus Operator Notes  | ---> |   LLM Directive Interpreter   | (Gemini / Groq / OpenAI)
+------------------------+      +-------------------------------+
                                                |
                                                v
                                +-------------------------------+
                                |    Deterministic Guardrails   | (Section 08 & 11 validation)
                                +-------------------------------+
                                                |
                                                v
+------------------------+      +-------------------------------+
| Hourly Demand / Solar  | ---> |   HiGHS LP Energy Optimizer   | (scipy.optimize.linprog)
| Battery Specifications |      +-------------------------------+
+------------------------+                      |
                                                v
                                +-------------------------------+
                                |  Schedule Replay & Verifier   | (Zero-discrepancy recalculation)
                                +-------------------------------+
                                                |
                                                v
                                +-------------------------------+
                                |      HTTP JSON Response       | (GET /health, POST /optimize-energy)
                                +-------------------------------+
```

### Core Components
1. **LLM Interpreter (`app/llm_interpreter.py`)**:
   - Supports Google Gemini (`gemini-2.0-flash`), Groq (`llama-3.3-70b-versatile`), and OpenAI (`gpt-4o-mini`).
   - Translates natural-language operator notes into structured machine directives (`solar_reduction`, `minimum_battery_reserve`, `no_charge_window`, `no_discharge_window`, `max_grid_window`, or `no_op`).
   - Equipped with a zero-latency deterministic NLP fallback parser that guarantees continuous operation and 100% test pass rates even during API key absence or upstream network timeouts.
2. **Deterministic Guardrails (`app/guardrails.py`)**:
   - Strictly enforces canonical rules (Section 08 & 11): note index mapping, allowed enum types, whole-hour intervals, unique ascending hours $\in [0, 23]$, value boundaries (solar fraction $\in [0, 1]$, reserve $\le capacity$, grid cap $\ge 0$).
   - Safely recovers from malformed model outputs without crashing.
3. **HiGHS LP Optimizer (`app/optimizer.py`)**:
   - Formulates the exact 96-variable Linear Program over the 24-hour horizon.
   - Strictly enforces battery capacity, hourly charge/discharge limits, energy balance ($g_h + s_h + d_h = demand_h + c_h$), and end-of-day battery neutrality ($E_{23} = E_{init}$).
   - Solves for the true global minimum cost in $\approx 4\text{ms}$.
4. **Constraint Verifier (`app/verifier.py`)**:
   - Independently replays the hourly schedule hour-by-hour prior to API response return.
   - Recalculates `total_grid_kwh`, `total_cost_bdt`, and `peak_grid_kwh` directly from the schedule to guarantee zero divergence.

---

## 2. Quickstart & Local Reproduction

### Prerequisites
- Python 3.10+ (or Docker)
- Git

### 1. Clone Repository & Setup
```bash
git clone https://github.com/abdullah09c/bup-hackathon.git
cd bup-hackathon
git checkout arafat
```

### 2. Create Virtual Environment & Install Dependencies
```bash
python -m venv venv
# On Linux/macOS:
source venv/bin/activate
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Environment Configuration (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your chosen API key (e.g. `GEMINI_API_KEY=...` or `GROQ_API_KEY=...`).  
*Note: If no API key is provided, the service automatically uses its deterministic rule engine, achieving 100% accuracy on all public sample cases without external network dependencies.*

### 4. Start the Service
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
The service will boot and log readiness on `http://0.0.0.0:8000`.

---

## 3. API Contract & Testing

### Health Readiness Endpoint
**Linux / macOS / Git Bash:**
```bash
curl -X GET http://localhost:8000/health
```

**Windows (PowerShell):**
> *Note: In Windows PowerShell, `curl` is an alias for `Invoke-WebRequest`. Use `curl.exe` or `Invoke-RestMethod`:*
```powershell
curl.exe http://localhost:8000/health
# or
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
```

**Expected Response:**
```json
{
  "status": "ok"
}
```

### Optimize Energy Endpoint
```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d @BUP_CSE_FEST_2026_Participant_Docs/sample_01_payload.json
```

Or using an inline test request:
```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "TEST-01",
    "operator_notes": ["The cafeteria menu changes tomorrow."],
    "hours": [
      {"hour": 0, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 1, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 2, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 3, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 4, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 5, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 6, "demand_kwh": 100, "solar_kwh": 10, "tariff_bdt_per_kwh": 6.0},
      {"hour": 7, "demand_kwh": 100, "solar_kwh": 20, "tariff_bdt_per_kwh": 8.0},
      {"hour": 8, "demand_kwh": 100, "solar_kwh": 40, "tariff_bdt_per_kwh": 10.0},
      {"hour": 9, "demand_kwh": 100, "solar_kwh": 60, "tariff_bdt_per_kwh": 12.0},
      {"hour": 10, "demand_kwh": 100, "solar_kwh": 80, "tariff_bdt_per_kwh": 14.0},
      {"hour": 11, "demand_kwh": 100, "solar_kwh": 100, "tariff_bdt_per_kwh": 15.0},
      {"hour": 12, "demand_kwh": 100, "solar_kwh": 100, "tariff_bdt_per_kwh": 15.0},
      {"hour": 13, "demand_kwh": 100, "solar_kwh": 80, "tariff_bdt_per_kwh": 14.0},
      {"hour": 14, "demand_kwh": 100, "solar_kwh": 60, "tariff_bdt_per_kwh": 12.0},
      {"hour": 15, "demand_kwh": 100, "solar_kwh": 40, "tariff_bdt_per_kwh": 10.0},
      {"hour": 16, "demand_kwh": 100, "solar_kwh": 20, "tariff_bdt_per_kwh": 8.0},
      {"hour": 17, "demand_kwh": 100, "solar_kwh": 10, "tariff_bdt_per_kwh": 6.0},
      {"hour": 18, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 20.0},
      {"hour": 19, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 22.0},
      {"hour": 20, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 20.0},
      {"hour": 21, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 15.0},
      {"hour": 22, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 10.0},
      {"hour": 23, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 6.0}
    ],
    "battery": {
      "capacity_kwh": 200,
      "initial_energy_kwh": 100,
      "minimum_energy_kwh": 40,
      "max_charge_kwh_per_hour": 50,
      "max_discharge_kwh_per_hour": 50
    }
  }'
```

---

## 4. Automated Verification Suite

Run the full public sample test suite covering all 10 official cases:
```bash
python test_public_samples.py
```

### Benchmark Results (10 / 10 Passing)
```
================================================================================
        GRIDWISE PUBLIC SAMPLE CASES - VERIFICATION & EVALUATION
================================================================================
Case ID     | Label                               | Constraints | Cost Match      
--------------------------------------------------------------------------------
SAMPLE-01   | Solar cleaning + distractor         | PASSED      | EXACT (38365.00)
SAMPLE-02   | Battery charging maintenance        | PASSED      | EXACT (42885.00)
SAMPLE-03   | Emergency reserve as percentage     | PASSED      | EXACT (35480.00)
SAMPLE-04   | No-discharge protection test        | PASSED      | EXACT (40495.00)
SAMPLE-05   | Temporary feeder grid cap           | PASSED      | EXACT (33950.00)
SAMPLE-06   | Multiple notes with distractor      | PASSED      | EXACT (34090.00)
SAMPLE-07   | Reserve plus transformer cap        | PASSED      | EXACT (38550.00)
SAMPLE-08   | Separate charge/discharge outages   | PASSED      | EXACT (37665.00)
SAMPLE-09   | Reduction wording normalization     | PASSED      | EXACT (34873.00)
SAMPLE-10   | Multi-constraint evening operation  | PASSED      | EXACT (41620.00)
--------------------------------------------------------------------------------
Total processing time for 10 cases: 0.040s (Average 4.0ms per case)

ALL 10 PUBLIC SAMPLE CASES PASSED ALL CANONICAL RULES WITH OPTIMAL COST!
```

Run unit tests:
```bash
python -m unittest discover tests
```

---

## 5. Docker Deployment & Fallback Instructions

### Build Docker Image
```bash
docker build -t gridwise-app:latest .
```

### Run Docker Container
```bash
docker run -d --name gridwise -p 8000:8000 gridwise-app:latest
```

### Verify Container Health
```bash
curl http://localhost:8000/health
```

### Run Container Self-Test
```bash
docker exec gridwise python test_public_samples.py
```

---

## 6. Security, Limitations & Secret Safety

- **Zero Secret Exposure**: No API keys, tokens, or credentials are hardcoded into the repository or container image.
- **Error Shielding**: Controlled HTTP 400/500 handlers ensure internal tracebacks and environment secrets are never leaked to external clients.
- **Deterministic Bounds**: Time windows, battery SOC limits, and numeric factors are bounded by mathematical constraints prior to solver injection.
