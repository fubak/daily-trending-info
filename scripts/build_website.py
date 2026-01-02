#!/usr/bin/env python3
"""
Website Builder - Generates modern news-style websites with dynamic layouts.

Features:
- Multiple layout templates (newspaper, magazine, dashboard, minimal, bold)
- Source-grouped sections (News, Tech, Reddit, etc.)
- Word cloud visualization
- Dynamic hero styles
- Responsive design with CSS Grid
"""

import os
import json
import html
import random
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from fetch_images import FallbackImageGenerator


@dataclass
class BuildContext:
    """Context for building the website."""
    trends: List[Dict]
    images: List[Dict]
    design: Dict
    keywords: List[str]
    enriched_content: Optional[Dict] = None  # Word of Day, Grokipedia, summaries
    why_this_matters: Optional[List[Dict]] = None  # Context explanations for top stories
    yesterday_trends: Optional[List[Dict]] = None  # Previous day's trends for comparison
    editorial_article: Optional[Dict] = None  # Today's editorial article
    keyword_history: Optional[Dict] = None  # Historical keyword data for timeline
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().strftime("%B %d, %Y")


# Layout templates with different structures
LAYOUT_TEMPLATES = [
    "newspaper",   # Classic newspaper with columns
    "magazine",    # Large featured images, editorial style
    "dashboard",   # Data-dense with stats and grids
    "minimal",     # Clean, lots of whitespace
    "bold",        # Large typography, high contrast
    "mosaic",      # Asymmetric grid, varied card sizes
]

# Hero style variants - creative designs that change each generation
HERO_STYLES = [
    "cinematic",      # Dark overlay with dramatic gradient, image visible
    "glassmorphism",  # Frosted glass effect with visible background
    "neon",           # Neon glow effects with dark background
    "duotone",        # Two-tone color overlay on image
    "particles",      # Animated floating particles
    "waves",          # Animated wave pattern
    "geometric",      # Animated geometric shapes
    "spotlight",      # Spotlight/lens flare effect
    "glitch",         # Glitch art effect
    "aurora",         # Northern lights gradient animation
    "mesh",           # Gradient mesh background
    "retro",          # Retro/synthwave style
]


class WebsiteBuilder:
    """Builds dynamic news-style websites with varied layouts."""

    def __init__(self, context: BuildContext):
        self.ctx = context
        self.design = context.design

        # Use timestamp as seed for unique randomization on each generation
        timestamp_seed = datetime.now().isoformat()
        self.rng = random.Random(timestamp_seed)

        # Use layout and hero style from design spec if available, otherwise random
        self.layout = self.design.get('layout_style') or self.rng.choice(LAYOUT_TEMPLATES)
        self.hero_style = self.design.get('hero_style') or self.rng.choice(HERO_STYLES)

        # Group trends by category
        self.grouped_trends = self._group_trends()

        # Calculate keyword frequencies for word cloud
        self.keyword_freq = self._calculate_keyword_freq()

        # Pre-compute sorted categories for consistent ordering across nav/sections/footer
        self._sorted_categories = self._get_sorted_categories()

        # Find the best hero image based on headline content
        self._hero_image = self._find_relevant_hero_image()

    def _find_relevant_hero_image(self) -> Optional[Dict]:
        """Find an image that matches the headline/top story content."""
        if not self.ctx.images:
            return None

        # Get the headline and top trend for keyword matching
        headline = self.design.get('headline', '').lower()
        top_trend_title = ''
        if self.ctx.trends:
            top_trend_title = (self.ctx.trends[0].get('title') or '').lower()

        # Extract keywords from headline and top trend
        search_text = f"{headline} {top_trend_title}"
        # Remove common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                      'should', 'may', 'might', 'must', 'shall', 'can', 'of', 'in', 'to',
                      'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
                      'and', 'or', 'but', 'if', 'then', 'than', 'so', 'that', 'this',
                      'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
                      "today's", "trends", "trending", "world", "talking", "about"}
        words = [w.strip('.,!?()[]{}":;\'') for w in search_text.split()]
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]

        # Score each image based on keyword matches in query/description
        best_image = None
        best_score = 0

        for img in self.ctx.images:
            img_text = f"{img.get('query', '')} {img.get('description', '')}".lower()
            score = sum(1 for kw in keywords if kw in img_text)

            # Prefer larger images
            if img.get('width', 0) >= 1200:
                score += 0.5

            if score > best_score:
                best_score = score
                best_image = img

        # If no good match, use the first image
        if best_score == 0 and self.ctx.images:
            return self.ctx.images[0]

        return best_image

    def _get_sorted_categories(self) -> list:
        """Get categories sorted by trend count for consistent ordering."""
        sorted_cats = sorted(
            self.grouped_trends.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        # Filter to categories with 2+ trends
        return [(cat, trends) for cat, trends in sorted_cats if len(trends) >= 2][:8]

    def _group_trends(self) -> Dict[str, List[Dict]]:
        """Group trends by their source category."""
        groups = defaultdict(list)

        category_map = {
            'news_': 'World News',
            'tech_': 'Technology',
            'reddit_news': 'Reddit News',
            'reddit_worldnews': 'World News',
            'reddit_politics': 'Politics',
            'reddit_technology': 'Technology',
            'reddit_science': 'Science',
            'reddit_programming': 'Technology',
            'reddit_futurology': 'Future',
            'reddit_space': 'Science',
            'reddit_movies': 'Entertainment',
            'reddit_television': 'Entertainment',
            'reddit_music': 'Entertainment',
            'reddit_books': 'Culture',
            'reddit_sports': 'Sports',
            'reddit_nba': 'Sports',
            'reddit_soccer': 'Sports',
            'reddit_business': 'Business',
            'reddit_economics': 'Business',
            'reddit_gadgets': 'Technology',
            'reddit_': 'Trending',
            'hackernews': 'Hacker News',
            'google_trends': 'Trending',
            'github_trending': 'GitHub',
            'wikipedia_current': 'Current Events',
        }

        for trend in self.ctx.trends:
            source = trend.get('source', 'unknown')
            category = 'Other'

            for prefix, cat in category_map.items():
                if source.startswith(prefix):
                    category = cat
                    break

            groups[category].append(trend)

        return dict(groups)

    def _calculate_keyword_freq(self) -> List[Tuple[str, int]]:
        """Calculate keyword frequencies for word cloud."""
        freq = defaultdict(int)

        for trend in self.ctx.trends:
            keywords = trend.get('keywords', [])
            for kw in keywords:
                freq[kw.lower()] += 1

        # Also count from keyword list
        for kw in self.ctx.keywords:
            freq[kw.lower()] += 1

        # Sort by frequency
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return sorted_freq[:50]

    def _calculate_reading_time(self, word_count: int) -> int:
        """Calculate reading time in minutes (200 WPM average)."""
        return max(1, round(word_count / 200))

    def _get_total_reading_time(self) -> int:
        """Get total reading time for all trends on the page."""
        total_words = 0
        for trend in self.ctx.trends:
            title_words = len((trend.get('title', '') or '').split())
            desc_words = len((trend.get('description', '') or '').split())
            total_words += title_words + desc_words
        return self._calculate_reading_time(total_words)

    def _calculate_velocity(self, trend: Dict) -> Dict:
        """
        Calculate trending velocity for a story.

        Returns dict with:
        - score: 0-100 velocity score
        - label: 'hot', 'rising', 'steady', 'cooling'
        - sources: number of sources mentioning similar topic
        """
        title = (trend.get('title', '') or '').lower()
        source = trend.get('source', '')

        # Count how many other stories share keywords with this one
        trend_keywords = set(trend.get('keywords', []))
        title_words = set(title.split())

        cross_mentions = 0
        for other in self.ctx.trends:
            if other.get('url') == trend.get('url'):
                continue
            other_title = (other.get('title', '') or '').lower()
            other_keywords = set(other.get('keywords', []))

            # Check for keyword overlap
            keyword_overlap = len(trend_keywords & other_keywords)
            title_overlap = len(title_words & set(other_title.split())) - 3  # Subtract common words

            if keyword_overlap >= 2 or title_overlap >= 2:
                cross_mentions += 1

        # Calculate base score from cross-mentions
        score = min(100, cross_mentions * 20 + 20)

        # Boost for fresh content (has timestamp)
        if trend.get('timestamp'):
            score = min(100, score + 10)

        # Determine label
        if score >= 80:
            label = 'hot'
        elif score >= 50:
            label = 'rising'
        elif score >= 30:
            label = 'steady'
        else:
            label = 'new'

        return {
            'score': score,
            'label': label,
            'sources': cross_mentions + 1
        }

    def _find_related_stories(self, trend: Dict, max_related: int = 3) -> List[Dict]:
        """
        Find related stories based on keyword overlap.

        Returns list of related stories with source and title info.
        """
        title = (trend.get('title', '') or '').lower()
        trend_url = trend.get('url', '')
        trend_keywords = set(trend.get('keywords', []))
        title_words = set(w for w in title.split() if len(w) > 3)

        related = []
        for other in self.ctx.trends:
            if other.get('url') == trend_url:
                continue

            other_title = (other.get('title', '') or '').lower()
            other_keywords = set(other.get('keywords', []))
            other_title_words = set(w for w in other_title.split() if len(w) > 3)

            # Calculate overlap scores
            keyword_overlap = len(trend_keywords & other_keywords)
            title_overlap = len(title_words & other_title_words)

            # Need significant overlap to be considered related
            if keyword_overlap >= 2 or title_overlap >= 3:
                score = keyword_overlap * 2 + title_overlap
                related.append({
                    'source': (other.get('source') or '').replace('_', ' ').title(),
                    'title': other.get('title', 'Untitled'),
                    'url': other.get('url', '#'),
                    'score': score
                })

        # Sort by relevance score and return top results
        related.sort(key=lambda x: x['score'], reverse=True)
        return related[:max_related]

    def _find_discussion_links(self, trend: Dict) -> List[Dict]:
        """
        Find HN/Reddit discussion links for a story.

        Returns list of discussion links from community sources.
        """
        DISCUSSION_SOURCES = {'hacker news', 'hackernews', 'reddit', 'lobsters'}

        trend_source = (trend.get('source') or '').lower()
        # If this story is already from a discussion source, skip
        if trend_source in DISCUSSION_SOURCES:
            return []

        title = (trend.get('title', '') or '').lower()
        trend_url = trend.get('url', '')
        trend_keywords = set(trend.get('keywords', []))
        title_words = set(w for w in title.split() if len(w) > 3)

        discussions = []
        for other in self.ctx.trends:
            if other.get('url') == trend_url:
                continue

            other_source = (other.get('source') or '').lower()
            if other_source not in DISCUSSION_SOURCES:
                continue

            other_title = (other.get('title', '') or '').lower()
            other_keywords = set(other.get('keywords', []))
            other_title_words = set(w for w in other_title.split() if len(w) > 3)

            # Calculate overlap scores
            keyword_overlap = len(trend_keywords & other_keywords)
            title_overlap = len(title_words & other_title_words)

            # Need significant overlap
            if keyword_overlap >= 2 or title_overlap >= 3:
                source_display = other_source.replace('_', ' ').title()
                if 'hacker' in other_source:
                    source_display = 'HN'
                    icon = '🔶'
                elif 'reddit' in other_source:
                    source_display = 'Reddit'
                    icon = '🤖'
                elif 'lobster' in other_source:
                    source_display = 'Lobsters'
                    icon = '🦞'
                else:
                    icon = '💬'

                discussions.append({
                    'source': source_display,
                    'url': other.get('url', '#'),
                    'icon': icon,
                    'score': keyword_overlap * 2 + title_overlap
                })

        # Sort by relevance and return
        discussions.sort(key=lambda x: x['score'], reverse=True)
        return discussions[:2]  # Max 2 discussion links

    def _get_comparison_indicator(self, trend: Dict) -> Dict:
        """
        Compare trend to yesterday's data.

        Returns dict with:
        - status: 'new', 'returning', 'rising', 'steady'
        - icon: emoji/symbol
        - tooltip: description
        """
        if not self.ctx.yesterday_trends:
            return {'status': 'new', 'icon': '🆕', 'tooltip': 'New today'}

        title = (trend.get('title', '') or '').lower()
        url = trend.get('url', '')

        # Check for exact URL match
        yesterday_urls = {t.get('url', '') for t in self.ctx.yesterday_trends}
        if url in yesterday_urls:
            return {'status': 'steady', 'icon': '📊', 'tooltip': 'Continuing trend'}

        # Check for similar titles (fuzzy match)
        title_words = set(title.split())
        for yt in self.ctx.yesterday_trends:
            yt_title = (yt.get('title', '') or '').lower()
            yt_words = set(yt_title.split())

            # Calculate word overlap (excluding common stop words)
            stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'in', 'on', 'to', 'for', 'of', 'and'}
            overlap = (title_words - stop_words) & (yt_words - stop_words)

            if len(overlap) >= 3:
                return {'status': 'rising', 'icon': '🔥', 'tooltip': 'Trending up from yesterday'}

        return {'status': 'new', 'icon': '🆕', 'tooltip': 'New today'}

    def _get_top_topic(self) -> str:
        """Get the main topic for SEO title.

        Ensures the topic portion fits within SEO best practices:
        - Full title will be "DailyTrending.info - {topic}" (21 char prefix)
        - Total title should be under 60 chars for optimal display
        - Topic portion should be max 38 chars to stay under 60 total
        """
        max_topic_length = 38  # 60 - 21 (prefix) - 1 (buffer)

        # Try to get from top trend
        if self.ctx.trends:
            top_trend = self.ctx.trends[0]
            title = top_trend.get('title', '')

            # Smart truncation: try to break at word boundary
            if len(title) > max_topic_length:
                # Find a good break point (word boundary or punctuation)
                truncated = title[:max_topic_length]
                last_space = truncated.rfind(' ')
                last_dash = truncated.rfind(' - ')
                last_colon = truncated.rfind(': ')

                # Use the latest clean break point
                break_point = max(last_space, last_dash + 2 if last_dash > 0 else 0, last_colon + 1 if last_colon > 0 else 0)

                if break_point > max_topic_length // 2:  # Only use if not too short
                    title = title[:break_point].rstrip()
                else:
                    title = title[:max_topic_length - 3].rstrip() + '...'

            return title

        # Fall back to top keywords
        if self.keyword_freq:
            top_kws = [kw.title() for kw, _ in self.keyword_freq[:3]]
            topic = ', '.join(top_kws) + ' Trends'
            if len(topic) > max_topic_length:
                topic = topic[:max_topic_length - 3] + '...'
            return topic

        return "Today's Top Trends"

    def _build_meta_description(self) -> str:
        """Build SEO-friendly meta description."""
        date_str = datetime.now().strftime("%B %d, %Y")

        # Get category counts
        categories = list(self.grouped_trends.keys())[:4]
        category_str = ', '.join(categories) if categories else 'News, Technology, Science'

        # Get top keywords
        top_kws = [kw.title() for kw, _ in self.keyword_freq[:5]]
        kw_str = ', '.join(top_kws) if top_kws else 'trending topics'

        total_stories = len(self.ctx.trends)
        total_sources = len(set(t.get('source', '').split('_')[0] for t in self.ctx.trends))

        description = (
            f"Daily trending topics for {date_str}. "
            f"Discover {total_stories}+ stories from {total_sources} sources covering {category_str}. "
            f"Top trends: {kw_str}. Updated daily with the latest news and viral content."
        )

        # Truncate to optimal length (150-160 chars)
        if len(description) > 160:
            description = description[:157] + '...'

        return description

    def _build_og_image(self) -> str:
        """Build Open Graph image meta tags with dimensions."""
        if self._hero_image:
            url = self._hero_image.get('url_large') or self._hero_image.get('url_medium', '')
            if url:
                return f'''<meta property="og:image" content="{html.escape(url)}">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="Today's trending topics on DailyTrending.info">'''
        return '''<meta property="og:image" content="https://dailytrending.info/og-image.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="DailyTrending.info - What's trending today">'''

    def _build_twitter_image(self) -> str:
        """Build Twitter Card image meta tag."""
        if self._hero_image:
            url = self._hero_image.get('url_large') or self._hero_image.get('url_medium', '')
            if url:
                return f'<meta name="twitter:image" content="{html.escape(url)}">'
        return '<meta name="twitter:image" content="https://dailytrending.info/og-image.png">'

    def _build_structured_data(self) -> str:
        """Build JSON-LD structured data for LLMs and search engines."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        iso_date = datetime.now().isoformat()

        # Get top stories for article list (NewsArticle for news content)
        top_stories = []
        for i, trend in enumerate(self.ctx.trends[:10]):
            story = {
                "@type": "NewsArticle",
                "position": i + 1,
                "headline": trend.get('title', 'Untitled'),
                "name": trend.get('title', 'Untitled'),
                "url": trend.get('url', ''),
                "description": trend.get('description', '')[:200] if trend.get('description') else '',
                "datePublished": date_str,
            }
            top_stories.append(story)

        # Get category list
        categories = [{"@type": "Thing", "name": cat} for cat in self.grouped_trends.keys()]

        # Build main structured data
        structured_data = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "@id": "https://dailytrending.info/#website",
                    "url": "https://dailytrending.info/",
                    "name": "DailyTrending.info",
                    "description": "Daily aggregated trending topics from news, technology, social media, and more",
                    "publisher": {
                        "@type": "Organization",
                        "name": "DailyTrending.info",
                        "url": "https://dailytrending.info/"
                    },
                    "inLanguage": "en-US"
                },
                {
                    "@type": "WebPage",
                    "@id": "https://dailytrending.info/#webpage",
                    "url": "https://dailytrending.info/",
                    "name": f"DailyTrending.info - {self._get_top_topic()}",
                    "isPartOf": {"@id": "https://dailytrending.info/#website"},
                    "datePublished": date_str,
                    "dateModified": iso_date,
                    "description": self._build_meta_description(),
                    "breadcrumb": {
                        "@type": "BreadcrumbList",
                        "itemListElement": [
                            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://dailytrending.info/"}
                        ]
                    },
                    "inLanguage": "en-US",
                    "potentialAction": {
                        "@type": "ReadAction",
                        "target": "https://dailytrending.info/"
                    }
                },
                {
                    "@type": "ItemList",
                    "name": "Today's Trending Topics",
                    "description": f"Top {len(top_stories)} trending stories for {date_str}",
                    "numberOfItems": len(top_stories),
                    "itemListElement": top_stories
                },
                {
                    "@type": "CollectionPage",
                    "name": "Trending Categories",
                    "hasPart": categories,
                    "about": {
                        "@type": "Thing",
                        "name": "Trending Topics",
                        "description": "Aggregated trending content from multiple sources"
                    }
                }
            ]
        }

        # Add FAQ schema for common questions (helps with LLM understanding)
        faq_items = []
        if self.keyword_freq:
            top_kws = [kw.title() for kw, _ in self.keyword_freq[:3]]
            faq_items.append({
                "@type": "Question",
                "name": "What are today's top trending topics?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Today's top trending topics include: {', '.join(top_kws)}. We aggregate trends from {len(self.grouped_trends)} categories including news, technology, science, and entertainment."
                }
            })

        total_stories = len(self.ctx.trends)
        total_sources = len(set(t.get('source', '').split('_')[0] for t in self.ctx.trends))
        faq_items.append({
            "@type": "Question",
            "name": "How many trending stories are featured today?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"Today we feature {total_stories} trending stories from {total_sources} different sources across {len(self.grouped_trends)} categories."
            }
        })

        faq_items.append({
            "@type": "Question",
            "name": "How often is DailyTrending.info updated?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "DailyTrending.info is automatically regenerated every day at 6 AM UTC with fresh trending content from news outlets, social media, and technology sources."
            }
        })

        if faq_items:
            structured_data["@graph"].append({
                "@type": "FAQPage",
                "mainEntity": faq_items
            })

        # Add HowTo schema for using the site (helps LLMs understand site purpose)
        structured_data["@graph"].append({
            "@type": "HowTo",
            "name": "How to stay informed with DailyTrending.info",
            "description": "Get a quick overview of what's trending across news, technology, and social media",
            "step": [
                {
                    "@type": "HowToStep",
                    "position": 1,
                    "name": "Browse trending topics",
                    "text": "Scan the hero section and top stories for the biggest news of the day"
                },
                {
                    "@type": "HowToStep",
                    "position": 2,
                    "name": "Explore by category",
                    "text": "Navigate to specific sections like Technology, World News, or Social for focused content"
                },
                {
                    "@type": "HowToStep",
                    "position": 3,
                    "name": "Save stories for later",
                    "text": "Click the bookmark icon on any story to save it to your personal reading list"
                },
                {
                    "@type": "HowToStep",
                    "position": 4,
                    "name": "Subscribe via RSS",
                    "text": "Use the RSS feed at /feed.xml to get updates in your favorite reader"
                }
            ]
        })

        # Add speakable property for voice assistants
        structured_data["@graph"].append({
            "@type": "WebPage",
            "@id": "https://dailytrending.info/#speakable",
            "speakable": {
                "@type": "SpeakableSpecification",
                "cssSelector": [".headline-xl", ".hero-subheadline", ".story-title"]
            }
        })

        # Add mentions for key entities (helps LLMs understand content relationships)
        mentions = []
        for kw, freq in self.keyword_freq[:10]:
            mentions.append({
                "@type": "Thing",
                "name": kw.title(),
                "description": f"Trending topic appearing in {freq} stories today"
            })

        if mentions:
            structured_data["@graph"].append({
                "@type": "Article",
                "@id": "https://dailytrending.info/#article",
                "headline": self.design.get('headline', "Today's Trending Topics"),
                "datePublished": date_str,
                "dateModified": iso_date,
                "mentions": mentions,
                "about": [{"@type": "Thing", "name": cat} for cat in list(self.grouped_trends.keys())[:5]],
                "wordCount": sum(len((t.get('title', '') + ' ' + (t.get('description', '') or '')).split()) for t in self.ctx.trends),
                "timeRequired": f"PT{self._get_total_reading_time()}M"
            })

        return f'<script type="application/ld+json">\n{json.dumps(structured_data, indent=2)}\n    </script>'

    def build(self) -> str:
        """Build the complete HTML page."""
        # Get design system classes
        card_style = self.design.get('card_style', 'bordered')
        hover_effect = self.design.get('hover_effect', 'lift')
        text_transform = self.design.get('text_transform_headings', 'none')
        animation_level = self.design.get('animation_level', 'subtle')

        # Build body classes - always start with dark-mode
        # JavaScript will override based on user preference from localStorage
        body_classes = [
            f"layout-{self.layout}",
            f"hero-{self.hero_style}",
            f"card-style-{card_style}",
            f"hover-{hover_effect}",
            f"animation-{animation_level}",
            "dark-mode",  # Always default to dark mode
        ]

        if text_transform != 'none':
            body_classes.append(f"text-transform-{text_transform}")

        # Add creative flourish classes from design spec
        bg_pattern = self.design.get('background_pattern', 'none')
        if bg_pattern and bg_pattern != 'none':
            body_classes.append(f"bg-pattern-{bg_pattern}")

        accent_style = self.design.get('accent_style', 'none')
        if accent_style and accent_style != 'none':
            body_classes.append(f"accent-{accent_style}")

        special_mode = self.design.get('special_mode', 'standard')
        if special_mode and special_mode != 'standard':
            body_classes.append(f"mode-{special_mode}")

        # Add animation modifiers
        if self.design.get('use_float_animation', False):
            body_classes.append("use-float")
        if self.design.get('use_pulse_animation', False):
            body_classes.append("use-pulse")

        # Add new design dimension classes
        image_treatment = self.design.get('image_treatment', 'none')
        if image_treatment and image_treatment != 'none':
            body_classes.append(f"image-treatment-{image_treatment}")

        card_aspect = self.design.get('card_aspect_ratio', 'auto')
        if card_aspect and card_aspect != 'auto':
            body_classes.append(f"aspect-{card_aspect}")

        # Generate SEO-friendly title
        top_topic = self._get_top_topic()
        page_title = f"DailyTrending.info - {top_topic}"
        meta_description = self._build_meta_description()

        # Get top keywords for meta tags
        top_keywords = [kw for kw, _ in self.keyword_freq[:15]]
        keywords_str = ", ".join(top_keywords) if top_keywords else "trending, news, technology, world events"

        return f"""<!DOCTYPE html>
<html lang="en" itemscope itemtype="https://schema.org/WebPage">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- Primary Meta Tags -->
    <title>{html.escape(page_title)}</title>
    <meta name="title" content="{html.escape(page_title)}">
    <meta name="description" content="{html.escape(meta_description)}">
    <meta name="keywords" content="{html.escape(keywords_str)}">
    <meta name="author" content="DailyTrending.info">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
    <meta name="googlebot" content="index, follow">

    <!-- Canonical URL -->
    <link rel="canonical" href="https://dailytrending.info/">

    <!-- Theme Color - Always dark mode as default -->
    <meta name="theme-color" content="#0a0a0a">
    <meta name="color-scheme" content="dark light">

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://dailytrending.info/">
    <meta property="og:title" content="{html.escape(page_title)}">
    <meta property="og:description" content="{html.escape(meta_description)}">
    <meta property="og:site_name" content="DailyTrending.info">
    <meta property="og:locale" content="en_US">
    {self._build_og_image()}

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@bradshannon">
    <meta name="twitter:creator" content="@bradshannon">
    <meta name="twitter:url" content="https://dailytrending.info/">
    <meta name="twitter:title" content="{html.escape(page_title)}">
    <meta name="twitter:description" content="{html.escape(meta_description)}">
    {self._build_twitter_image()}

    <!-- Additional SEO -->
    <meta name="generator" content="DailyTrending.info Autonomous Generator">
    <meta name="date" content="{datetime.now().strftime('%Y-%m-%d')}">
    <meta name="last-modified" content="{datetime.now().isoformat()}">

    <!-- Structured Data for LLMs and Search Engines -->
    {self._build_structured_data()}

    <!-- Feeds -->
    <link rel="alternate" type="application/rss+xml" title="DailyTrending.info RSS" href="https://dailytrending.info/feed.xml">

    <!-- PWA Support -->
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/icons/icon-192.png">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="DailyTrending">

    {self._build_fonts()}
    {self._build_styles()}

    <!-- Google Analytics -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XZNXRW8S7L"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-XZNXRW8S7L');
    </script>

    <!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2196222970720414" crossorigin="anonymous"></script>
    <style>
      .ad-container {{
        display: flex;
        justify-content: center;
        padding: 1rem 0;
        min-height: 90px;
      }}
      .ad-container.ad-horizontal {{
        margin: 2rem auto;
        max-width: var(--max-width);
      }}
      .ad-container.ad-sidebar {{
        margin: 1rem 0;
      }}
      @media print {{
        .ad-container {{ display: none !important; }}
      }}
    </style>
</head>
<body class="{' '.join(body_classes)}">
    <a href="#main-content" class="skip-link">Skip to main content</a>
    {self._build_nav()}

    <article itemscope itemtype="https://schema.org/Article">
        {self._build_hero()}
        {self._build_breaking_ticker()}

        {self._build_ad_unit(ad_format="horizontal")}

        <main id="main-content" role="main">
            {self._build_word_cloud()}
            {self._build_top_stories()}

            {self._build_ad_unit(ad_format="horizontal")}

            {self._build_enriched_content_section()}

            {self._build_category_sections()}
            {self._build_stats_bar()}
        </main>
    </article>

    {self._build_footer()}
    {self._build_scripts()}
</body>
</html>"""

    def _build_fonts(self) -> str:
        """Build Google Fonts link with preload hints."""
        primary = self.design.get('font_primary', 'Space Grotesk').replace(' ', '+')
        secondary = self.design.get('font_secondary', 'Inter').replace(' ', '+')

        # Preload hero image if available
        hero_preload = ""
        if self._hero_image:
            img_url = self._hero_image.get('url_large', self._hero_image.get('url_medium', ''))
            if img_url and img_url.startswith('https://'):
                hero_preload = f'\n    <link rel="preload" as="image" href="{html.escape(img_url)}">'

        return f"""
    <!-- DNS Prefetch for external resources -->
    <link rel="dns-prefetch" href="https://fonts.googleapis.com">
    <link rel="dns-prefetch" href="https://fonts.gstatic.com">
    <link rel="dns-prefetch" href="https://www.googletagmanager.com">

    <!-- Font preconnect and load -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family={primary}:wght@400;500;600;700;800;900&family={secondary}:wght@400;500;600&display=swap" rel="stylesheet">{hero_preload}"""

    def _build_styles(self) -> str:
        """Build all CSS styles with layout variants."""
        d = self.design

        # Get hero image - use the pre-computed relevant image
        hero_image = self._hero_image
        hero_bg = ""
        if hero_image:
            # Validate and sanitize URL for CSS injection prevention
            img_url = hero_image.get('url_large', hero_image.get('url_medium', ''))
            if img_url and img_url.startswith(('https://', 'http://')):
                # Escape quotes and parentheses that could break CSS
                safe_url = img_url.replace("'", "%27").replace('"', "%22").replace("(", "%28").replace(")", "%29")
                hero_bg = f"url('{safe_url}') center/cover"
            else:
                hero_bg = FallbackImageGenerator.get_gradient_css()
        else:
            hero_bg = FallbackImageGenerator.get_gradient_css()

        # Extract design system properties with fallbacks
        card_style = d.get('card_style', 'bordered')
        card_radius = d.get('card_radius', '1rem')
        card_padding = d.get('card_padding', '1.5rem')
        hover_effect = d.get('hover_effect', 'lift')
        animation_level = d.get('animation_level', 'subtle')
        text_transform = d.get('text_transform_headings', 'none')
        is_dark = d.get('is_dark_mode', True)
        use_gradients = d.get('use_gradients', True)
        use_blur = d.get('use_blur', False)
        spacing = d.get('spacing', 'comfortable')

        # Creative flourishes
        bg_pattern = d.get('background_pattern', 'none')
        accent_style = d.get('accent_style', 'none')
        special_mode = d.get('special_mode', 'standard')
        transition_speed = d.get('transition_speed', '200ms')
        hover_transform = d.get('hover_transform', 'translateY(-2px)')
        use_pulse = d.get('use_pulse_animation', False)
        use_float = d.get('use_float_animation', False)

        # Map spacing to section gaps
        spacing_map = {
            'compact': '2rem',
            'comfortable': '3rem',
            'spacious': '4rem'
        }
        section_gap = spacing_map.get(spacing, '3rem')

        # Animation duration based on level
        animation_map = {
            'none': '0s',
            'subtle': '0.3s',
            'moderate': '0.4s',
            'playful': '0.5s'
        }
        anim_duration = animation_map.get(animation_level, '0.3s')

        # Always use dark mode as base - force dark background colors
        # but preserve the design's accent colors for theming
        dark_bg = '#0a0a0a'
        dark_text = '#ffffff'
        dark_muted = '#a1a1aa'
        dark_card_bg = '#18181b'
        dark_border = '#27272a'

        # Get accent colors from design (these work in both modes)
        accent = d.get('color_accent', '#6366f1')
        accent_secondary = d.get('color_accent_secondary', '#8b5cf6')

        return f"""
    <style>
        /* ===== CSS CUSTOM PROPERTIES ===== */
        /* Base theme is always dark mode */
        :root {{
            --color-bg: {dark_bg};
            --color-text: {dark_text};
            --color-accent: {accent};
            --color-accent-secondary: {accent_secondary};
            --color-muted: {dark_muted};
            --color-card-bg: {dark_card_bg};
            --color-border: {dark_border};

            --font-primary: '{d.get('font_primary', 'Space Grotesk')}', system-ui, sans-serif;
            --font-secondary: '{d.get('font_secondary', 'Inter')}', system-ui, sans-serif;

            /* Dynamic radius from design spec */
            --radius-sm: calc({card_radius} * 0.5);
            --radius: {card_radius};
            --radius-lg: calc({card_radius} * 1.5);
            --radius-xl: calc({card_radius} * 2);

            /* Dynamic spacing */
            --card-padding: {card_padding};
            --section-gap: {section_gap};

            /* Animation speed */
            --transition: {anim_duration} cubic-bezier(0.4, 0, 0.2, 1);
            --transition-fast: calc({anim_duration} * 0.5) cubic-bezier(0.4, 0, 0.2, 1);
            --transition-slow: calc({anim_duration} * 1.5) cubic-bezier(0.4, 0, 0.2, 1);
            --max-width: {d.get('max_width', '1400px')};

            --hero-bg: {hero_bg};
        }}

        /* ===== RESET & BASE ===== */
        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        html {{
            scroll-behavior: smooth;
            font-size: 16px;
        }}

        body {{
            font-family: var(--font-secondary);
            line-height: 1.6;
            color: var(--color-text);
            background: var(--color-bg);
            min-height: 100vh;
            overflow-x: hidden;
            transition: background-color 0.3s ease, color 0.3s ease;
        }}

        a {{
            color: inherit;
            text-decoration: none;
        }}

        img {{
            max-width: 100%;
            height: auto;
        }}

        /* ===== TYPOGRAPHY ===== */
        .headline-xl {{
            font-family: var(--font-primary);
            font-size: clamp(2.5rem, 8vw, 5rem);
            font-weight: 800;
            line-height: 1.05;
            letter-spacing: -0.02em;
        }}

        .headline-lg {{
            font-family: var(--font-primary);
            font-size: clamp(1.75rem, 4vw, 3rem);
            font-weight: 700;
            line-height: 1.1;
        }}

        .headline-md {{
            font-family: var(--font-primary);
            font-size: clamp(1.25rem, 2.5vw, 1.75rem);
            font-weight: 600;
            line-height: 1.2;
        }}

        .text-muted {{
            color: var(--color-muted);
        }}

        /* Text transform variants */
        .text-transform-uppercase .headline-xl,
        .text-transform-uppercase .headline-lg,
        .text-transform-uppercase .headline-md,
        .text-transform-uppercase .section-title,
        .text-transform-uppercase .story-title {{
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .text-transform-capitalize .headline-xl,
        .text-transform-capitalize .headline-lg,
        .text-transform-capitalize .headline-md,
        .text-transform-capitalize .section-title,
        .text-transform-capitalize .story-title {{
            text-transform: capitalize;
        }}

        /* Animation level variants */
        .animation-none *, .animation-none *::before, .animation-none *::after {{
            animation: none !important;
            transition: none !important;
        }}

        .animation-playful .story-card {{
            transition-timing-function: cubic-bezier(0.68, -0.55, 0.265, 1.55);
        }}

        .animation-playful .word-cloud-item:hover {{
            animation: bounce 0.5s ease;
        }}

        @keyframes bounce {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.2); }}
        }}

        /* ===== NAVIGATION ===== */
        .nav {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 100;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: linear-gradient(to bottom, var(--color-bg), transparent);
            transition: background var(--transition);
        }}

        .nav.scrolled {{
            background: rgba(10, 10, 10, 0.95);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--color-border);
        }}

        .nav-logo {{
            font-family: var(--font-primary);
            font-size: 1.5rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .nav-logo::before {{
            content: '';
            width: 8px;
            height: 8px;
            background: var(--color-accent);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}

        .nav-links {{
            display: flex;
            gap: 2rem;
            list-style: none;
        }}

        .nav-links a {{
            font-size: 0.9rem;
            color: var(--color-muted);
            transition: color var(--transition);
        }}

        .nav-links a:hover {{
            color: var(--color-text);
        }}

        .nav-actions {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .nav-date {{
            font-size: 0.85rem;
            color: var(--color-muted);
        }}

        .nav-github {{
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0.5rem;
            color: var(--color-muted);
            border-radius: var(--radius-sm);
            transition: all var(--transition);
        }}

        .nav-github:hover {{
            color: var(--color-text);
            background: var(--color-card-bg);
        }}

        /* ===== MOBILE MENU ===== */
        .mobile-menu-toggle {{
            display: none;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 5px;
            width: 44px;
            height: 44px;
            padding: 0;
            background: transparent;
            border: none;
            cursor: pointer;
            z-index: 1001;
        }}

        .hamburger-line {{
            display: block;
            width: 24px;
            height: 2px;
            background: var(--color-text);
            border-radius: 2px;
            transition: all 0.3s ease;
        }}

        .mobile-menu-toggle.active .hamburger-line:nth-child(1) {{
            transform: rotate(45deg) translate(5px, 5px);
        }}

        .mobile-menu-toggle.active .hamburger-line:nth-child(2) {{
            opacity: 0;
        }}

        .mobile-menu-toggle.active .hamburger-line:nth-child(3) {{
            transform: rotate(-45deg) translate(5px, -5px);
        }}

        @media (max-width: 1024px) {{
            .mobile-menu-toggle {{
                display: flex;
            }}

            .nav-links {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                height: 100vh;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                gap: 2rem;
                background: var(--color-bg);
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s ease, visibility 0.3s ease;
                z-index: 1000;
                overflow: hidden;
            }}

            .nav-links.active {{
                opacity: 1;
                visibility: visible;
            }}

            .nav-links li {{
                opacity: 0;
                transform: translateY(20px);
                transition: opacity 0.3s ease, transform 0.3s ease;
            }}

            .nav-links.active li {{
                opacity: 1;
                transform: translateY(0);
            }}

            .nav-links.active li:nth-child(1) {{ transition-delay: 0.1s; }}
            .nav-links.active li:nth-child(2) {{ transition-delay: 0.15s; }}
            .nav-links.active li:nth-child(3) {{ transition-delay: 0.2s; }}
            .nav-links.active li:nth-child(4) {{ transition-delay: 0.25s; }}
            .nav-links.active li:nth-child(5) {{ transition-delay: 0.3s; }}
            .nav-links.active li:nth-child(6) {{ transition-delay: 0.35s; }}
            .nav-links.active li:nth-child(7) {{ transition-delay: 0.4s; }}

            .nav-links a {{
                font-size: 1.5rem;
                padding: 0.5rem 1rem;
            }}

            .nav-date {{
                display: none;
            }}
        }}

        /* ===== THEME TOGGLE ===== */
        .theme-toggle {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            padding: 0;
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-sm);
            color: var(--color-muted);
            cursor: pointer;
            transition: all var(--transition);
        }}

        .theme-toggle:hover {{
            color: var(--color-text);
            border-color: var(--color-accent);
            background: rgba(99, 102, 241, 0.1);
        }}

        .theme-toggle .sun-icon {{
            display: none;
        }}

        .theme-toggle .moon-icon {{
            display: block;
        }}

        /* Light mode: show sun, hide moon */
        body.light-mode .theme-toggle .sun-icon {{
            display: block;
        }}

        body.light-mode .theme-toggle .moon-icon {{
            display: none;
        }}

        /* ===== LIGHT MODE OVERRIDES ===== */
        body.light-mode {{
            --color-bg: #ffffff;
            --color-text: #1a1a2e;
            --color-muted: #64748b;
            --color-card-bg: #f8fafc;
            --color-border: #e2e8f0;
            background-color: #ffffff !important;
            color: #1a1a2e !important;
        }}

        body.light-mode .nav {{
            background: linear-gradient(to bottom, var(--color-bg), transparent);
        }}

        body.light-mode .nav.scrolled {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
        }}

        body.light-mode .hero::after {{
            background: linear-gradient(180deg, var(--color-bg) 0%, transparent 30%, transparent 70%, var(--color-bg) 100%);
        }}

        body.light-mode .word-cloud {{
            background: var(--color-card-bg);
            border-color: var(--color-border);
        }}

        body.light-mode .story-card {{
            background: var(--color-card-bg);
        }}

        body.light-mode .story-card.featured {{
            background: linear-gradient(135deg, var(--color-accent), var(--color-accent-secondary));
            color: #ffffff;
        }}

        body.light-mode .story-card.featured .story-title,
        body.light-mode .story-card.featured .story-source,
        body.light-mode .story-card.featured .story-description {{
            color: #ffffff;
        }}

        body.light-mode .compact-card {{
            background: var(--color-card-bg);
        }}

        body.light-mode .stats-bar {{
            background: var(--color-card-bg);
            border-color: var(--color-border);
        }}

        body.light-mode .ticker-wrap {{
            background: var(--color-card-bg);
            border-color: var(--color-border);
        }}

        body.light-mode .archive-btn,
        body.light-mode .github-btn {{
            background: var(--color-card-bg);
            border-color: var(--color-border);
            color: var(--color-text);
        }}

        body.light-mode .archive-btn:hover,
        body.light-mode .github-btn:hover {{
            border-color: var(--color-accent);
            background: rgba(99, 102, 241, 0.1);
        }}

        body.light-mode .theme-toggle {{
            background: var(--color-card-bg);
            border-color: var(--color-border);
        }}

        body.light-mode .nav-logo,
        body.light-mode .headline-xl,
        body.light-mode .headline-lg,
        body.light-mode .headline-md,
        body.light-mode .section-title,
        body.light-mode .story-title,
        body.light-mode .compact-card-title,
        body.light-mode .footer-brand {{
            color: #1a1a2e;
        }}

        body.light-mode .nav-links a,
        body.light-mode .nav-date,
        body.light-mode .text-muted,
        body.light-mode .story-description,
        body.light-mode .footer-description,
        body.light-mode .section-count {{
            color: #64748b;
        }}

        /* Hero text needs special handling in light mode for readability over images */
        body.light-mode .hero-subtitle,
        body.light-mode .hero-meta,
        body.light-mode .hero-secondary {{
            color: rgba(255, 255, 255, 0.95);
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5), 0 1px 3px rgba(0, 0, 0, 0.4);
        }}

        body.light-mode .section-header {{
            border-bottom-color: #e2e8f0;
        }}

        body.light-mode footer {{
            border-top-color: #e2e8f0;
            background-color: #ffffff;
        }}

        body.light-mode .footer-bottom {{
            border-top-color: #e2e8f0;
        }}

        body.light-mode .nav-github,
        body.light-mode .footer-github {{
            color: #64748b;
        }}

        body.light-mode .nav-github:hover,
        body.light-mode .footer-github:hover {{
            color: #1a1a2e;
        }}

        /* Light mode card style variants */
        body.light-mode .card-style-glass .story-card {{
            background: rgba(0, 0, 0, 0.03);
            border: 1px solid rgba(0, 0, 0, 0.08);
        }}

        body.light-mode .card-style-glass .compact-card {{
            background: rgba(0, 0, 0, 0.02);
            border: 1px solid rgba(0, 0, 0, 0.06);
        }}

        body.light-mode .card-style-minimal .story-card,
        body.light-mode .card-style-minimal .compact-card {{
            background: transparent;
            border-bottom-color: #e2e8f0;
        }}

        body.light-mode .card-style-outline .story-card,
        body.light-mode .card-style-outline .compact-card {{
            background: transparent;
            border-color: #e2e8f0;
        }}

        body.light-mode .card-style-shadow .story-card {{
            box-shadow: 0 4px 12px -2px rgba(0, 0, 0, 0.1);
        }}

        body.light-mode .card-style-shadow .compact-card {{
            box-shadow: 0 2px 8px -2px rgba(0, 0, 0, 0.08);
        }}

        /* Light mode hover effects */
        body.light-mode .hover-lift .story-card:hover {{
            box-shadow: 0 20px 40px -12px rgba(0, 0, 0, 0.15);
        }}

        body.light-mode .hover-lift .compact-card:hover {{
            box-shadow: 0 8px 20px -8px rgba(0, 0, 0, 0.12);
        }}

        /* ===== HERO SECTION ===== */
        .hero {{
            min-height: 50vh;
            max-height: 60vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 5rem 2rem 3rem;
            position: relative;
            overflow: hidden;
        }}

        /* Background image layer - now more visible */
        .hero::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: var(--hero-bg);
            opacity: 0.4;
            z-index: 0;
            filter: saturate(1.2);
        }}

        /* Overlay for text readability */
        .hero::after {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(
                180deg,
                rgba(var(--color-bg-rgb, 10, 10, 26), 0.7) 0%,
                rgba(var(--color-bg-rgb, 10, 10, 26), 0.4) 40%,
                rgba(var(--color-bg-rgb, 10, 10, 26), 0.5) 60%,
                rgba(var(--color-bg-rgb, 10, 10, 26), 0.9) 100%
            );
            z-index: 1;
        }}

        .hero-content {{
            max-width: var(--max-width);
            margin: 0 auto;
            width: 100%;
            position: relative;
            z-index: 2;
        }}

        .hero-eyebrow {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: var(--color-accent);
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            border-radius: var(--radius-sm);
            margin-bottom: 1.5rem;
            animation: fadeInUp 0.6s ease-out;
        }}

        .hero-eyebrow span {{
            animation: pulse 2s ease-in-out infinite;
        }}

        /* Fixed: headline now wraps properly and displays full text */
        .hero h1 {{
            margin-bottom: 1.5rem;
            max-width: 100%;
            word-wrap: break-word;
            overflow-wrap: break-word;
            hyphens: auto;
            animation: fadeInUp 0.8s ease-out 0.1s both;
        }}

        .hero-subtitle {{
            font-size: clamp(1.1rem, 2vw, 1.35rem);
            color: rgba(255, 255, 255, 0.9);
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.7), 0 1px 3px rgba(0, 0, 0, 0.5);
            max-width: 700px;
            margin-bottom: 2rem;
            animation: fadeInUp 0.8s ease-out 0.2s both;
        }}

        .hero-actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
            align-items: center;
            animation: fadeInUp 0.8s ease-out 0.25s both;
        }}

        .hero-cta {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.9rem 1.4rem;
            background: var(--color-accent);
            color: #0b0b0f;
            font-weight: 700;
            border-radius: var(--radius);
            border: 1px solid transparent;
            box-shadow: 0 10px 25px rgba(0,0,0,0.35);
            transition: transform var(--transition), box-shadow var(--transition), background var(--transition);
        }}

        .hero-cta:hover {{
            transform: translateY(-2px);
            box-shadow: 0 15px 35px rgba(0,0,0,0.45);
            background: var(--color-accent-secondary, var(--color-accent));
        }}

        .hero-secondary {{
            color: rgba(255, 255, 255, 0.85);
            text-shadow: 0 2px 6px rgba(0, 0, 0, 0.6);
            font-size: 0.95rem;
        }}

        .hero-capsule {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1rem;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            color: var(--color-text);
            max-width: 760px;
            backdrop-filter: blur(12px);
            animation: fadeInUp 0.8s ease-out 0.3s both;
        }}

        .hero-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.85);
            text-shadow: 0 2px 6px rgba(0, 0, 0, 0.6);
            animation: fadeInUp 0.8s ease-out 0.3s both;
        }}

        .hero-meta span {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        /* ===== HERO STYLE VARIANTS ===== */

        /* CINEMATIC - Dramatic movie-poster style */
        .hero-cinematic .hero::after {{
            background: linear-gradient(
                180deg,
                rgba(0, 0, 0, 0.3) 0%,
                rgba(0, 0, 0, 0.1) 30%,
                rgba(0, 0, 0, 0.2) 70%,
                rgba(0, 0, 0, 0.95) 100%
            );
        }}

        .hero-cinematic .hero::before {{
            opacity: 0.6;
            animation: cinematicZoom 20s ease-in-out infinite;
        }}

        /* GLASSMORPHISM - Frosted glass effect */
        .hero-glassmorphism .hero-content {{
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            padding: 3rem;
            border-radius: var(--radius-lg);
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}

        .hero-glassmorphism .hero::before {{
            opacity: 0.5;
        }}

        .hero-glassmorphism .hero::after {{
            background: transparent;
        }}

        /* NEON - Cyberpunk neon glow */
        .hero-neon .hero {{
            background: linear-gradient(135deg, #0a0a1a 0%, #1a0a2e 100%);
        }}

        .hero-neon .hero::before {{
            opacity: 0.3;
            mix-blend-mode: screen;
        }}

        .hero-neon .hero-content {{
            text-shadow: 0 0 10px var(--color-accent), 0 0 20px var(--color-accent), 0 0 40px var(--color-accent);
        }}

        .hero-neon .hero h1 {{
            animation: neonFlicker 3s ease-in-out infinite, fadeInUp 0.8s ease-out 0.1s both;
        }}

        .hero-neon .hero-eyebrow {{
            box-shadow: 0 0 10px var(--color-accent), 0 0 20px var(--color-accent);
        }}

        /* DUOTONE - Two-tone color overlay */
        .hero-duotone .hero::before {{
            opacity: 0.7;
            filter: grayscale(100%);
        }}

        .hero-duotone .hero::after {{
            background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-secondary) 100%);
            mix-blend-mode: multiply;
            opacity: 0.6;
        }}

        /* PARTICLES - Floating particles animation */
        .hero-particles .hero {{
            background: radial-gradient(ellipse at bottom, #1a1a3e 0%, #0a0a1a 100%);
        }}

        .hero-particles .hero::before {{
            opacity: 0.3;
        }}

        .hero-particles .hero .hero-particles-container {{
            position: absolute;
            inset: 0;
            z-index: 1;
            overflow: hidden;
        }}

        .hero-particles .hero .particle {{
            position: absolute;
            width: 4px;
            height: 4px;
            background: var(--color-accent);
            border-radius: 50%;
            animation: floatParticle 15s infinite ease-in-out;
            opacity: 0.6;
        }}

        /* WAVES - Animated wave background */
        .hero-waves .hero::after {{
            background: transparent;
        }}

        .hero-waves .hero .wave-container {{
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 200px;
            overflow: hidden;
            z-index: 1;
        }}

        .hero-waves .hero .wave {{
            position: absolute;
            bottom: 0;
            left: -50%;
            width: 200%;
            height: 100%;
            background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 120' preserveAspectRatio='none'%3E%3Cpath d='M0,60 C300,120 600,0 900,60 C1200,120 1200,60 1200,60 L1200,120 L0,120 Z' fill='rgba(26,26,60,0.8)'/%3E%3C/svg%3E") repeat-x;
            background-size: 50% 100%;
            animation: waveMove 10s linear infinite;
        }}

        .hero-waves .hero .wave:nth-child(2) {{
            animation-delay: -5s;
            opacity: 0.5;
        }}

        /* GEOMETRIC - Animated geometric shapes */
        .hero-geometric .hero {{
            background: linear-gradient(135deg, #0a0a2e 0%, #1a0a3e 50%, #0a1a2e 100%);
        }}

        .hero-geometric .hero::before {{
            opacity: 0.25;
        }}

        .hero-geometric .hero .geo-shapes {{
            position: absolute;
            inset: 0;
            z-index: 1;
            overflow: hidden;
        }}

        .hero-geometric .hero .geo-shape {{
            position: absolute;
            border: 2px solid var(--color-accent);
            opacity: 0.3;
            animation: geoFloat 20s infinite ease-in-out;
        }}

        .hero-geometric .hero .geo-shape.circle {{
            border-radius: 50%;
        }}

        /* SPOTLIGHT - Lens flare/spotlight effect */
        .hero-spotlight .hero::after {{
            background: radial-gradient(ellipse at 30% 20%, transparent 0%, rgba(0,0,0,0.4) 50%, rgba(0,0,0,0.9) 100%);
        }}

        .hero-spotlight .hero::before {{
            opacity: 0.5;
        }}

        .hero-spotlight .hero .spotlight {{
            position: absolute;
            top: 10%;
            left: 20%;
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, var(--color-accent) 0%, transparent 70%);
            opacity: 0.3;
            filter: blur(40px);
            animation: spotlightMove 15s ease-in-out infinite;
            z-index: 1;
        }}

        /* GLITCH - Glitch art effect */
        .hero-glitch .hero h1 {{
            animation: glitchText 3s infinite, fadeInUp 0.8s ease-out 0.1s both;
        }}

        .hero-glitch .hero::before {{
            animation: glitchBg 5s infinite;
            opacity: 0.5;
        }}

        /* AURORA - Northern lights effect */
        .hero-aurora .hero {{
            background: linear-gradient(180deg, #0a0a1a 0%, #0a1a2e 100%);
        }}

        .hero-aurora .hero::before {{
            opacity: 0.3;
        }}

        .hero-aurora .hero .aurora {{
            position: absolute;
            inset: 0;
            z-index: 1;
            background: linear-gradient(
                180deg,
                transparent 0%,
                rgba(0, 255, 150, 0.1) 20%,
                rgba(0, 200, 255, 0.15) 40%,
                rgba(150, 0, 255, 0.1) 60%,
                transparent 100%
            );
            animation: auroraShift 8s ease-in-out infinite;
            filter: blur(60px);
        }}

        /* MESH - Gradient mesh background */
        .hero-mesh .hero {{
            background:
                radial-gradient(at 40% 20%, var(--color-accent) 0%, transparent 50%),
                radial-gradient(at 80% 0%, var(--color-accent-secondary) 0%, transparent 50%),
                radial-gradient(at 0% 50%, rgba(100, 0, 255, 0.5) 0%, transparent 50%),
                radial-gradient(at 80% 50%, rgba(0, 200, 255, 0.3) 0%, transparent 50%),
                radial-gradient(at 0% 100%, var(--color-accent) 0%, transparent 50%),
                var(--color-bg);
            animation: meshShift 20s ease-in-out infinite;
        }}

        .hero-mesh .hero::before {{
            opacity: 0.2;
        }}

        .hero-mesh .hero::after {{
            background: rgba(var(--color-bg-rgb, 10, 10, 26), 0.3);
        }}

        /* RETRO - Synthwave/retrowave style */
        .hero-retro .hero {{
            background: linear-gradient(180deg, #0a0010 0%, #1a0030 50%, #2a0050 100%);
        }}

        .hero-retro .hero::before {{
            opacity: 0.4;
        }}

        .hero-retro .hero .retro-grid {{
            position: absolute;
            bottom: 0;
            left: -50%;
            right: -50%;
            height: 60%;
            background:
                linear-gradient(transparent 0%, transparent 49%, rgba(255, 0, 128, 0.5) 50%, transparent 51%, transparent 100%),
                linear-gradient(90deg, transparent 0%, transparent 49%, rgba(255, 0, 128, 0.3) 50%, transparent 51%, transparent 100%);
            background-size: 60px 60px;
            transform: perspective(500px) rotateX(60deg);
            transform-origin: center top;
            animation: retroGrid 2s linear infinite;
            z-index: 1;
        }}

        .hero-retro .hero .retro-sun {{
            position: absolute;
            bottom: 30%;
            left: 50%;
            transform: translateX(-50%);
            width: 200px;
            height: 200px;
            background: linear-gradient(180deg, #ff6b00 0%, #ff0066 50%, #9900ff 100%);
            border-radius: 50%;
            clip-path: polygon(0 0, 100% 0, 100% 50%, 0 50%);
            z-index: 1;
        }}

        /* Light mode adjustments for hero styles */
        body.light-mode .hero::after {{
            background: linear-gradient(
                180deg,
                rgba(255, 255, 255, 0.7) 0%,
                rgba(255, 255, 255, 0.3) 40%,
                rgba(255, 255, 255, 0.4) 60%,
                rgba(255, 255, 255, 0.95) 100%
            );
        }}

        body.light-mode .hero-glassmorphism .hero-content {{
            background: rgba(255, 255, 255, 0.6);
            border-color: rgba(0, 0, 0, 0.1);
        }}

        body.light-mode .hero-neon .hero {{
            background: linear-gradient(135deg, #f0f0ff 0%, #e0e0ff 100%);
        }}

        body.light-mode .hero-neon .hero-content {{
            text-shadow: none;
        }}

        /* ===== BREAKING NEWS TICKER ===== */
        .ticker-wrap {{
            overflow: hidden;
            background: var(--color-card-bg);
            border-top: 1px solid var(--color-border);
            border-bottom: 1px solid var(--color-border);
            position: relative;
        }}

        .ticker-label {{
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            background: var(--color-accent);
            color: white;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 0 1.5rem;
            display: flex;
            align-items: center;
            z-index: 2;
        }}

        .ticker {{
            display: flex;
            width: fit-content;
            animation: ticker 60s linear infinite;
            padding: 0.75rem 0;
            padding-left: 120px;
        }}

        .ticker:hover {{
            animation-play-state: paused;
        }}

        .ticker-item {{
            flex-shrink: 0;
            padding: 0 2rem;
            font-size: 0.9rem;
            color: var(--color-muted);
            display: flex;
            align-items: center;
            gap: 1rem;
            border-right: 1px solid var(--color-border);
        }}

        .ticker-item strong {{
            color: var(--color-text);
        }}

        .ticker-source {{
            font-size: 0.7rem;
            text-transform: uppercase;
            color: var(--color-accent);
            letter-spacing: 0.05em;
        }}

        /* ===== MAIN CONTENT ===== */
        main {{
            max-width: var(--max-width);
            margin: 0 auto;
            padding: 3rem 2rem;
        }}

        /* ===== WORD CLOUD ===== */
        .word-cloud-section {{
            margin-bottom: 4rem;
            text-align: center;
        }}

        .word-cloud {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            align-items: center;
            gap: 0.5rem 1rem;
            padding: 2rem;
            background: var(--color-card-bg);
            border-radius: var(--radius-lg);
            border: 1px solid var(--color-border);
            min-height: 200px;
        }}

        .word-cloud-item {{
            transition: all var(--transition);
            cursor: default;
            opacity: 0.7;
        }}

        .word-cloud-item:hover {{
            opacity: 1;
            transform: scale(1.1);
            color: var(--color-accent);
        }}

        .word-cloud-item.size-1 {{ font-size: 0.75rem; }}
        .word-cloud-item.size-2 {{ font-size: 0.9rem; }}
        .word-cloud-item.size-3 {{ font-size: 1.1rem; font-weight: 500; }}
        .word-cloud-item.size-4 {{ font-size: 1.4rem; font-weight: 600; }}
        .word-cloud-item.size-5 {{ font-size: 1.8rem; font-weight: 700; color: var(--color-accent); opacity: 1; }}
        .word-cloud-item.size-6 {{ font-size: 2.2rem; font-weight: 800; color: var(--color-accent); opacity: 1; }}

        /* ===== SECTION HEADERS ===== */
        .section {{
            margin-bottom: var(--section-gap);
        }}

        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid var(--color-border);
        }}

        .section-title {{
            font-family: var(--font-primary);
            font-size: 1.5rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .section-title::before {{
            content: '';
            width: 4px;
            height: 1.5rem;
            background: var(--color-accent);
            border-radius: 2px;
        }}

        .section-count {{
            font-size: 0.85rem;
            color: var(--color-muted);
            background: var(--color-card-bg);
            padding: 0.25rem 0.75rem;
            border-radius: var(--radius-sm);
        }}

        /* ===== TOP STORIES GRID ===== */
        .top-stories {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        /* Ensure all cards have consistent compact height */
        .top-stories .story-card {{
            min-height: 160px;
            max-height: 200px;
        }}

        /* Layout variants for top stories - all optimized for horizontal display */
        .layout-newspaper .top-stories {{
            grid-template-columns: repeat(4, 1fr);
        }}

        .layout-newspaper .top-stories .story-card:first-child {{
            grid-row: span 1;
        }}

        .layout-magazine .top-stories {{
            grid-template-columns: repeat(4, 1fr);
        }}

        .layout-magazine .top-stories .story-card:first-child {{
            grid-column: span 1;
        }}

        .layout-dashboard .top-stories {{
            grid-template-columns: repeat(4, 1fr);
        }}

        .layout-minimal .top-stories {{
            grid-template-columns: repeat(4, 1fr);
        }}

        .layout-bold .top-stories {{
            grid-template-columns: repeat(4, 1fr);
        }}

        .layout-bold .top-stories .story-card:first-child {{
            padding: 1rem;
        }}

        .layout-mosaic .top-stories {{
            grid-template-columns: repeat(4, 1fr);
        }}

        .layout-mosaic .top-stories .story-card:nth-child(1),
        .layout-mosaic .top-stories .story-card:nth-child(2),
        .layout-mosaic .top-stories .story-card:nth-child(3),
        .layout-mosaic .top-stories .story-card:nth-child(4) {{
            grid-column: span 1;
            grid-row: span 1;
        }}

        /* ===== STORY CARDS ===== */
        .story-card {{
            position: relative;
            background: var(--color-card-bg);
            border-radius: var(--radius);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
        }}

        /* Card style variants */
        .card-style-bordered .story-card {{
            border: 1px solid var(--color-border);
        }}

        .card-style-shadow .story-card {{
            border: none;
            box-shadow: 0 4px 12px -2px rgba(0, 0, 0, 0.2);
        }}

        .card-style-glass .story-card {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }}

        .card-style-minimal .story-card {{
            background: transparent;
            border: none;
            border-bottom: 1px solid var(--color-border);
            border-radius: 0;
        }}

        .card-style-accent .story-card {{
            border: none;
            border-left: 4px solid var(--color-accent);
        }}

        .card-style-outline .story-card {{
            background: transparent;
            border: 2px solid var(--color-border);
        }}

        /* Hover effect variants */
        .hover-lift .story-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 20px 40px -12px rgba(0, 0, 0, 0.4);
        }}

        .hover-glow .story-card:hover {{
            box-shadow: 0 0 30px -5px var(--color-accent);
        }}

        .hover-scale .story-card:hover {{
            transform: scale(1.02);
        }}

        .hover-border .story-card:hover {{
            border-color: var(--color-accent);
        }}

        .hover-none .story-card:hover {{
            transform: none;
            box-shadow: none;
        }}

        /* ===== STORY BADGES & INDICATORS ===== */
        .story-badges {{
            position: absolute;
            top: 0.75rem;
            left: 0.75rem;
            display: flex;
            gap: 0.5rem;
            z-index: 5;
        }}

        .comparison-badge {{
            font-size: 1rem;
            filter: drop-shadow(0 1px 2px rgba(0,0,0,0.3));
        }}

        .velocity-badge {{
            font-size: 0.65rem;
            font-weight: 700;
            padding: 0.2rem 0.5rem;
            border-radius: 999px;
            letter-spacing: 0.05em;
            text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }}

        .velocity-hot {{
            background: linear-gradient(135deg, #ef4444, #f97316);
            color: white;
            animation: pulse-hot 2s infinite;
        }}

        .velocity-rising {{
            background: linear-gradient(135deg, #f59e0b, #eab308);
            color: #1a1a1a;
        }}

        .velocity-steady {{
            background: var(--color-accent);
            color: white;
        }}

        @keyframes pulse-hot {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.9; transform: scale(1.05); }}
        }}

        /* ===== STORY ACTIONS (Save & Share) ===== */
        .story-actions {{
            position: absolute;
            top: 0.75rem;
            right: 0.75rem;
            display: flex;
            gap: 0.5rem;
            z-index: 5;
            opacity: 0;
            transition: opacity var(--transition);
        }}

        .story-card:hover .story-actions,
        .story-card:focus-within .story-actions {{
            opacity: 1;
        }}

        .save-btn, .share-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            padding: 0;
            background: rgba(0,0,0,0.6);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: var(--radius-sm);
            color: var(--color-muted);
            cursor: pointer;
            transition: all var(--transition);
        }}

        .save-btn:hover, .share-btn:hover {{
            background: var(--color-accent);
            color: white;
            border-color: var(--color-accent);
        }}

        .save-btn.saved {{
            background: var(--color-accent);
            color: white;
        }}

        .save-btn.saved svg {{
            fill: currentColor;
        }}

        /* ===== READING TIME ===== */
        .section-meta {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .reading-time {{
            display: flex;
            align-items: center;
            gap: 0.35rem;
            font-size: 0.8rem;
            color: var(--color-muted);
        }}

        .reading-time svg {{
            opacity: 0.7;
        }}

        /* ===== ACCESSIBILITY ENHANCEMENTS ===== */
        .skip-link {{
            position: absolute;
            top: -100%;
            left: 50%;
            transform: translateX(-50%);
            padding: 1rem 2rem;
            background: var(--color-accent);
            color: white;
            border-radius: var(--radius);
            font-weight: 600;
            z-index: 9999;
            transition: top 0.3s;
        }}

        .skip-link:focus {{
            top: 1rem;
        }}

        /* Focus visible for keyboard navigation */
        *:focus-visible {{
            outline: 2px solid var(--color-accent);
            outline-offset: 2px;
        }}

        /* Screen reader only content */
        .sr-only {{
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }}

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }}
        }}

        /* High contrast mode */
        @media (prefers-contrast: high) {{
            .story-card {{
                border: 2px solid var(--color-text);
            }}
            .velocity-badge, .comparison-badge {{
                border: 1px solid currentColor;
            }}
        }}

        /* ===== BACKGROUND PATTERNS FOR VARIETY ===== */
        /* Dots pattern */
        .pattern-dots .main-content::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: radial-gradient(circle, var(--color-border) 1px, transparent 1px);
            background-size: 24px 24px;
            opacity: 0.4;
            pointer-events: none;
            z-index: -1;
        }}

        /* Grid pattern */
        .pattern-grid .main-content::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image:
                linear-gradient(to right, var(--color-border) 1px, transparent 1px),
                linear-gradient(to bottom, var(--color-border) 1px, transparent 1px);
            background-size: 60px 60px;
            opacity: 0.3;
            pointer-events: none;
            z-index: -1;
        }}

        /* Diagonal lines */
        .pattern-lines .main-content::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: repeating-linear-gradient(
                45deg,
                transparent,
                transparent 10px,
                var(--color-border) 10px,
                var(--color-border) 11px
            );
            opacity: 0.15;
            pointer-events: none;
            z-index: -1;
        }}

        /* Cross pattern */
        .pattern-cross .main-content::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image:
                radial-gradient(circle, transparent 45%, var(--color-border) 55%, transparent 55%);
            background-size: 16px 16px;
            opacity: 0.2;
            pointer-events: none;
            z-index: -1;
        }}

        /* Noise texture */
        .pattern-noise .main-content::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
            opacity: 0.03;
            pointer-events: none;
            z-index: -1;
        }}

        /* Light mode pattern adjustments */
        body.light-mode.pattern-dots .main-content::before,
        body.light-mode.pattern-grid .main-content::before,
        body.light-mode.pattern-lines .main-content::before,
        body.light-mode.pattern-cross .main-content::before {{
            opacity: 0.08;
        }}

        .story-card.has-image {{
            background-size: cover;
            background-position: center;
        }}

        .story-card.has-image::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.7) 100%);
        }}

        /* Improve text legibility on image backgrounds */
        .story-card.has-image .story-title {{
            color: #ffffff;
            text-shadow: 0 2px 4px rgba(0,0,0,0.8), 0 4px 12px rgba(0,0,0,0.6);
        }}

        .story-card.has-image .story-description {{
            color: rgba(255,255,255,0.95);
            text-shadow: 0 1px 3px rgba(0,0,0,0.8), 0 2px 8px rgba(0,0,0,0.5);
        }}

        .story-card.has-image .story-source {{
            color: rgba(255,255,255,0.9);
            text-shadow: 0 1px 3px rgba(0,0,0,0.8);
        }}

        /* Light mode adjustments for image cards */
        body.light-mode .story-card.has-image .story-title,
        body.light-mode .story-card.has-image .story-description,
        body.light-mode .story-card.has-image .story-source {{
            color: #ffffff;
        }}

        .story-card.featured {{
            background: linear-gradient(135deg, var(--color-accent), var(--color-accent-secondary));
            border: none;
        }}

        .story-content {{
            position: relative;
            padding: var(--card-padding);
            padding-top: calc(var(--card-padding) + 1.5rem); /* Extra space for badges */
            display: flex;
            flex-direction: column;
            height: 100%;
            z-index: 1;
        }}

        .story-meta {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
            flex-wrap: wrap;
        }}

        .story-source {{
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--color-accent);
        }}

        .story-time {{
            font-size: 0.65rem;
            color: var(--color-muted);
            font-weight: 400;
        }}

        .story-time::before {{
            content: '•';
            margin-right: 0.5rem;
        }}

        .story-card.featured .story-source,
        .story-card.has-image .story-source {{
            color: rgba(255,255,255,0.8);
        }}

        .story-card.featured .story-time,
        .story-card.has-image .story-time {{
            color: rgba(255,255,255,0.7);
        }}

        /* Discussion Links */
        .discussion-links {{
            display: flex;
            gap: 0.5rem;
            margin-left: auto;
            position: relative;
            z-index: 4;
        }}

        .discussion-link {{
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            font-size: 0.6rem;
            font-weight: 600;
            padding: 0.15rem 0.4rem;
            background: var(--color-accent);
            color: #fff;
            text-decoration: none;
            border-radius: 3px;
            transition: all var(--transition);
        }}

        .discussion-link:hover {{
            transform: scale(1.05);
            filter: brightness(1.1);
        }}

        .story-card.featured .discussion-link,
        .story-card.has-image .discussion-link {{
            background: rgba(255,255,255,0.2);
        }}

        .story-title {{
            font-family: var(--font-primary);
            font-size: 1.1rem;
            font-weight: 600;
            line-height: 1.3;
            margin-bottom: 0.75rem;
            flex-grow: 1;
        }}

        .story-card:first-child .story-title {{
            font-size: 1.25rem;
        }}

        .story-description {{
            font-size: 0.85rem;
            color: var(--color-muted);
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .story-card.featured .story-description,
        .story-card.has-image .story-description {{
            color: rgba(255,255,255,0.9);
        }}

        /* Related Coverage - Story Clustering */
        .related-coverage {{
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid var(--color-border);
            position: relative;
            z-index: 3;
        }}

        .related-label {{
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--color-muted);
            display: block;
            margin-bottom: 0.5rem;
        }}

        .related-links {{
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }}

        .related-link {{
            display: flex;
            align-items: baseline;
            gap: 0.5rem;
            font-size: 0.75rem;
            color: var(--color-text);
            text-decoration: none;
            padding: 0.25rem 0;
            transition: color var(--transition);
            position: relative;
            z-index: 4;
        }}

        .related-link:hover {{
            color: var(--color-accent);
        }}

        .related-source {{
            font-size: 0.6rem;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--color-accent);
            flex-shrink: 0;
            min-width: 4rem;
        }}

        .related-title {{
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .story-card.featured .related-coverage,
        .story-card.has-image .related-coverage {{
            border-top-color: rgba(255,255,255,0.2);
        }}

        .story-card.featured .related-label,
        .story-card.has-image .related-label {{
            color: rgba(255,255,255,0.7);
        }}

        .story-card.featured .related-link,
        .story-card.has-image .related-link {{
            color: rgba(255,255,255,0.9);
        }}

        .story-card.featured .related-source,
        .story-card.has-image .related-source {{
            color: rgba(255,255,255,0.8);
        }}

        .story-link {{
            position: absolute;
            inset: 0;
            z-index: 2;
        }}

        /* ===== CATEGORIES MULTI-COLUMN LAYOUT ===== */
        .categories-section {{
            margin: 3rem 0;
        }}

        .categories-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 2rem;
            margin-top: 1.5rem;
        }}

        .category-column {{
            background: var(--color-card-bg);
            border-radius: var(--radius-lg);
            padding: 1.5rem;
            border: 1px solid var(--color-border);
        }}

        .category-header {{
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid var(--color-accent);
        }}

        .category-title {{
            font-family: var(--font-primary);
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--color-text);
            margin: 0;
        }}

        .category-list {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        @media (max-width: 768px) {{
            .categories-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Legacy category-grid support */
        .category-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem;
        }}

        .layout-newspaper .category-grid {{
            grid-template-columns: repeat(3, 1fr);
        }}

        .layout-minimal .category-grid {{
            grid-template-columns: 1fr;
        }}

        /* ===== COMPACT CARDS ===== */
        .compact-card {{
            display: flex;
            gap: 1rem;
            padding: var(--card-padding);
            background: var(--color-card-bg);
            border-radius: var(--radius-sm);
            transition: all var(--transition);
        }}

        /* Apply card styles to compact cards */
        .card-style-bordered .compact-card {{
            border: 1px solid var(--color-border);
        }}

        .card-style-shadow .compact-card {{
            box-shadow: 0 2px 8px -2px rgba(0, 0, 0, 0.15);
        }}

        .card-style-glass .compact-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(8px);
        }}

        .card-style-minimal .compact-card {{
            background: transparent;
            border-bottom: 1px solid var(--color-border);
            border-radius: 0;
            padding-left: 0;
            padding-right: 0;
        }}

        .card-style-accent .compact-card {{
            border-left: 3px solid var(--color-accent);
            padding-left: calc(var(--card-padding) - 3px);
        }}

        .card-style-outline .compact-card {{
            background: transparent;
            border: 1px solid var(--color-border);
        }}

        /* Apply hover effects to compact cards */
        .hover-lift .compact-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px -8px rgba(0, 0, 0, 0.3);
        }}

        .hover-glow .compact-card:hover {{
            box-shadow: 0 0 20px -5px var(--color-accent);
        }}

        .hover-scale .compact-card:hover {{
            transform: scale(1.01);
        }}

        .hover-border .compact-card:hover {{
            border-color: var(--color-accent);
        }}

        .hover-none .compact-card:hover {{
            transform: none;
        }}

        .compact-card-number {{
            font-family: var(--font-primary);
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--color-accent);
            opacity: 0.5;
            min-width: 2rem;
        }}

        .compact-card-content {{
            flex: 1;
        }}

        .compact-card-meta {{
            display: flex;
            align-items: center;
            gap: 0.4rem;
            margin-bottom: 0.25rem;
        }}

        .compact-card-source {{
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--color-accent);
        }}

        .compact-time {{
            font-size: 0.6rem;
            color: var(--color-muted);
        }}

        .compact-time::before {{
            content: '•';
            margin-right: 0.4rem;
        }}

        .compact-card-title {{
            font-family: var(--font-primary);
            font-size: 0.95rem;
            font-weight: 500;
            line-height: 1.4;
        }}

        /* ===== STATS BAR ===== */
        .stats-bar {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 2rem;
            padding: 2rem;
            background: var(--color-card-bg);
            border-radius: var(--radius-lg);
            border: 1px solid var(--color-border);
            margin: 4rem 0;
        }}

        .stats-summary {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1.5rem;
        }}

        .stat {{
            text-align: center;
        }}

        .stat-value {{
            font-family: var(--font-primary);
            font-size: 2rem;
            font-weight: 800;
            color: var(--color-accent);
        }}

        .stat-label {{
            font-size: 0.75rem;
            color: var(--color-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        /* Source Leaderboard */
        .source-leaderboard {{
            border-left: 1px solid var(--color-border);
            padding-left: 2rem;
        }}

        .leaderboard-title {{
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--color-muted);
            margin-bottom: 1rem;
        }}

        .leaderboard-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.35rem 0;
            border-bottom: 1px solid var(--color-border);
        }}

        .leaderboard-item:last-child {{
            border-bottom: none;
        }}

        .leaderboard-rank {{
            font-size: 0.85rem;
            min-width: 1.5rem;
        }}

        .leaderboard-source {{
            flex: 1;
            font-size: 0.8rem;
            font-weight: 500;
        }}

        .leaderboard-count {{
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--color-accent);
            background: rgba(var(--color-accent-rgb, 102, 126, 234), 0.1);
            padding: 0.15rem 0.4rem;
            border-radius: 3px;
        }}

        /* ===== ENRICHED CONTENT (Word of Day, Grokipedia) ===== */
        .enriched-content {{
            margin: 3rem 0;
        }}

        .enriched-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
            margin-top: 1.5rem;
        }}

        @media (max-width: 1024px) {{
            .enriched-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        .enriched-card {{
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            padding: 1.5rem;
            position: relative;
            transition: all 0.3s ease;
        }}

        .enriched-card:hover {{
            border-color: var(--color-accent);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        }}

        .enriched-card-icon {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        .enriched-card-label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--color-accent);
            font-weight: 600;
            margin-bottom: 0.75rem;
        }}

        /* Word of the Day styles */
        .word-of-the-day .wotd-word {{
            font-family: var(--font-primary);
            font-size: 1.75rem;
            font-weight: 700;
            margin: 0 0 0.25rem 0;
            color: var(--color-text);
        }}

        .word-of-the-day .wotd-pos {{
            font-size: 0.85rem;
            color: var(--color-muted);
            font-style: italic;
            display: block;
            margin-bottom: 1rem;
        }}

        .word-of-the-day .wotd-definition {{
            font-size: 1rem;
            line-height: 1.6;
            color: var(--color-text);
            margin-bottom: 1rem;
        }}

        .word-of-the-day .wotd-example {{
            font-style: italic;
            color: var(--color-muted);
            border-left: 3px solid var(--color-accent);
            padding-left: 1rem;
            margin: 1rem 0;
            font-size: 0.95rem;
        }}

        .word-of-the-day .wotd-origin {{
            font-size: 0.85rem;
            color: var(--color-muted);
            margin-top: 1rem;
        }}

        .word-of-the-day .wotd-why {{
            font-size: 0.85rem;
            color: var(--color-accent);
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid var(--color-border);
        }}

        /* Grokipedia Article styles */
        .grokipedia-article .grok-title {{
            font-family: var(--font-primary);
            font-size: 1.4rem;
            font-weight: 700;
            margin: 0 0 1rem 0;
            color: var(--color-text);
        }}

        .grokipedia-article .grok-summary {{
            font-size: 0.95rem;
            line-height: 1.7;
            color: var(--color-text);
            margin-bottom: 1.5rem;
        }}

        .grokipedia-article .grok-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 1rem;
            border-top: 1px solid var(--color-border);
        }}

        .grokipedia-article .grok-wordcount {{
            font-size: 0.8rem;
            color: var(--color-muted);
        }}

        .grokipedia-article .grok-link {{
            color: var(--color-accent);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.9rem;
            transition: color 0.2s ease;
        }}

        .grokipedia-article .grok-link:hover {{
            color: var(--color-accent-secondary);
        }}

        /* Editorial Article Card - Featured */
        .editorial-article.featured {{
            background: linear-gradient(135deg, var(--color-card-bg), rgba(var(--color-accent-rgb, 102, 126, 234), 0.1));
            border: 2px solid var(--color-accent);
            position: relative;
            overflow: hidden;
        }}

        /* Placeholder Cards - Muted appearance */
        .placeholder-card {{
            opacity: 0.7;
            border-style: dashed !important;
        }}

        .placeholder-card .wotd-word,
        .placeholder-card .grok-title,
        .placeholder-card .editorial-title {{
            color: var(--color-muted);
        }}

        .placeholder-note {{
            font-size: 0.75rem;
            color: var(--color-muted);
            font-style: italic;
        }}

        .editorial-article.featured::before {{
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 150px;
            height: 150px;
            background: linear-gradient(135deg, transparent 50%, rgba(var(--color-accent-rgb, 102, 126, 234), 0.15) 50%);
            pointer-events: none;
        }}

        .editorial-article .editorial-mood {{
            display: inline-block;
            background: var(--color-accent);
            color: white;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.75rem;
        }}

        .editorial-article .editorial-title {{
            font-family: var(--font-primary);
            font-size: 1.6rem;
            font-weight: 700;
            margin: 0 0 1rem 0;
            color: var(--color-text);
            line-height: 1.3;
        }}

        .editorial-article .editorial-summary {{
            font-size: 1rem;
            line-height: 1.7;
            color: var(--color-muted);
            margin-bottom: 1.5rem;
        }}

        .editorial-article .editorial-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 1rem;
            border-top: 1px solid var(--color-border);
        }}

        .editorial-article .editorial-wordcount {{
            font-size: 0.8rem;
            color: var(--color-muted);
        }}

        .editorial-article .editorial-link {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: white;
            background: var(--color-accent);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
            padding: 0.6rem 1.2rem;
            border-radius: var(--radius-md);
            transition: all 0.2s ease;
        }}

        .editorial-article .editorial-link:hover {{
            background: var(--color-accent-secondary);
            transform: translateX(4px);
        }}

        @media (max-width: 768px) {{
            .enriched-grid {{
                grid-template-columns: 1fr;
            }}

            .word-of-the-day .wotd-word {{
                font-size: 1.5rem;
            }}

            .grokipedia-article .grok-title {{
                font-size: 1.25rem;
            }}

            .editorial-article .editorial-title {{
                font-size: 1.3rem;
            }}
        }}

        /* ===== FOOTER ===== */
        footer {{
            border-top: 1px solid var(--color-border);
            padding: 4rem 2rem;
            margin-top: 4rem;
        }}

        .footer-content {{
            max-width: var(--max-width);
            margin: 0 auto;
            display: grid;
            grid-template-columns: 2fr 1fr 1fr;
            gap: 4rem;
        }}

        .footer-brand {{
            font-family: var(--font-primary);
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1rem;
        }}

        .footer-description {{
            color: var(--color-muted);
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
        }}

        .footer-section-title {{
            font-family: var(--font-primary);
            font-weight: 600;
            margin-bottom: 1rem;
        }}

        .footer-links {{
            list-style: none;
        }}

        .footer-links li {{
            margin-bottom: 0.5rem;
        }}

        .footer-links a {{
            color: var(--color-muted);
            font-size: 0.9rem;
            transition: color var(--transition);
        }}

        .footer-links a:hover {{
            color: var(--color-accent);
        }}

        .footer-bottom {{
            max-width: var(--max-width);
            margin: 3rem auto 0;
            padding-top: 2rem;
            border-top: 1px solid var(--color-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
            color: var(--color-muted);
        }}

        .archive-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            color: var(--color-text);
            font-size: 0.9rem;
            transition: all var(--transition);
        }}

        .archive-btn:hover {{
            border-color: var(--color-accent);
            background: rgba(99, 102, 241, 0.1);
        }}

        .footer-actions {{
            display: flex;
            gap: 1rem;
            align-items: center;
        }}

        .github-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            color: var(--color-text);
            font-size: 0.9rem;
            transition: all var(--transition);
        }}

        .github-btn:hover {{
            border-color: var(--color-accent);
            background: rgba(99, 102, 241, 0.1);
        }}

        .footer-github {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 1rem;
            color: var(--color-muted);
            font-size: 0.9rem;
            transition: color var(--transition);
        }}

        .footer-github:hover {{
            color: var(--color-accent);
        }}

        /* ===== ANIMATIONS ===== */
        @keyframes ticker {{
            0% {{ transform: translateX(0); }}
            100% {{ transform: translateX(-50%); }}
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}

        @keyframes gradientShift {{
            0%, 100% {{ transform: rotate(0deg) scale(1); }}
            50% {{ transform: rotate(180deg) scale(1.5); }}
        }}

        @keyframes fadeInUp {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Hero animation keyframes */
        @keyframes cinematicZoom {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.1); }}
        }}

        @keyframes neonFlicker {{
            0%, 100% {{ opacity: 1; }}
            92% {{ opacity: 1; }}
            93% {{ opacity: 0.8; }}
            94% {{ opacity: 1; }}
            96% {{ opacity: 0.9; }}
            97% {{ opacity: 1; }}
        }}

        @keyframes floatParticle {{
            0%, 100% {{ transform: translateY(100vh) rotate(0deg); opacity: 0; }}
            10% {{ opacity: 0.6; }}
            90% {{ opacity: 0.6; }}
            100% {{ transform: translateY(-100vh) rotate(720deg); opacity: 0; }}
        }}

        @keyframes waveMove {{
            0% {{ transform: translateX(0); }}
            100% {{ transform: translateX(50%); }}
        }}

        @keyframes geoFloat {{
            0%, 100% {{ transform: translateY(0) rotate(0deg); }}
            25% {{ transform: translateY(-20px) rotate(5deg); }}
            50% {{ transform: translateY(0) rotate(0deg); }}
            75% {{ transform: translateY(20px) rotate(-5deg); }}
        }}

        @keyframes spotlightMove {{
            0%, 100% {{ transform: translate(0, 0); opacity: 0.3; }}
            25% {{ transform: translate(100px, 50px); opacity: 0.5; }}
            50% {{ transform: translate(50px, 100px); opacity: 0.3; }}
            75% {{ transform: translate(-50px, 50px); opacity: 0.4; }}
        }}

        @keyframes glitchText {{
            0%, 100% {{ transform: translate(0); }}
            2% {{ transform: translate(-2px, 2px); }}
            4% {{ transform: translate(2px, -2px); }}
            6% {{ transform: translate(0); }}
            92% {{ transform: translate(0); }}
            94% {{ transform: translate(3px, 0); }}
            96% {{ transform: translate(-3px, 0); }}
            98% {{ transform: translate(0); }}
        }}

        @keyframes glitchBg {{
            0%, 100% {{ transform: translate(0); filter: saturate(1.2); }}
            5% {{ transform: translate(-5px, 0); filter: saturate(2) hue-rotate(20deg); }}
            10% {{ transform: translate(5px, 0); filter: saturate(1.2); }}
            90% {{ transform: translate(0); filter: saturate(1.2); }}
            95% {{ transform: translate(3px, -3px); filter: saturate(2) hue-rotate(-20deg); }}
        }}

        @keyframes auroraShift {{
            0%, 100% {{ transform: translateX(-20%) skewX(-5deg); opacity: 0.5; }}
            50% {{ transform: translateX(20%) skewX(5deg); opacity: 0.8; }}
        }}

        @keyframes meshShift {{
            0%, 100% {{ background-position: 0% 0%, 100% 0%, 0% 50%, 100% 50%, 0% 100%; }}
            50% {{ background-position: 100% 100%, 0% 100%, 100% 50%, 0% 50%, 100% 0%; }}
        }}

        @keyframes retroGrid {{
            0% {{ background-position: 0 0; }}
            100% {{ background-position: 0 60px; }}
        }}

        .animate-in {{
            animation: fadeInUp 0.6s ease-out forwards;
            opacity: 0;
        }}

        /* ===== ENHANCED SCROLL ANIMATIONS ===== */
        /* Different animation types for variety */
        .animate-fade-up {{
            animation: fadeInUp 0.6s ease-out forwards;
            opacity: 0;
        }}

        .animate-fade-left {{
            animation: fadeInLeft 0.6s ease-out forwards;
            opacity: 0;
        }}

        .animate-fade-right {{
            animation: fadeInRight 0.6s ease-out forwards;
            opacity: 0;
        }}

        .animate-scale-in {{
            animation: scaleIn 0.5s ease-out forwards;
            opacity: 0;
        }}

        .animate-slide-up {{
            animation: slideUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            opacity: 0;
        }}

        @keyframes fadeInLeft {{
            from {{ opacity: 0; transform: translateX(-30px); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}

        @keyframes fadeInRight {{
            from {{ opacity: 0; transform: translateX(30px); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}

        @keyframes scaleIn {{
            from {{ opacity: 0; transform: scale(0.9); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}

        @keyframes slideUp {{
            from {{ opacity: 0; transform: translateY(40px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Staggered animation delays for grid items */
        .stagger-1 {{ animation-delay: 0.05s; }}
        .stagger-2 {{ animation-delay: 0.1s; }}
        .stagger-3 {{ animation-delay: 0.15s; }}
        .stagger-4 {{ animation-delay: 0.2s; }}
        .stagger-5 {{ animation-delay: 0.25s; }}
        .stagger-6 {{ animation-delay: 0.3s; }}
        .stagger-7 {{ animation-delay: 0.35s; }}
        .stagger-8 {{ animation-delay: 0.4s; }}

        /* ===== IMAGE TREATMENTS ===== */
        .image-treatment-grayscale .story-card.has-image::before {{
            filter: grayscale(100%);
        }}
        .image-treatment-sepia .story-card.has-image::before {{
            filter: sepia(30%);
        }}
        .image-treatment-saturate .story-card.has-image::before {{
            filter: saturate(1.3);
        }}
        .image-treatment-contrast .story-card.has-image::before {{
            filter: contrast(1.1);
        }}
        .image-treatment-vignette .story-card.has-image::after {{
            box-shadow: inset 0 0 100px rgba(0,0,0,0.5);
        }}
        .image-treatment-duotone_warm .story-card.has-image::before {{
            filter: sepia(20%) saturate(1.2) hue-rotate(-10deg);
        }}
        .image-treatment-duotone_cool .story-card.has-image::before {{
            filter: saturate(0.8) hue-rotate(20deg);
        }}

        /* ===== SECTION DIVIDERS ===== */
        .section-divider {{
            margin: 2rem 0;
            width: 100%;
        }}
        .divider-line {{
            border-top: 1px solid var(--color-border);
            margin: 2rem 0;
        }}
        .divider-thick_line {{
            border-top: 3px solid var(--color-accent);
            margin: 2rem 0;
        }}
        .divider-gradient_line {{
            background: linear-gradient(90deg, transparent, var(--color-accent), transparent);
            height: 2px;
            margin: 2rem 0;
        }}
        .divider-dots {{
            background: radial-gradient(circle, var(--color-accent) 2px, transparent 2px);
            background-size: 20px 20px;
            height: 10px;
            margin: 2rem 0;
            opacity: 0.5;
        }}
        .divider-fade {{
            background: linear-gradient(180deg, var(--color-bg), var(--color-card-bg), var(--color-bg));
            height: 40px;
            margin: 2rem 0;
        }}
        .divider-wave {{
            background: var(--color-accent);
            height: 20px;
            margin: 2rem 0;
            opacity: 0.2;
            mask-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 1200 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 20 Q300 0 600 20 T1200 20 V40 H0 Z' fill='black'/%3E%3C/svg%3E");
            -webkit-mask-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 1200 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 20 Q300 0 600 20 T1200 20 V40 H0 Z' fill='black'/%3E%3C/svg%3E");
        }}

        /* ===== CARD ASPECT RATIOS ===== */
        .aspect-landscape .story-card:first-child {{
            aspect-ratio: 16/9;
        }}
        .aspect-portrait .story-card:first-child {{
            aspect-ratio: 3/4;
        }}
        .aspect-square .story-card {{
            aspect-ratio: 1/1;
        }}
        .aspect-wide .story-card:first-child {{
            aspect-ratio: 21/9;
        }}
        .aspect-classic .story-card:first-child {{
            aspect-ratio: 4/3;
        }}

        /* ===== ACCESSIBILITY: FOCUS STATES ===== */
        /* Visible focus indicators for keyboard navigation */
        a:focus-visible,
        button:focus-visible,
        .story-card:focus-visible,
        .compact-card:focus-visible,
        input:focus-visible,
        select:focus-visible,
        textarea:focus-visible {{
            outline: 3px solid var(--color-accent);
            outline-offset: 2px;
            border-radius: var(--radius-sm);
        }}

        /* Skip link for keyboard users */
        .skip-link {{
            position: absolute;
            top: -100px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--color-accent);
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: var(--radius);
            z-index: 1000;
            font-weight: 600;
            transition: top 0.3s ease;
        }}
        .skip-link:focus {{
            top: 1rem;
        }}

        /* Focus within for card containers */
        .story-card:focus-within {{
            box-shadow: 0 0 0 3px var(--color-accent);
        }}

        /* Minimum touch target size (44x44px) */
        .nav-links a,
        .theme-toggle,
        .story-card .story-link,
        .compact-card a {{
            min-height: 44px;
            min-width: 44px;
            display: inline-flex;
            align-items: center;
        }}

        /* ===== CREATIVE FLOURISHES ===== */
        @keyframes floatCard {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-8px); }}
        }}

        @keyframes pulseGlow {{
            0%, 100% {{ box-shadow: 0 0 5px var(--color-accent); }}
            50% {{ box-shadow: 0 0 20px var(--color-accent), 0 0 40px var(--color-accent); }}
        }}

        @keyframes borderGradient {{
            0% {{ border-color: var(--color-accent); }}
            50% {{ border-color: var(--color-accent-secondary); }}
            100% {{ border-color: var(--color-accent); }}
        }}

        /* Background pattern overlay */
        .bg-pattern-dots::before {{
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: radial-gradient(circle, var(--color-border) 1px, transparent 1px);
            background-size: 20px 20px;
            pointer-events: none;
            opacity: 0.4;
            z-index: -1;
        }}

        .bg-pattern-grid::before {{
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: linear-gradient(var(--color-border) 1px, transparent 1px),
                              linear-gradient(90deg, var(--color-border) 1px, transparent 1px);
            background-size: 40px 40px;
            pointer-events: none;
            opacity: 0.3;
            z-index: -1;
        }}

        .bg-pattern-diagonal::before {{
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: repeating-linear-gradient(
                45deg,
                transparent,
                transparent 10px,
                var(--color-border) 10px,
                var(--color-border) 11px
            );
            pointer-events: none;
            opacity: 0.2;
            z-index: -1;
        }}

        .bg-pattern-gradient_radial::before {{
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(ellipse at top, var(--color-accent) 0%, transparent 50%);
            pointer-events: none;
            opacity: 0.15;
            z-index: -1;
        }}

        /* Accent styles for highlighted elements */
        .accent-glow {{
            box-shadow: 0 0 60px -20px var(--color-accent);
        }}

        .accent-neon_border {{
            border: 2px solid var(--color-accent) !important;
            box-shadow: 0 0 20px var(--color-accent), inset 0 0 20px rgba(255,255,255,0.05);
        }}

        .accent-underline {{
            border-bottom: 3px solid var(--color-accent);
        }}

        .accent-corner_accent {{
            border-top: 4px solid var(--color-accent);
            border-left: 4px solid var(--color-accent);
        }}

        /* Special visual modes */
        .mode-high_contrast {{
            --color-text: #ffffff;
            --color-muted: #c0c0c0;
        }}

        .mode-high_contrast .story-card,
        .mode-high_contrast .compact-card {{
            border-width: 2px;
        }}

        .mode-glassmorphism .story-card,
        .mode-glassmorphism .section,
        .mode-glassmorphism .compact-card {{
            background: rgba(24, 24, 27, 0.7) !important;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .mode-vibrant {{
            --color-accent: color-mix(in srgb, var(--color-accent) 100%, white 20%);
        }}

        .mode-muted {{
            filter: saturate(0.7);
        }}

        .mode-duotone {{
            filter: sepia(0.2) saturate(1.2);
        }}

        /* Float and pulse animations */
        .use-float .story-card:hover,
        .use-float .compact-card:hover {{
            animation: floatCard 3s ease-in-out infinite;
        }}

        .use-pulse .story-card {{
            animation: pulseGlow 3s ease-in-out infinite;
        }}

        /* ===== RESPONSIVE ===== */
        @media (max-width: 1024px) {{
            .layout-newspaper .top-stories,
            .layout-mosaic .top-stories {{
                grid-template-columns: 1fr 1fr;
            }}

            .layout-newspaper .top-stories .story-card:first-child,
            .layout-mosaic .top-stories .story-card:first-child {{
                grid-column: span 2;
                grid-row: span 1;
            }}

            .layout-mosaic .top-stories .story-card {{
                grid-column: span 1 !important;
                grid-row: span 1 !important;
            }}

            .footer-content {{
                grid-template-columns: 1fr;
                gap: 2rem;
            }}
        }}

        @media (max-width: 768px) {{
            .hero {{
                padding: 5rem 1rem 2rem;
                min-height: 50vh;
                max-height: 60vh;
            }}

            .hero h1 {{
                font-size: clamp(1.5rem, 6vw, 2.5rem);
            }}

            .hero-subtitle {{
                font-size: 1rem;
                margin-bottom: 1.5rem;
            }}

            .hero-eyebrow {{
                padding: 0.4rem 0.75rem;
                font-size: 0.65rem;
            }}

            .hero-cta {{
                padding: 0.75rem 1.25rem;
                font-size: 0.9rem;
            }}

            .hero-capsule {{
                font-size: 0.85rem;
                padding: 0.5rem 0.75rem;
            }}

            .hero-meta {{
                font-size: 0.8rem;
                gap: 1rem;
            }}

            .hero-split .hero {{
                grid-template-columns: 1fr;
            }}

            .top-stories,
            .layout-newspaper .top-stories,
            .layout-magazine .top-stories,
            .layout-dashboard .top-stories,
            .layout-mosaic .top-stories,
            .layout-bold .top-stories,
            .layout-minimal .top-stories {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .top-stories .story-card {{
                min-height: 140px;
                max-height: 180px;
            }}

            .top-stories .story-card:first-child {{
                grid-column: span 1 !important;
                grid-row: span 1 !important;
            }}

            .category-grid {{
                grid-template-columns: 1fr;
            }}

            .stats-bar {{
                grid-template-columns: 1fr;
            }}

            .source-leaderboard {{
                border-left: none;
                border-top: 1px solid var(--color-border);
                padding-left: 0;
                padding-top: 1.5rem;
            }}

            .word-cloud {{
                padding: 1rem;
            }}

            main {{
                padding: 2rem 1rem;
            }}

            .section-title {{
                font-size: 1.25rem;
            }}

            .footer-bottom {{
                flex-direction: column;
                gap: 1rem;
                text-align: center;
            }}

            .enriched-card {{
                padding: 1.25rem;
            }}

            .enriched-card-icon {{
                font-size: 1.5rem;
            }}
        }}

        /* Small phones */
        @media (max-width: 480px) {{
            .hero {{
                padding: 5.5rem 0.75rem 1.5rem;
                min-height: 45vh;
            }}

            .hero h1 {{
                font-size: 1.5rem;
            }}

            .hero-actions {{
                flex-direction: column;
                align-items: stretch;
            }}

            .hero-cta {{
                text-align: center;
                justify-content: center;
            }}

            .hero-secondary {{
                text-align: center;
            }}

            .nav {{
                padding: 0.75rem 1rem;
            }}

            .nav-logo {{
                font-size: 1.2rem;
            }}

            .top-stories {{
                grid-template-columns: 1fr;
                gap: 0.75rem;
            }}

            .stats-bar {{
                grid-template-columns: 1fr;
            }}

            .stats-summary {{
                grid-template-columns: repeat(2, 1fr);
            }}

            main {{
                padding: 1.5rem 0.75rem;
            }}

            .section {{
                margin-bottom: 2rem;
            }}
        }}

        /* ===== REDUCED MOTION ===== */
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }}
        }}

        /* ===== PRINT STYLES ===== */
        @media print {{
            /* Force light mode colors for printing */
            body {{
                background: white !important;
                color: black !important;
            }}

            .nav, .theme-toggle, .breaking-ticker, .footer-actions {{
                display: none !important;
            }}

            .story-card, .compact-card, .section {{
                background: white !important;
                color: black !important;
                border: 1px solid #ccc !important;
                box-shadow: none !important;
                break-inside: avoid;
            }}

            .story-title, .section-title, .headline-xl, .headline-lg {{
                color: black !important;
            }}

            .story-source, .text-muted {{
                color: #666 !important;
            }}

            .word-cloud {{
                display: none !important;
            }}

            a {{
                color: black !important;
                text-decoration: underline !important;
            }}

            /* Show URLs after links */
            a[href]::after {{
                content: " (" attr(href) ")";
                font-size: 0.8em;
                color: #666;
            }}

            a[href^="#"]::after,
            a[href^="javascript"]::after {{
                content: "" !important;
            }}
        }}
    </style>"""

    def _build_ad_unit(self, slot_id: str = "", ad_format: str = "auto") -> str:
        """Build an AdSense ad unit placeholder.

        Args:
            slot_id: The ad slot ID (e.g., "1234567890") - leave empty for auto ads
            ad_format: Ad format (auto, horizontal, rectangle, vertical)
        """
        # Format-specific styles
        format_styles = {
            "horizontal": "display:block; min-height:90px;",
            "rectangle": "display:block; min-height:250px;",
            "vertical": "display:block; min-height:600px;",
            "auto": "display:block;",
        }

        style = format_styles.get(ad_format, format_styles["auto"])
        container_class = f"ad-container ad-{ad_format}"

        # If no slot_id provided, return a placeholder for auto ads
        if not slot_id:
            return f"""
        <div class="{container_class}">
            <ins class="adsbygoogle"
                 style="{style}"
                 data-ad-client="ca-pub-2196222970720414"
                 data-ad-format="{ad_format}"
                 data-full-width-responsive="true"></ins>
            <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
        </div>"""

        return f"""
        <div class="{container_class}">
            <ins class="adsbygoogle"
                 style="{style}"
                 data-ad-client="ca-pub-2196222970720414"
                 data-ad-slot="{slot_id}"
                 data-ad-format="{ad_format}"
                 data-full-width-responsive="true"></ins>
            <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
        </div>"""

    def _build_nav(self) -> str:
        """Build the navigation bar."""
        # Build links: Home, Topic Pages, Articles
        links_list = []

        # Home
        links_list.append('<li><a href="/">Home</a></li>')

        # Topic pages
        topic_pages = [
            ('Tech', '/tech/'),
            ('World', '/world/'),
            ('Science', '/science/'),
            ('Politics', '/politics/'),
            ('Finance', '/finance/'),
        ]
        for name, url in topic_pages:
            links_list.append(f'<li><a href="{url}">{name}</a></li>')

        # Articles
        links_list.append('<li><a href="/articles/">Articles</a></li>')

        links = '\n                '.join(links_list)

        return f"""
    <nav class="nav" id="nav" role="navigation" aria-label="Main navigation">
        <a href="/" class="nav-logo" aria-label="DailyTrending.info Home">
            <span>DailyTrending.info</span>
        </a>
        <button class="mobile-menu-toggle" id="mobile-menu-toggle" aria-label="Toggle navigation menu" aria-expanded="false">
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
        </button>
        <ul class="nav-links" id="nav-links">
{links}
        </ul>
        <div class="nav-actions">
            <span class="nav-date">{self.ctx.generated_at}</span>
            <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark/light mode" title="Toggle dark/light mode">
                <svg class="sun-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="12" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                </svg>
                <svg class="moon-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                </svg>
            </button>
            <a href="https://github.com/fubak/daily-trending-info" class="nav-github" target="_blank" rel="noopener noreferrer" aria-label="View source on GitHub" title="View source on GitHub">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
            </a>
        </div>
    </nav>"""

    def _build_hero(self) -> str:
        """Build the hero section with creative animated designs."""
        headline = html.escape(self.design.get('headline', "Today's Trends"))
        subheadline = html.escape(self.design.get('subheadline', 'What the world is talking about'))

        total_trends = len(self.ctx.trends)
        total_sources = len(set(t.get('source', '').split('_')[0] for t in self.ctx.trends))
        cta_label = html.escape(self.design.get('cta_primary') or "See today's pulse")
        cta_secondary = ""
        cta_options = self.design.get('cta_options') or []
        if len(cta_options) > 1:
            cta_secondary = html.escape(cta_options[1])
        capsule = html.escape(self._get_story_capsule() or "")

        # Build extra elements based on hero style
        extra_elements = self._build_hero_extras()

        # Build extra elements based on hero style
        extra_elements = self._build_hero_extras()

        # Build accessible alt text for hero background
        hero_alt = f"Trending topics visualization for {self.ctx.generated_at}"
        if self._hero_image:
            hero_alt = html.escape(self._hero_image.get('alt', '') or self._hero_image.get('description', '') or hero_alt)

        return f"""
    <header class="hero" role="img" aria-label="{hero_alt}">
        {extra_elements}
        <div class="hero-content">
            <div class="hero-eyebrow">
                <span>Live</span> Trending Now
            </div>
            <h1 class="headline-xl">{headline}</h1>
            <p class="hero-subtitle">{subheadline}</p>
            <div class="hero-actions">
                <a href="#top-stories" class="hero-cta">
                    {cta_label}
                </a>
                {f'<div class="hero-secondary">{cta_secondary}</div>' if cta_secondary else ''}
            </div>
            {f'<div class="hero-capsule">⚡ {capsule}</div>' if capsule else ''}
            <div class="hero-meta">
                <span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    Updated {self.ctx.generated_at}
                </span>
                <span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 20V10"></path>
                        <path d="M18 20V4"></path>
                        <path d="M6 20v-4"></path>
                    </svg>
                    {total_trends} stories from {total_sources} sources
                </span>
                <span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                    </svg>
                    Style: {self.hero_style.title()}
                </span>
            </div>
        </div>
    </header>"""

    def _build_hero_extras(self) -> str:
        """Build extra HTML elements for animated hero styles."""
        if self.hero_style == "particles":
            # Generate random particles
            particles = []
            for i in range(30):
                left = self.rng.randint(0, 100)
                delay = self.rng.uniform(0, 15)
                size = self.rng.randint(2, 6)
                particles.append(
                    f'<div class="particle" style="left:{left}%;animation-delay:{delay:.1f}s;width:{size}px;height:{size}px;"></div>'
                )
            return f'<div class="hero-particles-container">{"".join(particles)}</div>'

        elif self.hero_style == "waves":
            return '''<div class="wave-container">
                <div class="wave"></div>
                <div class="wave"></div>
            </div>'''

        elif self.hero_style == "geometric":
            # Generate random geometric shapes
            shapes = []
            shape_types = ["circle", "square", "triangle"]
            for i in range(8):
                shape = self.rng.choice(shape_types)
                left = self.rng.randint(5, 95)
                top = self.rng.randint(5, 95)
                size = self.rng.randint(50, 150)
                delay = self.rng.uniform(0, 10)
                rotation = self.rng.randint(0, 360)
                shape_class = "circle" if shape == "circle" else ""
                shapes.append(
                    f'<div class="geo-shape {shape_class}" style="left:{left}%;top:{top}%;width:{size}px;height:{size}px;animation-delay:{delay:.1f}s;transform:rotate({rotation}deg);"></div>'
                )
            return f'<div class="geo-shapes">{"".join(shapes)}</div>'

        elif self.hero_style == "spotlight":
            return '<div class="spotlight"></div>'

        elif self.hero_style == "aurora":
            return '<div class="aurora"></div>'

        elif self.hero_style == "retro":
            return '''<div class="retro-grid"></div>
            <div class="retro-sun"></div>'''

        return ""

    def _get_story_capsule(self) -> str:
        """Return a short story capsule from AI or fallbacks."""
        capsules = self.design.get('story_capsules') or []
        for capsule in capsules:
            if capsule:
                return capsule

        # Fallback to top trend descriptions or titles
        for trend in self.ctx.trends[:5]:
            desc = trend.get('description') or trend.get('title')
            if desc:
                clean = desc.strip()
                if len(clean) > 90:
                    clean = clean[:87] + "..."
                return clean
        return ""

    def _build_breaking_ticker(self) -> str:
        """Build the breaking news ticker."""
        # Get top 10 trends for ticker
        top_trends = self.ctx.trends[:15]

        items = []
        for trend in top_trends:
            source = html.escape((trend.get('source') or '').replace('_', ' ').title())
            title = html.escape((trend.get('title') or '')[:80])
            items.append(f'''
            <div class="ticker-item">
                <span class="ticker-source">{source}</span>
                <strong>{title}</strong>
            </div>''')

        # Double for seamless loop
        ticker_content = ''.join(items) + ''.join(items)

        return f"""
    <div class="ticker-wrap">
        <div class="ticker-label">TRENDING</div>
        <div class="ticker">
            {ticker_content}
        </div>
    </div>"""

    def _build_word_cloud(self) -> str:
        """Build the word cloud visualization."""
        if not self.keyword_freq:
            return ""

        max_freq = self.keyword_freq[0][1] if self.keyword_freq else 1

        words_html = []
        for word, freq in self.keyword_freq[:40]:
            # Calculate size class (1-6)
            ratio = freq / max_freq
            if ratio > 0.8:
                size = 6
            elif ratio > 0.6:
                size = 5
            elif ratio > 0.4:
                size = 4
            elif ratio > 0.25:
                size = 3
            elif ratio > 0.1:
                size = 2
            else:
                size = 1

            words_html.append(
                f'<span class="word-cloud-item size-{size}">{html.escape(word.title())}</span>'
            )

        # Shuffle for visual variety
        self.rng.shuffle(words_html)

        return f"""
    <section class="word-cloud-section section" id="whats-trending">
        <div class="section-header">
            <h2 class="section-title">What's Trending</h2>
            <span class="section-count">{len(self.keyword_freq)} keywords</span>
        </div>
        <div class="word-cloud">
            {' '.join(words_html)}
        </div>
    </section>"""

    def _build_top_stories(self) -> str:
        """Build the top stories section with AI summaries."""
        top = self.ctx.trends[:4]  # Reduced from 6 to 4
        images = self.ctx.images[1:5] if len(self.ctx.images) > 1 else []

        # Get AI summaries if available
        summaries = {}
        if self.ctx.enriched_content and self.ctx.enriched_content.get('story_summaries'):
            for s in self.ctx.enriched_content['story_summaries']:
                summaries[s.get('title', '')] = s.get('summary', '')

        cards_html = []
        for i, trend in enumerate(top):
            title = html.escape(trend.get('title') or 'Untitled')
            source = html.escape((trend.get('source') or '').replace('_', ' ').title())
            url = trend.get('url') or '#'

            # Use AI summary if available, otherwise use description
            raw_title = trend.get('title', '')
            ai_summary = summaries.get(raw_title, '')
            desc = html.escape(ai_summary) if ai_summary else html.escape((trend.get('description') or '')[:150])

            # Add image to first few cards
            image = images[i] if i < len(images) else None
            image_style = ""
            extra_class = ""

            if i == 0:
                extra_class = "featured"
            elif image:
                safe_img_url = html.escape(image.get("url_medium", "")).replace("'", "").replace('"', '')
                image_style = f'style="background-image: url(\'{safe_img_url}\');"'
                extra_class = "has-image"

            # Build accessibility attributes for cards with images
            img_attrs = ""
            if image and i > 0:
                # Get image description or fall back to story title for alt text
                img_desc = image.get("description", "") or trend.get('title', '')
                safe_img_desc = html.escape(img_desc[:100]) if img_desc else "Story image"
                img_attrs = f'role="img" aria-label="Image: {safe_img_desc}"'

            # Calculate velocity and comparison indicators
            velocity = self._calculate_velocity(trend)
            comparison = self._get_comparison_indicator(trend)
            discussions = self._find_discussion_links(trend)

            # Velocity badge HTML
            velocity_class = f"velocity-{velocity['label']}"
            velocity_html = f'<span class="velocity-badge {velocity_class}" title="{velocity["sources"]} sources">{velocity["label"].upper()}</span>' if velocity['label'] in ('hot', 'rising') else ''

            # Comparison indicator HTML
            comparison_html = f'<span class="comparison-badge" title="{comparison["tooltip"]}">{comparison["icon"]}</span>'

            # Discussion links HTML
            discussion_html = ''
            if discussions:
                disc_items = ''.join([
                    f'<a href="{html.escape(d["url"])}" class="discussion-link" target="_blank" rel="noopener" title="Discuss on {d["source"]}">'
                    f'{d["icon"]} {d["source"]}'
                    f'</a>'
                    for d in discussions
                ])
                discussion_html = f'<div class="discussion-links">{disc_items}</div>'

            # Get timestamp for relative time display
            timestamp = trend.get('timestamp')
            timestamp_iso = ''
            timestamp_html = ''
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp_iso = timestamp
                else:
                    timestamp_iso = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
                timestamp_html = f'<time class="story-time" datetime="{timestamp_iso}"></time>'

            # Save button HTML
            safe_title = html.escape(title).replace("'", "\\'")
            save_btn = f'''<button class="save-btn" data-url="{html.escape(url)}" data-title="{safe_title}" data-source="{source}" aria-label="Save for later" title="Save for later">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
            </button>'''

            # Share button HTML (uses Web Share API)
            share_btn = f'''<button class="share-btn" data-url="{html.escape(url)}" data-title="{safe_title}" aria-label="Share story" title="Share">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
            </button>'''

            # Find related stories for clustering
            related = self._find_related_stories(trend)
            related_html = ''
            if related:
                related_items = ''.join([
                    f'<a href="{html.escape(r["url"])}" class="related-link" target="_blank" rel="noopener">'
                    f'<span class="related-source">{html.escape(r["source"])}</span>'
                    f'<span class="related-title">{html.escape(r["title"][:60])}{"..." if len(r["title"]) > 60 else ""}</span>'
                    f'</a>'
                    for r in related
                ])
                related_html = f'''
                <div class="related-coverage">
                    <span class="related-label">Related coverage ({len(related)})</span>
                    <div class="related-links">{related_items}</div>
                </div>'''

            cards_html.append(f'''
            <article class="story-card {extra_class}" {image_style} {img_attrs}>
                <div class="story-badges">
                    {comparison_html}
                    {velocity_html}
                </div>
                <div class="story-content">
                    <div class="story-meta">
                        <span class="story-source">{source}</span>
                        {timestamp_html}
                        {discussion_html}
                    </div>
                    <h3 class="story-title">{title}</h3>
                    {f'<p class="story-description">{desc}</p>' if desc else ''}
                    {related_html}
                </div>
                <div class="story-actions">
                    {save_btn}
                    {share_btn}
                </div>
                <a href="{html.escape(url)}" class="story-link" target="_blank" rel="noopener" aria-label="Read more about {title[:50]}"></a>
            </article>''')

        reading_time = self._get_total_reading_time()
        return f"""
    <section class="section" id="top-stories">
        <div class="section-header">
            <h2 class="section-title">Top Stories</h2>
            <div class="section-meta">
                <span class="section-count">{len(top)} featured</span>
                <span class="reading-time" title="Estimated reading time">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                    {reading_time} min read
                </span>
            </div>
        </div>
        <div class="top-stories">
            {''.join(cards_html)}
        </div>
    </section>"""

    def _build_category_sections(self) -> str:
        """Build compact category sections in a multi-column layout."""
        sections_html = []

        # Limit to top 4 categories, 4 articles each for a cleaner layout
        categories_to_show = self._sorted_categories[:4]

        for category, trends in categories_to_show:
            if len(trends) < 2:
                continue

            section_id = category.lower().replace(' ', '-')

            cards_html = []
            for i, trend in enumerate(trends[:4]):  # Reduced from 6 to 4
                title = html.escape(trend.get('title') or 'Untitled')
                source = html.escape((trend.get('source') or '').replace('_', ' ').title())
                url = trend.get('url') or '#'

                # Get timestamp for relative time display
                timestamp = trend.get('timestamp')
                timestamp_html = ''
                if timestamp:
                    if isinstance(timestamp, str):
                        timestamp_iso = timestamp
                    else:
                        timestamp_iso = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
                    timestamp_html = f'<time class="story-time compact-time" datetime="{timestamp_iso}"></time>'

                cards_html.append(f'''
                <a href="{html.escape(url)}" class="compact-card" target="_blank" rel="noopener">
                    <span class="compact-card-number">{i + 1:02d}</span>
                    <div class="compact-card-content">
                        <div class="compact-card-meta">
                            <span class="compact-card-source">{source}</span>
                            {timestamp_html}
                        </div>
                        <h4 class="compact-card-title">{title}</h4>
                    </div>
                </a>''')

            sections_html.append(f'''
        <div class="category-column">
            <div class="category-header">
                <h3 class="category-title">{html.escape(category)}</h3>
            </div>
            <div class="category-list">
                {''.join(cards_html)}
            </div>
        </div>''')

        # Wrap all categories in a multi-column container
        return f"""
    <section class="section categories-section" id="categories">
        <div class="section-header">
            <h2 class="section-title">By Category</h2>
            <span class="section-count">{len(categories_to_show)} sections</span>
        </div>
        <div class="categories-grid">
            {''.join(sections_html)}
        </div>
    </section>"""

    def _build_enriched_content_section(self) -> str:
        """Build the enriched content section with Editorial, Word of Day and Grokipedia."""
        sections = []

        # Word of the Day (always show, with placeholder if missing)
        if self.ctx.enriched_content:
            word_section = self._build_word_of_the_day()
            if word_section:
                sections.append(word_section)
            else:
                sections.append(self._build_word_of_the_day_placeholder())
        else:
            sections.append(self._build_word_of_the_day_placeholder())

        # Grokipedia Article (always show, with placeholder if missing)
        if self.ctx.enriched_content:
            article_section = self._build_grokipedia_article()
            if article_section:
                sections.append(article_section)
            else:
                sections.append(self._build_grokipedia_placeholder())
        else:
            sections.append(self._build_grokipedia_placeholder())

        # Today's Editorial Article (always show, with placeholder if missing)
        editorial_section = self._build_editorial_article_card()
        if editorial_section:
            sections.append(editorial_section)
        else:
            sections.append(self._build_editorial_placeholder())

        return f"""
    <section class="section enriched-content" id="daily-features">
        <div class="section-header">
            <h2 class="section-title">Daily Features</h2>
            <span class="section-count">Learn something new</span>
        </div>
        <div class="enriched-grid">
            {''.join(sections)}
        </div>
    </section>"""

    def _build_word_of_the_day(self) -> str:
        """Build the Word of the Day card."""
        if not self.ctx.enriched_content:
            return ""

        wotd = self.ctx.enriched_content.get('word_of_the_day')
        if not wotd:
            return ""

        word = html.escape(wotd.get('word', ''))
        pos = html.escape(wotd.get('part_of_speech', ''))
        definition = html.escape(wotd.get('definition', ''))
        example = html.escape(wotd.get('example_usage', ''))
        origin = html.escape(wotd.get('origin', '') or '')
        why_chosen = html.escape(wotd.get('why_chosen', '') or '')

        origin_html = f'<p class="wotd-origin"><strong>Origin:</strong> {origin}</p>' if origin else ''
        why_html = f'<p class="wotd-why">{why_chosen}</p>' if why_chosen else ''

        return f"""
            <div class="enriched-card word-of-the-day">
                <div class="enriched-card-icon">📚</div>
                <div class="enriched-card-label">Word of the Day</div>
                <h3 class="wotd-word">{word}</h3>
                <span class="wotd-pos">{pos}</span>
                <p class="wotd-definition">{definition}</p>
                <blockquote class="wotd-example">"{example}"</blockquote>
                {origin_html}
                {why_html}
            </div>"""

    def _build_grokipedia_article(self) -> str:
        """Build the Grokipedia Article of the Day card."""
        if not self.ctx.enriched_content:
            return ""

        article = self.ctx.enriched_content.get('grokipedia_article')
        if not article:
            return ""

        title = html.escape(article.get('title', ''))
        summary = html.escape(article.get('summary', ''))
        url = html.escape(article.get('url', ''))
        word_count = article.get('word_count', 0)

        word_count_html = f'<span class="grok-wordcount">{word_count:,} words</span>' if word_count else ''

        return f"""
            <div class="enriched-card grokipedia-article">
                <div class="enriched-card-icon">📖</div>
                <div class="enriched-card-label">From Grokipedia</div>
                <h3 class="grok-title">{title}</h3>
                <p class="grok-summary">{summary}</p>
                <div class="grok-footer">
                    {word_count_html}
                    <a href="{url}" class="grok-link" target="_blank" rel="noopener">
                        Read full article →
                    </a>
                </div>
            </div>"""

    def _build_editorial_article_card(self) -> str:
        """Build the Today's Editorial Article card (featured prominently)."""
        if not self.ctx.editorial_article:
            return ""

        article = self.ctx.editorial_article
        title = html.escape(article.get('title', ''))
        summary = html.escape(article.get('summary', ''))
        url = html.escape(article.get('url', ''))
        mood = html.escape(article.get('mood', 'informative'))
        word_count = article.get('word_count', 0)

        if not title or not url:
            return ""

        return f"""
            <div class="enriched-card editorial-article featured">
                <div class="enriched-card-icon">✍️</div>
                <div class="enriched-card-label">Today's Editorial</div>
                <span class="editorial-mood">{mood}</span>
                <h3 class="editorial-title">{title}</h3>
                <p class="editorial-summary">{summary}</p>
                <div class="editorial-footer">
                    <span class="editorial-wordcount">{word_count:,} words</span>
                    <a href="{url}" class="editorial-link">
                        Read analysis →
                    </a>
                </div>
            </div>"""

    def _build_word_of_the_day_placeholder(self) -> str:
        """Build placeholder card when Word of the Day is unavailable."""
        return """
            <div class="enriched-card word-of-the-day placeholder-card">
                <div class="enriched-card-icon">📚</div>
                <div class="enriched-card-label">Word of the Day</div>
                <h3 class="wotd-word">Coming Soon</h3>
                <span class="wotd-pos">placeholder</span>
                <p class="wotd-definition">Today's word of the day is being prepared. Check back shortly for an interesting vocabulary addition related to today's trending topics.</p>
                <p class="wotd-why placeholder-note">Generated daily from trending content</p>
            </div>"""

    def _build_grokipedia_placeholder(self) -> str:
        """Build placeholder card when Grokipedia article is unavailable."""
        return """
            <div class="enriched-card grokipedia-article placeholder-card">
                <div class="enriched-card-icon">📖</div>
                <div class="enriched-card-label">From Grokipedia</div>
                <h3 class="grok-title">Article Loading</h3>
                <p class="grok-summary">Today's featured encyclopedia article is being curated. We select articles related to trending topics to provide deeper context and background information.</p>
                <div class="grok-footer">
                    <span class="grok-wordcount placeholder-note">Updated daily</span>
                </div>
            </div>"""

    def _build_editorial_placeholder(self) -> str:
        """Build placeholder card when Editorial is unavailable."""
        return """
            <div class="enriched-card editorial-article placeholder-card">
                <div class="enriched-card-icon">✍️</div>
                <div class="enriched-card-label">Today's Editorial</div>
                <span class="editorial-mood">archive</span>
                <h3 class="editorial-title">Browse Our Editorial Archive</h3>
                <p class="editorial-summary">Today's editorial is being crafted. In the meantime, explore our archive of in-depth analyses on trending stories, offering context and insights from previous days.</p>
                <div class="editorial-footer">
                    <span class="editorial-wordcount placeholder-note">Updated daily</span>
                    <a href="/articles/" class="editorial-link">
                        View all articles →
                    </a>
                </div>
            </div>"""

    def _build_stats_bar(self) -> str:
        """Build statistics bar with source leaderboard."""
        total_trends = len(self.ctx.trends)
        total_sources = len(set(t.get('source', '') for t in self.ctx.trends))
        total_categories = len(self.grouped_trends)
        total_keywords = len(self.keyword_freq)

        # Calculate source leaderboard
        source_counts = defaultdict(int)
        for t in self.ctx.trends:
            source = (t.get('source') or '').replace('_', ' ').title()
            if source:
                source_counts[source] += 1

        # Sort by count and take top 5
        top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Build leaderboard HTML
        leaderboard_items = []
        for i, (source, count) in enumerate(top_sources):
            rank = i + 1
            medal = '🥇' if rank == 1 else ('🥈' if rank == 2 else ('🥉' if rank == 3 else f'{rank}.'))
            leaderboard_items.append(
                f'<div class="leaderboard-item">'
                f'<span class="leaderboard-rank">{medal}</span>'
                f'<span class="leaderboard-source">{html.escape(source)}</span>'
                f'<span class="leaderboard-count">{count}</span>'
                f'</div>'
            )

        leaderboard_html = '\n            '.join(leaderboard_items)

        return f"""
    <div class="stats-bar">
        <div class="stats-summary">
            <div class="stat">
                <div class="stat-value">{total_trends}</div>
                <div class="stat-label">Stories</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_sources}</div>
                <div class="stat-label">Sources</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_categories}</div>
                <div class="stat-label">Categories</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_keywords}</div>
                <div class="stat-label">Keywords</div>
            </div>
        </div>
        <div class="source-leaderboard">
            <div class="leaderboard-title">Top Sources</div>
            {leaderboard_html}
        </div>
    </div>"""

    def _build_footer(self) -> str:
        """Build the footer."""
        # Image credits
        credits = []
        photographers = set()
        for img in self.ctx.images[:5]:
            photographer = img.get('photographer', '')
            if photographer and photographer not in photographers:
                photographers.add(photographer)
                source = img.get('source', '').title()
                url = img.get('photographer_url', '#')
                credits.append(f'<li><a href="{html.escape(url)}" target="_blank">{html.escape(photographer)}</a> ({source})</li>')

        credits_html = '\n                '.join(credits) if credits else '<li>Gradient backgrounds</li>'

        # Source links - match nav order (Trending, Top Stories, then categories)
        source_links_list = [
            '<li><a href="#whats-trending">What\'s Trending</a></li>',
            '<li><a href="#top-stories">Top Stories</a></li>'
        ]
        for category, _ in self._sorted_categories[:4]:
            section_id = category.lower().replace(' ', '-')
            source_links_list.append(f'<li><a href="#{section_id}">{category}</a></li>')
        source_links = '\n                '.join(source_links_list)

        return f"""
    <footer role="contentinfo">
        <div class="footer-content">
            <div>
                <div class="footer-brand">DailyTrending.info</div>
                <p class="footer-description">
                    An autonomous trend aggregation website that regenerates daily
                    with fresh content from multiple sources worldwide.
                </p>
                <p class="footer-description">
                    Style: {html.escape(self.design.get('personality', 'modern').title())} |
                    Theme: {html.escape(self.design.get('theme_name', 'Auto-generated'))} |
                    Layout: {self.layout.title()}
                </p>
                <a href="https://github.com/fubak/daily-trending-info" class="footer-github" target="_blank" rel="noopener noreferrer">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                    </svg>
                    View Source on GitHub
                </a>
            </div>
            <div>
                <h4 class="footer-section-title">Categories</h4>
                <ul class="footer-links">
                    {source_links}
                </ul>
            </div>
            <div>
                <h4 class="footer-section-title">Photo Credits</h4>
                <ul class="footer-links">
                    {credits_html}
                </ul>
            </div>
        </div>
        <div class="footer-bottom">
            <span>Generated on {self.ctx.generated_at}</span>
            <div class="footer-actions">
                <a href="./archive/" class="archive-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 3h18v18H3z"></path>
                        <path d="M21 9H3"></path>
                        <path d="M9 21V9"></path>
                    </svg>
                    View Archive
                </a>
                <a href="https://github.com/fubak/daily-trending-info" class="github-btn" target="_blank" rel="noopener noreferrer">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                    </svg>
                    GitHub
                </a>
            </div>
        </div>
    </footer>"""

    def _build_scripts(self) -> str:
        """Build JavaScript for interactivity."""
        return """
    <script>
        // Theme toggle functionality with localStorage persistence
        (function() {
            const themeToggle = document.getElementById('theme-toggle');
            const body = document.body;

            // Check for saved theme preference or default to dark mode
            const savedTheme = localStorage.getItem('theme');

            // Default is dark mode (no class or dark-mode class)
            // Light mode adds light-mode class
            if (savedTheme === 'light') {
                body.classList.remove('dark-mode');
                body.classList.add('light-mode');
            } else {
                // Ensure dark mode is applied (default)
                body.classList.remove('light-mode');
                body.classList.add('dark-mode');
            }

            // Toggle theme on button click
            themeToggle.addEventListener('click', function() {
                if (body.classList.contains('light-mode')) {
                    // Switch to dark mode
                    body.classList.remove('light-mode');
                    body.classList.add('dark-mode');
                    localStorage.setItem('theme', 'dark');
                } else {
                    // Switch to light mode
                    body.classList.remove('dark-mode');
                    body.classList.add('light-mode');
                    localStorage.setItem('theme', 'light');
                }
            });
        })();

        // Mobile menu toggle functionality
        (function() {
            const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
            const navLinks = document.getElementById('nav-links');

            if (mobileMenuToggle && navLinks) {
                mobileMenuToggle.addEventListener('click', function() {
                    const isActive = navLinks.classList.contains('active');
                    navLinks.classList.toggle('active');
                    mobileMenuToggle.classList.toggle('active');
                    mobileMenuToggle.setAttribute('aria-expanded', !isActive);

                    // Prevent body scroll when menu is open
                    document.body.style.overflow = isActive ? '' : 'hidden';
                });

                // Close menu when clicking on a link
                navLinks.querySelectorAll('a').forEach(link => {
                    link.addEventListener('click', function() {
                        navLinks.classList.remove('active');
                        mobileMenuToggle.classList.remove('active');
                        mobileMenuToggle.setAttribute('aria-expanded', 'false');
                        document.body.style.overflow = '';
                    });
                });

                // Close menu on escape key
                document.addEventListener('keydown', function(e) {
                    if (e.key === 'Escape' && navLinks.classList.contains('active')) {
                        navLinks.classList.remove('active');
                        mobileMenuToggle.classList.remove('active');
                        mobileMenuToggle.setAttribute('aria-expanded', 'false');
                        document.body.style.overflow = '';
                    }
                });
            }
        })();

        // Navbar scroll effect
        const nav = document.getElementById('nav');
        window.addEventListener('scroll', () => {
            if (window.scrollY > 100) {
                nav.classList.add('scrolled');
            } else {
                nav.classList.remove('scrolled');
            }
        });

        // Enhanced scroll animations with variety
        const animationTypes = ['animate-fade-up', 'animate-fade-left', 'animate-fade-right', 'animate-scale-in', 'animate-slide-up'];

        // Check for reduced motion preference
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    const el = entry.target;

                    if (prefersReducedMotion) {
                        // Skip animations for users who prefer reduced motion
                        el.style.opacity = '1';
                    } else {
                        // Get element's position in its parent for stagger effect
                        const parent = el.parentElement;
                        const siblings = parent ? Array.from(parent.children) : [];
                        const index = siblings.indexOf(el);

                        // Add stagger class based on position (max 8)
                        const staggerClass = `stagger-${Math.min(index + 1, 8)}`;
                        el.classList.add(staggerClass);

                        // Select animation type based on element type and position
                        let animationType = 'animate-fade-up';
                        if (el.classList.contains('story-card')) {
                            // Alternate animations for story cards
                            if (index === 0) {
                                animationType = 'animate-scale-in';
                            } else if (index % 3 === 1) {
                                animationType = 'animate-fade-left';
                            } else if (index % 3 === 2) {
                                animationType = 'animate-fade-right';
                            } else {
                                animationType = 'animate-slide-up';
                            }
                        } else if (el.classList.contains('compact-card')) {
                            animationType = index % 2 === 0 ? 'animate-fade-left' : 'animate-fade-right';
                        } else if (el.classList.contains('stat')) {
                            animationType = 'animate-scale-in';
                        } else if (el.classList.contains('section')) {
                            animationType = 'animate-slide-up';
                        }

                        el.classList.add(animationType);
                    }

                    observer.unobserve(el);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '50px'
        });

        // Observe all animatable elements
        document.querySelectorAll('.story-card, .compact-card, .stat, .section, .enriched-card, .word-cloud').forEach(el => {
            if (!prefersReducedMotion) {
                el.style.opacity = '0';
            }
            observer.observe(el);
        });

        // Pause ticker on hover
        const ticker = document.querySelector('.ticker');
        if (ticker) {
            ticker.addEventListener('mouseenter', () => {
                ticker.style.animationPlayState = 'paused';
            });
            ticker.addEventListener('mouseleave', () => {
                ticker.style.animationPlayState = 'running';
            });
        }

        // =====================================================
        // SAVE STORY FEATURE - localStorage persistence
        // =====================================================
        const SavedStories = {
            STORAGE_KEY: 'dailytrending_saved_stories',
            MAX_SAVED: 50,
            MAX_AGE_DAYS: 30,

            getAll() {
                try {
                    const data = localStorage.getItem(this.STORAGE_KEY);
                    const stories = data ? JSON.parse(data) : [];
                    const cutoff = Date.now() - (this.MAX_AGE_DAYS * 24 * 60 * 60 * 1000);
                    return stories.filter(s => s.savedAt > cutoff);
                } catch (e) {
                    return [];
                }
            },

            save(story) {
                const stories = this.getAll();
                if (stories.some(s => s.url === story.url)) return false;
                stories.unshift({ ...story, savedAt: Date.now() });
                localStorage.setItem(this.STORAGE_KEY, JSON.stringify(stories.slice(0, this.MAX_SAVED)));
                this.updateUI();
                return true;
            },

            remove(url) {
                const stories = this.getAll().filter(s => s.url !== url);
                localStorage.setItem(this.STORAGE_KEY, JSON.stringify(stories));
                this.updateUI();
            },

            isSaved(url) {
                return this.getAll().some(s => s.url === url);
            },

            updateUI() {
                document.querySelectorAll('.save-btn').forEach(btn => {
                    const isSaved = this.isSaved(btn.dataset.url);
                    btn.classList.toggle('saved', isSaved);
                    btn.setAttribute('aria-label', isSaved ? 'Remove from saved' : 'Save for later');
                });
                const badge = document.getElementById('saved-count');
                if (badge) {
                    const count = this.getAll().length;
                    badge.textContent = count;
                    badge.style.display = count > 0 ? 'flex' : 'none';
                }
                this.renderSavedPanel();
            },

            renderSavedPanel() {
                const panel = document.getElementById('saved-panel');
                if (!panel) return;
                const list = panel.querySelector('.saved-list');
                if (!list) return;
                const stories = this.getAll();

                // Clear existing content safely
                while (list.firstChild) list.removeChild(list.firstChild);

                if (stories.length === 0) {
                    const p = document.createElement('p');
                    p.className = 'empty-state';
                    p.textContent = 'No saved stories yet. Click the bookmark icon to save.';
                    list.appendChild(p);
                    return;
                }

                stories.forEach(s => {
                    const div = document.createElement('div');
                    div.className = 'saved-item';

                    const link = document.createElement('a');
                    link.href = s.url;
                    link.target = '_blank';
                    link.rel = 'noopener';
                    link.textContent = s.title;

                    const meta = document.createElement('span');
                    meta.className = 'saved-meta';
                    meta.textContent = s.source + ' - ' + new Date(s.savedAt).toLocaleDateString();

                    const removeBtn = document.createElement('button');
                    removeBtn.className = 'remove-saved';
                    removeBtn.textContent = 'x';
                    removeBtn.setAttribute('aria-label', 'Remove');
                    removeBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        this.remove(s.url);
                    });

                    div.appendChild(link);
                    div.appendChild(meta);
                    div.appendChild(removeBtn);
                    list.appendChild(div);
                });
            },

            init() {
                document.querySelectorAll('.save-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const { url, title, source } = btn.dataset;
                        if (this.isSaved(url)) {
                            this.remove(url);
                        } else {
                            this.save({ url, title, source });
                        }
                    });
                });

                const toggle = document.getElementById('saved-toggle');
                const panel = document.getElementById('saved-panel');
                if (toggle && panel) {
                    toggle.addEventListener('click', () => {
                        panel.classList.toggle('open');
                        this.renderSavedPanel();
                    });
                    document.addEventListener('click', (e) => {
                        if (!panel.contains(e.target) && !toggle.contains(e.target)) {
                            panel.classList.remove('open');
                        }
                    });
                }
                this.updateUI();
            }
        };

        SavedStories.init();

        // =====================================================
        // WEB SHARE API - Native sharing functionality
        // =====================================================
        const ShareHandler = {
            init() {
                document.querySelectorAll('.share-btn').forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const { url, title } = btn.dataset;

                        if (navigator.share) {
                            try {
                                await navigator.share({
                                    title: title,
                                    text: `Check out: ${title}`,
                                    url: url
                                });
                            } catch (err) {
                                if (err.name !== 'AbortError') {
                                    this.fallbackShare(url);
                                }
                            }
                        } else {
                            this.fallbackShare(url);
                        }
                    });
                });
            },

            fallbackShare(url) {
                // Fallback: copy to clipboard
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(url).then(() => {
                        this.showToast('Link copied to clipboard!');
                    });
                } else {
                    // Final fallback: prompt
                    prompt('Copy this link:', url);
                }
            },

            showToast(message) {
                const toast = document.createElement('div');
                toast.className = 'share-toast';
                toast.textContent = message;
                toast.style.cssText = `
                    position: fixed;
                    bottom: 2rem;
                    left: 50%;
                    transform: translateX(-50%);
                    padding: 0.75rem 1.5rem;
                    background: var(--color-accent);
                    color: white;
                    border-radius: var(--radius);
                    font-size: 0.9rem;
                    z-index: 9999;
                    animation: toastFadeIn 0.3s ease;
                `;
                document.body.appendChild(toast);
                setTimeout(() => toast.remove(), 3000);
            }
        };
        ShareHandler.init();

        // =====================================================
        // KEYBOARD NAVIGATION - Accessibility enhancement
        // =====================================================
        const KeyboardNav = {
            init() {
                // Arrow key navigation for story cards
                const cards = Array.from(document.querySelectorAll('.story-card, .compact-card'));
                let currentIndex = -1;

                document.addEventListener('keydown', (e) => {
                    if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Enter', 'Escape'].includes(e.key)) return;
                    if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;

                    const focusedCard = document.activeElement.closest('.story-card, .compact-card');
                    if (focusedCard) {
                        currentIndex = cards.indexOf(focusedCard);
                    }

                    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
                        e.preventDefault();
                        currentIndex = Math.min(currentIndex + 1, cards.length - 1);
                        cards[currentIndex]?.focus();
                    } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
                        e.preventDefault();
                        currentIndex = Math.max(currentIndex - 1, 0);
                        cards[currentIndex]?.focus();
                    } else if (e.key === 'Enter' && focusedCard) {
                        const link = focusedCard.querySelector('.story-link') || focusedCard;
                        if (link.href) window.open(link.href, '_blank');
                    } else if (e.key === 'Escape') {
                        document.activeElement.blur();
                        currentIndex = -1;
                    }
                });

                // Make cards focusable
                cards.forEach(card => {
                    if (!card.hasAttribute('tabindex')) {
                        card.setAttribute('tabindex', '0');
                    }
                });
            }
        };
        KeyboardNav.init();

        // =====================================================
        // RELATIVE TIME - Convert timestamps to "2 hours ago" format
        // =====================================================
        const RelativeTime = {
            intervals: [
                { label: 'year', seconds: 31536000 },
                { label: 'month', seconds: 2592000 },
                { label: 'week', seconds: 604800 },
                { label: 'day', seconds: 86400 },
                { label: 'hour', seconds: 3600 },
                { label: 'minute', seconds: 60 }
            ],
            format(date) {
                const seconds = Math.floor((new Date() - date) / 1000);
                if (seconds < 60) return 'just now';
                for (const interval of this.intervals) {
                    const count = Math.floor(seconds / interval.seconds);
                    if (count >= 1) {
                        return count === 1 ? `1 ${interval.label} ago` : `${count} ${interval.label}s ago`;
                    }
                }
                return 'just now';
            },
            init() {
                document.querySelectorAll('time.story-time[datetime]').forEach(el => {
                    try {
                        const date = new Date(el.getAttribute('datetime'));
                        if (!isNaN(date)) {
                            el.textContent = this.format(date);
                            el.title = date.toLocaleString();
                        }
                    } catch (e) { /* ignore invalid dates */ }
                });
            }
        };
        RelativeTime.init();

        // =====================================================
        // LIVE REGION - Announce dynamic updates to screen readers
        // =====================================================
        const liveRegion = document.createElement('div');
        liveRegion.setAttribute('role', 'status');
        liveRegion.setAttribute('aria-live', 'polite');
        liveRegion.className = 'sr-only';
        document.body.appendChild(liveRegion);

        function announce(message) {
            liveRegion.textContent = '';
            setTimeout(() => { liveRegion.textContent = message; }, 100);
        }

        // Add toast animation (unique name to avoid conflict with main fadeInUp)
        const style = document.createElement('style');
        style.textContent = `
            @keyframes toastFadeIn {
                from { opacity: 0; transform: translate(-50%, 10px); }
                to { opacity: 1; transform: translate(-50%, 0); }
            }
        `;
        document.head.appendChild(style);
    </script>"""

    def save(self, filepath: str):
        """Save the built website to a file."""
        html_content = self.build()

        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Website saved to {filepath}")
        print(f"  Personality: {self.design.get('personality', 'modern')}")
        print(f"  Layout: {self.layout} / Hero: {self.hero_style}")
        print(f"  Card style: {self.design.get('card_style', 'bordered')}")
        print(f"  Hover effect: {self.design.get('hover_effect', 'lift')}")
        print(f"  Animation: {self.design.get('animation_level', 'subtle')}")
        print(f"  Categories: {len(self.grouped_trends)}")
        return filepath


def main():
    """Main entry point for testing."""
    sample_trends = [
        {"title": "AI Revolution in Healthcare", "source": "news_nyt", "description": "AI transforms medical diagnostics.", "url": "#", "keywords": ["ai", "healthcare", "medicine"]},
        {"title": "Climate Summit Reaches Agreement", "source": "news_bbc", "description": "World leaders commit to carbon reduction.", "url": "#", "keywords": ["climate", "environment"]},
        {"title": "SpaceX Launch Success", "source": "tech_verge", "description": "Starship completes orbital test.", "url": "#", "keywords": ["space", "spacex", "rocket"]},
        {"title": "New Framework Released", "source": "hackernews", "description": "Developer tool gains popularity.", "url": "#", "keywords": ["programming", "framework"]},
        {"title": "Global Markets Rally", "source": "reddit_business", "description": "Stock indices reach highs.", "url": "#", "keywords": ["markets", "stocks", "finance"]},
        {"title": "Quantum Computing Breakthrough", "source": "reddit_science", "description": "Researchers achieve milestone.", "url": "#", "keywords": ["quantum", "computing", "science"]},
        {"title": "Movie Breaks Records", "source": "reddit_movies", "description": "Box office success.", "url": "#", "keywords": ["movie", "entertainment"]},
        {"title": "Sports Championship", "source": "reddit_sports", "description": "Team wins title.", "url": "#", "keywords": ["sports", "championship"]},
    ]

    sample_design = {
        "theme_name": "Midnight Indigo",
        "personality": "tech",
        "font_primary": "Space Grotesk",
        "font_secondary": "Inter",
        "color_bg": "#0a0a0a",
        "color_text": "#ffffff",
        "color_accent": "#6366f1",
        "color_accent_secondary": "#8b5cf6",
        "color_muted": "#a1a1aa",
        "color_card_bg": "#18181b",
        "color_border": "#27272a",
        "headline": "Today's Pulse",
        "subheadline": "What the world is talking about",
        "card_style": "glass",
        "card_radius": "1rem",
        "card_padding": "1.5rem",
        "hover_effect": "glow",
        "animation_level": "moderate",
        "text_transform_headings": "none",
        "is_dark_mode": True,
        "use_gradients": True,
        "spacing": "comfortable",
        "layout_style": "magazine",
        "hero_style": "gradient"
    }

    ctx = BuildContext(
        trends=sample_trends,
        images=[],
        design=sample_design,
        keywords=["ai", "climate", "space", "tech", "markets", "quantum"]
    )

    builder = WebsiteBuilder(ctx)
    output_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'index.html')
    builder.save(output_path)


if __name__ == "__main__":
    main()
