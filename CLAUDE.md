# CLAUDE.md — Daily News Brief

## Project status (as of 2026-05-06)

All 7 build stages are complete. The pipeline is deployed to GitHub Actions.
The first automated cron run is expected tomorrow morning (~7:30–8:45 AM ET).
A manual Actions trigger failed today only because the Gemini free-tier daily
quota (20 RPD) was exhausted from development testing. The code itself is correct.

### What's working
- RSS fetch, filter, dedup (`src/fetch.py`, `src/sources.py`)
- Gemini story selection with JSON output (`src/select.py`)
- Parallel Gemini summarization with rate-limit retry (`src/summarize.py`)
- Jinja2 HTML email template (`templates/email.html`)
- Gmail SMTP sending with plain-text fallback (`src/email_sender.py`)
- Orchestrator with failure-email fallback (`src/main.py`)
- GitHub Actions cron at 12:30 UTC daily (`daily.yml`)
- Git history contains no real email addresses

### Immediate next step
Wait for the cron to fire tomorrow morning and confirm the brief arrives.
If it doesn't arrive, check the Actions log — most likely cause is another
429 from Gemini, which resolves on its own the next day.

---

## Key decisions and why

### Gemini model: `gemini-2.5-flash-lite`
Both `gemini-2.5-flash` and `gemini-2.5-flash-lite` have a 20 RPD free-tier
daily limit. `gemini-2.5-flash-lite` has 15 RPM vs. 5 RPM for the full model,
making it more tolerant of the parallel summarization calls. One production run
consumes ~11 of the 20 daily requests, leaving 9 for manual re-triggers.
`gemini-1.5-flash` (1500 RPD) no longer exists in the API (404). If the 20 RPD
limit becomes a problem long-term, the only path is enabling Gemini billing.

### RSS sources dropped from the build guide
These were in the original guide but have no working RSS:
- **Reuters** — officially killed RSS in 2020
- **AP News** — no public RSS feed
- **CISA** — retired all RSS feeds in May 2025
- **Brookings TechStream** — newsletter discontinued October 2023

Replaced with: SecurityWeek (cybersecurity), EFF Deeplinks (ethics/policy),
AI as Normal Technology at `normaltech.ai` (formerly "AI Snake Oil" by
Arvind Narayanan & Sayash Kapoor — rebranded ~2024).

### `_clean_json()` in `select.py`
Even with `response_mime_type="application/json"`, Gemini occasionally wraps
output in markdown fences or uses Python-style `True`/`False` instead of JSON
`true`/`false`. The helper strips fences and normalises Python literals before
`json.loads()`. Without it, parsing fails intermittently.

### Rate-limit retry only in `summarize.py`
The 429 retry loop (15 s / 30 s / 45 s backoff) lives in `summarize_story()`
because that function is called in parallel from a `ThreadPoolExecutor` and is
most likely to burst past the 15 RPM per-minute limit. `select_top_stories()`
makes a single serial call and is less likely to hit the per-minute limit; it
has no retry and will raise immediately if it gets a 429. If 429s on the
selection call become a problem, add the same retry pattern there.

### `max_workers=3` in `summarize_all()`
15 RPM / 5 workers would exceed the per-minute budget during bursts. 3 workers
provides a comfortable margin. If summaries start timing out or rate-limiting
frequently, drop to 2.

### Git privacy
`git config --global user.email` is set to the GitHub noreply address
`179532033+afeng28@users.noreply.github.com`. The repo is public. No real
email appears in any committed file or in git history. The `.env` file
(which contains real credentials) is gitignored and was never staged.

---

## Stretch goals (Part 8 of BUILD_GUIDE.md)
After the pipeline runs reliably for ~2 weeks:
- Slack or Telegram delivery alongside email
- Weekend digest mode (longer reads, fewer stories)
- Click tracking → preference learning
- Audio version via TTS for morning commute
- Multiple recipients with personalised topic profiles

## Running locally
```bash
source .venv/bin/activate
python -m src.fetch      # test RSS fetching
python -m src.select     # test Gemini selection (uses ~1 of 20 daily quota)
python -m src.summarize  # test summarization (uses ~11 of 20 daily quota)
python -m src.email_sender  # send placeholder test email (no Gemini)
python -m src.main       # full pipeline (uses ~11 of 20 daily quota)
```
