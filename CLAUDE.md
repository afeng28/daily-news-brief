# CLAUDE.md — Daily News Brief

## Project status (as of 2026-05-09)

All 7 build stages are complete and confirmed working end-to-end. The pipeline
is triggered daily at 8 AM ET via cron-job.org → GitHub Actions workflow_dispatch
(replaced the native GitHub cron). A full test run on 2026-05-09 delivered
successfully to both recipients.

### What's working
- RSS fetch, filter, dedup (`src/fetch.py`, `src/sources.py`)
- Gemini story selection with JSON output (`src/select.py`)
- Parallel Gemini summarization with rate-limit retry (`src/summarize.py`)
- Jinja2 HTML email template (`templates/email.html`)
- Gmail SMTP sending to multiple recipients (`src/email_sender.py`)
- Orchestrator with failure-email fallback (`src/main.py`)
- cron-job.org triggers `workflow_dispatch` at 12:00 UTC daily (`daily.yml`)
- Cross-day deduplication via `seen.json` + `src/seen.py`; `daily.yml` commits updated file after each run
- Git history contains no real email addresses

### Recipients
`EMAIL_TO` secret holds comma-separated addresses: both `security@copleyfinance.com`
and `angie.feng@duke.edu`. To add/remove recipients, update that secret only —
no code changes needed.

### Immediate next step
Monitor tomorrow's 8 AM ET run in GitHub Actions to confirm the seen.json
commit step completes green (fixed permissions on 2026-05-09).

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

### Cross-day deduplication via `seen.json`
After each successful send, `src/seen.py` appends the sent article URLs (with
date) to `seen.json`, keeping entries for 7 days. On the next run, `main.py`
loads these URLs and filters them out before passing candidates to Gemini.
`daily.yml` commits and pushes the updated `seen.json` back to the repo using
`github-actions[bot]` with `permissions: contents: write`. Without the explicit
permission, the push step returns a 403 and the job fails even though the email
was already sent.

### cron-job.org trigger
GitHub's native cron was replaced because it silently skips runs when Actions
queues are busy. cron-job.org POSTs to the workflow dispatch API at 12:00 UTC.
The `Authorization` header must be `Bearer <token>` (not just the raw token).
The PAT needs **Actions: read and write** permission on the repo.

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
