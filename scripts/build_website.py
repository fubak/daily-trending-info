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

    def _get_top_topic(self) -> str:
        """Get the main topic for SEO title."""
        # Try to get from top trend
        if self.ctx.trends:
            top_trend = self.ctx.trends[0]
            title = top_trend.get('title', '')
            # Truncate to reasonable length for title
            if len(title) > 60:
                words = title.split()[:8]
                title = ' '.join(words)
                if len(title) > 60:
                    title = title[:57] + '...'
            return title

        # Fall back to top keywords
        if self.keyword_freq:
            top_kws = [kw.title() for kw, _ in self.keyword_freq[:3]]
            return ', '.join(top_kws) + ' Trends'

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
        """Build Open Graph image meta tag."""
        if self.ctx.images:
            img = self.ctx.images[0]
            url = img.get('url_large') or img.get('url_medium', '')
            if url:
                return f'<meta property="og:image" content="{html.escape(url)}">'
        return '<meta property="og:image" content="https://dailytrending.info/og-image.png">'

    def _build_twitter_image(self) -> str:
        """Build Twitter Card image meta tag."""
        if self.ctx.images:
            img = self.ctx.images[0]
            url = img.get('url_large') or img.get('url_medium', '')
            if url:
                return f'<meta name="twitter:image" content="{html.escape(url)}">'
        return '<meta name="twitter:image" content="https://dailytrending.info/og-image.png">'

    def _build_structured_data(self) -> str:
        """Build JSON-LD structured data for LLMs and search engines."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        iso_date = datetime.now().isoformat()

        # Get top stories for article list
        top_stories = []
        for i, trend in enumerate(self.ctx.trends[:10]):
            story = {
                "@type": "Article",
                "position": i + 1,
                "name": trend.get('title', 'Untitled'),
                "url": trend.get('url', ''),
                "description": trend.get('description', '')[:200] if trend.get('description') else '',
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
        """Build Google Fonts link."""
        primary = self.design.get('font_primary', 'Space Grotesk').replace(' ', '+')
        secondary = self.design.get('font_secondary', 'Inter').replace(' ', '+')

        return f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family={primary}:wght@400;500;600;700;800;900&family={secondary}:wght@400;500;600&display=swap" rel="stylesheet">"""

    def _build_styles(self) -> str:
        """Build all CSS styles with layout variants."""
        d = self.design

        # Get hero image if available
        hero_image = self.ctx.images[0] if self.ctx.images else None
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
        body.light-mode .hero-subtitle,
        body.light-mode .hero-meta,
        body.light-mode .story-description,
        body.light-mode .footer-description,
        body.light-mode .section-count {{
            color: #64748b;
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
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 6rem 2rem 4rem;
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
            color: var(--color-muted);
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
            color: var(--color-muted);
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
            color: var(--color-muted);
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
            gap: 1.5rem;
            margin-bottom: 4rem;
        }}

        /* Layout variants for top stories */
        .layout-newspaper .top-stories {{
            grid-template-columns: 2fr 1fr 1fr;
            grid-template-rows: auto auto;
        }}

        .layout-newspaper .top-stories .story-card:first-child {{
            grid-row: span 2;
        }}

        .layout-magazine .top-stories {{
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 400px 200px;
        }}

        .layout-magazine .top-stories .story-card:first-child {{
            grid-column: span 2;
        }}

        .layout-dashboard .top-stories {{
            grid-template-columns: repeat(4, 1fr);
        }}

        .layout-minimal .top-stories {{
            grid-template-columns: 1fr;
            max-width: 800px;
            margin-left: auto;
            margin-right: auto;
        }}

        .layout-bold .top-stories {{
            grid-template-columns: 1fr;
        }}

        .layout-bold .top-stories .story-card:first-child {{
            padding: 3rem;
        }}

        .layout-mosaic .top-stories {{
            grid-template-columns: repeat(6, 1fr);
            grid-auto-rows: 150px;
        }}

        .layout-mosaic .top-stories .story-card:nth-child(1) {{
            grid-column: span 4;
            grid-row: span 2;
        }}

        .layout-mosaic .top-stories .story-card:nth-child(2) {{
            grid-column: span 2;
            grid-row: span 2;
        }}

        .layout-mosaic .top-stories .story-card:nth-child(3),
        .layout-mosaic .top-stories .story-card:nth-child(4) {{
            grid-column: span 3;
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
            background: linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.85) 100%);
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
            display: flex;
            flex-direction: column;
            height: 100%;
            z-index: 1;
        }}

        .story-source {{
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--color-accent);
            margin-bottom: 0.75rem;
        }}

        .story-card.featured .story-source,
        .story-card.has-image .story-source {{
            color: rgba(255,255,255,0.8);
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
            font-size: 1.5rem;
        }}

        .story-description {{
            font-size: 0.9rem;
            color: var(--color-muted);
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .story-card.featured .story-description,
        .story-card.has-image .story-description {{
            color: rgba(255,255,255,0.9);
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

        .compact-card-source {{
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--color-accent);
            margin-bottom: 0.25rem;
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
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            padding: 2rem;
            background: var(--color-card-bg);
            border-radius: var(--radius-lg);
            border: 1px solid var(--color-border);
            margin: 4rem 0;
        }}

        .stat {{
            text-align: center;
        }}

        .stat-value {{
            font-family: var(--font-primary);
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, var(--color-accent), var(--color-accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .stat-label {{
            font-size: 0.8rem;
            color: var(--color-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        /* ===== ENRICHED CONTENT (Word of Day, Grokipedia) ===== */
        .enriched-content {{
            margin: 3rem 0;
        }}

        .enriched-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-top: 1.5rem;
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

            .nav-links {{
                display: none;
            }}
        }}

        @media (max-width: 768px) {{
            .hero {{
                padding: 5rem 1rem 2rem;
                min-height: 70vh;
            }}

            .hero-split .hero {{
                grid-template-columns: 1fr;
            }}

            .top-stories,
            .layout-newspaper .top-stories,
            .layout-magazine .top-stories,
            .layout-dashboard .top-stories,
            .layout-mosaic .top-stories {{
                grid-template-columns: 1fr;
            }}

            .top-stories .story-card:first-child {{
                grid-column: span 1 !important;
                grid-row: span 1 !important;
            }}

            .category-grid {{
                grid-template-columns: 1fr;
            }}

            .stats-bar {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .word-cloud {{
                padding: 1rem;
            }}

            main {{
                padding: 2rem 1rem;
            }}

            .footer-bottom {{
                flex-direction: column;
                gap: 1rem;
                text-align: center;
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
        # Build links in same order as sections appear on page
        links_list = []

        # First: What's Trending (word cloud)
        links_list.append('<li><a href="#whats-trending">Trending</a></li>')

        # Second: Top Stories
        links_list.append('<li><a href="#top-stories">Top Stories</a></li>')

        # Then: Category sections (sorted by trend count, same as _build_category_sections)
        for category, _ in self._sorted_categories[:4]:
            section_id = category.lower().replace(' ', '-')
            links_list.append(f'<li><a href="#{section_id}">{category}</a></li>')

        links = '\n                '.join(links_list)

        return f"""
    <nav class="nav" id="nav" role="navigation" aria-label="Main navigation">
        <a href="/" class="nav-logo" aria-label="DailyTrending.info Home">
            <span>DailyTrending.info</span>
        </a>
        <ul class="nav-links">
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

        return f"""
    <header class="hero">
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

            cards_html.append(f'''
            <article class="story-card {extra_class}" {image_style}>
                <div class="story-content">
                    <span class="story-source">{source}</span>
                    <h3 class="story-title">{title}</h3>
                    {f'<p class="story-description">{desc}</p>' if desc else ''}
                </div>
                <a href="{html.escape(url)}" class="story-link" target="_blank" rel="noopener"></a>
            </article>''')

        return f"""
    <section class="section" id="top-stories">
        <div class="section-header">
            <h2 class="section-title">Top Stories</h2>
            <span class="section-count">{len(top)} featured</span>
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

                cards_html.append(f'''
                <a href="{html.escape(url)}" class="compact-card" target="_blank" rel="noopener">
                    <span class="compact-card-number">{i + 1:02d}</span>
                    <div class="compact-card-content">
                        <span class="compact-card-source">{source}</span>
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
        """Build the enriched content section with Word of Day and Grokipedia."""
        if not self.ctx.enriched_content:
            return ""

        sections = []

        # Word of the Day
        word_section = self._build_word_of_the_day()
        if word_section:
            sections.append(word_section)

        # Grokipedia Article
        article_section = self._build_grokipedia_article()
        if article_section:
            sections.append(article_section)

        if not sections:
            return ""

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

    def _build_stats_bar(self) -> str:
        """Build statistics bar."""
        total_trends = len(self.ctx.trends)
        total_sources = len(set(t.get('source', '') for t in self.ctx.trends))
        total_categories = len(self.grouped_trends)
        total_keywords = len(self.keyword_freq)

        return f"""
    <div class="stats-bar">
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

        // Navbar scroll effect
        const nav = document.getElementById('nav');
        window.addEventListener('scroll', () => {
            if (window.scrollY > 100) {
                nav.classList.add('scrolled');
            } else {
                nav.classList.remove('scrolled');
            }
        });

        // Animate elements on scroll
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    entry.target.style.animationDelay = `${index * 0.1}s`;
                    entry.target.classList.add('animate-in');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        document.querySelectorAll('.story-card, .compact-card, .stat').forEach(el => {
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
