# Daily News Brief — Build Guide (Gemini Edition)

A complete, step-by-step guide to building an automated daily news briefing
that emails you 10 curated stories with executive summaries every morning at 8am.

**Customized for: macOS, Python 3.13, Git already configured, Gmail (sending
and receiving), Eastern Time delivery, Google Gemini API (free tier),
GitHub Actions for scheduling.**

This document is your reference. Save it as `BUILD_GUIDE.md` in your project
folder and have Claude Code read it as context when you start building.

---

## Part 0 — What you're building

A Python script that runs every morning at ~7:30am Eastern via GitHub Actions.
It pulls ~24 hours of headlines from ~25 RSS feeds covering AI, tech,
cybersecurity, government, defense, ethics, and policy. It deduplicates, sends
the candidate pool to Gemini to pick the 10 best stories using editorial
judgment with soft topic-balance constraints, then sends each winner to Gemini
for a tight 3–4 sentence executive summary. Finally it emails an HTML briefing
to the user's Gmail with headlines, summaries, source attribution, and links.

**Cost: $0/month** (Gemini free tier, GitHub Actions free tier, Gmail).

Maintenance: ~5 minutes/week.

---

## Part 1 — Pre-build checklist

Confirm before opening Claude Code:

- [x] Python 3.13 installed
- [x] Git installed and configured
- [x] GitHub account ready
- [ ] Homebrew installed (only if Node isn't already)
- [ ] Node.js installed (`node --version` works) — needed for Claude Code
- [ ] Claude Code installed (`claude --version` works)
- [ ] Google Gemini API key generated (see Part 2 below)
- [ ] Gmail 2-Step Verification enabled
- [ ] Gmail App Password generated for "daily-brief" and saved (16 chars,
      strip spaces when using)

---

## Part 2 — Get a Gemini API key

1. Go to [aistudio.google.com](https://aistudio.google.com) and sign in
   with a Google account.
2. Click **Get API key** in the left sidebar (or top-right; the UI shifts).
3. Click **Create API key**. You can create it in a new project or an
   existing Google Cloud project; new project is fine.
4. Copy the key. It looks like `AIzaSy...`. Save it somewhere safe — you can
   re-view it later, but don't commit it anywhere public.
5. **Important about the free tier:** Free-tier traffic may be used by Google
   to improve their models. This is fine for processing public news content.
   If that's a problem, you'd need to enable billing for paid-tier usage
   (which has data-use opt-outs but isn't free).

The free tier on Gemini Flash models is generous — the request and token
limits are far more than this project will ever consume (one batch run/day
with a small handful of API calls).

---

## Part 3 — Repository structure (target end state)

```
daily-brief/
├── .github/
│   └── workflows/
│       └── daily.yml
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── sources.py
│   ├── fetch.py
│   ├── select.py
│   ├── summarize.py
│   └── email_sender.py
├── templates/
│   └── email.html
├── .env                       # NEVER commit this
├── .env.example
├── .gitignore
├── BUILD_GUIDE.md             # this file
├── requirements.txt
└── README.md
```

---

## Part 4 — Configuration specifics

### 4.1 Gemini model selection

Use **Gemini 2.0 Flash** (or the current latest Flash variant — Claude Code
should verify the current model name at [ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models)
before writing code).

Why Flash instead of Pro:
- Free tier covers Flash generously.
- Quality is more than sufficient for both selection and summarization.
- Pro adds latency and may have stricter free-tier limits.

Use the same model for both selection and summarization for v1. Simpler.

### 4.2 Gemini SDK

Use the **`google-genai`** Python SDK (the newer unified SDK, not the older
`google-generativeai`). Claude Code should verify the current install command
and import syntax against the official docs at
[github.com/googleapis/python-genai](https://github.com/googleapis/python-genai)
before writing code.

Expected install: `pip install google-genai`
Expected env var: `GEMINI_API_KEY` (or `GOOGLE_API_KEY` — confirm with docs)

### 4.3 Gmail SMTP settings

```
SMTP_HOST = smtp.gmail.com
SMTP_PORT = 587
SMTP_USERNAME = <your-gmail-address>
SMTP_PASSWORD = <16-char-app-password, no spaces>
EMAIL_FROM = <your-gmail-address>
EMAIL_TO = <your-gmail-address>
```

Use STARTTLS (port 587), not SSL (port 465).

### 4.4 GitHub Actions cron expression

GitHub Actions cron is **UTC** and does NOT adjust for daylight saving.

For ~8:00 AM Eastern delivery, target 7:30 AM ET (gives 30-min runtime
budget). Use:

```yaml
cron: '30 12 * * *'
```

= 12:30 UTC = 7:30 AM EST (winter) / 8:30 AM EDT (summer).

Brief arrives ~8:00 AM ET in winter, ~9:00 AM ET in summer. Accept this
drift for v1.

---

## Part 5 — File specifications

### 5.1 `requirements.txt`

```
google-genai>=0.3.0
feedparser>=6.0.10
python-dotenv>=1.0.0
jinja2>=3.1.0
trafilatura>=1.12.0
```

Claude Code: verify `google-genai` version against latest on PyPI before
finalizing.

### 5.2 `.gitignore`

```
.env
__pycache__/
*.pyc
.venv/
venv/
.DS_Store
```

### 5.3 `.env.example`

```
GEMINI_API_KEY=AIzaSy...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-16-char-app-password
EMAIL_FROM=your-sender@gmail.com
EMAIL_TO=your-recipient@gmail.com
```

### 5.4 `src/sources.py`

A Python list of dicts with `name`, `url`, `topic`, and optionally
`priority` (lower number = more authoritative, used for dedup tie-breaking).

Starter sources — Claude Code should verify each RSS URL is currently live
before committing the file (many feeds have moved over the years):

- **AI / Tech:** Ars Technica, Wired, MIT Technology Review, The Verge,
  TechCrunch
- **Cybersecurity:** Krebs on Security, The Record, Bleeping Computer,
  Dark Reading, CISA advisories
- **Government / Policy:** Politico, Axios, The Hill, Government Executive,
  Lawfare
- **National Defense:** Defense One, Breaking Defense, War on the Rocks, CSIS
- **Ethics / AI Policy:** Brookings TechStream, Just Security, AI Snake Oil
- **General / Wire services:** Reuters Top News, AP Top News, BBC, NYT, WaPo

### 5.5 `src/fetch.py`

Functions:
- `fetch_all_sources()` — iterates all sources, calls `fetch_one()` on each,
  wraps each call in try/except so one bad feed doesn't kill the run.
  Logs failures with source name.
- `fetch_one(source)` — uses `feedparser` to parse the RSS, returns a list of
  story dicts: `{title, url, source, topic, published, snippet}`.
- `filter_recent(stories, hours=24)` — keep only stories published in the
  last N hours. Use timezone-aware datetimes.
- `deduplicate(stories)` — remove near-duplicates. Normalize titles
  (lowercase, strip punctuation), use Jaccard similarity > 0.7 on token sets,
  cluster matches, keep the one from the most authoritative source (use
  `priority` field; lower wins).

Add a `__main__` block so you can run `python -m src.fetch` to test.

### 5.6 `src/select.py`

Function `select_top_stories(candidates: list) -> list`:

- Build a numbered list of all candidates with title, source, topic, snippet.
- Call Gemini with the system prompt below.
- Request JSON output. Parse it. Return the selected story dicts in order.

System prompt (use as-is, tune later):

```
You are an editorial briefer selecting 10 stories for a daily executive
news brief. The reader is interested in: AI, technology, cybersecurity,
government & public policy, national defense, and ethics.

You will receive a numbered list of candidate stories from the last 24
hours. Select exactly 10 by index.

Selection criteria, in priority order:
1. Significance — would this matter to a well-informed person in these fields?
2. Originality — prefer original reporting over aggregation/commentary.
3. Topic balance — no single topic should exceed 4 of 10 slots. Each
   interest area should get at least 1 slot if a worthwhile story exists.
4. One slot ("wildcard") should be a story of clear significance that the
   reader might not click on themselves but should know about. Mark it.
5. When two stories cover the same event, pick the one from the most
   authoritative source.

Return ONLY valid JSON in this exact shape, no markdown fences, no preamble:
{"selections": [{"index": 0, "topic": "...", "is_wildcard": false, "reason": "..."}, ...]}
```

**Gemini-specific JSON handling:** Use Gemini's `response_mime_type:
"application/json"` config option (or the current equivalent — check docs)
to force structured output. This is more reliable than relying on prompt
instructions alone.

Use `temperature=0.3` for consistency.

### 5.7 `src/summarize.py`

Function `summarize_story(story: dict) -> str`:

- Try to fetch the article body using `trafilatura.fetch_url()` and
  `trafilatura.extract()`. 10-second timeout. Fall back to RSS snippet if
  extraction fails or returns empty.
- Cap input body at ~3000 characters.
- Call Gemini with this prompt:

```
Write a 3-4 sentence executive summary of this news story. Voice: factual,
direct, no hedging. Lead with the news itself, not "this article discusses."
Assume the reader is well-informed and short on time. Do not editorialize.
Do not include the headline or source — just the summary.

Headline: {title}
Source: {source}
Body: {body}
```

Use `temperature=0.5`.

Run summaries in parallel using `concurrent.futures.ThreadPoolExecutor` with
`max_workers=5`. Be mindful of free-tier rate limits — if you hit them,
reduce `max_workers` to 2 or 3. Total runtime should still stay under 30s.

### 5.8 `templates/email.html`

Jinja2 template, inline styles only (email clients strip CSS).

Structure:
- Header: "Daily Brief — {{ date_str }}" (e.g., "Daily Brief — May 6, 2026")
- For each of the 10 stories:
  - Topic pill (small colored label)
  - Headline (bold, 18px)
  - Summary (paragraph, 15px, line-height 1.5)
  - "Read more at {{ source }} →" link
  - Wildcard items get a "WILDCARD" tag
- Footer: small text with run timestamp

Color palette: white background, near-black text (#222), accent (#3b6ef0)
for links and pills.

### 5.9 `src/email_sender.py`

Function `send_email(subject: str, html_body: str)`:

- Uses `smtplib.SMTP("smtp.gmail.com", 587)` with `.starttls()`.
- `MIMEMultipart("alternative")` with both plain-text fallback and HTML.
- Logs in with username + app password from env vars.
- Sets From, To, Subject headers.
- Wrap in try/except and re-raise so main.py can catch.

### 5.10 `src/main.py`

Orchestrator. Pseudocode:

```python
def main():
    load_dotenv()
    try:
        stories = fetch_all_sources()
        stories = filter_recent(stories, hours=24)
        stories = deduplicate(stories)
        print(f"{len(stories)} candidates after dedup")

        selected = select_top_stories(stories)
        print(f"Selected {len(selected)} stories")

        # parallel summarization
        with ThreadPoolExecutor(max_workers=5) as ex:
            summaries = list(ex.map(summarize_story, selected))
        for story, summary in zip(selected, summaries):
            story['summary'] = summary

        html = render_template(selected)
        send_email(f"Daily Brief — {today_str()}", html)
        print("Brief sent.")
    except Exception:
        send_failure_email(traceback.format_exc())
        raise
```

### 5.11 `.github/workflows/daily.yml`

```yaml
name: Daily News Brief

on:
  schedule:
    - cron: '30 12 * * *'   # 7:30 AM ET in winter, 8:30 AM ET in summer
  workflow_dispatch:

jobs:
  send-brief:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run brief
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          SMTP_HOST: smtp.gmail.com
          SMTP_PORT: 587
          SMTP_USERNAME: ${{ secrets.SMTP_USERNAME }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
        run: python -m src.main
```

Secrets to add in GitHub repo Settings → Secrets and variables → Actions:
`GEMINI_API_KEY`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`.

### 5.12 `README.md`

Write for your future self:
- What this is, in one paragraph
- How to set up locally (clone, venv, .env, run `python -m src.main`)
- How to deploy to GitHub Actions (push, configure secrets, manual trigger)
- How to add/remove sources
- How to tune the selection prompt
- Common failure modes (see Part 7 below)

---

## Part 6 — Build sequence (incremental)

Build → test → next. Don't have Claude Code build everything at once.

### Stage 1: Foundation (~30 min)
1. Folder structure, `.gitignore`, `requirements.txt`, `.env.example`
2. Create venv: `python3 -m venv .venv`
3. Activate: `source .venv/bin/activate`
4. Install: `pip install -r requirements.txt`
5. Create real `.env` with Gemini key + Gmail credentials

**Verify:** `python -c "from google import genai; import feedparser; print('ok')"`
(or whatever the correct genai import is — Claude Code should confirm)

### Stage 2: RSS fetching (~45 min)
1. Build `sources.py`
2. Build `fetch.py`
3. Run `python -m src.fetch`

**Verify:** 50–150 candidates after dedup, no errors. Fix any 404 feeds.

### Stage 3: Story selection (~45 min)
1. Build `select.py` with Gemini call
2. Add `__main__` block: fetch → select → print results
3. Run a few times, read picks, tune prompt

**Verify:** Picks feel reasonable, topic balance sane, JSON parses cleanly.

### Stage 4: Summarization (~45 min)
1. Build `summarize.py` with parallel execution
2. Add `__main__` block: select 10 → summarize → print
3. Read summaries, tune voice/length

**Verify:** Summaries are 3–4 sentences, factual, no hedging.

### Stage 5: Email (~60 min — debugging SMTP usually takes a while)
1. Build `templates/email.html`
2. Build `email_sender.py`
3. Send a test email with placeholder content first
4. Fix Gmail auth issues

**Verify:** Test email arrives, renders cleanly on phone and desktop.

### Stage 6: Wire it together (~30 min)
1. Build `main.py`
2. Run end-to-end: `python -m src.main`
3. Receive a real brief

**Verify:** Full pipeline runs in <90 seconds, email arrives, content good.

### Stage 7: GitHub Actions (~45 min)
1. Create new GitHub repo (private is fine)
2. Push code
3. Add secrets in Settings → Secrets and variables → Actions
4. Manually trigger via Actions tab → workflow_dispatch
5. Confirm brief arrives
6. Wait until tomorrow morning to confirm cron fires

**Verify:** Manual run works, then scheduled run works the next morning.

---

## Part 7 — Things that will go wrong

- **Feed URL 404s.** Sites move RSS endpoints. Fix in `sources.py`.
- **Gmail SMTP authentication fails.** 99% of the time:
  (a) regular password instead of app password,
  (b) 2SV not enabled,
  (c) app password copied with spaces (remove them).
- **Gemini returns malformed JSON.** Use the structured-output config option
  (`response_mime_type: "application/json"`). If still flaky, lower temperature.
- **Gemini rate limits hit on summaries.** Reduce `ThreadPoolExecutor`
  `max_workers` to 2 or 3. Free tier has per-minute limits.
- **Email goes to spam.** Mark first one as "not spam" — Gmail learns fast
  when sending to yourself.
- **Cron runs late.** GitHub Actions free-tier crons can be delayed 5–15
  minutes during high load. Documented and unavoidable on free tier.
- **Article extraction fails.** Trafilatura handles most sites but paywalls
  and JS-heavy sites defeat it. Falling back to RSS snippet is fine.

---

## Part 8 — Stretch goals (after v1 runs reliably for 2 weeks)

- Slack or Telegram delivery alongside email
- "Reply with story number" → deeper analysis
- Click tracking → preference learning
- Weekend digest mode (longer reads)
- Multiple recipients with personalized profiles
- Audio version (TTS) for morning commute

---

End of guide.
