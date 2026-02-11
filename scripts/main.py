#!/usr/bin/env python3
"""
Main Pipeline Orchestrator - Runs the complete trend website generation pipeline.

Pipeline steps:
1. Archive previous website (if exists)
2. Collect trends from multiple sources
3. Fetch images based on trending keywords
4. Apply fixed design specification
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
import re
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from typing import List

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    MIN_TRENDS,
    MIN_FRESH_RATIO,
    setup_logging,
    MAX_IMAGE_KEYWORDS,
    IMAGES_PER_KEYWORD,
)
from collect_trends import TrendCollector
from fetch_images import ImageFetcher
from build_website import WebsiteBuilder, BuildContext
from fixed_design import build_fixed_design
from archive_manager import ArchiveManager
from generate_rss import generate_rss_feed, generate_cmmc_rss_feed
from enrich_content import ContentEnricher, EnrichedContent
from keyword_tracker import KeywordTracker
from pwa_generator import save_pwa_assets
from sitemap_generator import save_sitemap
from editorial_generator import EditorialGenerator
from fetch_media_of_day import MediaOfDayFetcher
from cmmc_page_generator import generate_cmmc_page, filter_cmmc_trends
from shared_components import (
    build_header,
    build_footer,
    get_header_styles,
    get_footer_styles,
    get_theme_script,
)
from image_utils import (
    validate_image_url,
    sanitize_image_url,
    get_image_quality_score,
    get_fallback_gradient_css,
)

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
        self.archive_manager = ArchiveManager(public_dir=str(self.public_dir))
        self.keyword_tracker = KeywordTracker()
        self.content_enricher = ContentEnricher()
        self.editorial_generator = EditorialGenerator(public_dir=self.public_dir)
        self.media_fetcher = MediaOfDayFetcher()

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
        self.media_data = None

    def _persist_daily_design(self, design) -> None:
        """Persist fixed design spec for deterministic rebuilds."""
        design_file = self.data_dir / "design.json"
        design_data = (
            asdict(design) if hasattr(design, "__dataclass_fields__") else design
        )
        with open(design_file, "w") as f:
            json.dump(design_data, f, indent=2)

    def _validate_environment(self) -> List[str]:
        """
        Validate environment configuration and API keys.

        Returns:
            List of warning messages (empty if all OK)
        """
        warnings = []

        # Check image API keys
        pexels_key = os.getenv("PEXELS_API_KEY")
        unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")
        if not pexels_key and not unsplash_key:
            warnings.append(
                "No image API keys configured (PEXELS_API_KEY or UNSPLASH_ACCESS_KEY). "
                "Images will use fallback gradients."
            )

        # Design is now fixed and deterministic, no LLM keys required.

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

            # Step 6: Apply fixed design
            self._step_apply_fixed_design()

            # Step 7: Generate editorial article and Why This Matters
            if not dry_run:
                self._step_generate_editorial()

            # Step 8: Build website
            if not dry_run:
                self._step_build_website()

            # Step 9: Generate topic sub-pages
            if not dry_run:
                self._step_generate_topic_pages()

            # Step 9b: Generate CMMC Watch page
            if not dry_run:
                self._step_generate_cmmc_page()

            # Step 10: Fetch media of the day
            self._step_fetch_media_of_day()

            # Step 11: Generate media page
            if not dry_run:
                self._step_generate_media_page()

            # Step 12: Generate RSS feed
            if not dry_run:
                self._step_generate_rss()

            # Step 13: Generate PWA assets
            if not dry_run:
                self._step_generate_pwa()

            # Step 14: Generate sitemap
            if not dry_run:
                self._step_generate_sitemap()

            # Step 15: Cleanup old archives (not articles - those are permanent)
            if archive and not dry_run:
                self._step_cleanup()

            # Step 16: Save pipeline data
            self._save_data()

            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETE")
            logger.info("=" * 60)

            if not dry_run:
                logger.info(f"Website generated at: {self.public_dir / 'index.html'}")
                logger.info(
                    f"Archive available at: {self.public_dir / 'archive' / 'index.html'}"
                )

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
        logger.info("[1/16] Archiving previous website...")

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
        logger.info("[2/16] Loading yesterday's trends...")

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
                            logger.info(
                                f"Loaded {len(self.yesterday_trends)} trends from previous build"
                            )
                            break
                    except Exception:
                        pass

        if not self.yesterday_trends:
            logger.info("No previous trends available for comparison")

    def _step_collect_trends(self):
        """Collect trends from all sources."""
        logger.info("[3/16] Collecting trends...")

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
        logger.info("[4/16] Fetching images...")

        search_keywords = []

        # Priority 0: Visual queries for the Top Story (Hero Image Fix)
        if self.trends:
            top_story = self.trends[0]
            # Use attribute access for Trend dataclass, not .get()
            top_title = top_story.title
            if top_title:
                logger.info(
                    f"Optimizing visual queries for top story: {top_title[:50]}..."
                )
                visual_queries = self.image_fetcher.optimize_query(top_title)
                if visual_queries:
                    logger.info(f"  Generated visual queries: {visual_queries}")
                    search_keywords.extend(visual_queries)

        # Prioritize global keywords (meta-trends) for image search
        # These are words appearing in 3+ stories, more likely to be relevant

        # Add global keywords first (up to half the slots)
        global_slots = MAX_IMAGE_KEYWORDS // 2
        if self.global_keywords:
            # Filter out duplicates
            new_globals = [
                kw for kw in self.global_keywords if kw not in search_keywords
            ]
            search_keywords.extend(new_globals[:global_slots])
            logger.info(
                f"Using {len(new_globals[:global_slots])} global keywords for images"
            )

        # Extract keywords from top headlines of each topic category
        # This ensures we have images matching topic page hero sections
        headline_keywords = self._extract_headline_keywords_for_images()
        for kw in headline_keywords:
            if kw not in search_keywords and len(search_keywords) < MAX_IMAGE_KEYWORDS:
                search_keywords.append(kw)
        if headline_keywords:
            logger.info(
                f"Added {len(headline_keywords)} headline keywords for topic heroes"
            )

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
                search_keywords, images_per_keyword=IMAGES_PER_KEYWORD
            )
            logger.info(f"Fetched {len(self.images)} images")
        else:
            logger.warning("No keywords for image search, using fallback gradients")

    def _extract_headline_keywords_for_images(self) -> List[str]:
        """Extract significant keywords from top headlines of each topic category.

        This ensures we fetch images that can match topic page hero sections.
        """
        # Topic source prefixes (same as in _step_generate_topic_pages)
        topic_sources = {
            "tech": [
                "hackernews",
                "lobsters",
                "tech_",
                "github_trending",
                "product_hunt",
                "devto",
                "slashdot",
                "ars_",
            ],
            "world": ["news_", "wikipedia", "google_trends"],
            "science": ["science_"],
            "politics": ["politics_"],
            "finance": ["finance_"],
        }

        # Stop words to filter out
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
            "says",
            "said",
            "new",
            "first",
            "after",
            "year",
            "years",
            "now",
            "today's",
            "trends",
            "trending",
            "world",
            "its",
            "it",
            "just",
            "about",
            "over",
            "out",
            "top",
            "all",
            "more",
            "not",
            "your",
            "you",
        }

        def matches_prefix(source: str, prefixes: list) -> bool:
            for prefix in prefixes:
                if prefix.endswith("_"):
                    if source.startswith(prefix):
                        return True
                else:
                    if source == prefix:
                        return True
            return False

        headline_keywords = []

        # Convert trends to dict if needed
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]

        # For each topic, find the top story and extract keywords
        for topic_name, prefixes in topic_sources.items():
            # Find stories for this topic
            topic_stories = [
                t for t in trends_data if matches_prefix(t.get("source", ""), prefixes)
            ]

            if topic_stories:
                top_story = topic_stories[0]
                top_title = top_story.get("title", "")
                top_description = top_story.get("description", "") or ""

                # Extract words from title, preserving case for proper noun detection
                title_words = top_title.split()

                # Prioritize capitalized words (proper nouns, entities) - these are more specific
                proper_nouns = []
                regular_words = []
                for w in title_words:
                    cleaned = w.strip(".,!?()[]{}\":;'")
                    if len(cleaned) > 3 and cleaned.lower() not in stop_words:
                        # Check if it's a proper noun (capitalized, not at start of sentence)
                        if cleaned[0].isupper() and title_words.index(w) > 0:
                            proper_nouns.append(cleaned.lower())
                        else:
                            regular_words.append(cleaned.lower())

                # Combine: proper nouns first (more specific), then regular words
                keywords = proper_nouns + regular_words

                # If title keywords are too generic (less than 2), use description too
                if len(keywords) < 2 and top_description:
                    desc_words = [
                        w.strip(".,!?()[]{}\":;'").lower()
                        for w in top_description.split()
                    ]
                    desc_keywords = [
                        w for w in desc_words if len(w) > 4 and w not in stop_words
                    ]
                    for kw in desc_keywords[:2]:
                        if kw not in keywords:
                            keywords.append(kw)

                # Add top 3 keywords from this headline (increased from 2 for better matching)
                for kw in keywords[:3]:
                    if kw not in headline_keywords:
                        headline_keywords.append(kw)

        return headline_keywords

    def _normalize_title(self, title: str) -> str:
        """Normalize titles for summary matching."""
        if not title:
            return ""
        cleaned = re.sub(r"[^a-z0-9]+", " ", title.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def _apply_story_summaries(self, trends: List[dict]) -> None:
        """Attach AI summaries to trend items when available."""
        if not self.enriched_content or not getattr(
            self.enriched_content, "story_summaries", None
        ):
            return

        summary_map = {}
        for item in self.enriched_content.story_summaries:
            title = getattr(item, "title", None) or item.get("title")
            summary = getattr(item, "summary", None) or item.get("summary")
            if not title or not summary:
                continue
            summary_map[self._normalize_title(title)] = summary.strip()

        if not summary_map:
            return

        for trend in trends:
            title = trend.get("title", "")
            if not title:
                continue
            summary = summary_map.get(self._normalize_title(title))
            if summary:
                trend["summary"] = summary
                if not trend.get("description"):
                    trend["description"] = summary

    def _step_enrich_content(self):
        """Enrich content with Word of Day, Grokipedia article, and story summaries."""
        logger.info("[5/16] Enriching content...")

        # Convert trends to dict format
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]

        # Get enriched content
        self.enriched_content = self.content_enricher.enrich(trends_data, self.keywords)

        # Log results
        if self.enriched_content.word_of_the_day:
            logger.info(
                f"  Word of the Day: {self.enriched_content.word_of_the_day.word}"
            )
        if self.enriched_content.grokipedia_article:
            logger.info(
                f"  Grokipedia Article: {self.enriched_content.grokipedia_article.title}"
            )
        logger.info(f"  Story summaries: {len(self.enriched_content.story_summaries)}")

    def _step_apply_fixed_design(self):
        """Apply fixed design specification (no automatic style variation)."""
        logger.info("[6/16] Applying fixed design...")

        # Convert trends to dict format for deterministic content text generation.
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]

        self.design = build_fixed_design(trends_data, self.keywords)
        self._persist_daily_design(self.design)
        logger.info("Using fixed design profile: Signal Desk")

        if isinstance(self.design, dict):
            logger.info(f"Theme: {self.design.get('theme_name')}")
            logger.info(f"Mood: {self.design.get('mood')}")
            logger.info(f"Headline: {self.design.get('headline')}")
        else:
            logger.info(f"Theme: {self.design.theme_name}")
            logger.info(f"Mood: {self.design.mood}")
            logger.info(f"Headline: {self.design.headline}")

    def _step_generate_editorial(self):
        """Generate editorial article and Why This Matters context."""
        logger.info("[7/16] Generating editorial content...")

        # Convert trends to dict format
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]
        design_data = (
            asdict(self.design)
            if hasattr(self.design, "__dataclass_fields__")
            else self.design
        )

        # Generate editorial article
        self.editorial_article = self.editorial_generator.generate_editorial(
            trends_data, self.keywords, design_data
        )

        if self.editorial_article:
            logger.info(
                f"  Editorial: {self.editorial_article.title} ({self.editorial_article.word_count} words)"
            )
            logger.info(f"  URL: {self.editorial_article.url}")

        # Regenerate HTML for all existing articles (updates header/footer styling)
        regenerated_count = self.editorial_generator.regenerate_all_article_pages(
            design_data
        )
        if regenerated_count > 0:
            logger.info(f"  Regenerated {regenerated_count} existing article pages")

        # Generate Why This Matters for top 3 stories
        self.why_this_matters = self.editorial_generator.generate_why_this_matters(
            trends_data, count=3
        )
        logger.info(f"  Why This Matters: {len(self.why_this_matters)} explanations")

        # Generate articles index page
        self.editorial_generator.generate_articles_index(design_data)
        logger.info("  Articles index updated")

    def _step_build_website(self):
        """Build the final HTML website."""
        logger.info("[8/16] Building website...")
        logger.info(
            f"Building with {len(self.trends)} trends, {len(self.images)} images"
        )

        # Convert data to proper format
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]
        logger.info(f"Converted {len(trends_data)} trends to dict format")

        # Log sample trend for debugging
        if trends_data:
            sample = trends_data[0]
            logger.info(
                f"Sample trend: title='{sample.get('title', '')[:50]}', source='{sample.get('source', '')}'"
            )

        self._apply_story_summaries(trends_data)

        images_data = [
            asdict(i) if hasattr(i, "__dataclass_fields__") else i for i in self.images
        ]
        design_data = (
            asdict(self.design)
            if hasattr(self.design, "__dataclass_fields__")
            else self.design
        )

        # Convert enriched content to dict format
        enriched_data = None
        if self.enriched_content:
            enriched_data = {
                "word_of_the_day": (
                    asdict(self.enriched_content.word_of_the_day)
                    if self.enriched_content.word_of_the_day
                    else None
                ),
                "grokipedia_article": (
                    asdict(self.enriched_content.grokipedia_article)
                    if self.enriched_content.grokipedia_article
                    else None
                ),
                "story_summaries": (
                    [asdict(s) for s in self.enriched_content.story_summaries]
                    if self.enriched_content.story_summaries
                    else []
                ),
            }
            # Log enriched content status
            if enriched_data.get("grokipedia_article"):
                article = enriched_data["grokipedia_article"]
                logger.info(
                    f"Grokipedia article: '{article.get('title', '')}' ({len(article.get('summary', ''))} chars)"
                )

        # Convert why_this_matters to dict format
        why_this_matters_data = None
        if self.why_this_matters:
            why_this_matters_data = [
                asdict(wtm) if hasattr(wtm, "__dataclass_fields__") else wtm
                for wtm in self.why_this_matters
            ]

        # Convert editorial article to dict format
        editorial_data = None
        if self.editorial_article:
            editorial_data = (
                asdict(self.editorial_article)
                if hasattr(self.editorial_article, "__dataclass_fields__")
                else self.editorial_article
            )

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
            keyword_history=keyword_history,
        )

        # Build and save
        builder = WebsiteBuilder(context)
        output_path = self.public_dir / "index.html"
        builder.save(str(output_path))

        logger.info(f"Website saved to {output_path}")

    def _step_generate_topic_pages(self):
        """Generate topic-specific sub-pages (/tech, /world, /science, etc.)."""
        logger.info("[9/16] Generating topic sub-pages...")

        # Convert data to proper format
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]
        design_data = (
            asdict(self.design)
            if hasattr(self.design, "__dataclass_fields__")
            else self.design
        )
        images_data = [
            asdict(i) if hasattr(i, "__dataclass_fields__") else i for i in self.images
        ]

        self._apply_story_summaries(trends_data)

        # Define topic categories and their filters
        # Sources use prefix matching: 'tech_' matches 'tech_verge', 'tech_wired', etc.
        # hero_keywords used to find relevant hero images for each topic
        topic_configs = [
            {
                "slug": "tech",
                "title": "Technology",
                "description": "Latest technology news, startups, and developer trends",
                "source_prefixes": [
                    "hackernews",
                    "lobsters",
                    "tech_",
                    "github_trending",
                    "product_hunt",
                    "devto",
                    "slashdot",
                    "ars_",
                ],
                "hero_keywords": [
                    "technology",
                    "computer",
                    "code",
                    "programming",
                    "software",
                    "digital",
                    "tech",
                    "innovation",
                    "startup",
                ],
                "image_index": 0,  # Fallback index if no keyword match
            },
            {
                "slug": "world",
                "title": "World News",
                "description": "Breaking news and current events from around the world",
                "source_prefixes": ["news_", "wikipedia", "google_trends"],
                "hero_keywords": [
                    "world",
                    "globe",
                    "city",
                    "cityscape",
                    "urban",
                    "international",
                    "news",
                    "global",
                    "earth",
                ],
                "image_index": 1,
            },
            {
                "slug": "science",
                "title": "Science & Health",
                "description": "Latest discoveries in science, technology, medicine, and space",
                "source_prefixes": ["science_"],
                "hero_keywords": [
                    "science",
                    "laboratory",
                    "research",
                    "space",
                    "medical",
                    "health",
                    "biology",
                    "chemistry",
                    "physics",
                ],
                "image_index": 2,
            },
            {
                "slug": "politics",
                "title": "Politics & Policy",
                "description": "Political news, policy analysis, and government updates",
                "source_prefixes": ["politics_"],
                "hero_keywords": [
                    "politics",
                    "government",
                    "capitol",
                    "democracy",
                    "vote",
                    "election",
                    "law",
                    "justice",
                    "congress",
                ],
                "image_index": 3,
            },
            {
                "slug": "finance",
                "title": "Business & Finance",
                "description": "Market news, business trends, and economic analysis",
                "source_prefixes": ["finance_"],
                "hero_keywords": [
                    "finance",
                    "business",
                    "money",
                    "stock",
                    "market",
                    "office",
                    "corporate",
                    "economy",
                    "trading",
                ],
                "image_index": 4,
            },
            {
                "slug": "business",
                "title": "Business",
                "description": "Latest business news, entrepreneurship, and corporate trends",
                "source_prefixes": ["finance_", "business"],
                "hero_keywords": [
                    "business",
                    "entrepreneur",
                    "startup",
                    "corporate",
                    "office",
                    "meeting",
                    "professional",
                    "commerce",
                    "trade",
                ],
                "image_index": 5,
            },
            {
                "slug": "sports",
                "title": "Sports",
                "description": "Latest sports news, scores, and athletic highlights",
                "source_prefixes": ["sports_"],
                "hero_keywords": [
                    "sports",
                    "athlete",
                    "game",
                    "stadium",
                    "competition",
                    "fitness",
                    "team",
                    "basketball",
                    "football",
                ],
                "image_index": 6,
            },
        ]

        def find_topic_image(
            images: list,
            headline: str,
            category_keywords: list,
            fallback_index: int,
            used_image_ids: set,
        ) -> dict:
            """Find an image matching headline content, excluding already-used images.

            Priority:
            1. Match keywords from the actual headline (top story title)
            2. Fall back to generic category keywords
            3. Use fallback index if no matches (cycling through unused images)

            Args:
                images: List of available images
                headline: The headline text to match
                category_keywords: Fallback keywords for the category
                fallback_index: Index for fallback selection
                used_image_ids: Set of image IDs already used (will be modified)

            Returns:
                Best matching image dict, or empty dict if none available
            """
            if not images:
                return {}

            # Filter out already-used images to ensure each topic page gets a unique image
            available_images = [
                img for img in images if img.get("id") not in used_image_ids
            ]
            if not available_images:
                # If all images used, reset and allow reuse (better than no image)
                available_images = images

            # Extract keywords from headline (similar to _find_relevant_hero_image)
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
                "says",
                "said",
                "new",
                "first",
                "after",
                "year",
                "years",
                "now",
                "today's",
                "trends",
                "trending",
                "world",
                "its",
                "it",
                "just",
            }

            headline_lower = headline.lower()
            words = [w.strip(".,!?()[]{}\":;'") for w in headline_lower.split()]
            headline_keywords = [w for w in words if len(w) > 2 and w not in stop_words]

            # Score images - prioritize headline keywords over category keywords
            best_image = None
            best_score = 0

            for img in available_images:
                img_text = f"{img.get('query', '')} {img.get('description', '')} {img.get('alt', '')}".lower()

                # Score based on headline keywords (weighted higher)
                headline_score = sum(2 for kw in headline_keywords if kw in img_text)

                # Add score for category keywords (weighted lower)
                category_score = sum(1 for kw in category_keywords if kw in img_text)

                total_score = headline_score + category_score

                # Prefer larger images
                if img.get("width", 0) >= 1200:
                    total_score += 0.5

                if total_score > best_score:
                    best_score = total_score
                    best_image = img

            # If found a match, use it
            if best_image and best_score > 0:
                if best_image.get("id"):
                    used_image_ids.add(best_image["id"])
                return best_image

            # Otherwise use fallback index (cycling through available images)
            idx = fallback_index % len(available_images)
            selected = available_images[idx]
            if selected.get("id"):
                used_image_ids.add(selected["id"])
            return selected

        def matches_topic(source: str, prefixes: list) -> bool:
            """Check if a source matches any of the topic's prefixes."""
            for prefix in prefixes:
                if prefix.endswith("_"):
                    if source.startswith(prefix):
                        return True
                else:
                    if source == prefix:
                        return True
            return False

        pages_created = 0
        used_image_ids = set()  # Track used images to prevent reuse across topic pages

        for config in topic_configs:
            # Filter trends for this topic using prefix matching
            topic_trends = [
                t
                for t in trends_data
                if matches_topic(t.get("source", ""), config["source_prefixes"])
            ]

            if len(topic_trends) < 3:
                logger.info(
                    f"  Skipping /{config['slug']}/ - only {len(topic_trends)} stories"
                )
                continue

            # Get the top story for hero image matching
            top_story = topic_trends[0] if topic_trends else {}
            top_story_title = top_story.get("title", "")

            # Priority 1: Use article image from RSS feed if available
            article_image_url = top_story.get("image_url")
            if article_image_url:
                # Create hero_image dict from article image
                hero_image = {
                    "url_large": article_image_url,
                    "url_medium": article_image_url,
                    "url_original": article_image_url,
                    "photographer": "Article Image",
                    "source": "article",
                    "alt": top_story_title,
                    "id": f"article_{hash(article_image_url) % 100000}",
                }
                logger.debug(
                    f"  Using article image for {config['slug']}: {article_image_url[:60]}..."
                )
            else:
                # Priority 2: Fall back to stock photo search
                hero_image = find_topic_image(
                    images_data,
                    top_story_title,
                    config.get("hero_keywords", []),
                    config.get("image_index", 0),
                    used_image_ids,
                )

            # Create topic directory
            topic_dir = self.public_dir / config["slug"]
            topic_dir.mkdir(parents=True, exist_ok=True)

            # Build topic page HTML
            html = self._build_topic_page(config, topic_trends, design_data, hero_image)

            # Save
            (topic_dir / "index.html").write_text(html, encoding="utf-8")
            pages_created += 1
            logger.info(
                f"  Created /{config['slug']}/ with {len(topic_trends)} stories"
            )

        logger.info(f"Generated {pages_created} topic sub-pages")

    def _step_generate_cmmc_page(self):
        """Generate CMMC Watch standalone page."""
        logger.info("[9b] Generating CMMC Watch page...")

        # Convert trends to dict format
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]

        # Check if we have CMMC trends
        cmmc_trends = filter_cmmc_trends(trends_data)
        if not cmmc_trends:
            logger.info("  No CMMC trends found, skipping CMMC page generation")
            return

        # Convert design to dict format
        design_data = (
            asdict(self.design)
            if hasattr(self.design, "__dataclass_fields__")
            else self.design or {}
        )

        # Convert images to dict format
        images_data = [
            asdict(img) if hasattr(img, "__dataclass_fields__") else img
            for img in self.images
        ]

        # Generate the page
        result = generate_cmmc_page(
            trends=trends_data,
            images=images_data,
            design=design_data,
            output_dir=self.public_dir,
        )

        if result:
            logger.info(f"  Created /cmmc/ with {len(cmmc_trends)} stories")
        else:
            logger.warning("  Failed to generate CMMC page")

    def _build_topic_page(
        self, config: dict, trends: list, design: dict, hero_image: dict
    ) -> str:
        """Build HTML for a topic sub-page with shared header/footer."""
        from datetime import datetime
        import html as html_module

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

        # Get date info
        now = datetime.now()
        date_str = now.strftime("%B %d, %Y")
        date_iso = now.isoformat()

        # Get hero image URL and alt text (topic-specific image passed in)
        hero_image_url = ""
        hero_image_alt = ""
        if hero_image:
            hero_image_url = hero_image.get(
                "url_large", hero_image.get("url_medium", hero_image.get("url", ""))
            )
            hero_image_alt = hero_image.get(
                "alt", hero_image.get("description", f'{config["title"]} hero image')
            )

        # Get featured story info (handle None values safely)
        featured_story = trends[0] if trends else {}
        featured_title = html_module.escape((featured_story.get("title") or "")[:100])
        featured_url = html_module.escape(featured_story.get("url") or "#")
        featured_source = html_module.escape(
            (featured_story.get("source") or "").replace("_", " ").title()
        )
        featured_desc = html_module.escape(
            (featured_story.get("summary") or featured_story.get("description") or "")[
                :200
            ]
        )

        # Placeholder image URL (gradient fallback from homepage)
        placeholder_url = "/assets/nano-banana.png"

        # Build story cards with enhanced design (skip first since it's in hero)
        cards = []
        for i, t in enumerate(trends[1:20]):  # Start from index 1, skip featured
            title = html_module.escape((t.get("title") or "")[:100])
            url = html_module.escape(t.get("url") or "#")
            source = html_module.escape(
                (t.get("source") or "").replace("_", " ").title()
            )
            raw_image_url = t.get("image_url") or ""

            # Validate and sanitize the image URL for reliability
            is_valid, validated_url = validate_image_url(raw_image_url)

            # Always show an image - use placeholder if no valid image available
            if is_valid and validated_url:
                img_src = html_module.escape(validated_url)
                img_class = "story-image"
                img_alt = title
                # Add data attribute for quality score (helps with debugging)
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

        /* Density settings */
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

        /* View list mode */
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

        /* Hero Header with Featured Story */
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

        /* Darkened scaled version behind for full coverage */
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

        /* Main Content */
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

        /* Loading state - shimmer effect */
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

        /* Loaded state */
        .story-image[loaded] {{
            opacity: 1;
        }}

        .story-image.placeholder {{
            opacity: 0.85;
            filter: grayscale(0.1);
        }}

        /* Fallback indicator (subtle) */
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

        /* Responsive - Mobile (1 column) */
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

        /* Responsive - Tablet (2 columns) */
        @media (min-width: 641px) and (max-width: 1024px) {{
            .stories-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .topic-hero {{
                min-height: 400px;
            }}
        }}

        /* Responsive - Small Desktop (3 columns) */
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
            const LOAD_TIMEOUT_MS = 8000; // 8 second timeout for slow images

            const markBroken = (img, reason = 'error') => {{
                if (!placeholderImage) return;
                if (img.dataset.fallbackApplied) return;
                img.dataset.fallbackApplied = 'true';
                img.dataset.fallbackReason = reason;
                img.src = placeholderImage;
                img.classList.add('placeholder');
                img.title = 'Image unavailable';
                // Add visual indicator class for styling
                img.parentElement?.classList.add('image-fallback');
            }};

            const bindErrors = () => {{
                document.querySelectorAll('.story-image').forEach((img) => {{
                    if (img.dataset.boundError) return;
                    img.dataset.boundError = 'true';

                    // Skip if already a placeholder
                    if (img.dataset.isPlaceholder === 'true') {{
                        img.setAttribute('loaded', '');
                        return;
                    }}

                    // Set up timeout for slow-loading images
                    let loadTimeout;
                    const startTimeout = () => {{
                        loadTimeout = setTimeout(() => {{
                            if (!img.complete || img.naturalWidth === 0) {{
                                markBroken(img, 'timeout');
                            }}
                        }}, LOAD_TIMEOUT_MS);
                    }};

                    // Handle successful image load
                    img.addEventListener('load', () => {{
                        clearTimeout(loadTimeout);
                        if (img.naturalWidth > 0) {{
                            img.setAttribute('loaded', '');
                            img.parentElement?.classList.add('image-loaded');
                        }} else {{
                            markBroken(img, 'zero-size');
                        }}
                    }});

                    // Handle image error
                    img.addEventListener('error', () => {{
                        clearTimeout(loadTimeout);
                        markBroken(img, 'error');
                    }});

                    // Handle already-loaded images
                    if (img.complete) {{
                        if (img.naturalWidth === 0) {{
                            markBroken(img, 'already-broken');
                        }} else {{
                            img.setAttribute('loaded', '');
                            img.parentElement?.classList.add('image-loaded');
                        }}
                    }} else {{
                        // Start timeout for images still loading
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

    def _step_fetch_media_of_day(self):
        """Fetch image and video of the day from curated sources."""
        logger.info("[10/16] Fetching Media of the Day...")

        try:
            self.media_data = self.media_fetcher.fetch_all()

            if self.media_data.get("image_of_day"):
                logger.info(f"  Image: {self.media_data['image_of_day']['title']}")
            else:
                logger.warning("  No Image of the Day available")

            if self.media_data.get("video_of_day"):
                logger.info(f"  Video: {self.media_data['video_of_day']['title']}")
            else:
                logger.warning("  No Video of the Day available")

        except Exception as e:
            logger.warning(f"Media of the Day fetch failed: {e}")
            self.media_data = None

    def _step_generate_media_page(self):
        """Generate the Media of the Day page."""
        logger.info("[11/16] Generating Media of the Day page...")

        if not self.media_data:
            logger.warning("No media data available, skipping media page")
            return

        # Get design data for styling
        design_data = (
            asdict(self.design)
            if hasattr(self.design, "__dataclass_fields__")
            else self.design
        )

        # Create media directory
        media_dir = self.public_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        # Build media page HTML
        html = self._build_media_page(self.media_data, design_data)

        # Save
        (media_dir / "index.html").write_text(html, encoding="utf-8")
        logger.info(f"Media page saved to {media_dir / 'index.html'}")

    def _build_media_page(self, media_data: dict, design: dict) -> str:
        """Build HTML for the Media of the Day page."""
        from datetime import datetime
        import html as html_module

        now = datetime.now()
        date_str = now.strftime("%B %d, %Y")
        date_iso = now.isoformat()

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
        transition = design.get("transition_speed", "200ms")
        base_mode = "dark-mode" if design.get("is_dark_mode", True) else "light-mode"

        # Helper to ensure value is a string before escaping
        def safe_str(val, default=""):
            if val is None:
                return default
            if isinstance(val, list):
                return val[0] if val else default
            return str(val)

        # Get image data
        image = media_data.get("image_of_day") or {}
        image_title = html_module.escape(
            safe_str(image.get("title"), "Image of the Day")
        )
        image_url = html_module.escape(safe_str(image.get("url")))
        image_hd_url = html_module.escape(safe_str(image.get("url_hd")))
        image_explanation = html_module.escape(safe_str(image.get("explanation")))
        image_source = safe_str(image.get("source"))
        image_source_url = html_module.escape(safe_str(image.get("source_url")))
        image_copyright = html_module.escape(safe_str(image.get("copyright")))
        image_date = safe_str(image.get("date"))

        # Get video data
        video = media_data.get("video_of_day") or {}
        video_title = html_module.escape(
            safe_str(video.get("title"), "Video of the Day")
        )
        video_description = html_module.escape(safe_str(video.get("description")))
        video_embed_url = html_module.escape(safe_str(video.get("embed_url")))
        video_url = html_module.escape(safe_str(video.get("video_url")))
        video_thumbnail = html_module.escape(safe_str(video.get("thumbnail_url")))
        video_author = html_module.escape(safe_str(video.get("author")))
        video_author_url = html_module.escape(safe_str(video.get("author_url")))
        video_duration = safe_str(video.get("duration"))

        # Source display names
        source_names = {
            "nasa_apod": "NASA Astronomy Picture of the Day",
            "bing": "Bing Image of the Day",
            "vimeo_staff_picks": "Vimeo Staff Picks",
        }

        image_source_name = source_names.get(image_source, image_source)
        video_source_name = source_names.get(
            video.get("source", ""), "Vimeo Staff Picks"
        )

        # Build conditional HTML parts to avoid nested f-string issues
        copyright_html = ""
        if image_copyright:
            copyright_html = f"""<span class="meta-item">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"/>
                                <path d="M14.31 8l5.74 9.94M9.69 8h11.48M7.38 12l5.74-9.94M9.69 16L3.95 6.06M14.31 16H2.83M16.62 12l-5.74 9.94"/>
                            </svg>
                            © {image_copyright}
                        </span>"""

        hd_link_html = ""
        if image_hd_url:
            hd_link_html = f"""<a href="{image_hd_url}" target="_blank" rel="noopener" class="action-btn secondary">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            HD Version
                        </a>"""

        author_html = ""
        if video_author:
            author_initial = video_author[0].upper() if video_author else "V"
            author_html = f"""<div class="author-info">
                        <div class="author-avatar">{author_initial}</div>
                        <div>
                            <span class="author-name">{video_author}</span>
                        </div>
                    </div>"""

        # Build image section HTML
        explanation_truncated = (
            image_explanation[:800] + "..."
            if len(image_explanation) > 800
            else image_explanation
        )
        image_source_short = (
            image_source_name.split()[0] if image_source_name else "Source"
        )
        if image:
            image_section = f"""<section class="media-section">
            <div class="section-header">
                <h2 class="section-title">
                    <span class="section-icon">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                            <circle cx="8.5" cy="8.5" r="1.5"/>
                            <polyline points="21 15 16 10 5 21"/>
                        </svg>
                    </span>
                    Image of the Day
                </h2>
                <a href="{image_source_url}" target="_blank" rel="noopener" class="source-link">
                    {image_source_name}
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                        <polyline points="15 3 21 3 21 9"/>
                        <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                </a>
            </div>
            <div class="image-container">
                <img src="{image_url}" alt="{image_title}" class="featured-image" loading="lazy">
                <div class="image-info">
                    <h3 class="media-title">{image_title}</h3>
                    <p class="media-description">{explanation_truncated}</p>
                    <div class="media-meta">
                        <span class="meta-item">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                                <line x1="16" y1="2" x2="16" y2="6"/>
                                <line x1="8" y1="2" x2="8" y2="6"/>
                                <line x1="3" y1="10" x2="21" y2="10"/>
                            </svg>
                            {image_date}
                        </span>
                        {copyright_html}
                    </div>
                    <div class="image-actions">
                        <a href="{image_source_url}" target="_blank" rel="noopener" class="action-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                                <polyline points="15 3 21 3 21 9"/>
                                <line x1="10" y1="14" x2="21" y2="3"/>
                            </svg>
                            View on {image_source_short}
                        </a>
                        {hd_link_html}
                    </div>
                </div>
            </div>
        </section>"""
        else:
            image_section = '<p style="color: var(--color-muted); text-align: center; padding: 2rem;">Image of the Day is temporarily unavailable.</p>'

        # Build video section HTML
        description_truncated = (
            video_description[:500] + "..."
            if len(video_description) > 500
            else video_description
        )
        if video:
            video_section = f"""<section class="media-section">
            <div class="section-header">
                <h2 class="section-title">
                    <span class="section-icon">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2">
                            <polygon points="5 3 19 12 5 21 5 3"/>
                        </svg>
                    </span>
                    Video of the Day
                </h2>
                <a href="https://vimeo.com/channels/staffpicks" target="_blank" rel="noopener" class="source-link">
                    {video_source_name}
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                        <polyline points="15 3 21 3 21 9"/>
                        <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                </a>
            </div>
            <div class="video-container">
                <div class="video-embed">
                    <iframe src="{video_embed_url}?title=0&byline=0&portrait=0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>
                </div>
                <div class="video-info">
                    <h3 class="media-title">{video_title}</h3>
                    <p class="media-description">{description_truncated}</p>
                    {author_html}
                    <div class="image-actions">
                        <a href="{video_url}" target="_blank" rel="noopener" class="action-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                                <polyline points="15 3 21 3 21 9"/>
                                <line x1="10" y1="14" x2="21" y2="3"/>
                            </svg>
                            Watch on Vimeo
                        </a>
                    </div>
                </div>
            </div>
        </section>"""
        else:
            video_section = '<p style="color: var(--color-muted); text-align: center; padding: 2rem;">Video of the Day is temporarily unavailable.</p>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Media of the Day | DailyTrending.info</title>
    <meta name="description" content="Daily curated image and video content - featuring NASA's Astronomy Picture of the Day and Vimeo Staff Picks.">
    <link rel="canonical" href="https://dailytrending.info/media/">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">

    <meta property="og:title" content="Media of the Day | DailyTrending.info">
    <meta property="og:description" content="Daily curated image and video content">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://dailytrending.info/media/">
    {f'<meta property="og:image" content="{image_url}">' if image_url else ''}

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Media of the Day | DailyTrending.info">
    <meta name="twitter:description" content="Daily curated image and video content">

    <!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2196222970720414"
         crossorigin="anonymous"></script>

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

        /* Density settings */
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

        /* View list mode */
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

        /* Page Header */
        .page-header {{
            text-align: center;
            padding: 4rem 2rem 3rem;
            border-bottom: 1px solid var(--color-border);
        }}

        .page-title {{
            font-family: var(--font-primary);
            font-size: clamp(2rem, 5vw, 3.5rem);
            font-weight: 700;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .page-subtitle {{
            font-size: 1.1rem;
            color: var(--color-muted);
            max-width: 600px;
            margin: 0 auto;
        }}

        /* Main Content */
        .main-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 3rem 2rem;
        }}

        /* Media Sections */
        .media-section {{
            margin-bottom: 4rem;
        }}

        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--color-border);
        }}

        .section-title {{
            font-family: var(--font-primary);
            font-size: 1.5rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .section-icon {{
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--color-accent);
            border-radius: 8px;
        }}

        .source-link {{
            font-size: 0.85rem;
            color: var(--color-accent);
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: color var(--transition);
        }}

        .source-link:hover {{
            color: var(--color-accent-secondary);
        }}

        /* Image of the Day */
        .image-container {{
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            overflow: hidden;
        }}

        .featured-image {{
            width: 100%;
            max-height: 70vh;
            object-fit: contain;
            background: #000;
            display: block;
        }}

        .image-info {{
            padding: 1.5rem;
        }}

        .media-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }}

        .media-description {{
            color: var(--color-muted);
            font-size: 0.95rem;
            line-height: 1.7;
            margin-bottom: 1rem;
        }}

        .media-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            font-size: 0.85rem;
            color: var(--color-muted);
        }}

        .meta-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .image-actions {{
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
        }}

        .action-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.25rem;
            background: var(--color-accent);
            color: #000;
            font-weight: 600;
            border-radius: var(--radius);
            text-decoration: none;
            transition: transform var(--transition), box-shadow var(--transition);
        }}

        .action-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }}

        .action-btn.secondary {{
            background: var(--color-card-bg);
            color: var(--color-text);
            border: 1px solid var(--color-border);
        }}

        /* Video of the Day */
        .video-container {{
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            overflow: hidden;
        }}

        .video-embed {{
            position: relative;
            padding-bottom: 56.25%;
            height: 0;
            overflow: hidden;
        }}

        .video-embed iframe {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: none;
        }}

        .video-info {{
            padding: 1.5rem;
        }}

        .author-info {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-top: 0.75rem;
        }}

        .author-avatar {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--color-accent);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
        }}

        .author-name {{
            color: var(--color-text);
            text-decoration: none;
            font-weight: 500;
        }}

        .author-name:hover {{
            color: var(--color-accent);
        }}

        /* About Section */
        .about-section {{
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            padding: 2rem;
            margin-top: 3rem;
        }}

        .about-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }}

        .about-text {{
            color: var(--color-muted);
            line-height: 1.7;
        }}

        .about-text a {{
            color: var(--color-accent);
            text-decoration: none;
        }}

        .about-text a:hover {{
            text-decoration: underline;
        }}

        .source-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-top: 1.5rem;
        }}

        .source-card {{
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--color-border);
            border-radius: 0.75rem;
            padding: 1.25rem;
        }}

        .source-card h4 {{
            font-size: 1rem;
            margin-bottom: 0.5rem;
        }}

        .source-card p {{
            font-size: 0.85rem;
            color: var(--color-muted);
        }}

        {get_footer_styles()}

        /* Mobile responsive */
        @media (max-width: 768px) {{
            .page-header {{
                padding: 3rem 1rem 2rem;
            }}

            .main-content {{
                padding: 2rem 1rem;
            }}

            .section-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 0.75rem;
            }}

            .image-actions {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body class="{base_mode}">
    {build_header('media', date_str)}

    <header class="page-header">
        <h1 class="page-title">Media of the Day</h1>
        <p class="page-subtitle">Curated daily content featuring stunning space imagery from NASA and award-winning short films from Vimeo's finest creators.</p>
    </header>

    <main class="main-content">
        <!-- Image of the Day Section -->
        {image_section}

        <!-- Video of the Day Section -->
        {video_section}

        <!-- About Section -->
        <div class="about-section">
            <h3 class="about-title">About Media of the Day</h3>
            <p class="about-text">
                Every day, we curate the best visual content from trusted sources across the web.
                Our selections feature stunning space imagery and thought-provoking short films
                that inspire curiosity and creativity.
            </p>
            <div class="source-list">
                <div class="source-card">
                    <h4>🚀 NASA APOD</h4>
                    <p>The Astronomy Picture of the Day features a different image or photograph of our universe each day, along with a brief explanation by a professional astronomer.</p>
                </div>
                <div class="source-card">
                    <h4>🎬 Vimeo Staff Picks</h4>
                    <p>Hand-picked by Vimeo's curation team, Staff Picks showcase the best short films, documentaries, and creative videos from filmmakers around the world.</p>
                </div>
            </div>
        </div>
    </main>

    {build_footer(date_str)}

    {get_theme_script()}
</body>
</html>"""

    def _step_generate_rss(self):
        """Generate RSS feed."""
        logger.info("[12/16] Generating RSS feed...")

        # Convert trends to dict format
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]

        # Generate main RSS feed
        output_path = self.public_dir / "feed.xml"
        generate_rss_feed(trends_data, output_path)
        logger.info(f"RSS feed saved to {output_path}")

        # Generate CMMC Watch RSS feed
        cmmc_output_path = self.public_dir / "cmmc" / "feed.xml"
        cmmc_result = generate_cmmc_rss_feed(trends_data, cmmc_output_path)
        if cmmc_result:
            logger.info(f"CMMC RSS feed saved to {cmmc_output_path}")
        else:
            logger.info("No CMMC trends found, skipping CMMC RSS feed")

    def _step_generate_pwa(self):
        """Generate PWA assets (manifest, service worker, offline page)."""
        logger.info("[13/16] Generating PWA assets...")

        save_pwa_assets(self.public_dir)
        logger.info("PWA assets generated")

    def _step_generate_sitemap(self):
        """Generate sitemap.xml and robots.txt with articles and topic pages."""
        logger.info("[14/16] Generating sitemap...")

        # Get all article URLs
        article_urls = []
        articles_dir = self.public_dir / "articles"
        if articles_dir.exists():
            for metadata_file in articles_dir.rglob("metadata.json"):
                try:
                    with open(metadata_file) as f:
                        article = json.load(f)
                        article_urls.append(article.get("url", ""))
                except Exception:
                    pass

        # Get topic page URLs (matching topic_configs in _step_generate_topic_pages)
        topic_urls = [
            "/tech/",
            "/world/",
            "/science/",
            "/politics/",
            "/finance/",
            "/business/",
            "/sports/",
        ]

        # Generate enhanced sitemap
        save_sitemap(self.public_dir, extra_urls=article_urls + topic_urls)
        logger.info(
            f"Sitemap generated with {len(article_urls)} articles, {len(topic_urls)} topic pages"
        )

    def _step_cleanup(self):
        """Clean up old archives (NOT articles - those are permanent)."""
        logger.info("[15/16] Cleaning up old archives...")

        removed = self.archive_manager.cleanup_old(keep_days=30)
        logger.info(f"Removed {removed} old archives")

    def _save_data(self):
        """Save pipeline data for debugging/reference."""
        saved_files = []
        errors = []

        # Save trends
        try:
            with open(self.data_dir / "trends.json", "w") as f:
                trends_data = [
                    asdict(t) if hasattr(t, "__dataclass_fields__") else t
                    for t in self.trends
                ]
                json.dump(trends_data, f, indent=2, default=str)
            saved_files.append("trends.json")
        except (IOError, OSError) as e:
            errors.append(f"trends.json: {e}")

        # Save images
        try:
            with open(self.data_dir / "images.json", "w") as f:
                images_data = [
                    asdict(i) if hasattr(i, "__dataclass_fields__") else i
                    for i in self.images
                ]
                json.dump(images_data, f, indent=2, default=str)
            saved_files.append("images.json")
        except (IOError, OSError) as e:
            errors.append(f"images.json: {e}")

        # Save design
        try:
            with open(self.data_dir / "design.json", "w") as f:
                design_data = (
                    asdict(self.design)
                    if hasattr(self.design, "__dataclass_fields__")
                    else self.design
                )
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
                        "word_of_the_day": (
                            asdict(self.enriched_content.word_of_the_day)
                            if self.enriched_content.word_of_the_day
                            else None
                        ),
                        "grokipedia_article": (
                            asdict(self.enriched_content.grokipedia_article)
                            if self.enriched_content.grokipedia_article
                            else None
                        ),
                        "story_summaries": (
                            [asdict(s) for s in self.enriched_content.story_summaries]
                            if self.enriched_content.story_summaries
                            else []
                        ),
                    }
                    json.dump(enriched_data, f, indent=2, default=str)
                saved_files.append("enriched.json")
            except (IOError, OSError) as e:
                errors.append(f"enriched.json: {e}")

        if saved_files:
            logger.info(
                f"Pipeline data saved to {self.data_dir}: {', '.join(saved_files)}"
            )
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
    GROQ_API_KEY        - Groq API key for enrichment/editorial generation
    OPENROUTER_API_KEY  - OpenRouter API key (backup LLM provider)
    PEXELS_API_KEY      - Pexels API key for images
    UNSPLASH_ACCESS_KEY - Unsplash API key (backup images)
        """,
    )

    parser.add_argument(
        "--no-archive", action="store_true", help="Skip archiving the previous website"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect trends and apply fixed design, but don't build website",
    )

    parser.add_argument(
        "--project-root",
        type=str,
        help="Project root directory (default: parent of scripts/)",
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

    success = pipeline.run(archive=not args.no_archive, dry_run=args.dry_run)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
