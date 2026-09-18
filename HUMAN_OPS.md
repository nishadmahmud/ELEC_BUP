# Human ops checklist (agent cannot do these)

## Keep-alive (you said cron is already set)
Confirm cron-job.org still hits every 10 minutes:
`GET https://elec-bup.onrender.com/health`

## Video (tie-break)
Record ≤3 minutes using [VIDEO_SCRIPT.md](VIDEO_SCRIPT.md) against the live URL.

## Repository
Keep https://github.com/nishadmahmud/ELEC_BUP **private until after the submission deadline**, then make it public.

## After pulling these code changes
Push/redeploy to Render so window-expansion + LP relaxation + note cache go live, then:

```powershell
python scripts/run_samples.py --base-url https://elec-bup.onrender.com
```
