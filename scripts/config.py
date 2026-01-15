#!/usr/bin/env python3
"""
Configuration settings for DailyTrending.info pipeline.

Centralizes all magic numbers, timeouts, and environment-specific settings.
"""

import os
import logging
from pathlib import Path

# ============================================================================
# ENVIRONMENT
# ============================================================================

# Detect environment
ENV = os.getenv("ENVIRONMENT", "production")
DEBUG = ENV == "development" or os.getenv("DEBUG", "").lower() == "true"

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
PUBLIC_DIR = PROJECT_ROOT / "public"

# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# TREND COLLECTION LIMITS
# ============================================================================

# Per-source limits (how many items to fetch from each source)
# Balanced for diverse content: World/General news gets more weight
LIMITS = {
    # General/World News (higher limits)
    "google_trends": 20,
    "news_rss": 10,  # Per feed - increased from 8
    "wikipedia": 20,
    # Reddit (balanced across categories)
    "reddit": 8,  # Per subreddit
    # Tech sources (reduced for balance)
    "tech_rss": 5,  # Per feed - reduced from 6
    "hackernews": 15,  # Reduced from 25
    "lobsters": 10,  # Reduced from 20
    "product_hunt": 8,  # Reduced from 15
    "devto": 8,  # Reduced from 15
    "slashdot": 6,  # Reduced from 10
    "ars_technica": 6,  # Reduced from 10
    "github_trending": 10,  # Reduced from 15
    # Other categories
    "science_rss": 8,  # Science news
    "politics_rss": 8,  # Politics news
    "finance_rss": 8,  # Finance/Business news
    "sports_rss": 6,  # Sports news
    "entertainment_rss": 6,  # Entertainment news
    "cmmc_rss": 8,  # CMMC/Federal compliance news
}

# ============================================================================
# CMMC WATCH KEYWORDS
# ============================================================================

# Keywords for filtering CMMC-relevant content from RSS feeds
CMMC_KEYWORDS = [
    # Primary CMMC terms
    "cmmc",
    "cmmc 2.0",
    "cmmc level",
    "c3pao",
    "cyber-ab",
    "cyberab",
    "cmmc certification",
    "cmmc assessment",
    "cmmc compliance",
    # NIST/Compliance
    "nist 800-171",
    "nist sp 800-171",
    "nist 800-172",
    "sp 800-172",
    "dfars",
    "dfars 252.204",
    "dfars 7012",
    "dfars compliance",
    "cui",
    "controlled unclassified",
    "fedramp",
    # Defense Industrial Base
    "defense industrial base",
    "dib",
    "defense contractor",
    "dod contractor",
    "cleared contractor",
    "industrial security",
    # Federal cybersecurity
    "federal cybersecurity",
    "dod cybersecurity",
    "government compliance",
]

# Quality gates
MIN_TRENDS = 5  # Minimum trends required to build
MIN_FRESH_RATIO = 0.5  # At least 50% of trends must be from past 24h
TREND_FRESHNESS_HOURS = 24  # How old a trend can be to count as "fresh"

# ============================================================================
# API TIMEOUTS & RETRIES
# ============================================================================

# HTTP request timeouts (seconds)
TIMEOUTS = {
    "default": 15,
    "hackernews_story": 5,
    "rss_feed": 20,  # Increased for slow feeds like Washington Post
    "image_api": 15,
    "ai_api": 30,
}

# Retry settings
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2  # Exponential backoff: 1s, 2s, 4s
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
MAX_RETRY_WAIT_SECONDS = (
    10  # Cap retry waits to prevent long delays (e.g., 360s from Groq)
)

# Rate limiting delays (seconds)
DELAYS = {
    "between_sources": 0.5,
    "between_requests": 0.15,
    "between_images": 0.3,
}

# ============================================================================
# IMAGE SETTINGS
# ============================================================================

# Cache settings
IMAGE_CACHE_DIR = DATA_DIR / "image_cache"
IMAGE_CACHE_MAX_AGE_DAYS = 7
IMAGE_CACHE_MAX_ENTRIES = 500

# Fetching settings
IMAGES_PER_KEYWORD = 3  # Images to fetch per keyword (was 2)
MAX_IMAGE_KEYWORDS = 10  # Max keywords to search for (was 8)
MIN_IMAGES_REQUIRED = 5  # Total: 30 images (10 × 3) for better variety


# ============================================================================
# API KEY ROTATION
# ============================================================================


def get_api_keys(env_var: str) -> list:
    """
    Get API keys from environment variable, supporting comma-separated multiple keys.

    Example: PEXELS_API_KEY="key1,key2,key3"

    Args:
        env_var: Environment variable name

    Returns:
        List of API keys (empty if not set)
    """
    value = os.getenv(env_var, "")
    if not value:
        return []
    # Split by comma and strip whitespace
    keys = [k.strip() for k in value.split(",") if k.strip()]
    return keys


# API key collections (supports multiple keys per service for rotation)
PEXELS_KEYS = get_api_keys("PEXELS_API_KEY")
UNSPLASH_KEYS = get_api_keys("UNSPLASH_ACCESS_KEY")
PIXABAY_KEYS = get_api_keys("PIXABAY_API_KEY")
GROQ_KEYS = get_api_keys("GROQ_API_KEY")
OPENROUTER_KEYS = get_api_keys("OPENROUTER_API_KEY")

# ============================================================================
# DEDUPLICATION
# ============================================================================

# Similarity threshold for considering two titles as duplicates
DEDUP_SIMILARITY_THRESHOLD = 0.8
DEDUP_SEMANTIC_THRESHOLD = 0.7  # Lower threshold for semantic matching

# ============================================================================
# DESIGN SETTINGS
# ============================================================================

# Font whitelist (prevents injection via font names)
ALLOWED_FONTS = [
    "Space Grotesk",
    "Inter",
    "Playfair Display",
    "Roboto",
    "Open Sans",
    "Lato",
    "Montserrat",
    "Oswald",
    "Raleway",
    "Poppins",
    "Merriweather",
    "Source Sans Pro",
    "Nunito",
    "Work Sans",
    "Fira Sans",
    "IBM Plex Sans",
    "IBM Plex Mono",
    "JetBrains Mono",
    "Courier Prime",
    "DM Sans",
    "Outfit",
    "Plus Jakarta Sans",
    "Sora",
    "Lexend",
    "Manrope",
    "Archivo",
]

# ============================================================================
# ARCHIVE SETTINGS
# ============================================================================

ARCHIVE_KEEP_DAYS = 30
ARCHIVE_SUBDIR = "archive"

# ============================================================================
# RSS FEED SETTINGS
# ============================================================================

RSS_FEED_TITLE = "DailyTrending.info"
RSS_FEED_DESCRIPTION = (
    "Daily aggregated trending topics from news, technology, social media, and more"
)
RSS_FEED_LINK = "https://dailytrending.info"
RSS_FEED_MAX_ITEMS = 50

# ============================================================================
# KEYWORD TRENDING
# ============================================================================

KEYWORD_HISTORY_FILE = DATA_DIR / "keyword_history.json"
KEYWORD_HISTORY_DAYS = 30  # How many days to keep keyword history


def setup_logging(name: str = "dailytrending") -> logging.Logger:
    """Configure and return a logger instance."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        logger.addHandler(handler)

    logger.setLevel(LOG_LEVEL)
    return logger
