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
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from fetch_images import FallbackImageGenerator
from shared_components import build_header, build_footer, get_header_styles, get_footer_styles, get_theme_script


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
        
        # Setup Jinja2 environment
        # Assuming templates are in a 'templates' folder at the project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(project_root, 'templates')
        
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )

        # Use timestamp as seed for unique randomization on each generation
        timestamp_seed = datetime.now().isoformat()
        self.rng = random.Random(timestamp_seed)

        self.layout = self.design.layout_style if self.design and hasattr(self.design, 'layout_style') else self.rng.choice(LAYOUT_TEMPLATES)
        self.hero_style = self.design.hero_style if self.design and hasattr(self.design, 'hero_style') else self.rng.choice(HERO_STYLES)

        # Group trends by category
        self.grouped_trends = self._group_trends()

        # Calculate keyword frequencies for word cloud
        self.keyword_freq = self._calculate_keyword_freq()

        # Find the best hero image based on headline content
        self._hero_image = self._find_relevant_hero_image()

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
            article_image_url = top_trend.get('image_url')
            if article_image_url:
                return {
                    'url_large': article_image_url,
                    'url_medium': article_image_url,
                    'url_original': article_image_url,
                    'photographer': 'Article Image',
                    'source': 'article',
                    'alt': top_trend.get('title', 'Today\'s trending topic'),
                    'id': f"article_{hash(article_image_url) % 100000}"
                }

        # Priority 2: Fall back to stock photo matching
        if not self.ctx.images:
            return None

        # Get the headline and top trend for keyword matching
        headline = self.design.get('headline', '').lower()
        top_trend_title = ''
        if self.ctx.trends:
            top_trend_title = (self.ctx.trends[0].get('title') or '').lower()

        # Extract keywords from headline and top trend
        search_text = f"{headline} {top_trend_title}"
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                      'should', 'may', 'might', 'must', 'shall', 'can', 'of', 'in', 'to',
                      'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
                      'and', 'or', 'but', 'if', 'then', 'than', 'so', 'that', 'this',
                      'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
                      "today's", "trends", "trending", "world", "talking", "about"}
        words = [w.strip('.,!?()[]{}ப்படாத') for w in search_text.split()]
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

    def _group_trends(self) -> Dict[str, List[Dict]]:
        """Group trends by their source category."""
        groups = defaultdict(list)

        category_map = {
            'news_': 'World News',
            'tech_': 'Technology',
            'science_': 'Science',
            'politics_': 'Politics',
            'finance_': 'Finance',
            'entertainment_': 'Entertainment',
            'sports_': 'Sports',
            'reddit_news': 'World News',
            'reddit_worldnews': 'World News',
            'reddit_politics': 'Politics',
            'reddit_technology': 'Technology',
            'reddit_science': 'Science',
            'reddit_programming': 'Technology',
            'reddit_futurology': 'Future',
            'reddit_business': 'Business',
            'reddit_economics': 'Finance',
            'hackernews': 'Hacker News',
            'lobsters': 'Technology',
            'product_hunt': 'Technology',
            'devto': 'Technology',
            'slashdot': 'Technology',
            'ars_features': 'Technology',
            'github_trending': 'Technology',
            'wikipedia_current': 'World News',
        }

        for trend in self.ctx.trends:
            source = trend.get('source', 'unknown')
            category = 'Other'

            # Check for explicit category override (from NLP)
            if trend.get('category'):
                category = trend['category']
            else:
                # Fallback to source-based mapping
                for prefix, cat in category_map.items():
                    if source.startswith(prefix):
                        category = cat
                        break
            
            # Format timestamp for display
            if trend.get('timestamp'):
                ts = trend['timestamp']
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts)
                    except ValueError:
                        ts = datetime.now()
                else:
                    ts = trend['timestamp']
                
                # Calculate time ago
                diff = datetime.now() - ts
                hours = int(diff.total_seconds() / 3600)
                if hours < 1:
                    trend['time_ago'] = "Just now"
                elif hours < 24:
                    trend['time_ago'] = f"{hours}h ago"
                else:
                    trend['time_ago'] = "1d ago"
            else:
                trend['time_ago'] = "Today"

            groups[category].append(trend)

        return dict(groups)

    def _select_top_stories(self) -> List[Dict]:
        """
        Select top stories using the 'Diversity Mix' algorithm.
        Ensures representation from World, Tech, and Finance.
        """
        selected_urls = set()
        top_stories = []
        
        # Helper to find best available story from a category
        def get_best_from_category(category_names: List[str]) -> Optional[Dict]:
            candidates = []
            for cat in category_names:
                candidates.extend(self.grouped_trends.get(cat, []))
            
            # Sort by score
            candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            for story in candidates:
                if story.get('url') not in selected_urls:
                    return story
            return None

        # Slot 1: Hero - Absolute highest scoring story
        if self.ctx.trends:
            hero = self.ctx.trends[0]
            selected_urls.add(hero.get('url'))
            top_stories.append(hero)

        # Slot 2: World News
        world = get_best_from_category(['World News', 'Politics', 'Current Events'])
        if world:
            selected_urls.add(world.get('url'))
            top_stories.append(world)

        # Slot 3: Technology
        tech = get_best_from_category(['Technology', 'Hacker News', 'Science'])
        if tech:
            selected_urls.add(tech.get('url'))
            top_stories.append(tech)

        # Slot 4: Finance/Business
        finance = get_best_from_category(['Finance', 'Business'])
        if finance:
            selected_urls.add(finance.get('url'))
            top_stories.append(finance)

        # Fill remaining slots (up to 8 total) with highest scoring remaining stories
        remaining_slots = 8 - len(top_stories)
        if remaining_slots > 0:
            for story in self.ctx.trends:
                if story.get('url') not in selected_urls:
                    selected_urls.add(story.get('url'))
                    top_stories.append(story)
                    if len(top_stories) >= 8:
                        break
        
        return top_stories

    def _calculate_keyword_freq(self) -> List[Tuple[str, int, int]]:
        """Calculate keyword frequencies and assign size classes 1-6."""
        freq = defaultdict(int)
        for trend in self.ctx.trends:
            for kw in trend.get('keywords', []):
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
        """Get the main topic for SEO title."""
        if self.ctx.trends:
            return self.ctx.trends[0].get('title', '')[:60]
        return "Today's Top Trends"

    def _build_meta_description(self) -> str:
        """Build SEO-friendly meta description."""
        categories = list(self.grouped_trends.keys())[:4]
        cat_str = ', '.join(categories)
        return f"Daily trending topics for {self.ctx.generated_at}. {len(self.ctx.trends)} stories covering {cat_str}."

    def build(self) -> str:
        """Render the website using Jinja2 templates."""
        template = self.env.get_template('index.html')
        
        # Prepare hero background CSS
        hero_bg_css = FallbackImageGenerator.get_gradient_css()
        hero_image_url = ""
        if self._hero_image:
            url = self._hero_image.get('url_large') or self._hero_image.get('url_medium')
            if url:
                hero_image_url = url
                hero_bg_css = f"url('{url}') center center / cover no-repeat #0a0a0a"

        # Prepare styles from design spec
        d = self.design
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
        base_mode = "dark-mode" if d.get('is_dark_mode', True) else "light-mode"
        body_classes = [
            f"layout-{self.layout}",
            f"hero-{self.hero_style}",
            f"card-style-{card_style}",
            f"hover-{hover_effect}",
            f"animation-{animation_level}",
            base_mode,
        ]

        if d.get('text_transform_headings') != 'none':
            body_classes.append(f"text-transform-{d.get('text_transform_headings')}")

        # Add creative flourish classes from design spec
        bg_pattern = d.get('background_pattern', 'none')
        if bg_pattern and bg_pattern != 'none':
            body_classes.append(f"bg-pattern-{bg_pattern}")

        accent_style = d.get('accent_style', 'none')
        if accent_style and accent_style != 'none':
            body_classes.append(f"accent-{accent_style}")

        special_mode = d.get('special_mode', 'standard')
        if special_mode and special_mode != 'standard':
            body_classes.append(f"mode-{special_mode}")

        # Add animation modifiers
        if d.get('use_float_animation', False):
            body_classes.append("use-float")
        if d.get('use_pulse_animation', False):
            body_classes.append("use-pulse")

        # Add new design dimension classes
        image_treatment = d.get('image_treatment', 'none')
        if image_treatment and image_treatment != 'none':
            body_classes.append(f"image-treatment-{image_treatment}")

        card_aspect = d.get('card_aspect_ratio', 'auto')
        if card_aspect and card_aspect != 'auto':
            body_classes.append(f"aspect-{card_aspect}")

        # Build context variables for the template
        render_context = {
            'page_title': f"DailyTrending.info - {self._get_top_topic()}",
            'meta_description': self._build_meta_description(),
            'keywords_str': ', '.join(self.ctx.keywords[:15]),
            'canonical_url': 'https://dailytrending.info/',
            'date_str': self.ctx.generated_at,
            'date_iso': datetime.now().strftime("%Y-%m-%d"),
            'last_modified': datetime.now().isoformat(),
            'font_primary': d.get('font_primary', 'Space Grotesk').replace(' ', '+'),
            'font_secondary': d.get('font_secondary', 'Inter').replace(' ', '+'),
            'font_primary_family': d.get('font_primary', 'Space Grotesk'),
            'font_secondary_family': d.get('font_secondary', 'Inter'),
            'hero_image_url': hero_image_url,
            'colors': {
                'bg': d.get('color_bg', '#0a0a0a'),
                'text': d.get('color_text', '#ffffff'),
                'accent': d.get('color_accent', '#6366f1'),
                'accent_secondary': d.get('color_accent_secondary', '#8b5cf6'),
                'muted': d.get('color_muted', '#a1a1aa'),
                'card_bg': d.get('color_card_bg', '#18181b'),
                'border': d.get('color_border', '#27272a'),
            },
            'design': {
                'card_radius': d.get('card_radius', '1rem'),
                'card_padding': d.get('card_padding', '1.5rem'),
                'max_width': d.get('max_width', '1400px'),
                'theme_name': d.get('theme_name'),
                'subheadline': d.get('subheadline'),
                'story_capsules': d.get('story_capsules', [])
            },
            'hero_bg_css': hero_bg_css,
            'body_classes': ' '.join(body_classes),
            'custom_styles': custom_styles,
            
            # Content
            'hero_story': self.ctx.trends[0] if self.ctx.trends else {},
            'top_stories': self._select_top_stories(),
            'trends': self.ctx.trends,
            'total_trends_count': len(self.ctx.trends),
            'word_cloud': self.keyword_freq,
            'categories': sorted(self.grouped_trends.items(), key=lambda x: len(x[1]), reverse=True),
            
            # SEO Placeholders (can be enhanced further)
            'og_image_tags': f'<meta property="og:image" content="{hero_image_url}">',
            'twitter_image_tags': f'<meta name="twitter:image" content="{hero_image_url}">',
            'structured_data': ''  # JSON-LD generation can be moved to a helper
        }

        return template.render(render_context)

    def save(self, output_path: str):
        """Build and save the website."""
        html_content = self.build()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
