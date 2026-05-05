#!/usr/bin/env python3
"""
Topic Page Generator - Modular functions for generating topic-specific pages.

This module extracts topic page generation logic from main.py for better
maintainability and testability. Each function has a single, focused responsibility.
"""

import html as html_module
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from image_utils import validate_image_url, get_image_quality_score
from shared_components import (
    build_header,
    build_footer,
    get_header_styles,
    get_footer_styles,
    get_theme_script,
)

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

    total_score = float(headline_score + category_score)

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


def build_topic_page(
    config: Dict,
    trends: List[Dict],
    design: Dict,
    hero_image: Dict,
) -> str:
    """Build HTML for a topic sub-page with shared header/footer."""
    colors = {
        "bg": design.get("color_bg", "#0a0a0a"),
        "card_bg": design.get("color_card_bg", "#18181b"),
        "text": design.get("color_text", "#ffffff"),
        "muted": design.get("color_muted", "#a1a1aa"),
        "border": design.get("color_border", "#27272a"),
        "accent": design.get("color_accent", "#6366f1"),
        "accent_secondary": design.get("color_accent_secondary", "#8b5cf6"),
    }
    font_primary = design.get("font_primary", "Space Grotesk")
    font_secondary = design.get("font_secondary", "Inter")
    radius = design.get("card_radius", "1rem")
    card_padding = design.get("card_padding", "1.5rem")
    transition = design.get("transition_speed", "200ms")
    base_mode = "dark-mode" if design.get("is_dark_mode", True) else "light-mode"

    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")
    date_iso = now.isoformat()

    hero_image_url = ""
    hero_image_alt = ""
    if hero_image:
        hero_image_url = str(
            hero_image.get(
                "url_large",
                hero_image.get("url_medium", hero_image.get("url", "")),
            )
            or ""
        )
        hero_image_alt = str(
            hero_image.get(
                "alt",
                hero_image.get(
                    "description", f"{str(config.get('title', 'Topic'))} hero image"
                ),
            )
            or ""
        )

    featured_story = trends[0] if trends else {}
    featured_title = html_module.escape((featured_story.get("title") or "")[:100])
    featured_url = html_module.escape(featured_story.get("url") or "#")
    featured_source_raw = featured_story.get("source_label")
    if not featured_source_raw:
        featured_source_raw = (featured_story.get("source") or "").replace("_", " ").title()
    featured_source = html_module.escape(featured_source_raw)
    featured_desc = html_module.escape(
        (featured_story.get("summary") or featured_story.get("description") or "")[:200]
    )

    placeholder_url = "/assets/nano-banana.png"

    cards: List[str] = []
    for t in trends[1:20]:
        title = html_module.escape((t.get("title") or "")[:100])
        url = html_module.escape(t.get("url") or "#")
        source_raw = t.get("source_label")
        if not source_raw:
            source_raw = (t.get("source") or "").replace("_", " ").title()
        source = html_module.escape(source_raw)
        raw_image_url = t.get("image_url") or ""

        is_valid, validated_url = validate_image_url(raw_image_url)

        if is_valid and validated_url:
            img_src = html_module.escape(validated_url)
            img_class = "story-image"
            img_alt = title
            img_quality = get_image_quality_score(validated_url)
            img_data_attrs = f'data-quality="{img_quality}"'
        else:
            img_src = placeholder_url
            img_class = "story-image placeholder"
            img_alt = f"{source} story placeholder"
            img_data_attrs = 'data-is-placeholder="true"'

        cards.append(
            f"""
        <article class="story-card">
            <div class="story-wrapper">
                <figure class="story-media">
                    <img src="{img_src}"
                         alt="{img_alt}"
                         class="{img_class}"
                         loading="lazy"
                         referrerpolicy="no-referrer"
                         width="640"
                         height="360"
                         {img_data_attrs}
                         onerror="this.onerror=null;this.src='{placeholder_url}';this.classList.add('placeholder');">
                </figure>
                <div class="story-content">
                    <span class="source-badge">{source}</span>
                    <h3 class="story-title">
                        <a href="{url}" target="_blank" rel="noopener">{title}</a>
                    </h3>
                </div>
            </div>
        </article>"""
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config['title']} | DailyTrending.info</title>
    <meta name="description" content="{config['description']}">
    <meta name="author" content="DailyTrending.info">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
    <link rel="canonical" href="https://dailytrending.info/{config['slug']}/">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">

    <meta property="og:title" content="{config['title']} | DailyTrending.info">
    <meta property="og:description" content="{config['description']}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://dailytrending.info/{config['slug']}/">
    <meta property="og:image" content="https://dailytrending.info/og-image.png">
    <meta property="og:site_name" content="DailyTrending.info">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@bradshannon">
    <meta name="twitter:title" content="{config['title']} | DailyTrending.info">
    <meta name="twitter:description" content="{config['description']}">

    <!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2196222970720414"
         crossorigin="anonymous"></script>

    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@graph": [
            {{
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {{
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": "https://dailytrending.info/"
                    }},
                    {{
                        "@type": "ListItem",
                        "position": 2,
                        "name": "{config['title']}",
                        "item": "https://dailytrending.info/{config['slug']}/"
                    }}
                ]
            }},
            {{
                "@type": "CollectionPage",
                "name": "{config['title']} Trends",
                "description": "{config['description']}",
                "url": "https://dailytrending.info/{config['slug']}/",
                "isPartOf": {{"@id": "https://dailytrending.info"}},
                "dateModified": "{date_iso}",
                "numberOfItems": {len(trends)},
                "publisher": {{
                    "@type": "Organization",
                    "name": "DailyTrending.info",
                    "url": "https://dailytrending.info/"
                }}
            }}
        ]
    }}
    </script>

    <link href="https://fonts.googleapis.com/css2?family={font_primary.replace(' ', '+')}:wght@400;500;600;700;800&family={font_secondary.replace(' ', '+')}:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --color-bg: {colors['bg']};
            --color-card-bg: {colors['card_bg']};
            --color-text: {colors['text']};
            --color-muted: {colors['muted']};
            --color-border: {colors['border']};
            --color-accent: {colors['accent']};
            --color-accent-secondary: {colors['accent_secondary']};
            --radius: {radius};
            --card-padding: {card_padding};
            --transition: {transition} ease;
            --font-primary: '{font_primary}', system-ui, sans-serif;
            --font-secondary: '{font_secondary}', system-ui, sans-serif;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: var(--font-secondary);
            background: var(--color-bg);
            color: var(--color-text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        body.light-mode {{
            --color-bg: #ffffff;
            --color-card-bg: #f8fafc;
            --color-text: #1a1a2e;
            --color-muted: #64748b;
            --color-border: #e2e8f0;
            background: var(--color-bg);
        }}

        body.dark-mode {{
            --color-bg: #0a0a0a;
            --color-card-bg: #18181b;
            --color-text: #ffffff;
            --color-muted: #a1a1aa;
            --color-border: #27272a;
            background: var(--color-bg);
        }}

        body.density-compact {{
            --section-gap: 1.5rem;
            --card-gap: 0.75rem;
            --card-padding: 0.75rem;
        }}
        body.density-comfortable {{
            --section-gap: 2.5rem;
            --card-gap: 1.25rem;
            --card-padding: 1.25rem;
        }}
        body.density-spacious {{
            --section-gap: 4rem;
            --card-gap: 2rem;
            --card-padding: 1.75rem;
        }}

        body.view-list .stories-grid,
        body.view-list .trend-grid {{
            display: flex;
            flex-direction: column;
            gap: 0;
        }}
        body.view-list .story-card,
        body.view-list .trend-card {{
            background: transparent;
            border: none;
            border-bottom: 1px solid var(--color-border);
            border-radius: 0;
            padding: 0.5rem 0;
            padding-left: 1.5rem;
        }}
        body.view-list .story-card img,
        body.view-list .trend-card img,
        body.view-list .card-image {{
            display: none;
        }}

        {get_header_styles()}

        .topic-hero {{
            position: relative;
            min-height: 500px;
            display: flex;
            align-items: flex-end;
            overflow: hidden;
            border-bottom: 1px solid var(--color-border);
        }}

        .hero-image {{
            position: absolute;
            inset: 0;
            background-size: contain;
            background-position: center center;
            background-repeat: no-repeat;
            background-color: var(--color-bg);
            z-index: 0;
        }}

        .hero-image::before {{
            content: '';
            position: absolute;
            inset: -20px;
            background: inherit;
            background-size: cover;
            filter: brightness(0.5);
            z-index: -1;
        }}

        .hero-image::after {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.4) 50%, rgba(0,0,0,0.2) 100%);
        }}

        .hero-content {{
            position: relative;
            z-index: 1;
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
            padding: 3rem 2rem;
        }}

        .topic-label {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: var(--color-accent);
            color: #000;
            padding: 0.4rem 1rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 1rem;
        }}

        .hero-title {{
            font-family: var(--font-primary);
            font-size: clamp(1.75rem, 4vw, 2.75rem);
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 1rem;
            max-width: 800px;
        }}

        .hero-title a {{
            color: var(--color-text);
            text-decoration: none;
            transition: color var(--transition);
        }}

        .hero-title a:hover {{
            color: var(--color-accent);
        }}

        .hero-desc {{
            font-size: 1.1rem;
            color: var(--color-muted);
            max-width: 600px;
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }}

        .hero-meta {{
            display: flex;
            align-items: center;
            gap: 1.5rem;
            flex-wrap: wrap;
        }}

        .hero-source {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--color-accent);
            font-weight: 600;
            font-size: 0.9rem;
        }}

        .hero-stats {{
            display: flex;
            gap: 1.5rem;
            font-size: 0.9rem;
            color: var(--color-muted);
        }}

        .hero-stats span {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .hero-cta {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            background: var(--color-accent);
            color: #000;
            font-weight: 600;
            border-radius: var(--radius);
            text-decoration: none;
            transition: transform var(--transition), box-shadow var(--transition);
        }}

        .hero-cta:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }}

        .main-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 3rem 2rem;
        }}

        .stories-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.25rem;
        }}

        .story-card {{
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
        }}

        .story-card:hover {{
            transform: translateY(-4px);
            border-color: var(--color-accent);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }}

        .story-wrapper {{
            display: flex;
            flex-direction: column;
            width: 100%;
            height: 100%;
        }}

        .story-media {{
            width: 100%;
            flex-shrink: 0;
            border-radius: 0;
            overflow: hidden;
            position: relative;
            background: color-mix(in srgb, rgba(12, 16, 24, 0.95), rgba(34, 45, 63, 0.9));
            background-image: radial-gradient(circle at 30% 25%, rgba(255, 255, 255, 0.18), transparent 40%),
                              radial-gradient(circle at 70% 80%, rgba(255, 255, 255, 0.08), transparent 55%);
            min-height: 180px;
        }}

        .story-media::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(to bottom, rgba(0, 0, 0, 0.02), rgba(0, 0, 0, 0.25));
            pointer-events: none;
        }}

        .story-image {{
            width: 100%;
            height: 180px;
            min-height: 180px;
            object-fit: cover;
            object-position: center;
            background-color: var(--color-border);
            transition: opacity 0.3s ease;
        }}

        .story-image:not([loaded]):not(.placeholder) {{
            opacity: 0;
        }}

        .story-media:not(.image-loaded):not(.image-fallback)::after {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.08) 50%,
                transparent 100%);
            animation: shimmer 1.5s infinite;
        }}

        @keyframes shimmer {{
            0% {{ transform: translateX(-100%); }}
            100% {{ transform: translateX(100%); }}
        }}

        .story-image[loaded] {{
            opacity: 1;
        }}

        .story-image.placeholder {{
            opacity: 0.85;
            filter: grayscale(0.1);
        }}

        .image-fallback .story-image {{
            opacity: 0.8;
        }}

        .story-content {{
            padding: 1rem;
            flex: 1;
            display: flex;
            flex-direction: column;
        }}

        .source-badge {{
            display: inline-block;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--color-accent);
            margin-bottom: 0.4rem;
        }}

        .story-title {{
            font-size: 0.95rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .story-title a {{
            color: var(--color-text);
            text-decoration: none;
            background: linear-gradient(to right, var(--color-accent), var(--color-accent)) 0 100% / 0 2px no-repeat;
            transition: background-size 0.3s;
        }}

        .story-title a:hover {{
            background-size: 100% 2px;
        }}

        .story-desc {{
            color: var(--color-muted);
            font-size: 0.8rem;
            line-height: 1.5;
            margin-bottom: 0.75rem;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        {get_footer_styles()}

        @media (max-width: 640px) {{
            .stories-grid {{
                grid-template-columns: 1fr;
            }}
            .topic-hero {{
                min-height: 350px;
            }}
            .hero-content {{
                padding: 2rem 1rem;
            }}
            .hero-title {{
                font-size: 1.5rem;
            }}
            .hero-desc {{
                font-size: 1rem;
            }}
            .hero-meta {{
                flex-direction: column;
                align-items: flex-start;
                gap: 1rem;
            }}
            .main-content {{
                padding: 2rem 1rem;
            }}
            .story-card.featured {{
                grid-column: 1;
            }}
        }}

        @media (min-width: 641px) and (max-width: 1024px) {{
            .stories-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .topic-hero {{
                min-height: 400px;
            }}
        }}

        @media (min-width: 1025px) and (max-width: 1280px) {{
            .stories-grid {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}
    </style>
</head>
<body class="{base_mode}">
    {build_header(config['slug'], date_str)}

    <header class="topic-hero">
        <div class="hero-image" style="background-image: url('{hero_image_url}');" role="img" aria-label="{hero_image_alt}"></div>
        <div class="hero-content">
            <span class="topic-label">{config['title']}</span>
            <h1 class="hero-title"><a href="{featured_url}" target="_blank" rel="noopener">{featured_title}</a></h1>
            {f'<p class="hero-desc">{featured_desc}</p>' if featured_desc else ''}
            <div class="hero-meta">
                <span class="hero-source">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                    {featured_source}
                </span>
                <div class="hero-stats">
                    <span>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20V10M18 20V4M6 20v-4"/></svg>
                        {len(trends)} stories
                    </span>
                    <span>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                        {date_str}
                    </span>
                </div>
            </div>
        </div>
    </header>

    <main class="main-content">
        <div class="stories-grid">
            {''.join(cards)}
        </div>
    </main>

    {build_footer(date_str)}

    <script>
        (function () {{
            const placeholderImage = "{placeholder_url}";
            const LOAD_TIMEOUT_MS = 8000;

            const markBroken = (img, reason = 'error') => {{
                if (!placeholderImage) return;
                if (img.dataset.fallbackApplied) return;
                img.dataset.fallbackApplied = 'true';
                img.dataset.fallbackReason = reason;
                img.src = placeholderImage;
                img.classList.add('placeholder');
                img.title = 'Image unavailable';
                img.parentElement?.classList.add('image-fallback');
            }};

            const bindErrors = () => {{
                document.querySelectorAll('.story-image').forEach((img) => {{
                    if (img.dataset.boundError) return;
                    img.dataset.boundError = 'true';

                    if (img.dataset.isPlaceholder === 'true') {{
                        img.setAttribute('loaded', '');
                        return;
                    }}

                    let loadTimeout;
                    const startTimeout = () => {{
                        loadTimeout = setTimeout(() => {{
                            if (!img.complete || img.naturalWidth === 0) {{
                                markBroken(img, 'timeout');
                            }}
                        }}, LOAD_TIMEOUT_MS);
                    }};

                    img.addEventListener('load', () => {{
                        clearTimeout(loadTimeout);
                        if (img.naturalWidth > 0) {{
                            img.setAttribute('loaded', '');
                            img.parentElement?.classList.add('image-loaded');
                        }} else {{
                            markBroken(img, 'zero-size');
                        }}
                    }});

                    img.addEventListener('error', () => {{
                        clearTimeout(loadTimeout);
                        markBroken(img, 'error');
                    }});

                    if (img.complete) {{
                        if (img.naturalWidth === 0) {{
                            markBroken(img, 'already-broken');
                        }} else {{
                            img.setAttribute('loaded', '');
                            img.parentElement?.classList.add('image-loaded');
                        }}
                    }} else {{
                        startTimeout();
                    }}
                }});
            }};

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', bindErrors);
            }} else {{
                bindErrors();
            }}
        }})();
    </script>

    {get_theme_script()}
</body>
</html>"""


def generate_all_topic_pages(
    public_dir: Path,
    trends_data: List[Dict],
    images_data: List[Dict],
    design_data: Dict,
) -> int:
    """Build and write all topic sub-pages.

    Args:
        public_dir: Destination root (pages go to public_dir/<slug>/index.html).
        trends_data: All trends as plain dicts (summaries already applied).
        images_data: Available images as plain dicts.
        design_data: Design tokens as a plain dict.

    Returns:
        Number of topic pages successfully created.
    """
    topic_configs = get_topic_configurations()
    pages_created = 0
    used_image_ids: Set[str] = set()

    for config in topic_configs:
        source_prefixes = config.get("source_prefixes", [])
        if not isinstance(source_prefixes, list):
            continue
        source_prefixes = [str(p) for p in source_prefixes]
        slug = str(config.get("slug", "")).strip()
        if not slug:
            continue

        topic_trends = filter_trends_by_topic(trends_data, source_prefixes)

        if not should_generate_topic_page(topic_trends):
            logger.info(f"  Skipping /{slug}/ - only {len(topic_trends)} stories")
            continue

        top_story = topic_trends[0] if topic_trends else {}
        hero_keywords_raw = config.get("hero_keywords", [])
        hero_keywords = [str(k) for k in hero_keywords_raw] if isinstance(hero_keywords_raw, list) else []
        image_index_raw = config.get("image_index", 0)
        image_index = int(image_index_raw) if isinstance(image_index_raw, (int, float)) else 0

        hero_image = get_topic_hero_image_from_story_or_search(
            top_story, images_data, hero_keywords, image_index, used_image_ids
        )

        topic_dir = public_dir / slug
        topic_dir.mkdir(parents=True, exist_ok=True)

        page_html = build_topic_page(config, topic_trends, design_data, hero_image)
        (topic_dir / "index.html").write_text(page_html, encoding="utf-8")
        pages_created += 1
        logger.info(f"  Created /{slug}/ with {len(topic_trends)} stories")

    return pages_created
