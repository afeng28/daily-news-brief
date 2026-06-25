import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests
import trafilatura
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

logger = logging.getLogger(__name__)

MODEL = "gemini-2.0-flash"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; daily-brief/1.0)"}

_PROMPT_TEMPLATE = """\
Write a 3-4 sentence executive summary of this news story. Voice: factual,
direct, no hedging. Lead with the news itself, not "this article discusses."
Assume the reader is well-informed and short on time. Do not editorialize.
Do not include the headline or source — just the summary.

Headline: {title}
Source: {source}
Body: {body}\
"""


def summarize_story(story: dict) -> str:
    body = _fetch_body(story["url"])
    if not body:
        body = story.get("snippet") or ""
        logger.debug("Fell back to snippet for: %s", story["title"][:60])

    body = body[:3000]

    prompt = _PROMPT_TEMPLATE.format(
        title=story["title"],
        source=story["source"],
        body=body,
    )

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.5),
            )
            return response.text.strip()
        except (ClientError, ServerError) as exc:
            retryable = "429" in str(exc) or "503" in str(exc)
            if retryable and attempt < 3:
                wait = 60 * (attempt + 1)  # 60s, 120s, 180s
                logger.info("Transient error (%s); waiting %ds (attempt %d/3)…", exc.__class__.__name__, wait, attempt + 1)
                time.sleep(wait)
            else:
                raise


def summarize_all(stories: list[dict], max_workers: int = 3) -> list[str]:
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(summarize_story, stories))


# ── helpers ────────────────────────────────────────────────────────────────

def _fetch_body(url: str) -> str:
    try:
        resp = requests.get(url, timeout=10, headers=_HEADERS)
        resp.raise_for_status()
        text = trafilatura.extract(resp.text)
        return text or ""
    except Exception as exc:
        logger.debug("Article fetch failed for %s: %s", url, exc)
        return ""


# ── manual test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from src.fetch import deduplicate, fetch_all_sources, filter_recent
    from src.select import select_top_stories

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("Fetching and selecting stories…")
    stories = fetch_all_sources()
    stories = filter_recent(stories, hours=24)
    stories = deduplicate(stories)
    selected = select_top_stories(stories)
    print(f"Selected {len(selected)} stories. Summarizing in parallel…\n")

    summaries = summarize_all(selected)

    if len(summaries) != len(selected):
        print("ERROR: summary count mismatch", file=sys.stderr)
        sys.exit(1)

    for story, summary in zip(selected, summaries):
        wildcard = " [WILDCARD]" if story.get("is_wildcard") else ""
        print(f"── [{story['topic']}] {story['source']}{wildcard}")
        print(f"   {story['title']}")
        print(f"   {summary}")
        print()
