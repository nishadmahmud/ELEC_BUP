# 3-minute solution video — talking points (tie-break only)

Record a screen + voice clip, max 3:00. No fancy editing needed.

Demo against: `https://elec-bup.onrender.com`

## Suggested outline (≈2:30–3:00)

1. **Problem (20s)**  
   Smart campus energy: 24h demand/solar/tariff + 1–3 operator notes. API must interpret notes and return a valid low-cost schedule.

2. **Architecture (45s)**  
   Show README architecture or code folders:  
   `operator_notes → OpenAI gpt-4o-mini (structured JSON) → deterministic guardrails → PuLP/CBC optimizer → replay verifier → JSON`.  
   Emphasize: LLM is on the interpretation path (not just plan_summary).

3. **Key rules (30s)**  
   Half-open hours (`1 PM–3 PM` → `[13,14]`), solar factor = remaining fraction (`80% reduction` → `0.2`), end-of-day battery neutrality, energy balance.

4. **Demo (45s)**  
   - `curl https://elec-bup.onrender.com/health` → `{"status":"ok"}`  
   - Run `python scripts/run_samples.py --base-url https://elec-bup.onrender.com` or one POST  
   - Point at `directive_interpretation` + `total_cost_bdt`

5. **How to run/test (30s)**  
   Local: `.env` with `OPENAI_API_KEY`, `uvicorn app.main:app --host 0.0.0.0 --port 8000`.  
   Docker: `docker pull nishadmahmud/elec_bup:v1` then  
   `docker run --rm -p 8000:8000 -e OPENAI_API_KEY=... -e OPENAI_MODEL=gpt-4o-mini nishadmahmud/elec_bup:v1`.

## Upload

MP4 or organizer-accessible link. Keep under 3 minutes.
