#!/usr/bin/env python3
"""
AI Pulse - RSS Feed Fetcher
Fetches AI news from multiple RSS feeds and saves to feed.json.

Usage:
    python fetch_feeds.py

Run this 3x daily (or set up a cron job):
    0 0 * * *   python /path/to/fetch_feeds.py   # 00:00 UTC (9am JST)
    0 8 * * *   python /path/to/fetch_feeds.py   # 08:00 UTC (9am CET)
    0 14 * * *  python /path/to/fetch_feeds.py   # 14:00 UTC (9am EST)

Requirements:
    pip install feedparser requests
"""

import feedparser
import json
import re
import os
import html
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# --- Configuration ---

FEEDS = [
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "source": "TechCrunch"
    },
    {
        "name": "The Verge AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "source": "The Verge"
    },
    {
        "name": "Ars Technica AI",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "source": "Ars Technica"
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "source": "MIT Tech Review"
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "source": "VentureBeat"
    },
    {
        "name": "Wired AI",
        "url": "https://www.wired.com/feed/tag/ai/latest/rss",
        "source": "Wired"
    },
    {
        "name": "Reuters Tech",
        "url": "https://www.rss.app/feeds/v1.1/tDxHblYnloaSvbhO.json",
        "source": "Reuters"
    },
    {
        "name": "The Decoder",
        "url": "https://the-decoder.com/feed/",
        "source": "The Decoder"
    },
    {
        "name": "AI News",
        "url": "https://www.artificialintelligence-news.com/feed/",
        "source": "AI News"
    },
    {
        "name": "Hacker News (AI)",
        "url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+artificial+intelligence&points=50",
        "source": "Hacker News"
    }
]

# AI-related keywords to filter articles
AI_KEYWORDS = [
    'ai', 'artificial intelligence', 'machine learning', 'deep learning',
    'neural network', 'llm', 'large language model', 'gpt', 'chatgpt',
    'claude', 'gemini', 'copilot', 'openai', 'anthropic', 'deepmind',
    'midjourney', 'stable diffusion', 'generative ai', 'transformer',
    'nlp', 'natural language', 'computer vision', 'robotics', 'agi',
    'foundation model', 'fine-tuning', 'training data', 'gpu', 'nvidia',
    'hugging face', 'open source model', 'llama', 'mistral', 'runway',
    'sora', 'dall-e', 'diffusion model', 'autonomous', 'agent',
    'prompt', 'tokens', 'inference', 'alignment', 'safety'
]

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feed.js")
MAX_ITEMS = 200  # keep the feed manageable


def clean_html(text):
    """Remove HTML tags and clean up text."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def truncate_summary(text, max_sentences=2, max_chars=280):
    """Trim summary to 1-2 sentences, Twitter-length."""
    text = clean_html(text)
    if not text:
        return ""

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = ""
    for s in sentences[:max_sentences]:
        if len(result) + len(s) > max_chars:
            break
        result += s + " "

    result = result.strip()
    if not result and text:
        result = text[:max_chars].rsplit(' ', 1)[0] + "..."

    return result


def is_ai_related(title, summary):
    """Check if article is AI-related based on keywords."""
    text = (title + " " + summary).lower()
    return any(kw in text for kw in AI_KEYWORDS)


def parse_date(entry):
    """Extract and normalize the published date from a feed entry."""
    date_str = entry.get('published') or entry.get('updated') or entry.get('created')
    if date_str:
        try:
            dt = parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass

    # Try struct_time fields
    for field in ['published_parsed', 'updated_parsed', 'created_parsed']:
        st = entry.get(field)
        if st:
            try:
                dt = datetime(*st[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass

    return datetime.now(timezone.utc).isoformat()


def fetch_feed(feed_config):
    """Fetch and parse a single RSS feed."""
    items = []
    print(f"  Fetching: {feed_config['name']}...")

    try:
        parsed = feedparser.parse(feed_config['url'])

        if parsed.bozo and not parsed.entries:
            print(f"    Warning: feed error for {feed_config['name']}")
            return items

        for entry in parsed.entries:
            title = clean_html(entry.get('title', ''))
            summary = truncate_summary(
                entry.get('summary') or entry.get('description') or ''
            )
            link = entry.get('link', '')

            if not title:
                continue

            # Filter for AI-related content (skip filter for AI-specific feeds)
            ai_specific_sources = ['The Decoder', 'AI News', 'Hacker News']
            if feed_config['source'] not in ai_specific_sources:
                if not is_ai_related(title, summary):
                    continue

            items.append({
                "title": title,
                "summary": summary if summary else title,
                "source": feed_config['source'],
                "published": parse_date(entry),
                "link": link
            })

        print(f"    Found {len(items)} AI-related articles")

    except Exception as e:
        print(f"    Error fetching {feed_config['name']}: {e}")

    return items


def load_existing():
    """Load existing feed data to merge with new items."""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r') as f:
                content = f.read()
                # Strip the "const FEED_DATA = " prefix and trailing ";"
                json_str = content.replace('const FEED_DATA = ', '', 1).rstrip().rstrip(';')
                data = json.loads(json_str)
                return data.get('items', [])
        except Exception:
            pass
    return []


def deduplicate(items):
    """Remove duplicate articles based on title similarity."""
    seen_titles = set()
    unique = []

    for item in items:
        # Normalize title for comparison
        normalized = re.sub(r'[^a-z0-9\s]', '', item['title'].lower()).strip()
        # Use first 60 chars as fingerprint
        fingerprint = normalized[:60]

        if fingerprint not in seen_titles:
            seen_titles.add(fingerprint)
            unique.append(item)

    return unique


def main():
    print("AI Pulse - Fetching feeds...")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    # Fetch new items from all feeds
    new_items = []
    for feed_config in FEEDS:
        items = fetch_feed(feed_config)
        new_items.extend(items)

    print(f"\nTotal new items fetched: {len(new_items)}")

    # Merge with existing items
    existing = load_existing()
    all_items = new_items + existing

    # Deduplicate
    all_items = deduplicate(all_items)

    # Sort by date (newest first)
    all_items.sort(key=lambda x: x['published'], reverse=True)

    # Trim to max size
    all_items = all_items[:MAX_ITEMS]

    # Save
    output = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "items": all_items
    }

    with open(OUTPUT_FILE, 'w') as f:
        f.write('const FEED_DATA = ')
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write(';')

    print(f"\nSaved {len(all_items)} items to {OUTPUT_FILE}")
    print("Done!")


if __name__ == "__main__":
    main()
