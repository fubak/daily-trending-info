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

        # Extract keywords from top headlines of each topic category
        # This ensures we have images matching topic page hero sections
        headline_keywords = self._extract_headline_keywords_for_images()
        for kw in headline_keywords:
            if kw not in search_keywords and len(search_keywords) < MAX_IMAGE_KEYWORDS:
                search_keywords.append(kw)
        if headline_keywords:
            logger.info(f"Added {len(headline_keywords)} headline keywords for topic heroes")

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

    def _extract_headline_keywords_for_images(self) -> List[str]:
        """Extract significant keywords from top headlines of each topic category.

        This ensures we fetch images that can match topic page hero sections.
        """
        # Topic source prefixes (same as in _step_generate_topic_pages)
        topic_sources = {
            'tech': ['hackernews', 'lobsters', 'tech_', 'github_trending', 'product_hunt', 'devto', 'slashdot', 'ars_'],
            'world': ['news_', 'wikipedia', 'google_trends'],
            'science': ['science_'],
            'politics': ['politics_'],
            'finance': ['finance_'],
        }

        # Stop words to filter out
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                      'should', 'may', 'might', 'must', 'shall', 'can', 'of', 'in', 'to',
                      'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
                      'and', 'or', 'but', 'if', 'then', 'than', 'so', 'that', 'this',
                      'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
                      'says', 'said', 'new', 'first', 'after', 'year', 'years', 'now',
                      "today's", 'trends', 'trending', 'world', 'its', 'it', 'just',
                      'about', 'over', 'out', 'top', 'all', 'more', 'not', 'your', 'you'}

        def matches_prefix(source: str, prefixes: list) -> bool:
            for prefix in prefixes:
                if prefix.endswith('_'):
                    if source.startswith(prefix):
                        return True
                else:
                    if source == prefix:
                        return True
            return False

        headline_keywords = []

        # Convert trends to dict if needed
        trends_data = [asdict(t) if hasattr(t, '__dataclass_fields__') else t for t in self.trends]

        # For each topic, find the top story and extract keywords
        for topic_name, prefixes in topic_sources.items():
            # Find stories for this topic
            topic_stories = [t for t in trends_data if matches_prefix(t.get('source', ''), prefixes)]

            if topic_stories:
                top_story = topic_stories[0]
                top_title = top_story.get('title', '')
                top_description = top_story.get('description', '') or ''

                # Extract words from title, preserving case for proper noun detection
                title_words = top_title.split()

                # Prioritize capitalized words (proper nouns, entities) - these are more specific
                proper_nouns = []
                regular_words = []
                for w in title_words:
                    cleaned = w.strip('.,!?()[]{}":;\'')
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
                    desc_words = [w.strip('.,!?()[]{}":;\'').lower() for w in top_description.split()]
                    desc_keywords = [w for w in desc_words if len(w) > 4 and w not in stop_words]
                    for kw in desc_keywords[:2]:
                        if kw not in keywords:
                            keywords.append(kw)

                # Add top 3 keywords from this headline (increased from 2 for better matching)
                for kw in keywords[:3]:
                    if kw not in headline_keywords:
                        headline_keywords.append(kw)

        return headline_keywords

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
        # hero_keywords used to find relevant hero images for each topic
        topic_configs = [
            {
                'slug': 'tech',
                'title': 'Technology',
                'description': 'Latest technology news, startups, and developer trends',
                'source_prefixes': ['hackernews', 'lobsters', 'tech_', 'github_trending', 'product_hunt', 'devto', 'slashdot', 'ars_'],
                'hero_keywords': ['technology', 'computer', 'code', 'programming', 'software', 'digital', 'tech', 'innovation', 'startup'],
                'image_index': 0  # Fallback index if no keyword match
            },
            {
                'slug': 'world',
                'title': 'World News',
                'description': 'Breaking news and current events from around the world',
                'source_prefixes': ['news_', 'wikipedia', 'google_trends'],
                'hero_keywords': ['world', 'globe', 'city', 'cityscape', 'urban', 'international', 'news', 'global', 'earth'],
                'image_index': 1
            },
            {
                'slug': 'science',
                'title': 'Science & Health',
                'description': 'Latest discoveries in science, technology, medicine, and space',
                'source_prefixes': ['science_'],
                'hero_keywords': ['science', 'laboratory', 'research', 'space', 'medical', 'health', 'biology', 'chemistry', 'physics'],
                'image_index': 2
            },
            {
                'slug': 'politics',
                'title': 'Politics & Policy',
                'description': 'Political news, policy analysis, and government updates',
                'source_prefixes': ['politics_'],
                'hero_keywords': ['politics', 'government', 'capitol', 'democracy', 'vote', 'election', 'law', 'justice', 'congress'],
                'image_index': 3
            },
            {
                'slug': 'finance',
                'title': 'Business & Finance',
                'description': 'Market news, business trends, and economic analysis',
                'source_prefixes': ['finance_'],
                'hero_keywords': ['finance', 'business', 'money', 'stock', 'market', 'office', 'corporate', 'economy', 'trading'],
                'image_index': 4
            }
        ]

        def find_topic_image(images: list, headline: str, category_keywords: list,
                             fallback_index: int, used_image_ids: set) -> dict:
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
            available_images = [img for img in images if img.get('id') not in used_image_ids]
            if not available_images:
                # If all images used, reset and allow reuse (better than no image)
                available_images = images

            # Extract keywords from headline (similar to _find_relevant_hero_image)
            stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                          'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                          'should', 'may', 'might', 'must', 'shall', 'can', 'of', 'in', 'to',
                          'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
                          'and', 'or', 'but', 'if', 'then', 'than', 'so', 'that', 'this',
                          'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
                          'says', 'said', 'new', 'first', 'after', 'year', 'years', 'now',
                          "today's", 'trends', 'trending', 'world', 'its', 'it', 'just'}

            headline_lower = headline.lower()
            words = [w.strip('.,!?()[]{}":;\'') for w in headline_lower.split()]
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
                if img.get('width', 0) >= 1200:
                    total_score += 0.5

                if total_score > best_score:
                    best_score = total_score
                    best_image = img

            # If found a match, use it
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
        used_image_ids = set()  # Track used images to prevent reuse across topic pages

        for config in topic_configs:
            # Filter trends for this topic using prefix matching
            topic_trends = [
                t for t in trends_data
                if matches_topic(t.get('source', ''), config['source_prefixes'])
            ]

            if len(topic_trends) < 3:
                logger.info(f"  Skipping /{config['slug']}/ - only {len(topic_trends)} stories")
                continue

            # Get the top story for hero image matching
            top_story = topic_trends[0] if topic_trends else {}
            top_story_title = top_story.get('title', '')

            # Priority 1: Use article image from RSS feed if available
            article_image_url = top_story.get('image_url')
            if article_image_url:
                # Create hero_image dict from article image
                hero_image = {
                    'url_large': article_image_url,
                    'url_medium': article_image_url,
                    'url_original': article_image_url,
                    'photographer': 'Article Image',
                    'source': 'article',
                    'alt': top_story_title,
                    'id': f"article_{hash(article_image_url) % 100000}"
                }
                logger.debug(f"  Using article image for {config['slug']}: {article_image_url[:60]}...")
            else:
                # Priority 2: Fall back to stock photo search
                hero_image = find_topic_image(
                    images_data,
                    top_story_title,
                    config.get('hero_keywords', []),
                    config.get('image_index', 0),
                    used_image_ids
                )

            # Create topic directory
            topic_dir = self.public_dir / config['slug']
            topic_dir.mkdir(parents=True, exist_ok=True)

            # Build topic page HTML
            html = self._build_topic_page(
                config, topic_trends, design_data, hero_image
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
        hero_image: dict
    ) -> str:
        """Build HTML for a topic sub-page with shared header/footer."""
        from datetime import datetime
        import html as html_module

        # Topic-specific color schemes for unique designs
        topic_colors = {
            'tech': {'accent': '#00d4ff', 'accent_secondary': '#7c3aed', 'gradient': 'linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%)'},
            'world': {'accent': '#ef4444', 'accent_secondary': '#f97316', 'gradient': 'linear-gradient(135deg, #1a0a0a 0%, #2d1f1f 100%)'},
            'science': {'accent': '#10b981', 'accent_secondary': '#06b6d4', 'gradient': 'linear-gradient(135deg, #0a1a14 0%, #1a2f25 100%)'},
            'politics': {'accent': '#8b5cf6', 'accent_secondary': '#ec4899', 'gradient': 'linear-gradient(135deg, #1a0f2e 0%, #2d1f3f 100%)'},
            'finance': {'accent': '#f59e0b', 'accent_secondary': '#84cc16', 'gradient': 'linear-gradient(135deg, #1a1408 0%, #2d2410 100%)'},
        }

        colors = topic_colors.get(config['slug'], {'accent': '#6366f1', 'accent_secondary': '#8b5cf6', 'gradient': 'linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%)'})
        accent = colors['accent']
        accent_secondary = colors['accent_secondary']
        gradient = colors['gradient']

        # Get date info
        now = datetime.now()
        date_str = now.strftime('%B %d, %Y')
        date_iso = now.isoformat()

        # Get hero image URL and alt text (topic-specific image passed in)
        hero_image_url = ''
        hero_image_alt = ''
        if hero_image:
            hero_image_url = hero_image.get('url_large', hero_image.get('url_medium', hero_image.get('url', '')))
            hero_image_alt = hero_image.get('alt', hero_image.get('description', f'{config["title"]} hero image'))

        # Get featured story info (handle None values safely)
        featured_story = trends[0] if trends else {}
        featured_title = html_module.escape((featured_story.get('title') or '')[:100])
        featured_url = html_module.escape(featured_story.get('url') or '#')
        featured_source = html_module.escape((featured_story.get('source') or '').replace('_', ' ').title())
        featured_desc = html_module.escape((featured_story.get('description') or '')[:200])

        # Build story cards with enhanced design (skip first since it's in hero)
        cards = []
        for i, t in enumerate(trends[1:20]):  # Start from index 1, skip featured
            title = html_module.escape((t.get('title') or '')[:100])
            url = html_module.escape(t.get('url') or '#')
            source = html_module.escape((t.get('source') or '').replace('_', ' ').title())
            desc = html_module.escape((t.get('description') or '')[:150])

            cards.append(f'''
            <article class="story-card">
                <span class="source-badge">{source}</span>
                <h3><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
                {'<p class="story-desc">' + desc + '</p>' if desc else ''}
            </article>''')

        # Build nav links
        nav_links = '''
            <li><a href="/">Home</a></li>
            <li><a href="/tech/"''' + (' class="active"' if config['slug'] == 'tech' else '') + '''>Tech</a></li>
            <li><a href="/world/"''' + (' class="active"' if config['slug'] == 'world' else '') + '''>World</a></li>
            <li><a href="/science/"''' + (' class="active"' if config['slug'] == 'science' else '') + '''>Science</a></li>
            <li><a href="/politics/"''' + (' class="active"' if config['slug'] == 'politics' else '') + '''>Politics</a></li>
            <li><a href="/finance/"''' + (' class="active"' if config['slug'] == 'finance' else '') + '''>Finance</a></li>
            <li><a href="/articles/">Articles</a></li>'''

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config['title']} | DailyTrending.info</title>
    <meta name="description" content="{config['description']}">
    <link rel="canonical" href="https://dailytrending.info/{config['slug']}/">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">

    <meta property="og:title" content="{config['title']} | DailyTrending.info">
    <meta property="og:description" content="{config['description']}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://dailytrending.info/{config['slug']}/">
    <meta property="og:image" content="https://dailytrending.info/og-image.png">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{config['title']} | DailyTrending.info">
    <meta name="twitter:description" content="{config['description']}">

    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "{config['title']} Trends",
        "description": "{config['description']}",
        "url": "https://dailytrending.info/{config['slug']}/",
        "isPartOf": {{"@id": "https://dailytrending.info"}},
        "dateModified": "{date_iso}",
        "numberOfItems": {len(trends)}
    }}
    </script>

    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --color-bg: #0a0a0a;
            --color-card-bg: #18181b;
            --color-text: #ffffff;
            --color-muted: #a1a1aa;
            --color-border: #27272a;
            --color-accent: {accent};
            --color-accent-secondary: {accent_secondary};
            --radius: 1rem;
            --transition: 200ms ease;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: {gradient};
            color: var(--color-text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* Navigation */
        .nav {{
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 2rem;
            background: rgba(10, 10, 10, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--color-border);
        }}

        .nav-logo {{
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 1.25rem;
            color: var(--color-text);
            text-decoration: none;
        }}

        .nav-links {{
            display: flex;
            gap: 0.25rem;
            list-style: none;
        }}

        .nav-links a {{
            padding: 0.5rem 1rem;
            color: var(--color-muted);
            text-decoration: none;
            font-size: 0.9rem;
            font-weight: 500;
            border-radius: 0.5rem;
            transition: color var(--transition), background var(--transition);
        }}

        .nav-links a:hover {{
            color: var(--color-text);
            background: rgba(255,255,255,0.05);
        }}

        .nav-links a.active {{
            color: var(--color-accent);
            background: rgba(255,255,255,0.08);
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

        .mobile-menu-toggle {{
            display: none;
            background: none;
            border: none;
            cursor: pointer;
            padding: 0.5rem;
        }}

        .hamburger-line {{
            display: block;
            width: 24px;
            height: 2px;
            background: var(--color-text);
            margin: 5px 0;
            transition: transform 0.3s;
        }}

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
            background-size: cover;
            background-position: center;
            z-index: 0;
        }}

        .hero-image::after {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.6) 40%, rgba(0,0,0,0.3) 100%);
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
            font-family: 'Space Grotesk', sans-serif;
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
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1.5rem;
        }}

        .story-card {{
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            padding: 1.5rem;
            transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
        }}

        .story-card:hover {{
            transform: translateY(-4px);
            border-color: var(--color-accent);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }}

        .story-card.featured {{
            grid-column: 1 / -1;
            background: linear-gradient(135deg, var(--color-card-bg) 0%, rgba(99, 102, 241, 0.1) 100%);
            border-color: var(--color-accent);
        }}

        .source-badge {{
            display: inline-block;
            background: var(--color-accent);
            color: #000;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.75rem;
        }}

        .story-card h3 {{
            font-size: 1.15rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            line-height: 1.4;
        }}

        .story-card.featured h3 {{
            font-size: 1.5rem;
        }}

        .story-card h3 a {{
            color: var(--color-text);
            text-decoration: none;
            transition: color var(--transition);
        }}

        .story-card h3 a:hover {{
            color: var(--color-accent);
        }}

        .story-desc {{
            color: var(--color-muted);
            font-size: 0.9rem;
            line-height: 1.5;
        }}

        /* Footer */
        .footer {{
            margin-top: 4rem;
            padding: 3rem 2rem;
            background: var(--color-card-bg);
            border-top: 1px solid var(--color-border);
            text-align: center;
        }}

        .footer-content {{
            max-width: 800px;
            margin: 0 auto;
        }}

        .footer-logo {{
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 1.5rem;
            color: var(--color-text);
            margin-bottom: 1rem;
        }}

        .footer-tagline {{
            color: var(--color-muted);
            margin-bottom: 1.5rem;
        }}

        .footer-links {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-bottom: 1.5rem;
        }}

        .footer-links a {{
            color: var(--color-muted);
            text-decoration: none;
            font-size: 0.9rem;
            transition: color var(--transition);
        }}

        .footer-links a:hover {{
            color: var(--color-accent);
        }}

        .footer-bottom {{
            font-size: 0.8rem;
            color: var(--color-muted);
        }}

        /* Mobile responsive */
        @media (max-width: 768px) {{
            .mobile-menu-toggle {{
                display: block;
            }}

            .nav-links {{
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                flex-direction: column;
                background: var(--color-bg);
                border-bottom: 1px solid var(--color-border);
                padding: 1rem;
            }}

            .nav-links.active {{
                display: flex;
            }}

            .nav-date {{
                display: none;
            }}

            .topic-hero {{
                min-height: 400px;
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

            .stories-grid {{
                grid-template-columns: 1fr;
            }}

            .story-card.featured {{
                grid-column: 1;
            }}

            .footer-links {{
                flex-direction: column;
                gap: 1rem;
            }}
        }}
    </style>
</head>
<body>
    <nav class="nav">
        <a href="/" class="nav-logo">DailyTrending.info</a>
        <button class="mobile-menu-toggle" id="mobile-menu-toggle" aria-label="Toggle menu">
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
        </button>
        <ul class="nav-links" id="nav-links">
            {nav_links}
        </ul>
        <div class="nav-actions">
            <span class="nav-date">{date_str}</span>
        </div>
    </nav>

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

    <footer class="footer">
        <div class="footer-content">
            <div class="footer-logo">DailyTrending.info</div>
            <p class="footer-tagline">Curated trends from across the web, updated daily.</p>
            <div class="footer-links">
                <a href="/">Home</a>
                <a href="/tech/">Tech</a>
                <a href="/world/">World</a>
                <a href="/science/">Science</a>
                <a href="/politics/">Politics</a>
                <a href="/finance/">Finance</a>
                <a href="/articles/">Articles</a>
                <a href="/feed.xml">RSS Feed</a>
            </div>
            <div class="footer-bottom">
                &copy; {now.year} DailyTrending.info &bull; Regenerated daily at 6 AM EST
            </div>
        </div>
    </footer>

    <script>
        // Mobile menu toggle
        const toggle = document.getElementById('mobile-menu-toggle');
        const navLinks = document.getElementById('nav-links');
        if (toggle && navLinks) {{
            toggle.addEventListener('click', () => {{
                navLinks.classList.toggle('active');
            }});
        }}
    </script>
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
