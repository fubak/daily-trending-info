#!/usr/bin/env python3
"""
Topic Page Generator - Modular functions for generating topic-specific pages.

This module extracts topic page generation logic from main.py for better
maintainability and testability. Each function has a single, focused responsibility.
"""

from typing import List, Dict, Set, Optional
from pathlib import Path
import logging

logger = logging.getLogger("topic_page_generator")


def get_topic_configurations() -> List[Dict]:
    """
    Get configuration for all topic pages.

    Returns:
        List of topic configuration dictionaries with slug, title, description,
        source prefixes, hero keywords, and fallback image index.
    """
    return [
        {
            'slug': 'tech',
            'title': 'Technology',
            'description': 'Latest technology news, startups, and developer trends',
            'source_prefixes': [
                'hackernews', 'lobsters', 'tech_', 'github_trending',
                'product_hunt', 'devto', 'slashdot', 'ars_'
            ],
            'hero_keywords': [
                'technology', 'computer', 'code', 'programming', 'software',
                'digital', 'tech', 'innovation', 'startup'
            ],
            'image_index': 0
        },
        {
            'slug': 'world',
            'title': 'World News',
            'description': 'Breaking news and current events from around the world',
            'source_prefixes': ['news_', 'wikipedia', 'google_trends'],
            'hero_keywords': [
                'world', 'globe', 'city', 'cityscape', 'urban',
                'international', 'news', 'global', 'earth'
            ],
            'image_index': 1
        },
        {
            'slug': 'science',
            'title': 'Science & Health',
            'description': 'Latest discoveries in science, technology, medicine, and space',
            'source_prefixes': ['science_'],
            'hero_keywords': [
                'science', 'laboratory', 'research', 'space', 'medical',
                'health', 'biology', 'chemistry', 'physics'
            ],
            'image_index': 2
        },
        {
            'slug': 'politics',
            'title': 'Politics & Policy',
            'description': 'Political news, policy analysis, and government updates',
            'source_prefixes': ['politics_'],
            'hero_keywords': [
                'politics', 'government', 'capitol', 'democracy', 'vote',
                'election', 'law', 'justice', 'congress'
            ],
            'image_index': 3
        },
        {
            'slug': 'finance',
            'title': 'Business & Finance',
            'description': 'Market news, business trends, and economic analysis',
            'source_prefixes': ['finance_'],
            'hero_keywords': [
                'finance', 'business', 'money', 'stock', 'market',
                'office', 'corporate', 'economy', 'trading'
            ],
            'image_index': 4
        },
        {
            'slug': 'business',
            'title': 'Business',
            'description': 'Latest business news, entrepreneurship, and corporate trends',
            'source_prefixes': ['finance_', 'business'],
            'hero_keywords': [
                'business', 'entrepreneur', 'startup', 'corporate', 'office',
                'meeting', 'professional', 'commerce', 'trade'
            ],
            'image_index': 5
        },
        {
            'slug': 'sports',
            'title': 'Sports',
            'description': 'Latest sports news, scores, and athletic highlights',
            'source_prefixes': ['sports_'],
            'hero_keywords': [
                'sports', 'athlete', 'game', 'stadium', 'competition',
                'fitness', 'team', 'basketball', 'football'
            ],
            'image_index': 6
        }
    ]


def extract_headline_keywords(headline: str) -> List[str]:
    """
    Extract significant keywords from a headline by removing stop words.

    Args:
        headline: The headline text to process

    Returns:
        List of significant keywords (length > 2, not stop words)
    """
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'of', 'in', 'to',
        'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
        'and', 'or', 'but', 'if', 'then', 'than', 'so', 'that', 'this',
        'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
        'says', 'said', 'new', 'first', 'after', 'year', 'years', 'now',
        "today's", 'trends', 'trending', 'world', 'its', 'it', 'just'
    }

    headline_lower = headline.lower()
    words = []
    for raw_word in headline_lower.split():
        word = raw_word.strip('.,!?()[]{}":;\'')
        word = word.replace("’", "'")
        if word.endswith("'s"):
            word = word[:-2]
        word = word.strip("'")
        words.append(word)
    return [w for w in words if len(w) > 2 and w not in stop_words]


def score_image_relevance(
    image: Dict,
    headline_keywords: List[str],
    category_keywords: List[str]
) -> float:
    """
    Score an image's relevance based on keyword matching.

    Args:
        image: Image dictionary with query, description, alt, width fields
        headline_keywords: Keywords extracted from headline (weighted 2x)
        category_keywords: General category keywords (weighted 1x)

    Returns:
        Relevance score (higher is better)
    """
    img_text = f"{image.get('query', '')} {image.get('description', '')} {image.get('alt', '')}".lower()

    # Headline keywords weighted higher (2 points each)
    headline_score = sum(2 for kw in headline_keywords if kw in img_text)

    # Category keywords weighted lower (1 point each)
    category_score = sum(1 for kw in category_keywords if kw in img_text)

    total_score = headline_score + category_score

    # Bonus for larger images (better quality)
    if image.get('width', 0) >= 1200:
        total_score += 0.5

    return total_score


def find_topic_hero_image(
    images: List[Dict],
    headline: str,
    category_keywords: List[str],
    fallback_index: int,
    used_image_ids: Set[str]
) -> Dict:
    """
    Find the best hero image for a topic page.

    Priority:
    1. Match keywords from the actual headline (top story title)
    2. Fall back to generic category keywords
    3. Use fallback index if no matches (cycling through unused images)

    Args:
        images: List of available images
        headline: The headline text to match against
        category_keywords: Fallback keywords for the category
        fallback_index: Index for fallback selection
        used_image_ids: Set of image IDs already used (will be modified)

    Returns:
        Best matching image dict, or empty dict if none available
    """
    if not images:
        return {}

    # Filter out already-used images to ensure unique images per topic
    available_images = [
        img for img in images
        if img.get('id') not in used_image_ids
    ]

    # If all images used, reset and allow reuse (better than no image)
    if not available_images:
        available_images = images

    # Extract keywords from headline
    headline_keywords = extract_headline_keywords(headline)

    # Score all available images
    best_image = None
    best_score = 0.0

    for img in available_images:
        score = score_image_relevance(img, headline_keywords, category_keywords)
        if score > best_score:
            best_score = score
            best_image = img

    # If found a good match, use it
    if best_image and best_score > 0:
        if best_image.get('id'):
            used_image_ids.add(best_image['id'])
        return best_image

    # Otherwise use fallback index (cycling through available images)
    idx = fallback_index % len(available_images)
    selected = available_images[idx]
    if selected.get('id'):
        used_image_ids.add(selected['id'])
    return selected


def matches_topic_source(source: str, prefixes: List[str]) -> bool:
    """
    Check if a source matches any of the topic's source prefixes.

    Args:
        source: Source name (e.g., 'hackernews', 'tech_verge')
        prefixes: List of prefixes to match (e.g., ['hackernews', 'tech_'])

    Returns:
        True if source matches any prefix, False otherwise

    Note:
        Prefixes ending with '_' use startswith matching,
        others use exact matching.
    """
    for prefix in prefixes:
        if prefix.endswith('_'):
            # Prefix matching: 'tech_' matches 'tech_verge', 'tech_wired'
            if source.startswith(prefix):
                return True
        else:
            # Exact matching: 'hackernews' only matches 'hackernews'
            if source == prefix:
                return True
    return False


def filter_trends_by_topic(
    trends: List[Dict],
    source_prefixes: List[str]
) -> List[Dict]:
    """
    Filter trends that belong to a specific topic.

    Args:
        trends: List of all trend dictionaries
        source_prefixes: Source prefixes for this topic

    Returns:
        List of trends matching the topic's sources
    """
    return [
        trend for trend in trends
        if matches_topic_source(trend.get('source', ''), source_prefixes)
    ]


def get_topic_hero_image_from_story_or_search(
    top_story: Dict,
    images: List[Dict],
    topic_keywords: List[str],
    fallback_index: int,
    used_image_ids: Set[str]
) -> Dict:
    """
    Get hero image from article RSS feed or fall back to stock photo search.

    Priority:
    1. Use article image from RSS feed if available
    2. Fall back to stock photo search with keyword matching

    Args:
        top_story: Top story dictionary (may contain image_url)
        images: Available stock images
        topic_keywords: Keywords for image matching
        fallback_index: Fallback index for image selection
        used_image_ids: Set of already-used image IDs

    Returns:
        Hero image dictionary
    """
    top_story_title = top_story.get('title', '')
    article_image_url = top_story.get('image_url')

    # Priority 1: Use article image from RSS feed
    if article_image_url:
        return {
            'url_large': article_image_url,
            'url_medium': article_image_url,
            'url_original': article_image_url,
            'photographer': 'Article Image',
            'source': 'article',
            'alt': top_story_title,
            'id': f"article_{hash(article_image_url) % 100000}"
        }

    # Priority 2: Fall back to stock photo search
    return find_topic_hero_image(
        images,
        top_story_title,
        topic_keywords,
        fallback_index,
        used_image_ids
    )


def should_generate_topic_page(topic_trends: List[Dict], min_stories: int = 3) -> bool:
    """
    Determine if a topic page should be generated.

    Args:
        topic_trends: List of trends for this topic
        min_stories: Minimum number of stories required (default: 3)

    Returns:
        True if topic page should be generated, False otherwise
    """
    return len(topic_trends) >= min_stories
