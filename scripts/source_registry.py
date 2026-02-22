#!/usr/bin/env python3
"""Source registry and metadata utilities for trend ranking and labeling."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class SourceMetadata:
    """Describes quality and handling metadata for a trend source."""

    tier: int
    source_type: str
    risk: str
    language: str
    parser: str
    fallback_url: Optional[str] = None
    display_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "tier": self.tier,
            "type": self.source_type,
            "risk": self.risk,
            "language": self.language,
            "parser": self.parser,
            "fallback_url": self.fallback_url,
            "display_name": self.display_name,
        }


# Exact source keys from `Trend.source` fields.
EXACT_SOURCE_METADATA: Dict[str, SourceMetadata] = {
    "google_trends": SourceMetadata(
        tier=3,
        source_type="search",
        risk="medium",
        language="en",
        parser="rss",
        fallback_url="https://trends.google.com/trending/rss?geo=US",
        display_name="Google Trends",
    ),
    "hackernews": SourceMetadata(
        tier=2,
        source_type="community",
        risk="low",
        language="en",
        parser="json_api",
        fallback_url="https://hnrss.org/frontpage",
        display_name="Hacker News",
    ),
    "lobsters": SourceMetadata(
        tier=2,
        source_type="community",
        risk="low",
        language="en",
        parser="rss",
        fallback_url="https://lobste.rs/rss",
        display_name="Lobsters",
    ),
    "github_trending": SourceMetadata(
        tier=3,
        source_type="community",
        risk="low",
        language="en",
        parser="html_scrape",
        fallback_url="https://api.gitterapp.com/repositories?language=python&since=daily",
        display_name="GitHub Trending",
    ),
    "product_hunt": SourceMetadata(
        tier=3,
        source_type="product",
        risk="low",
        language="en",
        parser="rss",
        fallback_url="https://www.producthunt.com/feed",
        display_name="Product Hunt",
    ),
    "devto": SourceMetadata(
        tier=3,
        source_type="community",
        risk="low",
        language="en",
        parser="json_api",
        fallback_url="https://dev.to/api/articles?top=1&per_page=15",
        display_name="Dev.to",
    ),
    "slashdot": SourceMetadata(
        tier=3,
        source_type="news",
        risk="low",
        language="en",
        parser="rss",
        fallback_url="https://rss.slashdot.org/Slashdot/slashdotMain",
        display_name="Slashdot",
    ),
    "ars_features": SourceMetadata(
        tier=2,
        source_type="news",
        risk="low",
        language="en",
        parser="rss",
        fallback_url="https://feeds.arstechnica.com/arstechnica/features",
        display_name="Ars Features",
    ),
    "wikipedia_current": SourceMetadata(
        tier=3,
        source_type="reference",
        risk="low",
        language="en",
        parser="html_scrape",
        fallback_url="https://en.wikipedia.org/w/api.php?action=parse&page=Portal:Current_events&format=json&prop=text&formatversion=2",
        display_name="Wikipedia Current",
    ),
    "cmmc_linkedin": SourceMetadata(
        tier=3,
        source_type="social",
        risk="medium",
        language="en",
        parser="apify",
        fallback_url=None,
        display_name="LinkedIn",
    ),
}

# Prefix metadata catches the generated source keys like `news_bbc`, `reddit_science`.
PREFIX_SOURCE_METADATA: Tuple[Tuple[str, SourceMetadata], ...] = (
    (
        "news_",
        SourceMetadata(
            tier=1,
            source_type="news",
            risk="low",
            language="en",
            parser="rss",
            display_name="News",
        ),
    ),
    (
        "politics_",
        SourceMetadata(
            tier=2,
            source_type="news",
            risk="low",
            language="en",
            parser="rss",
            display_name="Politics",
        ),
    ),
    (
        "science_",
        SourceMetadata(
            tier=2,
            source_type="news",
            risk="low",
            language="en",
            parser="rss",
            display_name="Science",
        ),
    ),
    (
        "finance_",
        SourceMetadata(
            tier=2,
            source_type="news",
            risk="low",
            language="en",
            parser="rss",
            display_name="Finance",
        ),
    ),
    (
        "sports_",
        SourceMetadata(
            tier=3,
            source_type="news",
            risk="low",
            language="en",
            parser="rss",
            display_name="Sports",
        ),
    ),
    (
        "entertainment_",
        SourceMetadata(
            tier=3,
            source_type="news",
            risk="low",
            language="en",
            parser="rss",
            display_name="Entertainment",
        ),
    ),
    (
        "tech_",
        SourceMetadata(
            tier=2,
            source_type="news",
            risk="low",
            language="en",
            parser="rss",
            display_name="Tech",
        ),
    ),
    (
        "reddit_",
        SourceMetadata(
            tier=4,
            source_type="social",
            risk="medium",
            language="en",
            parser="rss",
            display_name="Reddit",
        ),
    ),
    (
        "cmmc_reddit_",
        SourceMetadata(
            tier=4,
            source_type="social",
            risk="medium",
            language="en",
            parser="rss",
            display_name="Reddit",
        ),
    ),
    (
        "cmmc_",
        SourceMetadata(
            tier=2,
            source_type="compliance",
            risk="low",
            language="en",
            parser="rss",
            display_name="CMMC",
        ),
    ),
)

DEFAULT_SOURCE_METADATA = SourceMetadata(
    tier=4,
    source_type="other",
    risk="medium",
    language="en",
    parser="unknown",
    display_name="Source",
)


def _humanize_source(source: str) -> str:
    """Convert an internal source key to a UI-friendly label."""
    if not source:
        return "Source"
    words = re.findall(r"[A-Za-z0-9]+", source.replace("_", " ").replace("-", " "))
    if not words:
        return "Source"
    cleaned = [w.upper() if len(w) <= 3 else w.capitalize() for w in words]
    return " ".join(cleaned)


def get_source_metadata(source: str) -> SourceMetadata:
    """Resolve metadata by exact source key first, then prefix rules."""
    if source in EXACT_SOURCE_METADATA:
        return EXACT_SOURCE_METADATA[source]

    for prefix, metadata in PREFIX_SOURCE_METADATA:
        if source.startswith(prefix):
            return metadata

    return DEFAULT_SOURCE_METADATA


def source_metadata_dict(source: str) -> Dict[str, Optional[str]]:
    """Get metadata as a serializable dict with resolved display name."""
    metadata = get_source_metadata(source)
    data = metadata.to_dict()
    if not data.get("display_name"):
        data["display_name"] = _humanize_source(source)
    return data


def format_source_label(source: str) -> str:
    """Format a compact source label with quality context for UI badges."""
    data = source_metadata_dict(source)
    display = data.get("display_name") or _humanize_source(source)
    tier = data.get("tier", 4)
    risk = data.get("risk", "medium")
    return f"{display} [T{tier}/{str(risk).upper()}]"


def source_quality_multiplier(source: str) -> float:
    """Source-quality multiplier for ranking scores."""
    metadata = get_source_metadata(source)

    # Tier factor: lower number (Tier 1) gets stronger boost.
    tier_boost = {
        1: 1.30,
        2: 1.18,
        3: 1.05,
        4: 0.95,
    }.get(metadata.tier, 0.90)

    # Risk factor: high-risk sources get a small downweight.
    risk_adjustment = {
        "low": 1.00,
        "medium": 0.95,
        "high": 0.88,
    }.get(metadata.risk, 0.95)

    return tier_boost * risk_adjustment
