import logging
import traceback
from datetime import date

from dotenv import load_dotenv

from src.email_sender import render_email, send_email
from src.fetch import deduplicate, fetch_all_sources, filter_recent
from src.select import select_top_stories
from src.summarize import summarize_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()

    try:
        # ── 1. Fetch ──────────────────────────────────────────────────
        logger.info("Fetching RSS feeds…")
        stories = fetch_all_sources()
        stories = filter_recent(stories, hours=24)
        stories = deduplicate(stories)
        logger.info("%d candidates after dedup", len(stories))

        # ── 2. Select ─────────────────────────────────────────────────
        logger.info("Selecting top 10 with Gemini…")
        selected = select_top_stories(stories)
        logger.info("Selected %d stories", len(selected))

        # ── 3. Summarize ──────────────────────────────────────────────
        logger.info("Summarizing in parallel…")
        summaries = summarize_all(selected)
        for story, summary in zip(selected, summaries):
            story["summary"] = summary

        # ── 4. Send ───────────────────────────────────────────────────
        date_str = _today_str()
        html = render_email(selected, date_str)
        send_email(f"Daily Brief — {date_str}", html)
        logger.info("Brief sent.")

    except Exception:
        tb = traceback.format_exc()
        logger.error("Pipeline failed:\n%s", tb)
        _send_failure_email(tb)
        raise


def _today_str() -> str:
    return date.today().strftime("%B %-d, %Y")


def _send_failure_email(tb: str) -> None:
    try:
        subject = f"Daily Brief FAILED — {_today_str()}"
        html = (
            "<p style='font-family:monospace;color:#c00'>The daily brief pipeline "
            f"failed with the following error:</p><pre>{tb}</pre>"
        )
        send_email(subject, html)
    except Exception as exc:
        logger.error("Could not send failure email: %s", exc)


if __name__ == "__main__":
    main()
