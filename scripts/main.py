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
import time
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional, Set

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
from topic_page_generator import generate_all_topic_pages
from media_page_generator import generate_media_page
from image_utils import (
    validate_image_url,
    sanitize_image_url,
    get_image_quality_score,
    get_fallback_gradient_css,
)
from metrics_collector import MetricsCollector

# Setup logging
logger = setup_logging("pipeline")

Record = Dict[str, Any]


class Pipeline:
    """Orchestrates the complete website generation pipeline."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
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
        self.metrics = MetricsCollector(self.data_dir / "metrics")
        self._run_started_at: Optional[float] = None

        # Pipeline data
        self.trends: List[Any] = []
        self.images: List[Any] = []
        self.design: Any = None
        self.keywords: List[str] = []
        self.global_keywords: List[str] = []
        self.enriched_content: Optional[EnrichedContent] = None
        self.editorial_article: Optional[Any] = None
        self.why_this_matters: List[Any] = []
        self.yesterday_trends: List[Record] = []
        self.media_data: Optional[Record] = None

    def _run_step(
        self, step_name: str, step_fn: Callable[[], None], *, enabled: bool = True
    ) -> None:
        """Run a pipeline step and record timing/success metrics."""
        if not enabled:
            self.metrics.record_step(step_name, 0.0, skipped=True)
            return

        start = time.perf_counter()
        try:
            step_fn()
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_step(
                step_name, duration_ms, success=False, error=str(exc)
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_step(step_name, duration_ms, success=True)

    def _persist_daily_design(self, design: Any) -> None:
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
        warnings: List[str] = []

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
        self.metrics.start_run({"archive": archive, "dry_run": dry_run})
        self.metrics.set_counter("environment_warning_count", len(env_warnings))
        self._run_started_at = time.perf_counter()
        for warning in env_warnings:
            logger.warning(f"Environment: {warning}")

        try:
            # Step 1: Archive previous website
            self._run_step("archive_previous_site", self._step_archive, enabled=archive)

            # Step 2: Load yesterday's trends for comparison
            self._run_step("load_yesterday_trends", self._step_load_yesterday)

            # Step 3: Collect trends
            self._run_step("collect_trends", self._step_collect_trends)

            # Step 4: Fetch images
            self._run_step("fetch_images", self._step_fetch_images)

            # Step 5: Enrich content (Word of Day, Grokipedia, summaries)
            self._run_step("enrich_content", self._step_enrich_content)

            # Step 6: Apply fixed design
            self._run_step("apply_fixed_design", self._step_apply_fixed_design)

            # Step 7: Generate editorial article and Why This Matters
            self._run_step(
                "generate_editorial", self._step_generate_editorial, enabled=not dry_run
            )

            # Step 8: Build website
            self._run_step("build_website", self._step_build_website, enabled=not dry_run)

            # Step 9: Generate topic sub-pages
            self._run_step(
                "generate_topic_pages",
                self._step_generate_topic_pages,
                enabled=not dry_run,
            )

            # Step 9b: Generate CMMC Watch page
            self._run_step(
                "generate_cmmc_page", self._step_generate_cmmc_page, enabled=not dry_run
            )

            # Step 10: Fetch media of the day
            self._run_step("fetch_media_of_day", self._step_fetch_media_of_day)

            # Step 11: Generate media page
            self._run_step(
                "generate_media_page", self._step_generate_media_page, enabled=not dry_run
            )

            # Step 12: Generate RSS feed
            self._run_step("generate_rss", self._step_generate_rss, enabled=not dry_run)

            # Step 13: Generate PWA assets
            self._run_step("generate_pwa", self._step_generate_pwa, enabled=not dry_run)

            # Step 14: Generate sitemap
            self._run_step(
                "generate_sitemap", self._step_generate_sitemap, enabled=not dry_run
            )

            # Step 15: Cleanup old archives (not articles - those are permanent)
            self._run_step(
                "cleanup_archives", self._step_cleanup, enabled=(archive and not dry_run)
            )

            # Step 16: Save pipeline data
            self._run_step("save_pipeline_data", self._save_data)

            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETE")
            logger.info("=" * 60)

            if self._run_started_at is not None:
                total_ms = (time.perf_counter() - self._run_started_at) * 1000
                self.metrics.set_counter("pipeline_duration_ms", round(total_ms, 2))

            metrics_path = self.metrics.finalize(success=True, metadata={"dry_run": dry_run})
            logger.info(f"Metrics report saved to {metrics_path}")

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
            if self._run_started_at is not None:
                total_ms = (time.perf_counter() - self._run_started_at) * 1000
                self.metrics.set_counter("pipeline_duration_ms", round(total_ms, 2))
            metrics_path = self.metrics.finalize(
                success=False,
                error=str(e),
                metadata={"dry_run": dry_run},
            )
            logger.info(f"Metrics report saved to {metrics_path}")
            return False

    def _step_archive(self) -> None:
        """Archive the previous website."""
        logger.info("[1/16] Archiving previous website...")

        # Try to load previous design metadata
        previous_design = None
        design_file = self.data_dir / "design.json"
        if design_file.exists():
            try:
                with open(design_file) as f:
                    previous_design = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load previous design.json: {e}")

        self.archive_manager.archive_current(design=previous_design)

    def _step_load_yesterday(self) -> None:
        """Load yesterday's trends for comparison feature."""
        logger.info("[2/16] Loading yesterday's trends...")

        # Try to load from most recent archive snapshot (each archive dir
        # contains its own trends.json captured at archive time).
        archive_dir = self.public_dir / "archive"
        if archive_dir.exists():
            archives = sorted(
                (a for a in archive_dir.iterdir() if a.is_dir()), reverse=True
            )
            for archive in archives[:3]:  # Check last 3 days
                trends_file = archive / "trends.json"
                if trends_file.exists():
                    try:
                        with open(trends_file) as f:
                            self.yesterday_trends = json.load(f)
                        logger.info(
                            f"Loaded {len(self.yesterday_trends)} trends from {archive.name}"
                        )
                        break
                    except (OSError, json.JSONDecodeError) as e:
                        logger.warning(
                            f"Could not load trends from {archive.name}: {e}"
                        )

        if not self.yesterday_trends:
            logger.info("No previous trends available for comparison")

    def _step_collect_trends(self) -> None:
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

        raw_trend_count = getattr(self.trend_collector, "pre_dedup_count", len(self.trends))
        dedup_rate = 0.0
        if raw_trend_count:
            dedup_rate = max(0.0, 1.0 - (len(self.trends) / float(raw_trend_count)))

        self.metrics.set_counter("trends_collected", len(self.trends))
        self.metrics.set_counter("keywords_extracted", len(self.keywords))
        self.metrics.set_counter("global_keywords_count", len(self.global_keywords))
        self.metrics.set_quality_metric("freshness_ratio", round(freshness_ratio, 4))
        self.metrics.set_quality_metric("deduplication_rate", round(dedup_rate, 4))

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

    def _step_fetch_images(self) -> None:
        """Fetch images based on trending keywords."""
        logger.info("[4/16] Fetching images...")

        search_keywords: List[str] = []

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

        self.metrics.set_counter("image_search_keywords", len(search_keywords))
        self.metrics.set_counter("images_fetched", len(self.images))

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

        def matches_prefix(source: str, prefixes: List[str]) -> bool:
            for prefix in prefixes:
                if prefix.endswith("_"):
                    if source.startswith(prefix):
                        return True
                else:
                    if source == prefix:
                        return True
            return False

        headline_keywords: List[str] = []

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

    def _apply_story_summaries(self, trends: List[Record]) -> None:
        """Attach AI summaries to trend items when available."""
        if not self.enriched_content or not getattr(
            self.enriched_content, "story_summaries", None
        ):
            return

        summary_map: Dict[str, str] = {}
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

    def _step_enrich_content(self) -> None:
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

        self.metrics.set_counter(
            "story_summaries_count", len(self.enriched_content.story_summaries)
        )
        self.metrics.set_counter(
            "has_word_of_day", 1 if self.enriched_content.word_of_the_day else 0
        )
        self.metrics.set_counter(
            "has_grokipedia_article",
            1 if self.enriched_content.grokipedia_article else 0,
        )

    def _step_apply_fixed_design(self) -> None:
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

    def _step_generate_editorial(self) -> None:
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

        self.metrics.set_counter("why_this_matters_count", len(self.why_this_matters))
        self.metrics.set_counter(
            "has_editorial_article", 1 if self.editorial_article else 0
        )

    def _step_build_website(self) -> None:
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
                if isinstance(article, dict):
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
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load keyword_history.json: {e}")

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
        self.metrics.set_counter("homepage_story_count", len(trends_data))

    def _step_generate_topic_pages(self) -> None:
        """Generate topic-specific sub-pages (/tech, /world, /science, etc.)."""
        logger.info("[9/16] Generating topic sub-pages...")
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]
        design_data = (
            asdict(self.design) if hasattr(self.design, "__dataclass_fields__") else self.design
        )
        images_data = [
            asdict(i) if hasattr(i, "__dataclass_fields__") else i for i in self.images
        ]

        self._apply_story_summaries(trends_data)

        pages_created = generate_all_topic_pages(
            public_dir=self.public_dir,
            trends_data=trends_data,
            images_data=images_data,
            design_data=design_data,
        )
        logger.info(f"Generated {pages_created} topic sub-pages")
        self.metrics.set_counter("topic_pages_created", pages_created)

    def _step_generate_cmmc_page(self) -> None:
        """Generate CMMC Watch standalone page."""
        logger.info("[9b] Generating CMMC Watch page...")

        # Convert trends to dict format
        trends_data = [
            asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in self.trends
        ]

        # Check if we have CMMC trends
        cmmc_trends = filter_cmmc_trends(trends_data)
        self.metrics.set_counter("cmmc_trend_count", len(cmmc_trends))
        if not cmmc_trends:
            logger.info("  No CMMC trends found, skipping CMMC page generation")
            self.metrics.set_counter("cmmc_page_generated", 0)
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
            self.metrics.set_counter("cmmc_page_generated", 1)
        else:
            logger.warning("  Failed to generate CMMC page")
            self.metrics.set_counter("cmmc_page_generated", 0)

    def _step_fetch_media_of_day(self) -> None:
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

            self.metrics.set_counter(
                "has_media_image",
                1 if self.media_data.get("image_of_day") else 0,
            )
            self.metrics.set_counter(
                "has_media_video",
                1 if self.media_data.get("video_of_day") else 0,
            )

        except Exception as e:
            logger.warning(f"Media of the Day fetch failed: {e}")
            self.media_data = None
            self.metrics.set_counter("has_media_image", 0)
            self.metrics.set_counter("has_media_video", 0)

    def _step_generate_media_page(self) -> None:
        """Generate the Media of the Day page."""
        logger.info("[11/16] Generating Media of the Day page...")

        if not self.media_data:
            logger.warning("No media data available, skipping media page")
            self.metrics.set_counter("media_page_generated", 0)
            return

        design_data = (
            asdict(self.design) if hasattr(self.design, "__dataclass_fields__") else self.design
        )
        ok = generate_media_page(self.public_dir, self.media_data, design_data)
        self.metrics.set_counter("media_page_generated", 1 if ok else 0)
        if not ok:
            logger.warning("Media page generation failed")

    def _step_generate_rss(self) -> None:
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
        self.metrics.set_counter("rss_items_count", len(trends_data))

        # Generate CMMC Watch RSS feed
        cmmc_output_path = self.public_dir / "cmmc" / "feed.xml"
        cmmc_result = generate_cmmc_rss_feed(trends_data, cmmc_output_path)
        if cmmc_result:
            logger.info(f"CMMC RSS feed saved to {cmmc_output_path}")
            self.metrics.set_counter("cmmc_rss_generated", 1)
        else:
            logger.info("No CMMC trends found, skipping CMMC RSS feed")
            self.metrics.set_counter("cmmc_rss_generated", 0)

    def _step_generate_pwa(self) -> None:
        """Generate PWA assets (manifest, service worker, offline page)."""
        logger.info("[13/16] Generating PWA assets...")

        save_pwa_assets(self.public_dir)
        logger.info("PWA assets generated")

    def _step_generate_sitemap(self) -> None:
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
                except (OSError, json.JSONDecodeError) as e:
                    logger.warning(f"Skipping malformed {metadata_file}: {e}")

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
        self.metrics.set_counter("sitemap_article_urls", len(article_urls))
        self.metrics.set_counter("sitemap_topic_urls", len(topic_urls))

    def _step_cleanup(self) -> None:
        """Clean up old archives (NOT articles - those are permanent)."""
        logger.info("[15/16] Cleaning up old archives...")

        removed = self.archive_manager.cleanup_old(keep_days=30)
        logger.info(f"Removed {removed} old archives")

    def _save_data(self) -> None:
        """Save pipeline data for debugging/reference."""
        saved_files: List[str] = []
        errors: List[str] = []

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

        self.metrics.set_counter("data_files_saved", len(saved_files))
        self.metrics.set_counter("data_save_errors", len(errors))


def main() -> None:
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
