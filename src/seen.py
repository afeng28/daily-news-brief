import json
from datetime import date, timedelta
from pathlib import Path

_SEEN_FILE = Path(__file__).parent.parent / "seen.json"
_KEEP_DAYS = 7


def load_seen_urls() -> set[str]:
    if not _SEEN_FILE.exists():
        return set()
    data = json.loads(_SEEN_FILE.read_text())
    cutoff = (date.today() - timedelta(days=_KEEP_DAYS)).isoformat()
    return {entry["url"] for entry in data if entry["date"] >= cutoff}


def save_seen_urls(urls: list[str]) -> None:
    existing: list[dict] = []
    if _SEEN_FILE.exists():
        existing = json.loads(_SEEN_FILE.read_text())

    today = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=_KEEP_DAYS)).isoformat()

    kept = [e for e in existing if e["date"] >= cutoff]
    already_saved = {e["url"] for e in kept}
    for url in urls:
        if url not in already_saved:
            kept.append({"url": url, "date": today})

    _SEEN_FILE.write_text(json.dumps(kept, indent=2))
