import logging
import re
from datetime import datetime, timedelta, timezone

import feedparser

from src.sources import SOURCES

logger = logging.getLogger(__name__)


def fetch_all_sources() -> list[dict]:
    all_stories = []
    for source in SOURCES:
        try:
            stories = fetch_one(source)
            all_stories.extend(stories)
            logger.debug("  %s: %d stories", source["name"], len(stories))
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", source["name"], exc)
    return all_stories


def fetch_one(source: dict) -> list[dict]:
    feed = feedparser.parse(source["url"])
    stories = []
    for entry in feed.entries:
        stories.append({
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", ""),
            "source": source["name"],
            "topic": source["topic"],
            "priority": source.get("priority", 3),
            "published": _parse_date(entry),
            "snippet": _get_snippet(entry),
        })
    return stories


def filter_recent(stories: list[dict], hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [s for s in stories if s["published"] >= cutoff]


def deduplicate(stories: list[dict]) -> list[dict]:
    # Sort by priority so the most authoritative source survives each cluster.
    sorted_stories = sorted(stories, key=lambda s: s["priority"])
    kept: list[dict] = []
    kept_tokens: list[set] = []

    for story in sorted_stories:
        tokens = _title_tokens(story["title"])
        if not any(_jaccard(tokens, t) > 0.7 for t in kept_tokens):
            kept.append(story)
            kept_tokens.append(tokens)

    return kept


# ── helpers ────────────────────────────────────────────────────────────────

def _parse_date(entry) -> datetime:
    if getattr(entry, "published_parsed", None):
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc)


def _get_snippet(entry) -> str:
    text = entry.get("summary") or entry.get("description") or ""
    # Strip any embedded HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    return text[:500].strip()


def _title_tokens(title: str) -> set[str]:
    return set(re.sub(r"[^\w\s]", "", title.lower()).split())


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── manual test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("Fetching all sources…")
    raw = fetch_all_sources()
    print(f"Raw stories fetched:   {len(raw)}")

    recent = filter_recent(raw, hours=24)
    print(f"Recent (last 24h):     {len(recent)}")

    deduped = deduplicate(recent)
    print(f"After dedup:           {len(deduped)}")

    print("\nSample (first 10):")
    for s in deduped[:10]:
        print(f"  [{s['topic']:12}] {s['source']:25} {s['title'][:70]}")
