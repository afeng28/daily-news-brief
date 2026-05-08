import json
import logging
import os
import time

from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash-lite"

_SYSTEM_PROMPT = """\
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
{"selections": [{"index": 0, "topic": "...", "is_wildcard": false, "reason": "..."}, ...]}\
"""


def select_top_stories(candidates: list[dict]) -> list[dict]:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    candidate_text = _build_candidate_list(candidates)

    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=candidate_text,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )
            break
        except (ClientError, ServerError) as exc:
            retryable = "429" in str(exc) or "503" in str(exc)
            if retryable and attempt < 3:
                wait = 15 * (attempt + 1)  # 15s, 30s, 45s
                logger.info("Transient error (%s); waiting %ds (attempt %d/3)…", exc.__class__.__name__, wait, attempt + 1)
                time.sleep(wait)
            else:
                raise

    data = json.loads(_clean_json(response.text))
    selections = data["selections"]

    selected = []
    for sel in selections:
        idx = sel["index"]
        if idx >= len(candidates):
            logger.warning("Gemini returned out-of-range index %d, skipping", idx)
            continue
        story = dict(candidates[idx])
        story["is_wildcard"] = sel.get("is_wildcard", False)
        story["selection_reason"] = sel.get("reason", "")
        selected.append(story)

    return selected


def _clean_json(text: str) -> str:
    # Strip markdown fences Gemini occasionally adds despite response_mime_type
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    # Replace Python literals that break JSON parsing
    text = text.replace(": True,", ": true,").replace(": True\n", ": true\n")
    text = text.replace(": False,", ": false,").replace(": False\n", ": false\n")
    text = text.replace(": None,", ": null,").replace(": None\n", ": null\n")
    return text.strip()


def _build_candidate_list(candidates: list[dict]) -> str:
    lines = []
    for i, story in enumerate(candidates):
        snippet = (story.get("snippet") or "")[:200]
        lines.append(
            f"{i}. [{story['topic']}] {story['title']}\n"
            f"   Source: {story['source']}\n"
            f"   Snippet: {snippet}"
        )
    return "\n\n".join(lines)


# ── manual test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from src.fetch import deduplicate, fetch_all_sources, filter_recent

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("Fetching candidates…")
    stories = fetch_all_sources()
    stories = filter_recent(stories, hours=24)
    stories = deduplicate(stories)
    print(f"{len(stories)} candidates after dedup")

    if len(stories) < 10:
        print("Not enough candidates — check your feeds.", file=sys.stderr)
        sys.exit(1)

    print("Calling Gemini to select top 10…")
    selected = select_top_stories(stories)

    print(f"\nSelected {len(selected)} stories:\n")
    for i, s in enumerate(selected, 1):
        wildcard = " [WILDCARD]" if s.get("is_wildcard") else ""
        print(f"{i:2}. [{s['topic']:12}] {s['source']:25} {s['title'][:60]}{wildcard}")
        print(f"     Reason: {s.get('selection_reason', '')[:100]}")
