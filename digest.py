#!/usr/bin/env python3
"""
Spanish News Digest Bot
Fetches RSS feeds, summarizes with Claude, emails to haroldl1@pm.me.

Usage:
    python digest.py --mode daily
    python digest.py --mode weekly
"""

import os
import sys
import smtplib
import feedparser
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import anthropic
from feeds import FEEDS

SEND_FROM = "luke.harold89@gmail.com"
SEND_TO   = "haroldl1@pm.me"

GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]

USER_AGENT = "spanish-news-digest-bot/1.0 (+https://github.com/lukeharold/spanish-news-digest-bot)"


def fetch_recent_articles(hours=26, per_feed=15):
    """Fetch articles published in the last N hours across all feeds.

    per_feed caps how many of each feed's newest entries are considered
    (None for no cap).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for outlet, url in FEEDS.items():
        try:
            feed = feedparser.parse(url, agent=USER_AGENT)
            for entry in feed.entries[:per_feed]:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                pub_dt = None
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                link    = entry.get("link", "")
                if title:
                    articles.append({
                        "outlet": outlet,
                        "title":  title,
                        "summary": summary[:400],
                        "link":   link,
                        "date":   pub_dt.strftime("%Y-%m-%d %H:%M UTC") if pub_dt else "date unknown",
                    })
        except Exception as e:
            print(f"  Warning: could not fetch {outlet}: {e}")

    return articles


def fetch_week_articles():
    """Fetch articles from the last 7 days, with no per-feed cap."""
    return fetch_recent_articles(hours=170, per_feed=None)


def create_message(prompt, effort):
    """Call Claude, falling back to another model if a safety classifier declines."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    # Streaming avoids HTTP timeouts on long digests with a high max_tokens
    with client.beta.messages.stream(
        model="claude-opus-5-5",
        max_tokens=64000,
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()
    print(f"  {response.model}: {response.usage.input_tokens} input / "
          f"{response.usage.output_tokens} output tokens")
    return response


def response_text(response):
    """Return the reply text, warning in the log if it hit the token limit."""
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {response.stop_details}")
    # The response can start with (empty) thinking blocks, so keep only text blocks
    text = "".join(b.text for b in response.content if b.type == "text")
    if response.stop_reason == "max_tokens":
        print("  Warning: digest hit max_tokens and was truncated")
        text += "\n\n[Digest truncated: hit the length limit]"
    return text


def summarize_daily(articles):
    if not articles:
        return "No articles found in the last 24 hours."

    lines = "\n".join(
        f"[{a['outlet']}] {a['title']}\n{a['summary']}\n{a['link']}"
        for a in articles
    )

    prompt = f"""You are a research assistant for a journalist covering Latin America and the US-Mexico border.
Below are news headlines and summaries from Spanish-language outlets published in the last 24 hours.

Write a concise daily digest in English, to be read in a few minutes as a plain-text email.

Cover only news about Mexico and Latin America. Leave out international news from elsewhere
(Europe, Asia, the Middle East, etc.) and US news unless it directly involves Mexico or the border.

Start with a 4-6 sentence high-level summary of the day's news, leading with Tijuana.

Format: this is a plain-text email, so write plain prose with no Markdown or symbols
(no #, *, **, bullets, or horizontal rules). Write the summary as a conversational but
professional briefing, the way a colleague would brief a reporter at the start of the day.
For each section, put its name on a line by itself, then give each story as a short
paragraph followed by its link on its own line, with a blank line between stories.

Then list only the stories that matter most, in these three sections, in this order:
1. Tijuana & Baja California: about 8-12 stories
2. Mexico: national news and other states, about 6-10 stories
3. Latin America: just the 3-5 top headlines from the rest of the region

When several outlets cover the same story, list it once and name the outlets.
Skip minor items, sports, and entertainment news.
For each story give the outlet(s), a one-sentence summary, and one link.

Be factual and neutral. Do not editorialize. Flag anything that seems particularly significant for border/immigration coverage.

Articles:
{lines}"""

    response = create_message(prompt, effort="medium")
    return response_text(response)


def summarize_weekly(articles):
    if not articles:
        return "No articles found this week."

    lines = "\n".join(
        f"[{a['outlet']}] {a['date']} — {a['title']}\n{a['summary']}"
        for a in articles
    )

    prompt = f"""You are a research assistant for a journalist covering Latin America and the US-Mexico border.
Below are news headlines and summaries from Spanish-language outlets from the past 7 days.

Write a weekly trend analysis in English.

Cover only news about Mexico and Latin America. Leave out international news from elsewhere
(Europe, Asia, the Middle East, etc.) and US news unless it directly involves Mexico or the border.

Start with a 4-6 sentence high-level summary of the week's main trends and how they connect,
leading with Tijuana.

Format: this is a plain-text email, so write plain prose with no Markdown or symbols
(no #, *, **, bullets, or horizontal rules). Write the summary as a conversational but
professional briefing, the way a colleague would brief a reporter at the start of the week.
For each section, put its name on a line by itself, then give each theme as one or two
short paragraphs that open with the theme's name, with a blank line between themes.

Then identify the major themes or developing stories, in these three sections, in this order:
1. Tijuana & Baja California: 2-3 themes
2. Mexico: national news and other states, 2-3 themes
3. Latin America: 1-2 themes from the rest of the region

For each theme: name it, explain why it matters, note which outlets are covering it and how,
and flag anything a journalist should watch in the coming week.
Be specific — cite outlets and stories by name. Stay factual and neutral.

Articles:
{lines}"""

    response = create_message(prompt, effort="high")
    return response_text(response)


def send_email(subject, body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SEND_FROM
    msg["To"]      = SEND_TO

    # Plain text version
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SEND_FROM, GMAIL_APP_PASSWORD)
        server.sendmail(SEND_FROM, SEND_TO, msg.as_string())
    print(f"Email sent: {subject}")


def main():
    mode = "daily"
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        mode = sys.argv[idx + 1]

    today = datetime.now(timezone.utc).strftime("%A, %B %-d, %Y")

    if mode == "daily":
        print("Fetching articles (last 24h)...")
        articles = fetch_recent_articles()
        print(f"Found {len(articles)} articles. Summarizing...")
        digest = summarize_daily(articles)
        subject = f"🗞 Spanish News Digest — {today}"
        send_email(subject, digest)

    elif mode == "weekly":
        print("Fetching articles (last 7 days)...")
        articles = fetch_week_articles()
        print(f"Found {len(articles)} articles. Analyzing trends...")
        digest = summarize_weekly(articles)
        subject = f"📊 Weekly Trends Digest — Week of {today}"
        send_email(subject, digest)

    else:
        print(f"Unknown mode: {mode}. Use --mode daily or --mode weekly")
        sys.exit(1)


if __name__ == "__main__":
    main()
