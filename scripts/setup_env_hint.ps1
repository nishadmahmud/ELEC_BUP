# Create local .env for LLM tests / local server
#
# PowerShell (from repo root):
#   Copy-Item .env.example .env
#   notepad .env
# Then set OPENAI_API_KEY to your real key (never commit .env).

Write-Host "After creating .env with OPENAI_API_KEY, run:"
Write-Host "  python -m pytest tests/test_llm_samples.py tests/test_paraphrase.py -q"
Write-Host "  uvicorn app.main:app --host 0.0.0.0 --port 8000"
Write-Host "  python scripts/run_samples.py --base-url http://127.0.0.1:8000"
