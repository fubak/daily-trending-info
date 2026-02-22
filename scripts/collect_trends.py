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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, List, Dict, Optional, Tuple
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
    CMMC_LINKEDIN_PROFILES,
    setup_logging,
)
from source_registry import (
    source_metadata_dict,
    format_source_label,
    source_quality_multiplier,
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


def _normalize_datetime(value: datetime) -> datetime:
    """Convert timezone-aware datetimes to naive UTC for consistent comparisons."""
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Best-effort timestamp parser for API and feed values."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return _normalize_datetime(value)

    if isinstance(value, (int, float)):
        # LinkedIn/other APIs may return milliseconds.
        ts_value = float(value)
        if ts_value > 10_000_000_000:
            ts_value = ts_value / 1000.0
        try:
            return datetime.fromtimestamp(ts_value, tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        # Common ISO formats
        normalized = cleaned.replace("Z", "+00:00")
        try:
            return _normalize_datetime(datetime.fromisoformat(normalized))
        except ValueError:
            pass

        # RFC2822 / pubDate-like strings
        try:
            return _normalize_datetime(parsedate_to_datetime(cleaned))
        except (TypeError, ValueError):
            pass

        # Date-only format fallback
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue

    return None


def parse_feed_entry_timestamp(entry) -> Optional[datetime]:
    """Extract and parse timestamp fields from feedparser entries."""
    # feedparser exposes parsed fields as struct_time
    for parsed_key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed_value = entry.get(parsed_key)
        if parsed_value:
            try:
                return datetime(*parsed_value[:6])
            except Exception:
                continue

    # Fallback to string fields
    for key in ("published", "updated", "created", "dc_date", "pubDate"):
        parsed = parse_timestamp(entry.get(key))
        if parsed:
            return parsed

    return None


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
    source_metadata: Dict[str, Optional[str]] = None
    source_label: Optional[str] = None
    corroborating_sources: List[str] = None
    corroborating_urls: List[str] = None
    source_diversity: int = 1

    def __post_init__(self):
        parsed_timestamp = parse_timestamp(self.timestamp)
        self.timestamp = parsed_timestamp or datetime.now()

        if self.keywords is None:
            self.keywords = self._extract_keywords()

        if self.source_metadata is None:
            self.source_metadata = source_metadata_dict(self.source)

        if self.source_label is None:
            self.source_label = format_source_label(self.source)

        if self.corroborating_sources is None:
            self.corroborating_sources = [self.source]
        elif self.source not in self.corroborating_sources:
            self.corroborating_sources.append(self.source)

        if self.corroborating_urls is None:
            self.corroborating_urls = [self.url] if self.url else []
        elif self.url and self.url not in self.corroborating_urls:
            self.corroborating_urls.append(self.url)

        self.source_diversity = max(1, len(set(self.corroborating_sources)))

    def is_fresh(self, max_hours: int = TREND_FRESHNESS_HOURS) -> bool:
        """Check if this trend is from within the specified hours."""
        if not self.timestamp:
            return True  # Assume fresh if no timestamp
        age = datetime.now() - self.timestamp
        return age < timedelta(hours=max_hours)

    def register_corroboration(self, other: "Trend") -> None:
        """Merge corroborating source details from a duplicate/related trend."""
        other_sources = other.corroborating_sources or [other.source]
        for source in other_sources:
            if source and source not in self.corroborating_sources:
                self.corroborating_sources.append(source)

        other_urls = other.corroborating_urls
        if other_urls is None:
            other_urls = [other.url] if other.url else []
        for url in other_urls:
            if url and url not in self.corroborating_urls:
                self.corroborating_urls.append(url)

        # Prefer richer descriptions and available images from corroborating stories.
        if not self.description and other.description:
            self.description = other.description
        elif other.description and len(other.description) > len(self.description or ""):
            self.description = other.description

        if not self.image_url and other.image_url:
            self.image_url = other.image_url

        if other.timestamp and other.timestamp > self.timestamp:
            self.timestamp = other.timestamp

        self.source_diversity = max(1, len(set(self.corroborating_sources)))

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
        self.default_timeout = float(TIMEOUTS.get("default", 15))
        self.feed_timeout = float(TIMEOUTS.get("rss_feed", self.default_timeout))
        self.hn_story_timeout = float(TIMEOUTS.get("hackernews_story", 5))
        self.request_delay = float(DELAYS.get("between_requests", 0.15))

    def _get_limit(self, key: str, fallback: int) -> int:
        """Resolve configured collection limits with a safe fallback."""
        return max(1, int(LIMITS.get(key, fallback)))

    def _fetch_rss(
        self,
        url: str,
        timeout: Optional[float] = None,
        allowed_status: tuple = (200, 301, 302),
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[requests.Response]:
        timeout = timeout or self.feed_timeout
        try:
            response = self.session.get(url, timeout=timeout, headers=headers)
        except Exception as exc:
            logger.warning(f"RSS fetch error for {url}: {exc}")
            return None

        if response.status_code not in allowed_status:
            logger.warning(
                f"RSS fetch: unexpected status {response.status_code} for {url}"
            )
            return None

        content_type = response.headers.get("content-type", "").lower()
        if "xml" not in content_type and "rss" not in content_type:
            head = response.content[:120].lower()
            if b"<rss" not in head and b"<?xml" not in head and b"<feed" not in head:
                logger.warning(
                    f"RSS fetch: non-feed response for {url} (content-type: {content_type or 'unknown'})"
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
        limit = self._get_limit("sports_rss", 6)
        feeds = [
            ("ESPN", "https://www.espn.com/espn/rss/news"),
            ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
            ("CBS Sports", "https://www.cbssports.com/rss/headlines/"),
            ("Yahoo Sports", "https://sports.yahoo.com/rss/"),
        ]

        for name, url in feeds:
            try:
                response = self._fetch_rss(url)
                if not response:
                    continue

                feed = feedparser.parse(response.content)
                for entry in feed.entries[:limit]:
                    if is_english_text(entry.title):
                        trend = Trend(
                            title=entry.title,
                            source=f'sports_{name.lower().replace(" ", "")}',
                            url=entry.link,
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.4,
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)
            except Exception as exc:
                logger.warning(f"{name} sports RSS error: {exc}")
                continue

            time.sleep(self.request_delay)
        return trends

    def _collect_entertainment_rss(self) -> List[Trend]:
        """Collect trends from Entertainment RSS feeds."""
        trends = []
        limit = self._get_limit("entertainment_rss", 6)
        feeds = [
            ("Variety", "https://variety.com/feed/"),
            ("Hollywood Reporter", "https://www.hollywoodreporter.com/feed/"),
            ("Billboard", "https://www.billboard.com/feed/"),
            ("E! Online", "https://www.eonline.com/syndication/rss/top_stories/en_us"),
        ]

        for name, url in feeds:
            try:
                response = self._fetch_rss(url)
                if not response:
                    continue

                feed = feedparser.parse(response.content)
                for entry in feed.entries[:limit]:
                    if is_english_text(entry.title):
                        trend = Trend(
                            title=entry.title,
                            source=f'entertainment_{name.lower().replace(" ", "")}',
                            url=entry.link,
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.4,
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)
            except Exception as exc:
                logger.warning(f"{name} entertainment RSS error: {exc}")
                continue

            time.sleep(self.request_delay)
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
                time.sleep(DELAYS.get("between_images", 0.3))

        logger.info(f"  Scraped {scraped_count} additional images from OG tags")

        logger.info(f"Total unique trends: {len(self.trends)}")
        return self.trends

    def get_freshness_ratio(self) -> float:
        """Calculate the ratio of fresh trends (from past 24 hours)."""
        if not self.trends:
            return 1.0
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
        limit = self._get_limit("google_trends", 20)

        # Google Trends Daily RSS
        url = "https://trends.google.com/trending/rss?geo=US"

        try:
            response = self._fetch_rss(url, timeout=self.feed_timeout)
            if not response:
                return trends

            feed = feedparser.parse(response.content)

            for entry in feed.entries[:limit]:
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
                        timestamp=parse_feed_entry_timestamp(entry),
                        image_url=self._extract_image_from_entry(entry),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Google Trends error: {e}")

        return trends

    def _collect_news_rss(self) -> List[Trend]:
        """Collect trends from major news RSS feeds."""
        trends = []
        limit = self._get_limit("news_rss", 8)

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
                timeout = self.feed_timeout if "washingtonpost" in url else self.default_timeout
                response = self._fetch_rss(url, timeout=timeout)
                if not response:
                    continue

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:limit]:
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
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(self.request_delay)

        return trends

    def _collect_tech_rss(self) -> List[Trend]:
        """Collect trends from tech-focused RSS feeds."""
        trends = []
        limit = self._get_limit("tech_rss", 6)

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
                response = self._fetch_rss(url, timeout=self.default_timeout)
                if not response:
                    continue

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:limit]:
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
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(self.request_delay)

        return trends

    def _collect_science_rss(self) -> List[Trend]:
        """Collect trends from science and health RSS feeds."""
        trends = []
        limit = self._get_limit("science_rss", 6)

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
                response = self._fetch_rss(url, timeout=self.default_timeout)
                if not response:
                    continue

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:limit]:
                    title = entry.get("title", "").strip()
                    title = re.sub(r"\s+", " ", title)

                    if title and len(title) > 10 and is_english_text(title):
                        trend = Trend(
                            title=title,
                            source=f'science_{name.lower().replace(" ", "_").replace(".", "")}',
                            url=entry.get("link"),
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.5,
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(self.request_delay)

        return trends

    def _collect_politics_rss(self) -> List[Trend]:
        """Collect trends from politics-focused RSS feeds."""
        trends = []
        limit = self._get_limit("politics_rss", 6)

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
                response = self._fetch_rss(url, timeout=self.default_timeout)
                if not response:
                    continue

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:limit]:
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
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(self.request_delay)

        return trends

    def _collect_finance_rss(self) -> List[Trend]:
        """Collect trends from business and finance RSS feeds."""
        trends = []
        limit = self._get_limit("finance_rss", 6)

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
                response = self._fetch_rss(url, timeout=self.default_timeout)
                if not response:
                    continue

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:limit]:
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
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"{name} RSS error: {e}")
                continue

            time.sleep(self.request_delay)

        return trends

    def _collect_hackernews(self) -> List[Trend]:
        """Collect top stories from Hacker News API."""
        trends = []
        limit = self._get_limit("hackernews", 25)

        try:
            # Get top story IDs
            response = self.session.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=self.default_timeout,
            )
            response.raise_for_status()

            story_ids = response.json()[: max(limit * 2, limit)]

            def _fetch_story(index: int, story_id: int) -> Optional[Tuple[int, Trend]]:
                try:
                    story_response = self.session.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                        timeout=self.hn_story_timeout,
                    )
                    story_response.raise_for_status()
                    story = story_response.json()
                except Exception:
                    return None

                title = (story or {}).get("title", "")
                if not title or not is_english_text(title):
                    return None

                score = story.get("score", 0)
                normalized_score = min(score / 100, 3.0)
                story_url = story.get("url") or f"https://news.ycombinator.com/item?id={story_id}"

                trend = Trend(
                    title=title,
                    source="hackernews",
                    url=story_url,
                    description=self._clean_html(story.get("text", "")),
                    score=1.0 + normalized_score,
                    timestamp=parse_timestamp(story.get("time")),
                )
                return (index, trend)

            max_workers = max(2, min(8, limit // 2 or 2))
            fetched: List[Tuple[int, Trend]] = []

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(_fetch_story, idx, story_id)
                    for idx, story_id in enumerate(story_ids)
                ]
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        fetched.append(result)

            fetched.sort(key=lambda item: item[0])
            trends = [trend for _, trend in fetched[:limit]]

        except Exception as e:
            logger.warning(f"Hacker News error: {e}")

        return trends

    def _collect_reddit(self) -> List[Trend]:
        """Collect trending posts from Reddit using RSS feeds (more reliable than JSON API)."""
        trends = []
        limit = self._get_limit("reddit", 6)
        reddit_headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
                "DailyTrendingBot/1.0"
            ),
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        }

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
                response = self._fetch_rss(
                    url, timeout=self.feed_timeout, headers=reddit_headers
                )
                if not response:
                    continue

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:limit]:
                    title = entry.get("title", "").strip()

                    # Only include English content
                    if title and len(title) > 15 and is_english_text(title):
                        trend = Trend(
                            title=title,
                            source=f"reddit_{subreddit}",
                            url=entry.get("link"),
                            description=self._clean_html(entry.get("summary", "")),
                            score=1.5,
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)

            except Exception as e:
                logger.warning(f"Reddit r/{subreddit} RSS error: {e}")
                continue

            time.sleep(self.request_delay)

        return trends

    def _collect_github_trending(self) -> List[Trend]:
        """Collect trending repositories from GitHub (English descriptions)."""
        trends = []
        limit = self._get_limit("github_trending", 15)

        try:
            # GitHub trending page with English spoken language filter
            url = "https://github.com/trending?since=daily&spoken_language_code=en"
            response = self.session.get(url, timeout=self.default_timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            repos = soup.select("article.Box-row")[:limit]

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
                        timestamp=parse_timestamp(datetime.now(timezone.utc)),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"GitHub Trending error: {e}")

        if len(trends) >= max(3, limit // 2):
            return trends[:limit]

        logger.warning(
            "GitHub Trending HTML parser yielded limited results, using API fallback"
        )
        fallback = self._collect_github_trending_api(limit)
        if not trends:
            return fallback[:limit]

        seen_urls = {t.url for t in trends if t.url}
        for trend in fallback:
            if trend.url and trend.url in seen_urls:
                continue
            trends.append(trend)
            if trend.url:
                seen_urls.add(trend.url)
            if len(trends) >= limit:
                break

        return trends[:limit]

    def _collect_github_trending_api(self, limit: int) -> List[Trend]:
        """Fallback collector using GitHub's repository search API."""
        trends = []
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        per_page = max(10, min(limit, 50))

        try:
            response = self.session.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"created:>{since}",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": per_page,
                },
                timeout=self.default_timeout,
                headers={"Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            items = response.json().get("items", [])
        except Exception as exc:
            logger.warning(f"GitHub Trending API fallback failed: {exc}")
            return trends

        for repo in items[:limit]:
            name = repo.get("full_name") or repo.get("name")
            if not name:
                continue

            description = (repo.get("description") or "").strip()
            language = (repo.get("language") or "").strip()
            stars = int(repo.get("stargazers_count", 0) or 0)

            title = name
            if language:
                title += f" ({language})"
            if description:
                title += f": {description[:80]}"

            if description and not is_english_text(description):
                continue

            trends.append(
                Trend(
                    title=title[:120],
                    source="github_trending",
                    url=repo.get("html_url"),
                    description=description,
                    score=1.2 + min(stars / 50000, 2.0),
                    timestamp=parse_timestamp(repo.get("updated_at") or repo.get("created_at")),
                )
            )

        return trends

    def _collect_wikipedia_current(self) -> List[Trend]:
        """Collect current events from Wikipedia."""
        trends = []
        limit = self._get_limit("wikipedia", 20)
        page_url = "https://en.wikipedia.org/wiki/Portal:Current_events"

        try:
            response = self.session.get(page_url, timeout=self.default_timeout)
            response.raise_for_status()
            trends = self._parse_wikipedia_current_html(response.text, limit, page_url)
        except Exception as e:
            logger.warning(f"Wikipedia Current Events HTML scrape error: {e}")

        if len(trends) >= max(3, limit // 3):
            return trends[:limit]

        try:
            response = self.session.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "parse",
                    "page": "Portal:Current_events",
                    "prop": "text",
                    "format": "json",
                    "formatversion": "2",
                },
                timeout=self.default_timeout,
            )
            response.raise_for_status()
            payload = response.json()
            html_content = payload.get("parse", {}).get("text", "")
            if html_content:
                api_trends = self._parse_wikipedia_current_html(html_content, limit, page_url)
                if not trends:
                    trends = api_trends
                else:
                    seen_titles = {re.sub(r"[^\w\s]", "", t.title.lower()) for t in trends}
                    for trend in api_trends:
                        normalized = re.sub(r"[^\w\s]", "", trend.title.lower())
                        if normalized in seen_titles:
                            continue
                        trends.append(trend)
                        seen_titles.add(normalized)
                        if len(trends) >= limit:
                            break
        except Exception as e:
            logger.warning(f"Wikipedia Current Events API fallback error: {e}")

        return trends

    def _parse_wikipedia_current_html(
        self, html_content: str, limit: int, base_url: str
    ) -> List[Trend]:
        """Parse Wikipedia Current Events HTML into trends."""
        soup = BeautifulSoup(html_content, "html.parser")
        candidate_items = []

        selectors = [
            ".current-events-content li",
            "#mw-content-text .current-events-content li",
            "#mw-content-text .vevent li",
            ".vevent li",
        ]
        for selector in selectors:
            candidate_items = soup.select(selector)
            if candidate_items:
                break

        if not candidate_items:
            return []

        trends = []
        seen_titles = set()

        for item in candidate_items[: max(limit * 3, limit)]:
            text = item.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"\[[^\]]+\]", "", text).strip()

            if not text or len(text) < 20 or len(text) > 220:
                continue
            if not is_english_text(text):
                continue

            normalized = re.sub(r"[^\w\s]", "", text.lower())
            if normalized in seen_titles:
                continue
            seen_titles.add(normalized)

            story_url = None
            link = item.select_one("a")
            if link:
                href = link.get("href", "")
                if href.startswith("/wiki/"):
                    story_url = f"https://en.wikipedia.org{href}"
                elif href.startswith("http"):
                    story_url = href

            trends.append(
                Trend(
                    title=text[:150],
                    source="wikipedia_current",
                    url=story_url or base_url,
                    score=1.4,
                    timestamp=parse_timestamp(datetime.now(timezone.utc)),
                )
            )
            if len(trends) >= limit:
                break

        return trends

    def _collect_lobsters(self) -> List[Trend]:
        """Collect trending posts from Lobsters (tech community)."""
        trends = []
        limit = self._get_limit("lobsters", 15)

        try:
            # Main RSS feed - hottest.rss was removed, use main feed
            url = "https://lobste.rs/rss"
            response = self._fetch_rss(url, timeout=self.feed_timeout)
            if not response:
                return trends

            feed = feedparser.parse(response.content)

            # Check if feed parsed successfully
            if not feed.entries and feed.bozo:
                logger.warning(f"Lobsters feed parse error: {feed.bozo_exception}")
                return trends

            for entry in feed.entries[:limit]:
                title = entry.get("title", "").strip()

                if title and len(title) > 10 and is_english_text(title):
                    trend = Trend(
                        title=title,
                        source="lobsters",
                        url=entry.get("link"),
                        description=self._clean_html(entry.get("summary", "")),
                        score=1.6,  # Good quality tech content
                        timestamp=parse_feed_entry_timestamp(entry),
                        image_url=self._extract_image_from_entry(entry),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Lobsters error: {e}")

        return trends

    def _collect_product_hunt(self) -> List[Trend]:
        """Collect trending products from Product Hunt."""
        trends = []
        limit = self._get_limit("product_hunt", 10)

        try:
            # Product Hunt RSS feed
            url = "https://www.producthunt.com/feed"
            response = self._fetch_rss(url, timeout=self.feed_timeout)
            if not response:
                return trends

            feed = feedparser.parse(response.content)

            for entry in feed.entries[:limit]:
                title = entry.get("title", "").strip()

                if title and len(title) > 5 and is_english_text(title):
                    trend = Trend(
                        title=title,
                        source="product_hunt",
                        url=entry.get("link"),
                        description=self._clean_html(entry.get("summary", "")),
                        score=1.4,
                        timestamp=parse_feed_entry_timestamp(entry),
                        image_url=self._extract_image_from_entry(entry),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Product Hunt error: {e}")

        return trends

    def _collect_devto(self) -> List[Trend]:
        """Collect trending posts from Dev.to."""
        trends = []
        limit = self._get_limit("devto", 15)

        try:
            # Dev.to top articles API
            url = f"https://dev.to/api/articles?top=1&per_page={limit}"
            response = self.session.get(url, timeout=self.default_timeout)
            response.raise_for_status()

            articles = response.json()
            if not isinstance(articles, list):
                return trends

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
                        timestamp=parse_timestamp(
                            article.get("published_timestamp")
                            or article.get("published_at")
                            or article.get("readable_publish_date")
                        ),
                        image_url=article.get("cover_image"),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Dev.to error: {e}")

        return trends

    def _collect_slashdot(self) -> List[Trend]:
        """Collect stories from Slashdot."""
        trends = []
        limit = self._get_limit("slashdot", 12)

        try:
            url = "https://rss.slashdot.org/Slashdot/slashdotMain"
            response = self._fetch_rss(url, timeout=self.feed_timeout)
            if not response:
                return trends

            feed = feedparser.parse(response.content)

            for entry in feed.entries[:limit]:
                title = entry.get("title", "").strip()

                if title and len(title) > 10 and is_english_text(title):
                    trend = Trend(
                        title=title,
                        source="slashdot",
                        url=entry.get("link"),
                        description=self._clean_html(entry.get("summary", "")),
                        score=1.4,
                        timestamp=parse_feed_entry_timestamp(entry),
                        image_url=self._extract_image_from_entry(entry),
                    )
                    trends.append(trend)

        except Exception as e:
            logger.warning(f"Slashdot error: {e}")

        return trends

    def _collect_ars_frontpage(self) -> List[Trend]:
        """Collect front page stories from Ars Technica (high quality tech journalism)."""
        trends = []
        limit = self._get_limit("ars_technica", 8)

        try:
            url = "https://feeds.arstechnica.com/arstechnica/features"
            response = self._fetch_rss(url, timeout=self.feed_timeout)
            if not response:
                return trends

            feed = feedparser.parse(response.content)

            for entry in feed.entries[:limit]:
                title = entry.get("title", "").strip()
                title = title.replace(" | Ars Technica", "")

                if title and len(title) > 10 and is_english_text(title):
                    trend = Trend(
                        title=title,
                        source="ars_features",
                        url=entry.get("link"),
                        description=self._clean_html(entry.get("summary", "")),
                        score=1.7,  # High quality long-form content
                        timestamp=parse_feed_entry_timestamp(entry),
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
        rss_limit = self._get_limit("cmmc_rss", 8)
        keyword_scan_limit = max(20, rss_limit * 3)
        reddit_limit = max(6, min(15, rss_limit * 2))

        # Federal IT, defense, and cybersecurity news sources
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
            # Defense-focused sources
            ("Breaking Defense", "https://breakingdefense.com/feed/"),
            ("Defense One", "https://www.defenseone.com/rss/all/"),
            (
                "Defense News",
                "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
            ),
            ("ExecutiveGov", "https://executivegov.com/feed/"),
            # SC Media removed - returns 403 Forbidden for automated access
        ]

        for name, url in feeds:
            try:
                response = self._fetch_rss(url, timeout=self.feed_timeout)
                if not response:
                    continue

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:keyword_scan_limit]:
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
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)
                        if len(trends) >= rss_limit * len(feeds):
                            break

            except Exception as e:
                logger.warning(f"CMMC {name} RSS error: {e}")
                continue

            time.sleep(self.request_delay)

        logger.info(f"CMMC collector found {len(trends)} stories from RSS feeds")

        # Collect from CMMC-related Reddit communities
        cmmc_subreddits = [
            ("CMMC", "https://www.reddit.com/r/CMMC/.rss"),
            ("NISTControls", "https://www.reddit.com/r/NISTControls/.rss"),
            ("FederalEmployees", "https://www.reddit.com/r/FederalEmployees/.rss"),
        ]

        reddit_count = 0
        reddit_headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
                "CMMCWatch/1.0"
            ),
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        }

        for name, url in cmmc_subreddits:
            try:
                response = self._fetch_rss(
                    url,
                    timeout=self.feed_timeout,
                    headers=reddit_headers,
                )
                if not response:
                    continue

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:reddit_limit]:
                    title = entry.get("title", "").strip()
                    description = entry.get("summary", "")

                    # Clean up title
                    title = re.sub(r"\s+", " ", title)

                    if not title or len(title) < 10:
                        continue

                    # For CMMC and NISTControls subreddits, include all posts
                    # For others, apply keyword filter
                    include_post = False
                    if name in ["CMMC", "NISTControls"]:
                        include_post = True  # These are highly relevant by default
                    else:
                        # Check if content matches CMMC keywords
                        content_lower = (title + " " + description).lower()
                        include_post = any(
                            keyword.lower() in content_lower
                            for keyword in CMMC_KEYWORDS
                        )

                    if include_post:
                        trend = Trend(
                            title=title,
                            source=f"cmmc_reddit_{name.lower()}",
                            url=entry.get("link"),
                            description=self._clean_html(description),
                            category="cmmc",
                            score=1.4,  # Reddit community content
                            timestamp=parse_feed_entry_timestamp(entry),
                            image_url=self._extract_image_from_entry(entry),
                        )
                        trends.append(trend)
                        reddit_count += 1

            except Exception as e:
                logger.warning(f"CMMC Reddit r/{name} error: {e}")
                continue

            time.sleep(self.request_delay)

        logger.info(f"CMMC collector: {len(trends)} total ({reddit_count} from Reddit)")

        # Collect from LinkedIn influencers (if configured)
        linkedin_count = 0
        if CMMC_LINKEDIN_PROFILES:
            linkedin_trends = self._collect_cmmc_linkedin()
            trends.extend(linkedin_trends)
            linkedin_count = len(linkedin_trends)
            logger.info(f"CMMC LinkedIn: {linkedin_count} posts from influencers")

        logger.info(
            f"CMMC total: {len(trends)} "
            f"(RSS: {len(trends) - reddit_count - linkedin_count}, "
            f"Reddit: {reddit_count}, LinkedIn: {linkedin_count})"
        )
        return trends

    def _collect_cmmc_linkedin(self) -> List[Trend]:
        """Collect posts from key CMMC influencers on LinkedIn via Apify."""
        trends = []

        try:
            from fetch_linkedin_posts import (
                fetch_linkedin_posts,
                linkedin_posts_to_trends,
            )

            # Fetch LinkedIn posts
            posts = fetch_linkedin_posts(CMMC_LINKEDIN_PROFILES)

            # Convert to trend format
            trend_dicts = linkedin_posts_to_trends(posts)

            # Convert to Trend objects
            for td in trend_dicts:
                trend = Trend(
                    title=td["title"],
                    source=td["source"],
                    url=td.get("url"),
                    description=td.get("description"),
                    category=td.get("category"),
                    score=td.get("score", 1.5),
                    keywords=td.get("keywords"),
                    timestamp=parse_timestamp(td.get("timestamp") or td.get("published_at")),
                    image_url=td.get("image_url"),
                )
                trends.append(trend)

        except ImportError:
            logger.debug("LinkedIn scraping not available (apify-client not installed)")
        except Exception as e:
            logger.warning(f"CMMC LinkedIn collection error: {e}")

        return trends

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""

        # Only parse as HTML if it contains HTML-like content
        # This avoids BeautifulSoup's MarkupResemblesLocatorWarning
        if "<" not in text:
            # No HTML tags, just clean whitespace
            clean = text.strip()
        else:
            # Use 'html.parser' with markup_type to suppress warning
            soup = BeautifulSoup(text, "html.parser")
            clean = soup.get_text(separator=" ").strip()
        
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean)
        
        # Smart truncation at sentence boundaries (up to 1500 chars)
        max_length = 1500
        if len(clean) > max_length:
            truncated = clean[:max_length]
            # Find last sentence boundary
            last_period = max(
                truncated.rfind('. '),
                truncated.rfind('! '),
                truncated.rfind('? ')
            )
            
            # If found a good sentence boundary with reasonable content
            if last_period > 300:
                return clean[:last_period + 1]
            else:
                # Fall back to word boundary
                last_space = truncated.rfind(' ')
                if last_space > 200:
                    return clean[:last_space] + "..."
                else:
                    return clean[:max_length] + "..."
        
        return clean

    def _deduplicate(self):
        """Remove duplicate trends using semantic similarity matching.

        Uses a two-pass approach:
        1. Exact/near-exact matches (word overlap)
        2. Semantic similarity using SequenceMatcher for similar stories
        """
        if not self.trends:
            return

        clusters: List[Dict[str, Any]] = []

        for trend in self.trends:
            # Normalize title for comparison
            normalized = trend.title.lower().strip()
            normalized = re.sub(r"[^\w\s]", "", normalized)
            words = set(normalized.split())

            if not words:
                continue

            match_idx = None
            match_reason = ""
            match_value = 0.0

            for idx, cluster in enumerate(clusters):
                seen_norm = cluster["normalized"]
                seen_words = cluster["words"]

                overlap = 0.0
                if seen_words:
                    overlap = len(words & seen_words) / min(len(words), len(seen_words))
                if overlap > DEDUP_SIMILARITY_THRESHOLD:
                    match_idx = idx
                    match_reason = "word overlap"
                    match_value = overlap
                    break

                # Semantic check using SequenceMatcher for same-event headlines.
                similarity = SequenceMatcher(None, normalized, seen_norm).ratio()
                if similarity > DEDUP_SEMANTIC_THRESHOLD:
                    match_idx = idx
                    match_reason = "semantic"
                    match_value = similarity
                    break

                # Order-insensitive token similarity catches wording rearrangements.
                token_similarity = SequenceMatcher(
                    None,
                    " ".join(sorted(words)),
                    " ".join(sorted(seen_words)),
                ).ratio()
                if token_similarity > DEDUP_SEMANTIC_THRESHOLD:
                    match_idx = idx
                    match_reason = "token semantic"
                    match_value = token_similarity
                    break

            if match_idx is None:
                clusters.append(
                    {"trend": trend, "normalized": normalized, "words": words}
                )
                continue

            cluster = clusters[match_idx]
            canonical = cluster["trend"]
            canonical_quality = canonical.score * source_quality_multiplier(
                canonical.source
            )
            candidate_quality = trend.score * source_quality_multiplier(trend.source)

            if candidate_quality > canonical_quality:
                trend.register_corroboration(canonical)
                cluster["trend"] = trend
                cluster["normalized"] = normalized
                cluster["words"] = words
                logger.debug(
                    f"Duplicate ({match_reason} {match_value:.0%}) promoted: {trend.title[:50]}"
                )
            else:
                canonical.register_corroboration(trend)
                logger.debug(
                    f"Duplicate ({match_reason} {match_value:.0%}) merged: {trend.title[:50]}"
                )

        unique_trends = [cluster["trend"] for cluster in clusters]
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

            # Apply source quality calibration from the source registry.
            trend.score *= source_quality_multiplier(trend.source)

            # Reward stories corroborated by multiple independent sources.
            if trend.source_diversity > 1:
                diversity_boost = 1.0 + min((trend.source_diversity - 1) * 0.08, 0.35)
                trend.score *= diversity_boost

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
