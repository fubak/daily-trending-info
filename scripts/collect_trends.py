#!/usr/bin/env python3
"""
Trend Collector - Aggregates trending topics from multiple English sources.

Sources (English only):
- Google Trends (US daily trending searches)
- News RSS: AP News, NPR, NYT, BBC, Guardian, Reuters, ABC, CBS (English editions)
- Tech RSS: Verge, Ars Technica, Wired, TechCrunch, Engadget, MIT Tech Review, etc.
- Hacker News API (top stories)
- Lobsters (tech community, high-quality discussions)
- Reddit RSS (news, technology, science, etc. - uses RSS feeds for reliability)
- Product Hunt (new tech products and startups)
- Dev.to (developer community articles)
- Slashdot (classic tech news)
- Ars Technica Features (long-form tech journalism)
- GitHub Trending (English spoken language)
- Wikipedia Current Events (English)
"""

import os
import json
import re
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict, field
from urllib.parse import quote_plus
from difflib import SequenceMatcher

import requests
import feedparser
from bs4 import BeautifulSoup

from config import (
    LIMITS,
    TIMEOUTS,
    DELAYS,
    MIN_TRENDS,
    MIN_FRESH_RATIO,
    TREND_FRESHNESS_HOURS,
    DEDUP_SIMILARITY_THRESHOLD,
    DEDUP_SEMANTIC_THRESHOLD,
    CMMC_KEYWORDS,
    setup_logging,
)

# Setup logging
logger = setup_logging("collect_trends")


# Common non-English characters and patterns
NON_ENGLISH_PATTERNS = [
    r"[\u4e00-\u9fff]",  # Chinese
    r"[\u3040-\u309f\u30a0-\u30ff]",  # Japanese
    r"[\uac00-\ud7af]",  # Korean
    r"[\u0600-\u06ff]",  # Arabic
    r"[\u0400-\u04ff]",  # Cyrillic (Russian, etc.)
    r"[\u0900-\u097f]",  # Hindi/Devanagari
    r"[\u0e00-\u0e7f]",  # Thai
    r"[\u0590-\u05ff]",  # Hebrew
    r"[\u1100-\u11ff]",  # Korean Jamo
]


def is_english_text(text: str) -> bool:
    """Check if text appears to be primarily English."""
    if not text:
        return False

    # Check for non-English character patterns
    for pattern in NON_ENGLISH_PATTERNS:
        if re.search(pattern, text):
            return False

    # Check that most characters are ASCII/Latin
    ascii_chars = sum(
        1 for c in text if ord(c) < 128 or c in "àáâãäåæçèéêëìíîïðñòóôõöøùúûüýÿ"
    )
    if len(text) > 0 and ascii_chars / len(text) < 0.7:
        return False

    return True


@dataclass
class Trend:
    """Represents a single trending topic."""

    title: str
    source: str
    url: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None  # Added for explicit categorization
    score: float = 1.0
    keywords: List[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    image_url: Optional[str] = None  # Article image from RSS feed

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = self._extract_keywords()

    def is_fresh(self, max_hours: int = TREND_FRESHNESS_HOURS) -> bool:
        """Check if this trend is from within the specified hours."""
        if not self.timestamp:
            return True  # Assume fresh if no timestamp
        age = datetime.now() - self.timestamp
        return age < timedelta(hours=max_hours)

    def _extract_keywords(self) -> List[str]:
        """Extract meaningful keywords from title."""
        # Remove common words and extract meaningful terms
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "they",
            "them",
            "what",
            "which",
            "who",
            "whom",
            "whose",
            "where",
            "when",
            "why",
            "how",
            "all",
            "each",
            "every",
            "both",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "about",
            "after",
            "before",
            "between",
            "into",
            "through",
            "during",
            "above",
            "below",
            "up",
            "down",
            "out",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "new",
            "says",
            "said",
            "get",
            "got",
            "getting",
            "make",
            "made",
            "making",
            "know",
            "think",
            "take",
            "see",
            "come",
            "want",
            "look",
            "use",
            "find",
            "give",
            "tell",
            "ask",
            "work",
            "seem",
            "feel",
            "try",
            "leave",
            "call",
            "keep",
            "let",
            "begin",
            "show",
            "hear",
            "play",
            "run",
            "move",
            "like",
            "live",
            "believe",
            "hold",
            "bring",
            "happen",
            "write",
            "provide",
            "sit",
            "stand",
            "lose",
            "pay",
            "meet",
            "include",
            "continue",
            "set",
            "learn",
            "change",
            "lead",
            "understand",
            "watch",
            "follow",
            "stop",
            "create",
            "speak",
            "read",
            "allow",
            "add",
            "spend",
            "grow",
            "open",
            "walk",
            "win",
            "offer",
            "remember",
            "love",
            "consider",
            "appear",
            "buy",
            "wait",
            "serve",
            "die",
            "send",
            "expect",
            "build",
            "stay",
            "fall",
            "cut",
            "reach",
            "kill",
            "remain",
            "suggest",
            "raise",
            "pass",
            "sell",
            "require",
            "report",
            "decide",
            "pull",
            "breaking",
            "update",
            "latest",
            "news",
            "today",
        }

        # Clean and tokenize
        text = re.sub(r"[^\w\s]", " ", self.title.lower())
        words = text.split()

        # Filter and return meaningful keywords
        keywords = [
            word
            for word in words
            if word not in stop_words and len(word) > 2 and not word.isdigit()
        ]

        return keywords[:5]  # Top 5 keywords


from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


class TrendCollector:
    """Collects and aggregates trends from multiple sources."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=None,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.trends: List[Trend] = []

    def _fetch_rss(
        self,
        url: str,
        timeout: float = 10.0,
        allowed_status: tuple = (200, 301, 302, 404),
    ) -> Optional[requests.Response]:
        try:
            response = self.session.get(url, timeout=timeout)
        except Exception as exc:
            logger.warning(f"RSS fetch error for {url}: {exc}")
            return None

        if response.status_code not in allowed_status:
            logger.warning(
                f"RSS fetch: unexpected status {response.status_code} for {url}"
            )
            return None

        return response

    def _scrape_og_image(self, url: str) -> Optional[str]:
        """Scrape the Open Graph image from a URL."""
        if not url:
            return None

        try:
            # Short timeout, we only want the head/meta tags
            response = self.session.get(url, timeout=5, stream=True)

            # Read first 10KB which usually contains meta tags
            chunk = next(response.iter_content(chunk_size=10240), b"")
            html_content = chunk.decode("utf-8", errors="ignore")

            # Fast regex search for og:image
            match = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                html_content,
                re.I,
            )
            if match:
                img_url = match.group(1)
                # Ensure absolute URL
                if img_url.startswith("//"):
                    return "https:" + img_url
                elif img_url.startswith("/"):
                    from urllib.parse import urlparse

                    parsed = urlparse(url)
                    return f"{parsed.scheme}://{parsed.netloc}{img_url}"
                elif not img_url.startswith("http"):
                    return None
                return img_url

        except Exception as e:
            logger.debug(f"Failed to scrape OG image for {url}: {e}")

        return None

    def _collect_sports_rss(self) -> List[Trend]:
        """Collect trends from Sports RSS feeds."""
        trends = []
        feeds = [
            ("ESPN", "https://www.espn.com/espn/rss/news"),
            ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
            ("CBS Sports", "https://www.cbssports.com/rss/headlines/"),
            ("Yahoo Sports", "https://sports.yahoo.com/rss/"),
        ]

        for name, url in feeds:
            try:
                response = self.session.get(url, timeout=10)
                feed = feedparser.parse(response.content)
                for entry in feed.entries[:6]:
                    if is_english_text(entry.title):
                        trend = Trend(
                            title=entry.title,
                            source=f'sports_{name.lower().replace(" ", "")}',
                            url=entry.link,
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.4,
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)
            except Exception:
                continue
        return trends

    def _collect_entertainment_rss(self) -> List[Trend]:
        """Collect trends from Entertainment RSS feeds."""
        trends = []
        feeds = [
            ("Variety", "https://variety.com/feed/"),
            ("Hollywood Reporter", "https://www.hollywoodreporter.com/feed/"),
            ("Billboard", "https://www.billboard.com/feed/"),
            ("E! Online", "https://www.eonline.com/syndication/rss/top_stories/en_us"),
        ]

        for name, url in feeds:
            try:
                response = self.session.get(url, timeout=10)
                feed = feedparser.parse(response.content)
                for entry in feed.entries[:6]:
                    if is_english_text(entry.title):
                        trend = Trend(
                            title=entry.title,
                            source=f'entertainment_{name.lower().replace(" ", "")}',
                            url=entry.link,
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.4,
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)
            except Exception:
                continue
        return trends

    def collect_all(self) -> List[Trend]:
        """Collect trends from all available sources."""
        logger.info("Collecting trends from all sources...")

        collectors = [
            ("Google Trends", self._collect_google_trends),
            ("News RSS Feeds", self._collect_news_rss),
            ("Tech RSS Feeds", self._collect_tech_rss),
            ("Science RSS Feeds", self._collect_science_rss),
            ("Politics RSS Feeds", self._collect_politics_rss),
            ("Finance RSS Feeds", self._collect_finance_rss),
            ("Sports RSS Feeds", self._collect_sports_rss),
            ("Entertainment RSS Feeds", self._collect_entertainment_rss),
            ("Hacker News", self._collect_hackernews),
            ("Lobsters", self._collect_lobsters),
            ("Reddit", self._collect_reddit),
            ("Product Hunt", self._collect_product_hunt),
            ("Dev.to", self._collect_devto),
            ("Slashdot", self._collect_slashdot),
            ("Ars Features", self._collect_ars_frontpage),
            ("GitHub Trending", self._collect_github_trending),
            ("Wikipedia Current Events", self._collect_wikipedia_current),
            ("CMMC/Federal Compliance", self._collect_cmmc),
        ]

        for name, collector in collectors:
            try:
                logger.info(f"Fetching from {name}...")
                trends = collector()
                self.trends.extend(trends)
                logger.info(f"  Found {len(trends)} trends")
            except Exception as e:
                logger.warning(f"  Error from {name}: {e}")
                continue

            # Small delay between sources
            time.sleep(DELAYS["between_sources"])

        # Deduplicate and score
        self._deduplicate()
        self._calculate_scores()

        # Sort by score
        self.trends.sort(key=lambda t: t.score, reverse=True)

        # Post-processing: Scrape OG images for top stories if missing
        logger.info("Scraping OG images for top stories...")
        scrape_limit = min(
            50, len(self.trends)
        )  # Scrape up to top 50 stories to ensure coverage
        scraped_count = 0
        for trend in self.trends[:scrape_limit]:
            if not trend.image_url:
                trend.image_url = self._scrape_og_image(trend.url)
                if trend.image_url:
                    logger.info(f"  Found OG image for: {trend.title[:30]}...")
                    scraped_count += 1
                time.sleep(0.3)  # Be polite but faster

        logger.info(f"  Scraped {scraped_count} additional images from OG tags")

        logger.info(f"Total unique trends: {len(self.trends)}")
        return self.trends

    def get_freshness_ratio(self) -> float:
        """Calculate the ratio of fresh trends (from past 24 hours)."""
        if not self.trends:
            return 0.0
        fresh_count = sum(1 for t in self.trends if t.is_fresh())
        return fresh_count / len(self.trends)

    def _extract_image_from_entry(self, entry) -> Optional[str]:
        """Extract image URL from RSS entry using multiple strategies.

        Priority order:
        1. media_content (highest quality - NYT, Guardian)
        2. media_thumbnail (BBC)
        3. enclosures with image type
        4. Images in content:encoded or summary HTML
        """
        # Strategy 1: media_content (common in NYT, Guardian, etc.)
        if hasattr(entry, "media_content") and entry.media_content:
            for media in entry.media_content:
                url = media.get("url", "")
                medium = media.get("medium", "")
                content_type = media.get("type", "")
                if url and (
                    medium == "image"
                    or "image" in content_type
                    or any(
                        ext in url.lower()
                        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]
                    )
                ):
                    return url

        # Strategy 2: media_thumbnail (common in BBC)
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            for thumb in entry.media_thumbnail:
                url = thumb.get("url", "")
                if url:
                    return url

        # Strategy 3: enclosures with image type
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enc in entry.enclosures:
                enc_type = enc.get("type", "")
                url = enc.get("href", "") or enc.get("url", "")
                if url and "image" in enc_type:
                    return url

        # Strategy 4: Parse images from content:encoded or summary
        content_html = ""
        if hasattr(entry, "content") and entry.content:
            content_html = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            content_html = entry.get("summary", "")

        if content_html and "<img" in content_html.lower():
            # Extract first meaningful image (skip tracking pixels)
            img_matches = re.findall(
                r'<img[^>]+src=["\']([^"\']+)["\']', content_html, re.I
            )
            for img_url in img_matches:
                # Skip tracking pixels and tiny images
                if "pixel" in img_url.lower() or "tracking" in img_url.lower():
                    continue
                if "1x1" in img_url or "spacer" in img_url.lower():
                    continue
                # Return first valid image
                if any(
                    ext in img_url.lower()
                    for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]
                ):
                    return img_url

        return None

    def _collect_google_trends(self) -> List[Trend]:
        """Collect trends from Google Trends RSS."""
        trends = []

        # Google Trends Daily RSS
        url = "https://trends.google.com/trending/rss?geo=US"

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            for entry in feed.entries[:20]:
                title = entry.get("title", "").strip()
                # Only include English content
                if title and is_english_text(title):
                    trend = Trend(
                        title=title,
                        source="google_trends",
                        url=entry.get("link"),
                        description=(
                            entry.get("summary", "").strip()
                            if entry.get("summary")
                            else None
                        ),
                        score=2.0,  # Google Trends gets higher base score
                        image_url=self._extract_image_from_entry(entry),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Google Trends error: {e}")

        return trends

    def _collect_news_rss(self) -> List[Trend]:
        """Collect trends from major news RSS feeds."""
        trends = []

        # English-only news sources
        feeds = [
            ("NPR", "https://feeds.npr.org/1001/rss.xml"),
            ("NYT", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
            ("BBC", "https://feeds.bbci.co.uk/news/rss.xml"),
            ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
            ("Guardian", "https://www.theguardian.com/world/rss"),
            ("Guardian US", "https://www.theguardian.com/us-news/rss"),
            ("ABC News", "https://abcnews.go.com/abcnews/topstories"),
            ("CBS News", "https://www.cbsnews.com/latest/rss/main"),
            ("UPI", "https://rss.upi.com/news/news.rss"),
            ("Washington Post", "https://feeds.washingtonpost.com/rss/national"),
            ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
            ("PBS NewsHour", "https://www.pbs.org/newshour/feeds/rss/headlines"),
        ]

        for name, url in feeds:
            try:
                timeout = 15 if "washingtonpost" in url else 10
                response = self._fetch_rss(url, timeout=timeout)
                if not response:
                    continue

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:8]:
                    title = entry.get("title", "").strip()

                    # Clean up common suffixes
                    title = re.sub(r"\s+", " ", title)
                    for suffix in [
                        " - The New York Times",
                        " - BBC News",
                        " | AP News",
                        " - ABC News",
                        " | Reuters",
                        " - NPR",
                        " | The Guardian",
                    ]:
                        title = title.replace(suffix, "")

                    # Only include English content
                    if title and len(title) > 10 and is_english_text(title):
                        trend = Trend(
                            title=title,
                            source=f'news_{name.lower().replace(" ", "_")}',
                            url=entry.get("link"),
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.8,  # News sources get good score
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(0.15)

        return trends

    def _collect_tech_rss(self) -> List[Trend]:
        """Collect trends from tech-focused RSS feeds."""
        trends = []

        feeds = [
            ("Verge", "https://www.theverge.com/rss/index.xml"),
            ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
            ("Wired", "https://www.wired.com/feed/rss"),
            ("TechCrunch", "https://techcrunch.com/feed/"),
            ("Engadget", "https://www.engadget.com/rss.xml"),
            ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
            ("Gizmodo", "https://gizmodo.com/rss"),
            ("CNET", "https://www.cnet.com/rss/news/"),
            ("Mashable", "https://mashable.com/feeds/rss/all"),
            ("VentureBeat", "https://venturebeat.com/feed/"),
        ]

        for name, url in feeds:
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:6]:
                    title = entry.get("title", "").strip()

                    # Clean up title
                    title = re.sub(r"\s+", " ", title)
                    title = title.replace(" | Ars Technica", "")
                    title = title.replace(" - The Verge", "")

                    # Only include English content
                    if title and len(title) > 10 and is_english_text(title):
                        trend = Trend(
                            title=title,
                            source=f'tech_{name.lower().replace(" ", "_")}',
                            url=entry.get("link"),
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.5,
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(0.15)

        return trends

    def _collect_science_rss(self) -> List[Trend]:
        """Collect trends from science and health RSS feeds."""
        trends = []

        feeds = [
            ("Science Daily", "https://www.sciencedaily.com/rss/all.xml"),
            ("Nature News", "https://www.nature.com/nature.rss"),
            ("New Scientist", "https://www.newscientist.com/feed/home/"),
            ("Phys.org", "https://phys.org/rss-feed/"),
            ("Live Science", "https://www.livescience.com/feeds/all"),
            ("Space.com", "https://www.space.com/feeds/all"),
            ("ScienceNews", "https://www.sciencenews.org/feed"),
            (
                "Ars Technica Science",
                "https://feeds.arstechnica.com/arstechnica/science",
            ),
            ("Quanta Magazine", "https://api.quantamagazine.org/feed/"),
            ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
        ]

        for name, url in feeds:
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:6]:
                    title = entry.get("title", "").strip()
                    title = re.sub(r"\s+", " ", title)

                    if title and len(title) > 10 and is_english_text(title):
                        trend = Trend(
                            title=title,
                            source=f'science_{name.lower().replace(" ", "_").replace(".", "")}',
                            url=entry.get("link"),
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.5,
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(0.15)

        return trends

    def _collect_politics_rss(self) -> List[Trend]:
        """Collect trends from politics-focused RSS feeds."""
        trends = []

        feeds = [
            ("The Hill", "https://thehill.com/feed/"),
            ("Roll Call", "https://rollcall.com/feed/"),
            (
                "NYT Politics",
                "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
            ),
            ("WaPo Politics", "https://feeds.washingtonpost.com/rss/politics"),
            (
                "Guardian Politics",
                "https://www.theguardian.com/us-news/us-politics/rss",
            ),
            ("BBC Politics", "https://feeds.bbci.co.uk/news/politics/rss.xml"),
            ("Axios", "https://api.axios.com/feed/"),
            ("NPR Politics", "https://feeds.npr.org/1014/rss.xml"),
            ("Slate", "https://slate.com/feeds/all.rss"),
        ]

        for name, url in feeds:
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:6]:
                    title = entry.get("title", "").strip()
                    title = re.sub(r"\s+", " ", title)

                    # Clean common suffixes
                    for suffix in [
                        " - POLITICO",
                        " - The Hill",
                        " - The New York Times",
                    ]:
                        title = title.replace(suffix, "")

                    if title and len(title) > 10 and is_english_text(title):
                        trend = Trend(
                            title=title,
                            source=f'politics_{name.lower().replace(" ", "_").replace("-", "")}',
                            url=entry.get("link"),
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.6,
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(0.15)

        return trends

    def _collect_finance_rss(self) -> List[Trend]:
        """Collect trends from business and finance RSS feeds."""
        trends = []

        feeds = [
            ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
            ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
            ("Financial Times", "https://www.ft.com/rss/home"),
            ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
            ("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
            ("Economist", "https://www.economist.com/finance-and-economics/rss.xml"),
            ("Fortune", "https://fortune.com/feed/"),
            ("Business Insider", "https://www.businessinsider.com/rss"),
            ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
        ]

        for name, url in feeds:
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:6]:
                    title = entry.get("title", "").strip()
                    title = re.sub(r"\s+", " ", title)

                    # Clean common suffixes
                    for suffix in [" - Bloomberg", " - MarketWatch", " - CNBC"]:
                        title = title.replace(suffix, "")

                    if title and len(title) > 10 and is_english_text(title):
                        trend = Trend(
                            title=title,
                            source=f'finance_{name.lower().replace(" ", "_")}',
                            url=entry.get("link"),
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.5,
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(0.15)

        return trends

    def _collect_hackernews(self) -> List[Trend]:
        """Collect top stories from Hacker News API."""
        trends = []

        try:
            # Get top story IDs
            response = self.session.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
            )
            response.raise_for_status()

            story_ids = response.json()[:25]

            for story_id in story_ids:
                try:
                    story_response = self.session.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                        timeout=5,
                    )
                    story_response.raise_for_status()
                    story = story_response.json()

                    if story and story.get("title") and is_english_text(story["title"]):
                        score = story.get("score", 0)
                        normalized_score = min(score / 100, 3.0)  # Cap at 3x

                        trend = Trend(
                            title=story["title"],
                            source="hackernews",
                            url=story.get("url"),
                            score=1.0 + normalized_score,
                        )
                        trends.append(trend)

                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Hacker News error: {e}")

        return trends

    def _collect_reddit(self) -> List[Trend]:
        """Collect trending posts from Reddit using RSS feeds (more reliable than JSON API)."""
        trends = []

        # Use RSS feeds instead of JSON API - much more reliable
        # Balanced for diverse content across all categories
        subreddit_feeds = [
            # News & World (high priority)
            ("news", "https://www.reddit.com/r/news/.rss"),
            ("worldnews", "https://www.reddit.com/r/worldnews/.rss"),
            ("politics", "https://www.reddit.com/r/politics/.rss"),
            ("upliftingnews", "https://www.reddit.com/r/upliftingnews/.rss"),
            # Tech & Science
            ("technology", "https://www.reddit.com/r/technology/.rss"),
            ("science", "https://www.reddit.com/r/science/.rss"),
            ("space", "https://www.reddit.com/r/space/.rss"),
            # Business & Finance
            ("business", "https://www.reddit.com/r/business/.rss"),
            ("economics", "https://www.reddit.com/r/economics/.rss"),
            ("personalfinance", "https://www.reddit.com/r/personalfinance/.rss"),
            # Entertainment & Culture
            ("movies", "https://www.reddit.com/r/movies/.rss"),
            ("television", "https://www.reddit.com/r/television/.rss"),
            ("music", "https://www.reddit.com/r/music/.rss"),
            ("books", "https://www.reddit.com/r/books/.rss"),
            # Sports
            ("sports", "https://www.reddit.com/r/sports/.rss"),
            ("nba", "https://www.reddit.com/r/nba/.rss"),
            ("soccer", "https://www.reddit.com/r/soccer/.rss"),
            # Health & Lifestyle
            ("health", "https://www.reddit.com/r/health/.rss"),
            ("food", "https://www.reddit.com/r/food/.rss"),
            # General Interest
            ("todayilearned", "https://www.reddit.com/r/todayilearned/.rss"),
        ]

        for subreddit, url in subreddit_feeds:
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:6]:
                    title = entry.get("title", "").strip()

                    # Only include English content
                    if title and len(title) > 15 and is_english_text(title):
                        trend = Trend(
                            title=title,
                            source=f"reddit_{subreddit}",
                            url=entry.get("link"),
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.5,
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"Reddit r/{subreddit} RSS error: {e}")
                continue

            time.sleep(0.15)

        return trends

    def _collect_github_trending(self) -> List[Trend]:
        """Collect trending repositories from GitHub (English descriptions)."""
        trends = []

        try:
            # GitHub trending page with English spoken language filter
            url = "https://github.com/trending?since=daily&spoken_language_code=en"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            repos = soup.select("article.Box-row")[:15]

            for repo in repos:
                # Get repo name
                name_elem = repo.select_one("h2 a")
                if not name_elem:
                    continue

                repo_name = (
                    name_elem.get_text(strip=True).replace("\n", "").replace(" ", "")
                )

                # Get description
                desc_elem = repo.select_one("p")
                description = desc_elem.get_text(strip=True) if desc_elem else ""

                # Get stars today
                stars_elem = repo.select_one(".float-sm-right")
                stars_text = stars_elem.get_text(strip=True) if stars_elem else "0"
                stars = int(re.sub(r"[^\d]", "", stars_text) or 0)

                # Get language
                lang_elem = repo.select_one('[itemprop="programmingLanguage"]')
                language = lang_elem.get_text(strip=True) if lang_elem else ""

                title = f"{repo_name}"
                if language:
                    title += f" ({language})"
                if description:
                    title += f": {description[:80]}"

                # Only include repos with English descriptions (or no description)
                if not description or is_english_text(description):
                    trend = Trend(
                        title=title[:120],
                        source="github_trending",
                        url=f"https://github.com{name_elem.get('href', '')}",
                        description=description,
                        score=1.3 + min(stars / 500, 1.5),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"GitHub Trending error: {e}")

        return trends

    def _collect_wikipedia_current(self) -> List[Trend]:
        """Collect current events from Wikipedia."""
        trends = []

        try:
            # Wikipedia Current Events Portal
            url = "https://en.wikipedia.org/wiki/Portal:Current_events"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Find the current events content
            content = soup.select(".current-events-content li")[:20]

            for item in content:
                text = item.get_text(strip=True)

                # Clean up the text
                text = re.sub(r"\s+", " ", text)
                text = re.sub(r"\[.*?\]", "", text)  # Remove citations

                # Verify content is English
                if (
                    text
                    and len(text) > 20
                    and len(text) < 200
                    and is_english_text(text)
                ):
                    # Get the first link if available
                    link = item.select_one("a")
                    url = None
                    if link and link.get("href", "").startswith("/wiki/"):
                        url = f"https://en.wikipedia.org{link.get('href')}"

                    trend = Trend(
                        title=text[:150], source="wikipedia_current", url=url, score=1.4
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Wikipedia Current Events error: {e}")

        return trends

    def _collect_lobsters(self) -> List[Trend]:
        """Collect trending posts from Lobsters (tech community)."""
        trends = []

        try:
            # Main RSS feed - hottest.rss was removed, use main feed
            url = "https://lobste.rs/rss"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            # Check if response is actually RSS/XML, not HTML
            content_type = response.headers.get("content-type", "").lower()
            content_start = response.content[:100].lower()

            if b"<!doctype html" in content_start or b"<html" in content_start:
                logger.warning(f"Lobsters returned HTML instead of RSS, skipping")
                return trends

            feed = feedparser.parse(response.content)

            # Check if feed parsed successfully
            if not feed.entries and feed.bozo:
                logger.warning(f"Lobsters feed parse error: {feed.bozo_exception}")
                return trends

            for entry in feed.entries[:15]:
                title = entry.get("title", "").strip()

                if title and len(title) > 10 and is_english_text(title):
                    trend = Trend(
                        title=title,
                        source="lobsters",
                        url=entry.get("link"),
                        description=self._clean_html(entry.get("summary", "")),
                        score=1.6,  # Good quality tech content
                        image_url=self._extract_image_from_entry(entry),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Lobsters error: {e}")

        return trends

    def _collect_product_hunt(self) -> List[Trend]:
        """Collect trending products from Product Hunt."""
        trends = []

        try:
            # Product Hunt RSS feed
            url = "https://www.producthunt.com/feed"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            for entry in feed.entries[:10]:
                title = entry.get("title", "").strip()

                if title and len(title) > 5 and is_english_text(title):
                    trend = Trend(
                        title=title,
                        source="product_hunt",
                        url=entry.get("link"),
                        description=self._clean_html(entry.get("summary", "")),
                        score=1.4,
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Product Hunt error: {e}")

        return trends

    def _collect_devto(self) -> List[Trend]:
        """Collect trending posts from Dev.to."""
        trends = []

        try:
            # Dev.to top articles API
            url = "https://dev.to/api/articles?top=1&per_page=15"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            articles = response.json()

            for article in articles:
                title = article.get("title", "").strip()

                if title and len(title) > 10 and is_english_text(title):
                    # Include reaction count in score
                    reactions = article.get("public_reactions_count", 0)
                    score_boost = min(reactions / 100, 1.0)

                    trend = Trend(
                        title=title,
                        source="devto",
                        url=article.get("url"),
                        description=article.get("description", ""),
                        score=1.3 + score_boost,
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Dev.to error: {e}")

        return trends

    def _collect_slashdot(self) -> List[Trend]:
        """Collect stories from Slashdot."""
        trends = []

        try:
            url = "https://rss.slashdot.org/Slashdot/slashdotMain"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            for entry in feed.entries[:12]:
                title = entry.get("title", "").strip()

                if title and len(title) > 10 and is_english_text(title):
                    trend = Trend(
                        title=title,
                        source="slashdot",
                        url=entry.get("link"),
                        description=self._clean_html(entry.get("summary", "")),
                        score=1.4,
                        image_url=self._extract_image_from_entry(entry),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Slashdot error: {e}")

        return trends

    def _collect_ars_frontpage(self) -> List[Trend]:
        """Collect front page stories from Ars Technica (high quality tech journalism)."""
        trends = []

        try:
            url = "https://feeds.arstechnica.com/arstechnica/features"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                title = title.replace(" | Ars Technica", "")

                if title and len(title) > 10 and is_english_text(title):
                    trend = Trend(
                        title=title,
                        source="ars_features",
                        url=entry.get("link"),
                        description=self._clean_html(entry.get("summary", "")),
                        score=1.7,  # High quality long-form content
                        image_url=self._extract_image_from_entry(entry),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Ars Features error: {e}")

        return trends

    def _collect_cmmc(self) -> List[Trend]:
        """Collect CMMC and federal compliance news from specialized RSS feeds.

        Filters content by CMMC-relevant keywords to ensure relevance.
        Used for the standalone CMMC Watch page.
        """
        trends = []

        # Federal IT and cybersecurity news sources
        feeds = [
            ("FedScoop", "https://fedscoop.com/feed/"),
            ("DefenseScoop", "https://defensescoop.com/feed/"),
            (
                "Federal News Network",
                "https://federalnewsnetwork.com/category/technology-main/cybersecurity/feed/",
            ),
            ("Nextgov Cybersecurity", "https://www.nextgov.com/rss/cybersecurity/"),
            ("GovCon Wire", "https://www.govconwire.com/feed/"),
            ("SecurityWeek", "https://www.securityweek.com/feed/"),
            ("Cyberscoop", "https://cyberscoop.com/feed/"),
            # SC Media removed - returns 403 Forbidden for automated access
        ]

        for name, url in feeds:
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:10]:  # Check more entries, filter by keyword
                    title = entry.get("title", "").strip()
                    description = entry.get("summary", "")

                    # Clean up title
                    title = re.sub(r"\s+", " ", title)

                    # Only include English content
                    if not title or len(title) < 10 or not is_english_text(title):
                        continue

                    # Check if content matches CMMC keywords
                    content_lower = (title + " " + description).lower()
                    is_cmmc_relevant = any(
                        keyword.lower() in content_lower for keyword in CMMC_KEYWORDS
                    )

                    if is_cmmc_relevant:
                        trend = Trend(
                            title=title,
                            source=f'cmmc_{name.lower().replace(" ", "_")}',
                            url=entry.get("link"),
                            description=self._clean_html(description),
                            category="cmmc",  # Explicit categorization
                            score=1.6,  # Good quality federal news
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"CMMC {name} RSS error: {e}")
                continue

            time.sleep(0.15)

        logger.info(f"CMMC collector found {len(trends)} relevant stories")
        return trends

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""

        # Only parse as HTML if it contains HTML-like content
        # This avoids BeautifulSoup's MarkupResemblesLocatorWarning
        if "<" not in text:
            # No HTML tags, just clean whitespace
            return re.sub(r"\s+", " ", text.strip())[:500]

        # Use 'html.parser' with markup_type to suppress warning
        soup = BeautifulSoup(text, "html.parser")
        clean = soup.get_text(separator=" ").strip()
        return re.sub(r"\s+", " ", clean)[:500]

    def _deduplicate(self):
        """Remove duplicate trends using semantic similarity matching.

        Uses a two-pass approach:
        1. Exact/near-exact matches (word overlap)
        2. Semantic similarity using SequenceMatcher for similar stories
        """
        if not self.trends:
            return

        unique_trends = []
        seen_normalized = []  # List of (normalized_title, words_set)

        for trend in self.trends:
            # Normalize title for comparison
            normalized = trend.title.lower().strip()
            normalized = re.sub(r"[^\w\s]", "", normalized)
            words = set(normalized.split())

            if not words:
                continue

            is_dupe = False

            for seen_norm, seen_words in seen_normalized:
                # Fast check: word overlap (O(1) set operations)
                if seen_words:
                    overlap = len(words & seen_words) / min(len(words), len(seen_words))
                    if overlap > DEDUP_SIMILARITY_THRESHOLD:
                        is_dupe = True
                        logger.debug(
                            f"Duplicate (word overlap {overlap:.0%}): {trend.title[:50]}"
                        )
                        break

                # Semantic check using SequenceMatcher for stories about same event
                # E.g., "Sam Altman fired from OpenAI" vs "OpenAI removes Sam Altman as CEO"
                similarity = SequenceMatcher(None, normalized, seen_norm).ratio()
                if similarity > DEDUP_SEMANTIC_THRESHOLD:
                    is_dupe = True
                    logger.debug(
                        f"Duplicate (semantic {similarity:.0%}): {trend.title[:50]}"
                    )
                    break

            if not is_dupe:
                seen_normalized.append((normalized, words))
                unique_trends.append(trend)

        removed_count = len(self.trends) - len(unique_trends)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate trends")

        self.trends = unique_trends

    def _calculate_scores(self):
        """Recalculate trend scores based on various factors including global keyword frequency."""
        from collections import Counter

        # Count each keyword once per story (using sets) to find "meta-trends"
        # A word appearing in 3+ different stories is a global trend
        story_word_counts = Counter()

        for trend in self.trends:
            # Use set to count each word only once per story
            unique_keywords = set(trend.keywords)
            story_word_counts.update(unique_keywords)

        # Identify global keywords (appearing in 3+ distinct stories)
        global_keywords = {
            word for word, count in story_word_counts.items() if count >= 3
        }

        if global_keywords:
            logger.info(
                f"Found {len(global_keywords)} global keywords: {', '.join(list(global_keywords)[:10])}..."
            )

        # Store for later use (image fetching, word cloud)
        self.global_keywords = global_keywords

        for trend in self.trends:
            # Count how many global keywords this trend contains
            global_keyword_matches = sum(
                1 for kw in trend.keywords if kw in global_keywords
            )

            # Apply tiered boost based on global keyword matches
            # 1 match = 15% boost, 2 matches = 35% boost, 3+ matches = 60% boost
            if global_keyword_matches >= 3:
                trend.score *= 1.6
            elif global_keyword_matches == 2:
                trend.score *= 1.35
            elif global_keyword_matches == 1:
                trend.score *= 1.15

            # Additional small boost for keywords appearing in multiple stories
            keyword_boost = sum(
                0.1 for kw in trend.keywords if story_word_counts.get(kw, 0) > 1
            )
            trend.score += keyword_boost

    def get_global_keywords(self) -> List[str]:
        """Get keywords that appear across multiple stories (meta-trends)."""
        if hasattr(self, "global_keywords"):
            return list(self.global_keywords)
        return []

    def get_top_trends(self, limit: int = 10) -> List[Trend]:
        """Get top N trends by score."""
        return self.trends[:limit]

    def get_all_keywords(self) -> List[str]:
        """Get all unique keywords from trends."""
        keywords = []
        seen = set()

        for trend in self.trends:
            for kw in trend.keywords:
                if kw not in seen:
                    seen.add(kw)
                    keywords.append(kw)

        return keywords

    def to_json(self) -> str:
        """Export trends as JSON."""
        return json.dumps([asdict(t) for t in self.trends], indent=2)

    def save(self, filepath: str):
        """Save trends to a JSON file."""
        with open(filepath, "w") as f:
            f.write(self.to_json())
        logger.info(f"Saved {len(self.trends)} trends to {filepath}")


def main():
    """Main entry point for trend collection."""
    collector = TrendCollector()
    trends = collector.collect_all()

    logger.info("Top 10 Trends:")
    logger.info("-" * 60)

    for i, trend in enumerate(collector.get_top_trends(10), 1):
        logger.info(f"{i:2}. [{trend.source}] {trend.title}")
        logger.info(f"    Keywords: {', '.join(trend.keywords)}")
        logger.info(f"    Score: {trend.score:.2f}")

    # Save to file
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "..", "data", "trends.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    collector.save(output_path)

    return collector


if __name__ == "__main__":
    main()
