# Daily News Brief

A Python script that runs every morning via GitHub Actions, pulls ~24 hours of
headlines from 24 RSS feeds, asks Gemini to pick the 10 best stories with
editorial judgment, summarizes each one, and emails an HTML digest to your
Gmail. Cost: $0/month.

## Local setup

```bash
git clone <your-repo-url>
cd daily-news-brief
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env with your Gemini API key and Gmail credentials
python -m src.main
```

## Deploy to GitHub Actions

1. Push this repo to GitHub (private is fine).
2. Go to **Settings → Secrets and variables → Actions** and add:
   - `GEMINI_API_KEY` — your Gemini API key
   - `SMTP_USERNAME` — your Gmail address
   - `SMTP_PASSWORD` — your 16-character Gmail App Password (no spaces)
   - `EMAIL_FROM` — your Gmail address
   - `EMAIL_TO` — your Gmail address
3. Go to **Actions → Daily News Brief → Run workflow** to trigger manually.
4. Confirm the email arrives, then let the cron schedule take over.

The cron fires at 12:30 UTC = 7:30 AM ET in winter, 8:30 AM ET in summer.
GitHub Actions free-tier crons can be delayed 5–15 minutes under high load.

## Add or remove sources

Edit `src/sources.py`. Each entry is a dict with `name`, `url`, `topic`, and
`priority` (lower = more authoritative for dedup tie-breaking). Run
`python -m src.fetch` to verify new feeds return stories.

## Tune the selection prompt

Edit `_SYSTEM_PROMPT` in `src/select.py`. The current prompt selects for
significance, originality, topic balance, and one wildcard slot. Run
`python -m src.select` to preview picks without sending an email.

## Common failure modes

| Symptom | Fix |
|---|---|
| Feed returns 0 stories | URL moved — check the source site for its current RSS link and update `sources.py` |
| `429 RESOURCE_EXHAUSTED` (daily) | Free-tier daily quota exhausted from testing. Quota resets at midnight Pacific. One production run/day uses ~11 of the 20 allowed requests. |
| `429 RESOURCE_EXHAUSTED` (per-minute) | Reduce `max_workers` in `summarize.py` |
| Gmail SMTP auth fails | Check: (a) App Password used, not account password; (b) 2-Step Verification enabled; (c) no spaces in the 16-char password |
| Email goes to spam | Mark it "not spam" once — Gmail learns fast when sending to yourself |
| Summaries say "this article discusses" | Lower `temperature` in `summarize.py` or add "Do not use phrases like..." to the prompt |
| GitHub Actions cron fires late | Normal on free tier — up to 15-minute delay under load |
