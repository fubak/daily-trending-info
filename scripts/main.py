#!/usr/bin/env python3
"""
Main Pipeline Orchestrator - Runs the complete trend website generation pipeline.

Pipeline steps:
1. Archive previous website (if exists)
2. Collect trends from multiple sources
3. Fetch images based on trending keywords
4. Generate design specification (AI or preset)
5. Build the HTML/CSS website
6. Clean up old archives

Usage:
    python main.py              # Run full pipeline
    python main.py --no-archive # Skip archiving step
    python main.py --dry-run    # Collect data but don't build
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from typing import List

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    MIN_TRENDS, MIN_FRESH_RATIO, setup_logging,
    MAX_IMAGE_KEYWORDS, IMAGES_PER_KEYWORD
)
from collect_trends import TrendCollector
from fetch_images import ImageFetcher
from generate_design import DesignGenerator, DesignSpec
from build_website import WebsiteBuilder, BuildContext
from archive_manager import ArchiveManager
from generate_rss import generate_rss_feed
from enrich_content import ContentEnricher, EnrichedContent
from keyword_tracker import KeywordTracker
from pwa_generator import save_pwa_assets
from sitemap_generator import save_sitemap
from editorial_generator import EditorialGenerator

# Setup logging
logger = setup_logging("pipeline")


class Pipeline:
    """Orchestrates the complete website generation pipeline."""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.public_dir = self.project_root / "public"
        self.data_dir = self.project_root / "data"

        # Ensure directories exist
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.trend_collector = TrendCollector()
        self.image_fetcher = ImageFetcher()
        self.design_generator = DesignGenerator()
        self.archive_manager = ArchiveManager(public_dir=str(self.public_dir))
        self.keyword_tracker = KeywordTracker()
        self.content_enricher = ContentEnricher()
        self.editorial_generator = EditorialGenerator(public_dir=self.public_dir)

        # Pipeline data
        self.trends = []
        self.images = []
        self.design = None
        self.keywords = []
        self.global_keywords = []
        self.enriched_content = None
        self.editorial_article = None
        self.why_this_matters = []
        self.yesterday_trends = []

    def _validate_environment(self) -> List[str]:
        """
        Validate environment configuration and API keys.

        Returns:
            List of warning messages (empty if all OK)
        """
        warnings = []

        # Check image API keys
        pexels_key = os.getenv('PEXELS_API_KEY')
        unsplash_key = os.getenv('UNSPLASH_ACCESS_KEY')
        if not pexels_key and not unsplash_key:
            warnings.append(
                "No image API keys configured (PEXELS_API_KEY or UNSPLASH_ACCESS_KEY). "
                "Images will use fallback gradients."
            )

        # Check AI API keys for design generation
        google_key = os.getenv('GOOGLE_AI_API_KEY')
        groq_key = os.getenv('GROQ_API_KEY')
        openrouter_key = os.getenv('OPENROUTER_API_KEY')

        # Log available LLM providers
        available_providers = []
        if google_key:
            available_providers.append("Google AI (primary)")
        if openrouter_key:
            available_providers.append("OpenRouter")
        if groq_key:
            available_providers.append("Groq")

        if available_providers:
            logger.info(f"LLM providers available: {', '.join(available_providers)}")
        else:
            warnings.append(
                "No AI API keys configured (GOOGLE_AI_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY). "
                "Design will use preset themes."
            )

        # Check directory permissions
        try:
            test_file = self.public_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except (IOError, OSError) as e:
            warnings.append(f"Cannot write to public directory: {e}")

        try:
            test_file = self.data_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except (IOError, OSError) as e:
            warnings.append(f"Cannot write to data directory: {e}")

        return warnings

    def run(self, archive: bool = True, dry_run: bool = False) -> bool:
        """
        Run the complete pipeline.

        Args:
            archive: Whether to archive the previous website
            dry_run: If True, collect data but don't build

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("TREND WEBSITE GENERATOR")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        # Validate environment before starting
        env_warnings = self._validate_environment()
        for warning in env_warnings:
            logger.warning(f"Environment: {warning}")

        try:
            # Step 1: Archive previous website
            if archive:
                self._step_archive()

            # Step 2: Load yesterday's trends for comparison
            self._step_load_yesterday()

            # Step 3: Collect trends
            self._step_collect_trends()

            # Step 4: Fetch images
            self._step_fetch_images()

            # Step 5: Enrich content (Word of Day, Grokipedia, summaries)
            self._step_enrich_content()

            # Step 6: Generate design
            self._step_generate_design()

            # Step 7: Generate editorial article and Why This Matters
            if not dry_run:
                self._step_generate_editorial()

            # Step 8: Build website
            if not dry_run:
                self._step_build_website()

            # Step 9: Generate topic sub-pages
            if not dry_run:
                self._step_generate_topic_pages()

            # Step 10: Generate RSS feed
            if not dry_run:
                self._step_generate_rss()

            # Step 11: Generate PWA assets
            if not dry_run:
                self._step_generate_pwa()

            # Step 12: Generate sitemap
            if not dry_run:
                self._step_generate_sitemap()

            # Step 13: Cleanup old archives (not articles - those are permanent)
            if archive and not dry_run:
                self._step_cleanup()

            # Step 14: Save pipeline data
            self._save_data()

            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETE")
            logger.info("=" * 60)

            if not dry_run:
                logger.info(f"Website generated at: {self.public_dir / 'index.html'}")
                logger.info(f"Archive available at: {self.public_dir / 'archive' / 'index.html'}")

            return True

        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"PIPELINE FAILED: {e}")
            logger.error("=" * 60)
            import traceback
            traceback.print_exc()
            return False

    def _step_archive(self):
        """Archive the previous website."""
        logger.info("[1/14] Archiving previous website...")

        # Try to load previous design metadata
        previous_design = None
        design_file = self.data_dir / "design.json"
        if design_file.exists():
            try:
                with open(design_file) as f:
                    previous_design = json.load(f)
            except Exception:
                pass

        self.archive_manager.archive_current(design=previous_design)

    def _step_load_yesterday(self):
        """Load yesterday's trends for comparison feature."""
        logger.info("[2/14] Loading yesterday's trends...")

        # Try to load from most recent archive
        archive_dir = self.public_dir / "archive"
        if archive_dir.exists():
            # Find most recent archive with trends.json
            archives = sorted(archive_dir.iterdir(), reverse=True)
            for archive in archives[:3]:  # Check last 3 days
                trends_file = self.data_dir / "trends.json"
                if trends_file.exists():
                    try:
                        with open(trends_file) as f:
                            self.yesterday_trends = json.load(f)
                            logger.info(f"Loaded {len(self.yesterday_trends)} trends from previous build")
                            break
                    except Exception:
                        pass

        if not self.yesterday_trends:
            logger.info("No previous trends available for comparison")

    def _step_collect_trends(self):
        """Collect trends from all sources."""
        logger.info("[3/14] Collecting trends...")

        self.trends = self.trend_collector.collect_all()
        self.keywords = self.trend_collector.get_all_keywords()
        self.global_keywords = self.trend_collector.get_global_keywords()

        # Get freshness ratio
        freshness_ratio = self.trend_collector.get_freshness_ratio()

        logger.info(f"Collected {len(self.trends)} unique trends")
        logger.info(f"Extracted {len(self.keywords)} keywords")
        logger.info(f"Identified {len(self.global_keywords)} global meta-trends")
        logger.info(f"Freshness ratio: {freshness_ratio:.0%} from past 24h")

        # Log sample trends for debugging
        if self.trends:
            logger.info("Sample trends collected:")
            for i, trend in enumerate(self.trends[:3]):
                logger.info(f"  {i+1}. {trend.title[:50]}... (source: {trend.source})")

        # Record keywords for trending analysis
        self.keyword_tracker.record_keywords(self.keywords)

        # Log trending keywords
        trending = self.keyword_tracker.get_trending_keywords(5)
        if trending:
            trending_str = ", ".join([f"{t.keyword} ({t.trend})" for t in trending])
            logger.info(f"Top trending keywords: {trending_str}")

        # Quality gate 1: Ensure minimum content
        if len(self.trends) < MIN_TRENDS:
            raise Exception(
                f"Insufficient content: Only {len(self.trends)} trends found. "
                f"Minimum required is {MIN_TRENDS}. "
                "Aborting to prevent deploying a broken site."
            )

        # Quality gate 2: Ensure content freshness
        if freshness_ratio < MIN_FRESH_RATIO:
            logger.warning(
                f"Low freshness: Only {freshness_ratio:.0%} of trends are from past 24h. "
                f"Minimum recommended is {MIN_FRESH_RATIO:.0%}. Proceeding with caution."
            )

    def _step_fetch_images(self):
        """Fetch images based on trending keywords."""
        logger.info("[4/14] Fetching images...")

        # Prioritize global keywords (meta-trends) for image search
        # These are words appearing in 3+ stories, more likely to be relevant
        search_keywords = []

        # Add global keywords first (up to half the slots)
        global_slots = MAX_IMAGE_KEYWORDS // 2
        if self.global_keywords:
            search_keywords.extend(self.global_keywords[:global_slots])
            logger.info(f"Using {len(search_keywords)} global keywords for images")

        # Fill remaining slots with top regular keywords
        remaining_slots = MAX_IMAGE_KEYWORDS - len(search_keywords)
        if remaining_slots > 0:
            for kw in self.keywords:
                if kw not in search_keywords:
                    search_keywords.append(kw)
                    if len(search_keywords) >= MAX_IMAGE_KEYWORDS:
                        break

        if search_keywords:
            self.images = self.image_fetcher.fetch_for_keywords(
                search_keywords,
                images_per_keyword=IMAGES_PER_KEYWORD
            )
            logger.info(f"Fetched {len(self.images)} images")
        else:
            logger.warning("No keywords for image search, using fallback gradients")

    def _step_enrich_content(self):
        """Enrich content with Word of Day, Grokipedia article, and story summaries."""
        logger.info("[5/14] Enriching content...")

        # Convert trends to dict format
        trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]

        # Get enriched content
        self.enriched_content = self.content_enricher.enrich(trends_data, self.keywords)

        # Log results
        if self.enriched_content.word_of_the_day:
            logger.info(f"  Word of the Day: {self.enriched_content.word_of_the_day.word}")
        if self.enriched_content.grokipedia_article:
            logger.info(f"  Grokipedia Article: {self.enriched_content.grokipedia_article.title}")
        logger.info(f"  Story summaries: {len(self.enriched_content.story_summaries)}")

    def _step_generate_design(self):
        """Generate the design specification."""
        logger.info("[6/14] Generating design...")

        # Convert trends to dict format for the generator
        trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]

        self.design = self.design_generator.generate(trends_data, self.keywords)

        logger.info(f"Theme: {self.design.theme_name}")
        logger.info(f"Mood: {self.design.mood}")
        logger.info(f"Headline: {self.design.headline}")

    def _step_generate_editorial(self):
        """Generate editorial article and Why This Matters context."""
        logger.info("[7/14] Generating editorial content...")

        # Convert trends to dict format
        trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]
        design_data = asdict(self.design) if hasattr(self.design, '__dataclass_fields__') else self.design

        # Generate editorial article
        self.editorial_article = self.editorial_generator.generate_editorial(
            trends_data,
            self.keywords,
            design_data
        )

        if self.editorial_article:
            logger.info(f"  Editorial: {self.editorial_article.title} ({self.editorial_article.word_count} words)")
            logger.info(f"  URL: {self.editorial_article.url}")

        # Generate Why This Matters for top 3 stories
        self.why_this_matters = self.editorial_generator.generate_why_this_matters(
            trends_data,
            count=3
        )
        logger.info(f"  Why This Matters: {len(self.why_this_matters)} explanations")

        # Generate articles index page
        self.editorial_generator.generate_articles_index(design_data)
        logger.info("  Articles index updated")

    def _step_build_website(self):
        """Build the final HTML website."""
        logger.info("[8/14] Building website...")
        logger.info(f"Building with {len(self.trends)} trends, {len(self.images)} images")

        # Convert data to proper format
        trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]
        logger.info(f"Converted {len(trends_data)} trends to dict format")

        # Log sample trend for debugging
        if trends_data:
            sample = trends_data[0]
            logger.info(f"Sample trend: title='{sample.get('title', '')[:50]}', source='{sample.get('source', '')}'")

        images_data = [asdict(i) if hasattr(i, '__dataclass_fields__') else i for i in self.images]
        design_data = asdict(self.design) if hasattr(self.design, '__dataclass_fields__') else self.design

        # Convert enriched content to dict format
        enriched_data = None
        if self.enriched_content:
            enriched_data = {
                'word_of_the_day': asdict(self.enriched_content.word_of_the_day) if self.enriched_content.word_of_the_day else None,
                'grokipedia_article': asdict(self.enriched_content.grokipedia_article) if self.enriched_content.grokipedia_article else None,
                'story_summaries': [asdict(s) for s in self.enriched_content.story_summaries] if self.enriched_content.story_summaries else []
            }
            # Log enriched content status
            if enriched_data.get('grokipedia_article'):
                article = enriched_data['grokipedia_article']
                logger.info(f"Grokipedia article: '{article.get('title', '')}' ({len(article.get('summary', ''))} chars)")

        # Convert why_this_matters to dict format
        why_this_matters_data = None
        if self.why_this_matters:
            why_this_matters_data = [
                asdict(wtm) if hasattr(wtm, '__dataclass_fields__') else wtm
                for wtm in self.why_this_matters
            ]

        # Convert editorial article to dict format
        editorial_data = None
        if self.editorial_article:
            editorial_data = asdict(self.editorial_article) if hasattr(self.editorial_article, '__dataclass_fields__') else self.editorial_article

        # Load keyword history for timeline
        keyword_history = None
        keyword_history_file = self.data_dir / "keyword_history.json"
        if keyword_history_file.exists():
            try:
                with open(keyword_history_file) as f:
                    keyword_history = json.load(f)
            except Exception:
                pass

        # Build context with all new features
        context = BuildContext(
            trends=trends_data,
            images=images_data,
            design=design_data,
            keywords=self.keywords,
            enriched_content=enriched_data,
            why_this_matters=why_this_matters_data,
            yesterday_trends=self.yesterday_trends,
            editorial_article=editorial_data,
            keyword_history=keyword_history
        )

        # Build and save
        builder = WebsiteBuilder(context)
        output_path = self.public_dir / "index.html"
        builder.save(str(output_path))

        logger.info(f"Website saved to {output_path}")

    def _step_generate_topic_pages(self):
        """Generate topic-specific sub-pages (/tech, /world, /science, etc.)."""
        logger.info("[9/14] Generating topic sub-pages...")

        # Convert data to proper format
        trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]
        design_data = asdict(self.design) if hasattr(self.design, '__dataclass_fields__') else self.design
        images_data = [asdict(i) if hasattr(i, '__dataclass_fields__') else i for i in self.images]

        # Define topic categories and their filters
        # Sources use prefix matching: 'tech_' matches 'tech_verge', 'tech_wired', etc.
        topic_configs = [
            {
                'slug': 'tech',
                'title': 'Technology',
                'description': 'Latest technology news, startups, and developer trends',
                'source_prefixes': ['hackernews', 'lobsters', 'tech_', 'github_trending', 'product_hunt', 'devto', 'slashdot', 'ars_']
            },
            {
                'slug': 'world',
                'title': 'World News',
                'description': 'Breaking news and current events from around the world',
                'source_prefixes': ['news_', 'wikipedia', 'google_trends']
            },
            {
                'slug': 'science',
                'title': 'Science & Health',
                'description': 'Latest discoveries in science, technology, medicine, and space',
                'source_prefixes': ['science_']
            },
            {
                'slug': 'politics',
                'title': 'Politics & Policy',
                'description': 'Political news, policy analysis, and government updates',
                'source_prefixes': ['politics_']
            },
            {
                'slug': 'finance',
                'title': 'Business & Finance',
                'description': 'Market news, business trends, and economic analysis',
                'source_prefixes': ['finance_']
            }
        ]

        def matches_topic(source: str, prefixes: list) -> bool:
            """Check if a source matches any of the topic's prefixes."""
            for prefix in prefixes:
                if prefix.endswith('_'):
                    if source.startswith(prefix):
                        return True
                else:
                    if source == prefix:
                        return True
            return False

        pages_created = 0
        for config in topic_configs:
            # Filter trends for this topic using prefix matching
            topic_trends = [
                t for t in trends_data
                if matches_topic(t.get('source', ''), config['source_prefixes'])
            ]

            if len(topic_trends) < 3:
                logger.info(f"  Skipping /{config['slug']}/ - only {len(topic_trends)} stories")
                continue

            # Create topic directory
            topic_dir = self.public_dir / config['slug']
            topic_dir.mkdir(parents=True, exist_ok=True)

            # Build topic page HTML
            html = self._build_topic_page(
                config, topic_trends, design_data, images_data
            )

            # Save
            (topic_dir / "index.html").write_text(html, encoding='utf-8')
            pages_created += 1
            logger.info(f"  Created /{config['slug']}/ with {len(topic_trends)} stories")

        logger.info(f"Generated {pages_created} topic sub-pages")

    def _build_topic_page(
        self,
        config: dict,
        trends: list,
        design: dict,
        images: list
    ) -> str:
        """Build HTML for a topic sub-page."""
        from datetime import datetime

        primary = design.get('primary_color', '#667eea')
        accent = design.get('accent_color', '#4facfe')
        bg = design.get('background_color', '#0f0f23')

        # Build story cards
        cards = []
        for t in trends[:20]:
            title = t.get('title', '')[:100]
            url = t.get('url', '#')
            source = t.get('source', '').replace('_', ' ').title()
            desc = (t.get('description', '') or '')[:150]

            cards.append(f'''
            <article class="story-card">
                <span class="source-badge">{source}</span>
                <h3><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
                {'<p>' + desc + '</p>' if desc else ''}
            </article>
            ''')

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config['title']} | DailyTrending.info</title>
    <meta name="description" content="{config['description']}">
    <link rel="canonical" href="https://dailytrending.info/{config['slug']}/">

    <meta property="og:title" content="{config['title']} | DailyTrending.info">
    <meta property="og:description" content="{config['description']}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://dailytrending.info/{config['slug']}/">
    <meta property="og:image" content="https://dailytrending.info/og-image.png">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@bradshannon">
    <meta name="twitter:creator" content="@bradshannon">
    <meta name="twitter:title" content="{config['title']} | DailyTrending.info">
    <meta name="twitter:description" content="{config['description']}">
    <meta name="twitter:image" content="https://dailytrending.info/og-image.png">

    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "{config['title']} Trends",
        "description": "{config['description']}",
        "url": "https://dailytrending.info/{config['slug']}/",
        "isPartOf": {{"@id": "https://dailytrending.info"}},
        "dateModified": "{datetime.now().isoformat()}",
        "numberOfItems": {len(trends)}
    }}
    </script>

    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{ --primary: {primary}; --accent: {accent}; --bg: {bg}; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: #fff; line-height: 1.6; min-height: 100vh; }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 2rem 1.5rem; }}
        .back-link {{ display: inline-flex; align-items: center; gap: 0.5rem; color: var(--accent); text-decoration: none; margin-bottom: 2rem; }}
        .page-header {{ margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        .page-header h1 {{ font-size: 2.5rem; margin-bottom: 0.5rem; }}
        .page-header p {{ color: rgba(255,255,255,0.7); }}
        .stats {{ font-size: 0.875rem; color: var(--accent); margin-top: 0.5rem; }}
        .stories-grid {{ display: grid; gap: 1.5rem; }}
        .story-card {{ background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 1.5rem; transition: transform 0.2s, border-color 0.2s; }}
        .story-card:hover {{ transform: translateY(-2px); border-color: var(--primary); }}
        .source-badge {{ display: inline-block; background: var(--primary); color: white; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.7rem; font-weight: 500; text-transform: uppercase; margin-bottom: 0.5rem; }}
        .story-card h3 {{ font-size: 1.1rem; margin-bottom: 0.5rem; }}
        .story-card h3 a {{ color: #fff; text-decoration: none; }}
        .story-card h3 a:hover {{ color: var(--accent); }}
        .story-card p {{ color: rgba(255,255,255,0.6); font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            Back to All Trends
        </a>

        <header class="page-header">
            <h1>{config['title']}</h1>
            <p>{config['description']}</p>
            <div class="stats">{len(trends)} stories &bull; Updated {datetime.now().strftime('%B %d, %Y')}</div>
        </header>

        <div class="stories-grid">
            {''.join(cards)}
        </div>
    </div>
</body>
</html>'''

    def _step_generate_rss(self):
        """Generate RSS feed."""
        logger.info("[10/14] Generating RSS feed...")

        # Convert trends to dict format
        trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]

        # Generate RSS feed
        output_path = self.public_dir / "feed.xml"
        generate_rss_feed(trends_data, output_path)

        logger.info(f"RSS feed saved to {output_path}")

    def _step_generate_pwa(self):
        """Generate PWA assets (manifest, service worker, offline page)."""
        logger.info("[11/14] Generating PWA assets...")

        save_pwa_assets(self.public_dir)
        logger.info("PWA assets generated")

    def _step_generate_sitemap(self):
        """Generate sitemap.xml and robots.txt with articles and topic pages."""
        logger.info("[12/14] Generating sitemap...")

        # Get all article URLs
        article_urls = []
        articles_dir = self.public_dir / "articles"
        if articles_dir.exists():
            for metadata_file in articles_dir.rglob("metadata.json"):
                try:
                    with open(metadata_file) as f:
                        article = json.load(f)
                        article_urls.append(article.get('url', ''))
                except Exception:
                    pass

        # Get topic page URLs (matching topic_configs in _step_generate_topic_pages)
        topic_urls = ['/tech/', '/world/', '/science/', '/politics/', '/finance/']

        # Generate enhanced sitemap
        save_sitemap(self.public_dir, extra_urls=article_urls + topic_urls)
        logger.info(f"Sitemap generated with {len(article_urls)} articles, {len(topic_urls)} topic pages")

    def _step_cleanup(self):
        """Clean up old archives (NOT articles - those are permanent)."""
        logger.info("[13/14] Cleaning up old archives...")

        removed = self.archive_manager.cleanup_old(keep_days=30)
        logger.info(f"Removed {removed} old archives")

    def _save_data(self):
        """Save pipeline data for debugging/reference."""
        saved_files = []
        errors = []

        # Save trends
        try:
            with open(self.data_dir / "trends.json", "w") as f:
                trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]
                json.dump(trends_data, f, indent=2, default=str)
            saved_files.append("trends.json")
        except (IOError, OSError) as e:
            errors.append(f"trends.json: {e}")

        # Save images
        try:
            with open(self.data_dir / "images.json", "w") as f:
                images_data = [asdict(i) if hasattr(i, '__dataclass_fields__') else i for i in self.images]
                json.dump(images_data, f, indent=2, default=str)
            saved_files.append("images.json")
        except (IOError, OSError) as e:
            errors.append(f"images.json: {e}")

        # Save design
        try:
            with open(self.data_dir / "design.json", "w") as f:
                design_data = asdict(self.design) if hasattr(self.design, '__dataclass_fields__') else self.design
                json.dump(design_data, f, indent=2, default=str)
            saved_files.append("design.json")
        except (IOError, OSError) as e:
            errors.append(f"design.json: {e}")

        # Save keywords
        try:
            with open(self.data_dir / "keywords.json", "w") as f:
                json.dump(self.keywords, f, indent=2, default=str)
            saved_files.append("keywords.json")
        except (IOError, OSError) as e:
            errors.append(f"keywords.json: {e}")

        # Save enriched content
        if self.enriched_content:
            try:
                with open(self.data_dir / "enriched.json", "w") as f:
                    enriched_data = {
                        'word_of_the_day': asdict(self.enriched_content.word_of_the_day) if self.enriched_content.word_of_the_day else None,
                        'grokipedia_article': asdict(self.enriched_content.grokipedia_article) if self.enriched_content.grokipedia_article else None,
                        'story_summaries': [asdict(s) for s in self.enriched_content.story_summaries] if self.enriched_content.story_summaries else []
                    }
                    json.dump(enriched_data, f, indent=2, default=str)
                saved_files.append("enriched.json")
            except (IOError, OSError) as e:
                errors.append(f"enriched.json: {e}")

        if saved_files:
            logger.info(f"Pipeline data saved to {self.data_dir}: {', '.join(saved_files)}")
        if errors:
            for error in errors:
                logger.error(f"Failed to save: {error}")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Generate a trending topics website",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py              # Full pipeline run
    python main.py --no-archive # Skip archiving previous site
    python main.py --dry-run    # Collect data only, don't build

Environment variables:
    GROQ_API_KEY        - Groq API key for AI design generation
    OPENROUTER_API_KEY  - OpenRouter API key (backup AI)
    PEXELS_API_KEY      - Pexels API key for images
    UNSPLASH_ACCESS_KEY - Unsplash API key (backup images)
        """
    )

    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Skip archiving the previous website"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect trends and generate design, but don't build website"
    )

    parser.add_argument(
        "--project-root",
        type=str,
        help="Project root directory (default: parent of scripts/)"
    )

    args = parser.parse_args()

    # Load environment variables from .env if available
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded environment from {env_path}")
    except ImportError:
        pass

    # Run the pipeline
    project_root = Path(args.project_root) if args.project_root else None
    pipeline = Pipeline(project_root=project_root)

    success = pipeline.run(
        archive=not args.no_archive,
        dry_run=args.dry_run
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
