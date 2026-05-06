import logging
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def render_email(stories: list[dict], date_str: str) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("email.html")
    return template.render(
        stories=stories,
        date_str=date_str,
        run_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )


def send_email(subject: str, html_body: str) -> None:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", 587))
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    from_addr = os.environ["EMAIL_FROM"]
    to_addr = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(_html_to_plain(html_body), "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(username, password)
        smtp.sendmail(from_addr, [to_addr], msg.as_string())
        logger.info("Email sent to %s", to_addr)


def _html_to_plain(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r" {2,}", " ", text).strip()


# ── manual test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    placeholder_stories = [
        {
            "title": "Test Story One: Everything Is Working",
            "url": "https://example.com/story-1",
            "source": "Example News",
            "topic": "tech",
            "summary": "This is a placeholder summary to verify the email template renders correctly. "
                       "The layout, fonts, and colors should all look clean. "
                       "If you're reading this in Gmail, Stage 5 is complete.",
            "is_wildcard": False,
        },
        {
            "title": "Test Story Two: The Wildcard Slot",
            "url": "https://example.com/story-2",
            "source": "Another Source",
            "topic": "cybersecurity",
            "summary": "This second story tests the wildcard badge. "
                       "The orange WILDCARD label should appear next to the topic pill above. "
                       "Check that both badges render on mobile as well as desktop.",
            "is_wildcard": True,
        },
        {
            "title": "Test Story Three: Policy Coverage",
            "url": "https://example.com/story-3",
            "source": "Policy Weekly",
            "topic": "policy",
            "summary": "A third placeholder to confirm the topic pill text and 'Read more' link "
                       "both appear correctly. The footer below should show today's UTC timestamp.",
            "is_wildcard": False,
        },
    ]

    from datetime import date

    date_str = date.today().strftime("%B %-d, %Y")
    html = render_email(placeholder_stories, date_str)
    subject = f"[TEST] Daily Brief — {date_str}"

    print(f"Sending test email: {subject}")
    send_email(subject, html)
    print("Done — check your inbox.")
