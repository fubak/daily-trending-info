#!/usr/bin/env python3
"""
LinkedIn Post Scraper - Fetches posts from key CMMC influencers via Apify.

Uses the scraper-engine/linkedin-post-scraper actor on Apify to pull
recent posts from specified LinkedIn profiles.

Free tier limits (Apify):
- $5 credits per month
- 3 concurrent actors max
- 7-day data retention

To stay within free limits:
- Runs once daily (via main pipeline)
- Limited to 10 influencers max
- Fetches only 5 most recent posts per profile
"""

import os
import time
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests

from config import setup_logging

logger = setup_logging("linkedin_scraper")

# Default actor ID - can be overridden via environment variable
DEFAULT_APIFY_ACTOR = "scraper-engine/linkedin-post-scraper"

# Conservative limits to stay within Apify free tier
MAX_PROFILES = 10  # Maximum profiles to scrape per run
MAX_POSTS_PER_PROFILE = 5  # Maximum posts per profile
SCRAPER_TIMEOUT_SECONDS = 120  # Max wait time for scraper


@dataclass
class LinkedInPost:
    """Represents a LinkedIn post from a CMMC influencer."""

    title: str  # Post excerpt or author name
    author_name: str
    author_title: str
    author_url: str
    post_url: str
    content: str
    timestamp: Optional[datetime] = None
    likes: int = 0
    comments: int = 0
    shares: int = 0


def get_apify_client():
    """
    Get the Apify client, importing only when needed.

    Returns:
        ApifyClient instance or None if not available
    """
    api_key = os.getenv("APIFY_API_KEY")
    if not api_key:
        logger.warning("APIFY_API_KEY not set - LinkedIn scraping disabled")
        return None

    try:
        from apify_client import ApifyClient

        return ApifyClient(api_key)
    except ImportError:
        logger.warning("apify-client not installed - run: pip install apify-client")
        return None


def fetch_linkedin_posts(
    profile_urls: List[str],
    max_posts_per_profile: int = MAX_POSTS_PER_PROFILE,
) -> List[LinkedInPost]:
    """
    Fetch recent posts from LinkedIn profiles using Apify.

    Args:
        profile_urls: List of LinkedIn profile URLs to scrape
        max_posts_per_profile: Maximum posts to fetch per profile

    Returns:
        List of LinkedInPost objects
    """
    client = get_apify_client()
    if not client:
        return []

    actor_id = os.getenv("APIFY_ACTOR_ID", DEFAULT_APIFY_ACTOR)

    # Respect free tier limits
    profiles_to_scrape = profile_urls[:MAX_PROFILES]
    if len(profile_urls) > MAX_PROFILES:
        logger.warning(
            f"Limiting to {MAX_PROFILES} profiles (requested: {len(profile_urls)})"
        )

    posts = []

    for profile_url in profiles_to_scrape:
        try:
            logger.info(f"Fetching posts from: {profile_url}")

            # Prepare input for the scraper
            # Note: Input format may vary by actor - this is a common pattern
            run_input = {
                "profileUrls": [profile_url],
                "maxPosts": max_posts_per_profile,
                "scrapeComments": False,  # Save credits
                "scrapeReactions": False,  # Save credits
            }

            # Run the actor and wait for completion
            run = client.actor(actor_id).call(
                run_input=run_input,
                timeout_secs=SCRAPER_TIMEOUT_SECONDS,
            )

            # Fetch results from the dataset
            dataset_items = list(
                client.dataset(run["defaultDatasetId"]).iterate_items()
            )

            for item in dataset_items:
                post = _parse_linkedin_item(item)
                if post:
                    posts.append(post)

            logger.info(f"  Found {len(dataset_items)} posts")

            # Small delay between profiles to be respectful
            time.sleep(1)

        except (requests.RequestException, ValueError, KeyError, AttributeError) as e:
            logger.warning(f"Failed to fetch posts from {profile_url}: {e}")
            continue

    logger.info(f"Total LinkedIn posts collected: {len(posts)}")
    return posts


def _parse_linkedin_item(item: Dict) -> Optional[LinkedInPost]:
    """
    Parse a raw Apify result item into a LinkedInPost.

    The exact field names may vary depending on the scraper version.
    This function handles common field variations.
    """
    try:
        # Extract content - try multiple field names
        content = (
            item.get("text")
            or item.get("content")
            or item.get("postText")
            or item.get("description")
            or ""
        )

        if not content:
            return None

        # Extract author info
        author_name = (
            item.get("authorName")
            or item.get("author", {}).get("name")
            or item.get("profileName")
            or "Unknown"
        )

        author_title = (
            item.get("authorTitle")
            or item.get("author", {}).get("title")
            or item.get("profileTitle")
            or ""
        )

        author_url = (
            item.get("authorUrl")
            or item.get("author", {}).get("url")
            or item.get("profileUrl")
            or ""
        )

        post_url = item.get("postUrl") or item.get("url") or item.get("link") or ""

        # Extract timestamp
        timestamp = None
        ts_raw = item.get("timestamp") or item.get("postedAt") or item.get("date")
        if ts_raw:
            try:
                if isinstance(ts_raw, str):
                    # Try ISO format first
                    timestamp = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                elif isinstance(ts_raw, (int, float)):
                    timestamp = datetime.fromtimestamp(ts_raw / 1000)  # ms to seconds
            except (ValueError, TypeError, OSError):
                pass

        # Extract engagement metrics
        likes = int(item.get("likes") or item.get("numLikes") or 0)
        comments = int(item.get("comments") or item.get("numComments") or 0)
        shares = int(item.get("shares") or item.get("numShares") or 0)

        # Create title from content excerpt
        title = content[:100].replace("\n", " ").strip()
        if len(content) > 100:
            title += "..."

        return LinkedInPost(
            title=title,
            author_name=author_name,
            author_title=author_title,
            author_url=author_url,
            post_url=post_url,
            content=content,
            timestamp=timestamp,
            likes=likes,
            comments=comments,
            shares=shares,
        )

    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logger.debug(f"Failed to parse LinkedIn item: {e}")
        return None


def linkedin_posts_to_trends(posts: List[LinkedInPost]) -> List[Dict]:
    """
    Convert LinkedIn posts to the trend format used by the pipeline.

    Args:
        posts: List of LinkedInPost objects

    Returns:
        List of trend dictionaries compatible with Trend dataclass
    """
    trends = []

    for post in posts:
        # Create a trend-compatible dictionary
        trend = {
            "title": f"{post.author_name}: {post.title}",
            "source": "cmmc_linkedin",
            "url": post.post_url or post.author_url,
            "description": post.content[:500],
            "category": "cmmc",
            "score": _calculate_post_score(post),
            "keywords": _extract_keywords(post.content),
            "timestamp": post.timestamp.isoformat() if post.timestamp else None,
            "image_url": None,  # LinkedIn posts typically don't have extractable images
        }
        trends.append(trend)

    return trends


def _calculate_post_score(post: LinkedInPost) -> float:
    """
    Calculate a relevance score for a LinkedIn post.

    Based on engagement metrics and recency.
    """
    base_score = 1.5  # LinkedIn posts from key people are valuable

    # Engagement boost (capped)
    engagement = post.likes + (post.comments * 2) + (post.shares * 3)
    engagement_boost = min(engagement / 100, 1.0)  # Max 1.0 boost

    # Recency boost
    recency_boost = 0.0
    if post.timestamp:
        age_hours = (datetime.now() - post.timestamp).total_seconds() / 3600
        if age_hours < 24:
            recency_boost = 0.5
        elif age_hours < 72:
            recency_boost = 0.25

    return base_score + engagement_boost + recency_boost


def _extract_keywords(content: str) -> List[str]:
    """Extract meaningful keywords from post content."""
    import re

    # CMMC-specific keywords to look for
    cmmc_terms = {
        "cmmc",
        "nist",
        "dfars",
        "c3pao",
        "cui",
        "fedramp",
        "cybersecurity",
        "compliance",
        "dod",
        "defense",
        "certification",
        "assessment",
        "800-171",
        "contractor",
        "security",
    }

    # Extract words
    words = re.findall(r"\b[a-zA-Z0-9-]{3,}\b", content.lower())

    # Find CMMC-related keywords
    keywords = []
    seen = set()
    for word in words:
        if word in cmmc_terms and word not in seen:
            keywords.append(word)
            seen.add(word)

    return keywords[:5]  # Top 5 keywords


def test_connection() -> bool:
    """
    Test the Apify connection without running a full scrape.

    Returns:
        True if connection is working, False otherwise
    """
    client = get_apify_client()
    if not client:
        return False

    try:
        # Just check we can access the API
        user_info = client.user().get()
        logger.info(
            f"Apify connection OK - User: {user_info.get('username', 'unknown')}"
        )
        return True
    except (requests.RequestException, ValueError, KeyError, AttributeError) as e:
        logger.error(f"Apify connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test mode
    print("LinkedIn Post Scraper for DailyTrending.info")
    print("=" * 40)

    if test_connection():
        print("✓ Apify connection successful")
    else:
        print("✗ Apify connection failed")
        print("  Set APIFY_API_KEY environment variable")
