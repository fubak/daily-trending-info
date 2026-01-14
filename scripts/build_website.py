#!/usr/bin/env python3
"""
Website Builder - Generates modern news-style websites using Jinja2 templates.

Features:
- Multiple layout templates (newspaper, magazine, dashboard, minimal, bold)
- Source-grouped sections (News, Tech, Reddit, etc.)
- Word cloud visualization
- Dynamic hero styles
- Responsive design with CSS Grid
- Jinja2 templating
"""

import os
import json
import html
import random
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

from jinja2 import Environment, FileSystemLoader, select_autoescape

from fetch_images import FallbackImageGenerator
from shared_components import (
    build_header,
    build_footer,
    get_header_styles,
    get_footer_styles,
    get_theme_script,
)


LAYOUT_TEMPLATES = ["newspaper", "magazine", "bold", "mosaic"]
HERO_STYLES = [
    "cinematic",
    "glassmorphism",
    "neon",
    "duotone",
    "particles",
    "waves",
    "geometric",
    "spotlight",
    "glitch",
    "aurora",
    "mesh",
    "retro",
]


@dataclass
class BuildContext:
    """Context for building the website."""

    trends: List[Dict]
    images: List[Dict]
    design: Dict
    keywords: List[str]
    enriched_content: Optional[Dict] = None
    why_this_matters: Optional[List[Dict]] = None
    yesterday_trends: Optional[List[Dict]] = None
    editorial_article: Optional[Dict] = None
    keyword_history: Optional[Dict] = None
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().strftime("%B %d, %Y")


class WebsiteBuilder:
    """Builds dynamic news-style websites using Jinja2 templates."""

    def __init__(self, context: BuildContext):
        self.ctx = context
        self.design = context.design
        self._description_cache = {}

        # Setup Jinja2 environment
        # Assuming templates are in a 'templates' folder at the project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(project_root, "templates")

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Use timestamp as seed for unique randomization on each generation
        timestamp_seed = datetime.now().isoformat()
        self.rng = random.Random(timestamp_seed)

        if isinstance(self.design, dict):
            layout_style = self.design.get("layout_style")
            hero_style = self.design.get("hero_style")
        else:
            layout_style = (
                self.design.layout_style
                if self.design and hasattr(self.design, "layout_style")
                else None
            )
            hero_style = (
                self.design.hero_style
                if self.design and hasattr(self.design, "hero_style")
                else None
            )

        self.layout = layout_style or self.rng.choice(LAYOUT_TEMPLATES)
        self.hero_style = hero_style or self.rng.choice(HERO_STYLES)

        # Group trends by category
        self.grouped_trends = self._group_trends()

        # Calculate keyword frequencies for word cloud
        self.keyword_freq = self._calculate_keyword_freq()

        # Find the best hero image based on headline content
        self._hero_image = self._find_relevant_hero_image()
        self._category_card_limit = 8  # 2 rows × 4 columns (must be multiple of 4)

    def _choose_column_count(self, count: int) -> int:
        """Always use 4-column layout for consistency."""
        # Always return 4 columns for uniform grid layout
        # Card counts should be multiples of 4 for even distribution
        return 4

    def _prepare_categories(self) -> List[dict]:
        categories = []
        sorted_groups = sorted(
            self.grouped_trends.items(), key=lambda x: len(x[1]), reverse=True
        )
        for title, stories in sorted_groups:
            display_stories = stories[: self._category_card_limit]
            columns = self._choose_column_count(len(display_stories))
            categories.append(
                {
                    "title": title,
                    "stories": display_stories,
                    "count": len(display_stories),
                    "columns": columns,
                }
            )
        return categories

    def _find_relevant_hero_image(self) -> Optional[Dict]:
        """Find an image that matches the headline/top story content.

        Priority:
        1. Article image from top story's RSS feed (most relevant)
        2. Stock photo matching headline keywords
        3. First available image
        """
        # Priority 1: Check if top trend has an article image from RSS
        if self.ctx.trends:
            top_trend = self.ctx.trends[0]
            article_image_url = top_trend.get("image_url")
            if article_image_url:
                return {
                    "url_large": article_image_url,
                    "url_medium": article_image_url,
                    "url_original": article_image_url,
                    "photographer": "Article Image",
                    "source": "article",
                    "alt": top_trend.get("title", "Today's trending topic"),
                    "id": f"article_{hash(article_image_url) % 100000}",
                }

        # Priority 2: Fall back to stock photo matching
        if not self.ctx.images:
            return None

        # Get the headline and top trend for keyword matching
        headline = self.design.get("headline", "").lower()
        top_trend_title = ""
        if self.ctx.trends:
            top_trend_title = (self.ctx.trends[0].get("title") or "").lower()

        # Extract keywords from headline and top trend
        search_text = f"{headline} {top_trend_title}"
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
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
            "of",
            "in",
            "to",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "and",
            "or",
            "but",
            "if",
            "then",
            "than",
            "so",
            "that",
            "this",
            "what",
            "which",
            "who",
            "whom",
            "how",
            "when",
            "where",
            "why",
            "today's",
            "trends",
            "trending",
            "world",
            "talking",
            "about",
        }
        words = [w.strip(".,!?()[]{}ப்படாத") for w in search_text.split()]
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]

        # Score each image based on keyword matches in query/description
        best_image = None
        best_score = 0

        for img in self.ctx.images:
            img_text = f"{img.get('query', '')} {img.get('description', '')}".lower()
            score = sum(1 for kw in keywords if kw in img_text)

            # Prefer larger images
            if img.get("width", 0) >= 1200:
                score += 0.5

            if score > best_score:
                best_score = score
                best_image = img

        # If no good match, use the first image
        if best_score == 0 and self.ctx.images:
            return self.ctx.images[0]

        return best_image

    def _group_trends(self) -> Dict[str, List[Dict]]:
        """Group trends by their source category."""
        groups = defaultdict(list)

        category_map = {
            # RSS feeds by category prefix
            "news_": "World News",
            "tech_": "Technology",
            "science_": "Science",
            "politics_": "Politics",
            "finance_": "Finance",
            "entertainment_": "Entertainment",
            "sports_": "Sports",
            # Reddit - News & World
            "reddit_news": "World News",
            "reddit_worldnews": "World News",
            "reddit_politics": "Politics",
            "reddit_upliftingnews": "World News",
            # Reddit - Tech & Science
            "reddit_technology": "Technology",
            "reddit_science": "Science",
            "reddit_space": "Science",
            # Reddit - Business & Finance
            "reddit_business": "Business",
            "reddit_economics": "Finance",
            "reddit_personalfinance": "Finance",
            # Reddit - Entertainment & Culture
            "reddit_movies": "Entertainment",
            "reddit_television": "Entertainment",
            "reddit_music": "Entertainment",
            "reddit_books": "Entertainment",
            # Reddit - Sports
            "reddit_sports": "Sports",
            "reddit_nba": "Sports",
            "reddit_soccer": "Sports",
            # Reddit - Health & Lifestyle
            "reddit_health": "Health",
            "reddit_food": "Lifestyle",
            # Reddit - General
            "reddit_todayilearned": "World News",
            # Tech-specific sources
            "hackernews": "Hacker News",
            "lobsters": "Technology",
            "product_hunt": "Technology",
            "devto": "Technology",
            "slashdot": "Technology",
            "ars_features": "Technology",
            "github_trending": "Technology",
            # Other
            "wikipedia_current": "World News",
            "google_trends": "Trending",
        }

        for trend in self.ctx.trends:
            source = trend.get("source", "unknown")
            category = "Other"

            # Check for explicit category override (from NLP)
            if trend.get("category"):
                category = trend["category"]
            else:
                # Fallback to source-based mapping
                for prefix, cat in category_map.items():
                    if source.startswith(prefix):
                        category = cat
                        break

            # Format timestamp for display
            if trend.get("timestamp"):
                ts = trend["timestamp"]
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts)
                    except ValueError:
                        ts = datetime.now()
                else:
                    ts = trend["timestamp"]

                # Calculate time ago
                diff = datetime.now() - ts
                hours = int(diff.total_seconds() / 3600)
                if hours < 1:
                    trend["time_ago"] = "Just now"
                elif hours < 24:
                    trend["time_ago"] = f"{hours}h ago"
                else:
                    trend["time_ago"] = "1d ago"
            else:
                trend["time_ago"] = "Today"

            groups[category].append(trend)

        return dict(groups)

    def _select_top_stories(self) -> List[Dict]:
        """
        Select top stories using the 'Diversity Mix' algorithm.
        Ensures representation from World, Tech, and Finance.
        Enforces source diversity: max 2 stories per source.
        """
        selected_urls = set()
        top_stories = []
        source_counts = defaultdict(int)  # Track stories per source
        MAX_PER_SOURCE = 2

        def can_add_story(story: Dict) -> bool:
            """Check if story can be added based on source diversity limits."""
            source = story.get("source", "unknown")
            return source_counts[source] < MAX_PER_SOURCE

        def add_story(story: Dict) -> None:
            """Add story and update tracking."""
            selected_urls.add(story.get("url"))
            source_counts[story.get("source", "unknown")] += 1
            top_stories.append(story)

        # Helper to find best available story from a category
        def get_best_from_category(category_names: List[str]) -> Optional[Dict]:
            candidates = []
            for cat in category_names:
                candidates.extend(self.grouped_trends.get(cat, []))

            # Sort by score
            candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

            for story in candidates:
                if story.get("url") not in selected_urls and can_add_story(story):
                    return story
            return None

        # Slot 1: Hero - Absolute highest scoring story
        if self.ctx.trends:
            hero = self.ctx.trends[0]
            # Ensure the hero story has the same image as the hero section
            if self._hero_image and not hero.get("image_url"):
                hero_img_url = (
                    self._hero_image.get("url_large")
                    or self._hero_image.get("url_medium")
                    or self._hero_image.get("url_original")
                )
                if hero_img_url:
                    hero["image_url"] = hero_img_url
            add_story(hero)

        # Slot 2: World News
        world = get_best_from_category(["World News", "Politics", "Current Events"])
        if world:
            add_story(world)

        # Slot 3: Technology
        tech = get_best_from_category(["Technology", "Hacker News", "Science"])
        if tech:
            add_story(tech)

        # Slot 4: Finance/Business
        finance = get_best_from_category(["Finance", "Business"])
        if finance:
            add_story(finance)

        # Fill remaining slots (up to 9 total) with highest scoring remaining stories
        # while respecting source diversity
        remaining_slots = 9 - len(top_stories)
        if remaining_slots > 0:
            for story in self.ctx.trends:
                if story.get("url") not in selected_urls and can_add_story(story):
                    add_story(story)
                    if len(top_stories) >= 9:
                        break

        for story in top_stories:
            self._ensure_story_description(story)

        return top_stories

    def _fetch_story_description(self, url: str) -> str:
        """Fetch a concise meta description for a story URL."""
        if not url or not url.startswith(("http://", "https://")):
            return ""
        if url in self._description_cache:
            return self._description_cache[url]

        description = ""
        try:
            response = requests.get(
                url, timeout=6, headers={"User-Agent": "DailyTrendingBot/1.0"}
            )
            if response.status_code >= 400:
                self._description_cache[url] = ""
                return ""

            soup = BeautifulSoup(response.text, "lxml")
            for attr, key in (
                ("property", "og:description"),
                ("name", "description"),
                ("name", "twitter:description"),
            ):
                tag = soup.find("meta", attrs={attr: key})
                if tag and tag.get("content"):
                    description = tag.get("content", "").strip()
                    break
        except Exception:
            description = ""

        description = html.unescape(description)
        description = re.sub(r"\s+", " ", description).strip()
        if len(description) > 220:
            description = description[:217].rsplit(" ", 1)[0] + "..."

        self._description_cache[url] = description
        return description

    def _ensure_story_description(self, story: Dict) -> None:
        """Add a non-AI summary when a story lacks description content."""
        if story.get("summary") or story.get("description"):
            return
        description = self._fetch_story_description(story.get("url", ""))
        if description:
            story["description"] = description

    def _calculate_keyword_freq(self) -> List[Tuple[str, int, int]]:
        """Calculate keyword frequencies and assign size classes 1-6."""
        freq = defaultdict(int)
        for trend in self.ctx.trends:
            for kw in trend.get("keywords", []):
                freq[kw.lower()] += 1

        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:50]

        if not sorted_freq:
            return []

        max_freq = sorted_freq[0][1]
        min_freq = sorted_freq[-1][1]

        result = []
        for word, count in sorted_freq:
            if max_freq == min_freq:
                size = 3
            else:
                size = 1 + int((count - min_freq) / (max_freq - min_freq) * 5)
            result.append((word, count, size))

        return result

    def _get_top_topic(self) -> str:
        """Get the main topic for SEO title - ONLY use for non-homepage pages."""
        if self.ctx.trends:
            return self.ctx.trends[0].get("title", "")[:60]
        return "Today's Top Trends"

    def _build_page_title(self) -> str:
        """Build SEO-optimized page title - static for homepage to build domain authority."""
        return "DailyTrending.info | AI-Curated Tech & World News Aggregator"

    def _build_meta_description(self) -> str:
        """Build SEO-optimized meta description with consistent keywords."""
        return (
            "Real-time dashboard of trending tech, science, and world news stories. "
            "AI-curated daily from Hacker News, NPR, BBC, Reddit, and 12+ sources. "
            f"Updated {self.ctx.generated_at} with {len(self.ctx.trends)} stories."
        )

    def _build_structured_data(self) -> str:
        """Generate comprehensive JSON-LD structured data for SEO and LLMs."""
        import json

        # Base WebSite schema
        website_schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "DailyTrending.info",
            "alternateName": "Daily Trending",
            "url": "https://dailytrending.info/",
            "description": "AI-curated technology and world news aggregator, updated daily",
            "potentialAction": {
                "@type": "SearchAction",
                "target": "https://dailytrending.info/?q={search_term_string}",
                "query-input": "required name=search_term_string",
            },
            "sameAs": ["https://twitter.com/bradshannon"],
            "speakable": {
                "@type": "SpeakableSpecification",
                "cssSelector": [".hero-content h1", ".hero-subtitle", ".story-title"],
            },
        }

        # CollectionPage with ItemList
        top_stories = self._select_top_stories()
        item_list_elements = []

        for idx, story in enumerate(top_stories[:10], 1):
            item = {
                "@type": "ListItem",
                "position": idx,
                "item": {
                    "@type": "NewsArticle",
                    "headline": story.get("title", ""),
                    "url": story.get("url", ""),
                    "datePublished": (
                        story.get("timestamp", datetime.now().isoformat())
                        if isinstance(story.get("timestamp"), str)
                        else datetime.now().isoformat()
                    ),
                    "publisher": {
                        "@type": "Organization",
                        "name": story.get("source", "").replace("_", " ").title(),
                    },
                },
            }

            # Add image if available
            if story.get("image_url"):
                item["item"]["image"] = story.get("image_url")

            # Add description if available
            if story.get("summary") or story.get("description"):
                item["item"]["description"] = story.get("summary") or story.get(
                    "description"
                )

            item_list_elements.append(item)

        collection_schema = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"Daily Trending Topics - {self.ctx.generated_at}",
            "description": self._build_meta_description(),
            "url": "https://dailytrending.info/",
            "datePublished": datetime.now().isoformat(),
            "mainEntity": {
                "@type": "ItemList",
                "numberOfItems": len(item_list_elements),
                "itemListElement": item_list_elements,
            },
        }

        # FAQPage schema for common questions
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "How often is DailyTrending.info updated?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "DailyTrending.info regenerates automatically every day at 6 AM EST via GitHub Actions, aggregating the latest trending stories from 12+ sources including Hacker News, NPR, BBC, Reddit, and GitHub.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "What sources does DailyTrending.info aggregate?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "We aggregate from 12 curated sources: Hacker News, Lobsters, GitHub Trending, Reddit (r/technology, r/worldnews, r/programming), NPR, BBC, Reuters, Wikipedia Current Events, and specialized tech RSS feeds.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "Is DailyTrending.info content AI-generated?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Headlines and summaries are sourced from original publishers. Our AI curates, ranks, and selects trending topics, and generates unique editorial analysis for top stories.",
                    },
                },
            ],
        }

        # Combine all schemas using @graph
        combined_schema = {
            "@context": "https://schema.org",
            "@graph": [website_schema, collection_schema, faq_schema],
        }

        return f'<script type="application/ld+json">\n{json.dumps(combined_schema, indent=2)}\n</script>'

    def build(self) -> str:
        """Render the website using Jinja2 templates."""
        template = self.env.get_template("index.html")

        def hex_to_rgb(value: str, fallback: str = "10, 10, 10") -> str:
            """Convert a hex color (e.g. #0a0a0a) to an RGB string."""
            if not value:
                return fallback
            hex_value = value.lstrip("#")
            if len(hex_value) == 3:
                hex_value = "".join([c * 2 for c in hex_value])
            if len(hex_value) != 6:
                return fallback
            try:
                r = int(hex_value[0:2], 16)
                g = int(hex_value[2:4], 16)
                b = int(hex_value[4:6], 16)
                return f"{r}, {g}, {b}"
            except ValueError:
                return fallback

        # Prepare hero background CSS
        hero_bg_css = FallbackImageGenerator.get_gradient_css()
        hero_image_url = ""
        if self._hero_image:
            url = self._hero_image.get("url_large") or self._hero_image.get(
                "url_medium"
            )
            if url:
                hero_image_url = url
                hero_bg_css = f"url('{url}') center center / cover no-repeat #0a0a0a"

        # Prepare styles from design spec
        d = self.design
        card_style = d.get("card_style", "bordered")
        hover_effect = d.get("hover_effect", "lift")
        animation_level = d.get("animation_level", "subtle")
        custom_styles = f"""
            .hero-content {{ 
                text-align: { 'center' if d.get('hero_style') in ['minimal', 'centered'] else 'left' }; 
            }}
            .story-card {{
                border-radius: {d.get('card_radius', '1rem')};
            }}
        """

        # Build body classes - dynamically set mode from design
        # JavaScript will override based on user preference from localStorage
        base_mode = "dark-mode" if d.get("is_dark_mode", True) else "light-mode"
        spacing = d.get("spacing", "comfortable")
        body_classes = [
            f"layout-{self.layout}",
            f"hero-{self.hero_style}",
            f"card-style-{card_style}",
            f"hover-{hover_effect}",
            f"animation-{animation_level}",
            base_mode,
        ]

        if d.get("text_transform_headings") != "none":
            body_classes.append(f"text-transform-{d.get('text_transform_headings')}")

        # Add creative flourish classes from design spec
        bg_pattern = d.get("background_pattern", "none")
        if bg_pattern and bg_pattern != "none":
            body_classes.append(f"bg-pattern-{bg_pattern}")

        accent_style = d.get("accent_style", "none")
        if accent_style and accent_style != "none":
            body_classes.append(f"accent-{accent_style}")

        special_mode = d.get("special_mode", "standard")
        if special_mode and special_mode != "standard":
            body_classes.append(f"mode-{special_mode}")

        # Add animation modifiers
        if d.get("use_float_animation", False):
            body_classes.append("use-float")
        if d.get("use_pulse_animation", False):
            body_classes.append("use-pulse")

        # Add new design dimension classes
        image_treatment = d.get("image_treatment", "none")
        if image_treatment and image_treatment != "none":
            body_classes.append(f"image-treatment-{image_treatment}")

        card_aspect = d.get("card_aspect_ratio", "auto")
        if card_aspect and card_aspect != "auto":
            body_classes.append(f"aspect-{card_aspect}")

        if spacing:
            body_classes.append(f"density-{spacing}")

        section_gap_map = {
            "compact": "2.5rem",
            "comfortable": "3.5rem",
            "spacious": "5rem",
        }
        section_gap = section_gap_map.get(spacing, "3.5rem")

        categories = self._prepare_categories()

        # Build context variables for the template
        render_context = {
            "page_title": self._build_page_title(),
            "meta_description": self._build_meta_description(),
            "keywords_str": ", ".join(self.ctx.keywords[:15]),
            "canonical_url": "https://dailytrending.info/",
            "date_str": self.ctx.generated_at,
            "date_iso": datetime.now().strftime("%Y-%m-%d"),
            "last_modified": datetime.now().isoformat(),
            "active_page": "home",
            "font_primary": d.get("font_primary", "Space Grotesk").replace(" ", "+"),
            "font_secondary": d.get("font_secondary", "Inter").replace(" ", "+"),
            "font_primary_family": d.get("font_primary", "Space Grotesk"),
            "font_secondary_family": d.get("font_secondary", "Inter"),
            "hero_image_url": hero_image_url,
            "section_gap": section_gap,
            "colors": {
                "bg": d.get("color_bg", "#0a0a0a"),
                "bg_rgb": hex_to_rgb(d.get("color_bg", "#0a0a0a")),
                "text": d.get("color_text", "#ffffff"),
                "accent": d.get("color_accent", "#6366f1"),
                "accent_secondary": d.get("color_accent_secondary", "#8b5cf6"),
                "muted": d.get("color_muted", "#a1a1aa"),
                "card_bg": d.get("color_card_bg", "#18181b"),
                "border": d.get("color_border", "#27272a"),
            },
            "design": {
                "card_radius": d.get("card_radius", "1rem"),
                "card_padding": d.get("card_padding", "1.5rem"),
                "max_width": d.get("max_width", "1400px"),
                "theme_name": d.get("theme_name"),
                "subheadline": d.get("subheadline"),
                "story_capsules": d.get("story_capsules", []),
            },
            "hero_bg_css": hero_bg_css,
            "body_classes": " ".join(body_classes),
            "custom_styles": custom_styles,
            "placeholder_image_url": "/assets/nano-banana.png",
            # Content
            "hero_story": self.ctx.trends[0] if self.ctx.trends else {},
            "top_stories": self._select_top_stories(),
            "trends": self.ctx.trends,
            "total_trends_count": len(self.ctx.trends),
            "word_cloud": self.keyword_freq,
            "categories": categories,
            # SEO - Static branded OG image for consistent social sharing
            "og_image_tags": '<meta property="og:image" content="https://dailytrending.info/og-image.png">\n    <meta property="og:image:width" content="1200">\n    <meta property="og:image:height" content="630">\n    <meta property="og:image:type" content="image/png">',
            "twitter_image_tags": '<meta name="twitter:image" content="https://dailytrending.info/twitter-image.png">\n    <meta name="twitter:card" content="summary_large_image">',
            "structured_data": self._build_structured_data(),
        }

        return template.render(render_context)

    def save(self, output_path: str):
        """Build and save the website."""
        html_content = self.build()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
