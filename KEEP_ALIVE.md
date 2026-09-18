# Keep service awake during judging (Render free)

Render free sleeps after ~15 minutes idle. Set this up before evaluation:

1. Go to https://cron-job.org and create a free account
2. New cron job:
   - Title: `elec-bup health`
   - URL: `https://elec-bup.onrender.com/health`
   - Schedule: every **10 minutes**
   - Request method: **GET**
3. Enable the job and leave it running through the judging window

Quick manual check anytime:

```powershell
curl https://elec-bup.onrender.com/health
```

Expected: `{"status":"ok"}`
