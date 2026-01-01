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

        # Pipeline data
        self.trends = []
        self.images = []
        self.design = None
        self.keywords = []
        self.global_keywords = []
        self.enriched_content = None

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
        groq_key = os.getenv('GROQ_API_KEY')
        openrouter_key = os.getenv('OPENROUTER_API_KEY')
        if not groq_key and not openrouter_key:
            warnings.append(
                "No AI API keys configured (GROQ_API_KEY or OPENROUTER_API_KEY). "
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

            # Step 2: Collect trends
            self._step_collect_trends()

            # Step 3: Fetch images
            self._step_fetch_images()

            # Step 4: Enrich content (Word of Day, Grokipedia, summaries)
            self._step_enrich_content()

            # Step 5: Generate design
            self._step_generate_design()

            # Step 6: Build website
            if not dry_run:
                self._step_build_website()

            # Step 7: Generate RSS feed
            if not dry_run:
                self._step_generate_rss()

            # Step 8: Cleanup old archives
            if archive and not dry_run:
                self._step_cleanup()

            # Step 9: Save pipeline data
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
        logger.info("[1/9] Archiving previous website...")

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

    def _step_collect_trends(self):
        """Collect trends from all sources."""
        logger.info("[2/9] Collecting trends...")

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
        logger.info("[3/9] Fetching images...")

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
        logger.info("[4/9] Enriching content...")

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
        logger.info("[5/9] Generating design...")

        # Convert trends to dict format for the generator
        trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]

        self.design = self.design_generator.generate(trends_data, self.keywords)

        logger.info(f"Theme: {self.design.theme_name}")
        logger.info(f"Mood: {self.design.mood}")
        logger.info(f"Headline: {self.design.headline}")

    def _step_build_website(self):
        """Build the final HTML website."""
        logger.info("[6/9] Building website...")
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

        # Build context
        context = BuildContext(
            trends=trends_data,
            images=images_data,
            design=design_data,
            keywords=self.keywords,
            enriched_content=enriched_data
        )

        # Build and save
        builder = WebsiteBuilder(context)
        output_path = self.public_dir / "index.html"
        builder.save(str(output_path))

        logger.info(f"Website saved to {output_path}")

    def _step_generate_rss(self):
        """Generate RSS feed."""
        logger.info("[7/9] Generating RSS feed...")

        # Convert trends to dict format
        trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]

        # Generate RSS feed
        output_path = self.public_dir / "feed.xml"
        generate_rss_feed(trends_data, output_path)

        logger.info(f"RSS feed saved to {output_path}")

    def _step_cleanup(self):
        """Clean up old archives."""
        logger.info("[8/9] Cleaning up old archives...")

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
