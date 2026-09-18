# Deploy checklist — Render (free) primary

Railway is skipped (paid). Use **Render free Web Service** as primary.
Optional free backup: **Fly.io** (if Render cold-starts become an issue).

## Before deploy

1. Create `.env` locally (never commit):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_env.ps1
```

Or:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `OPENAI_API_KEY` to your real key. Keep `OPENAI_MODEL=gpt-4o-mini`.

2. Verify locally:

```powershell
python -m pytest tests/test_samples.py tests/test_extra_cases.py tests/test_failures.py -q
python -m pytest tests/test_llm_samples.py tests/test_paraphrase.py -q
uvicorn app.main:app --host 0.0.0.0 --port 8000
# other terminal:
python scripts/run_samples.py --base-url http://127.0.0.1:8000
```

## Render free (PRIMARY) — do this

### A. Push code to GitHub (private during event)

Create a **new private** repo after question reveal, then push this project.

### B. Create the Web Service

1. Go to [https://dashboard.render.com](https://dashboard.render.com)
2. **New +** → **Web Service**
3. Connect the GitHub repo
4. Settings:
   - **Runtime:** Docker (uses our `Dockerfile`)
   - **Instance type:** Free
   - **Health Check Path:** `/health`
5. Environment variables:
   - `OPENAI_API_KEY` = your key
   - `OPENAI_MODEL` = `gpt-4o-mini`
6. Click **Create Web Service** / **Deploy**

Blueprint alternative: this repo includes [`render.yaml`](render.yaml) — you can use **New → Blueprint** and select the repo.

### C. After deploy

**This team's live base URL:** `https://elec-bup.onrender.com`

```powershell
curl https://elec-bup.onrender.com/health
python scripts/run_samples.py --base-url https://elec-bup.onrender.com
```

### D. Free-tier cold starts (important for judging)

Render free **spins down** after ~15 minutes idle. First request can take 30–60s.

- Judging allows `/health` readiness within **60s** of start — usually OK.
- **Do this now for the evaluation window:** create a free job at [https://cron-job.org](https://cron-job.org):
  - URL: `https://elec-bup.onrender.com/health`
  - Schedule: every **10 minutes**
  - Method: GET
- Or open the health URL in a browser periodically while waiting for results.

## Fly.io (optional free backup)

If Render is too sleepy:

```powershell
# install flyctl, then:
fly launch --name gridwise-llm --dockerfile Dockerfile --no-deploy
fly secrets set OPENAI_API_KEY=sk-... OPENAI_MODEL=gpt-4o-mini
fly deploy
```

## Docker image fallback

Published image (use this on the submission form):

```text
nishadmahmud/elec_bup:v1
```

```bash
docker pull nishadmahmud/elec_bup:v1
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=<KEY> \
  -e OPENAI_MODEL=gpt-4o-mini \
  nishadmahmud/elec_bup:v1
curl http://127.0.0.1:8000/health
```

Republish after code changes: [`scripts/docker_publish.ps1`](scripts/docker_publish.ps1).

## Submission package

- [x] Public API base URL: `https://elec-bup.onrender.com`
- [x] GitHub repo: https://github.com/nishadmahmud/ELEC_BUP
- [x] README local quickstart works
- [x] Docker image pullable: `nishadmahmud/elec_bup:v1`
- [ ] 3-minute architecture/solution video (team-local; not in this repo)
- [ ] Cron keep-alive on `/health` during judging — see [`KEEP_ALIVE.md`](KEEP_ALIVE.md)
