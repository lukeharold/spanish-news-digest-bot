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


def fetch_recent_articles(hours=26):
    """Fetch articles published in the last N hours across all feeds."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for outlet, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
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
                        "date":   pub_dt.strftime("%Y-%m-%d %H:%M UTC"),
                    })
        except Exception as e:
            print(f"  Warning: could not fetch {outlet}: {e}")

    return articles


def fetch_week_articles():
    """Fetch articles from the last 7 days."""
    return fetch_recent_articles(hours=170)


def summarize_daily(articles):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    if not articles:
        return "No articles found in the last 24 hours."

    lines = "\n".join(
        f"[{a['outlet']}] {a['title']}\n{a['summary']}\n{a['link']}"
        for a in articles
    )

    prompt = f"""You are a research assistant for a journalist covering Latin America and the US-Mexico border.
Below are news headlines and summaries from Spanish-language outlets published in the last 24 hours.

Write a concise daily digest in English. Group stories by theme (e.g. border security, crime, politics, economy, culture).
For each story give: the outlet, a one-sentence summary, and the link.
Be factual and neutral. Do not editorialize. Flag anything that seems particularly significant for border/immigration coverage.

Articles:
{lines}"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def summarize_weekly(articles):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    if not articles:
        return "No articles found this week."

    lines = "\n".join(
        f"[{a['outlet']}] {a['date']} — {a['title']}\n{a['summary']}"
        for a in articles
    )

    prompt = f"""You are a research assistant for a journalist covering Latin America and the US-Mexico border.
Below are news headlines and summaries from Spanish-language outlets from the past 7 days.

Write a weekly trend analysis in English. Identify 4-6 major themes or developing stories.
For each theme: name it, explain why it matters, note which outlets are covering it and how,
and flag anything a journalist should watch in the coming week.
Be specific — cite outlets and stories by name. Stay factual and neutral.

Articles:
{lines}"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


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
