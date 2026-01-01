#!/usr/bin/env python3
"""Integration tests for the complete pipeline."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime


class TestPipelineIntegration:
    """Integration tests for the Pipeline class."""

    def test_pipeline_init(self, temp_dir):
        """Test Pipeline initialization."""
        from main import Pipeline

        pipeline = Pipeline(project_root=temp_dir)

        assert pipeline.project_root == temp_dir
        assert pipeline.public_dir.exists()
        assert pipeline.data_dir.exists()

    def test_validate_environment_no_keys(self, temp_dir):
        """Test environment validation with no API keys."""
        from main import Pipeline

        with patch.dict('os.environ', {}, clear=True):
            pipeline = Pipeline(project_root=temp_dir)
            warnings = pipeline._validate_environment()

            # Should have warnings about missing API keys
            assert len(warnings) >= 2
            assert any('image' in w.lower() for w in warnings)
            assert any('ai' in w.lower() for w in warnings)

    def test_validate_environment_with_keys(self, temp_dir):
        """Test environment validation with API keys set."""
        from main import Pipeline

        env = {
            'PEXELS_API_KEY': 'test_key',
            'GROQ_API_KEY': 'test_groq_key'
        }

        with patch.dict('os.environ', env):
            pipeline = Pipeline(project_root=temp_dir)
            warnings = pipeline._validate_environment()

            # Should not have API key warnings
            assert not any('image api' in w.lower() for w in warnings)
            assert not any('ai api' in w.lower() for w in warnings)

    def test_pipeline_data_flow(self, temp_dir, sample_trends, sample_images, sample_design):
        """Test data flows correctly through pipeline components."""
        from main import Pipeline
        from collect_trends import Trend

        pipeline = Pipeline(project_root=temp_dir)

        # Set up mock data
        pipeline.trends = [Trend(**t) for t in sample_trends]
        pipeline.images = sample_images
        pipeline.keywords = ['tech', 'ai', 'science']
        pipeline.global_keywords = ['ai']

        # Verify data is accessible
        assert len(pipeline.trends) == len(sample_trends)
        assert len(pipeline.images) == len(sample_images)
        assert 'tech' in pipeline.keywords

    @patch('main.TrendCollector')
    @patch('main.ImageFetcher')
    @patch('main.DesignGenerator')
    def test_pipeline_step_collect_trends(self, mock_design, mock_images, mock_collector, temp_dir, sample_trends):
        """Test trend collection step."""
        from main import Pipeline
        from collect_trends import Trend

        # Setup mock collector
        mock_collector_instance = MagicMock()
        mock_collector_instance.collect_all.return_value = [Trend(**t) for t in sample_trends]
        mock_collector_instance.get_all_keywords.return_value = ['ai', 'tech']
        mock_collector_instance.get_global_keywords.return_value = ['ai']
        mock_collector_instance.get_freshness_ratio.return_value = 0.8
        mock_collector.return_value = mock_collector_instance

        pipeline = Pipeline(project_root=temp_dir)
        pipeline._step_collect_trends()

        assert len(pipeline.trends) == len(sample_trends)
        mock_collector_instance.collect_all.assert_called_once()


class TestRSSIntegration:
    """Integration tests for RSS feed generation."""

    def test_rss_from_trends_data(self, temp_dir, sample_trends):
        """Test RSS generation from trends data file."""
        from generate_rss import generate_rss_feed, generate_from_data_file

        # Save sample trends to data file
        data_dir = temp_dir / "data"
        data_dir.mkdir(exist_ok=True)
        trends_file = data_dir / "trends.json"

        with open(trends_file, 'w') as f:
            json.dump(sample_trends, f)

        # Generate RSS from file
        output_path = temp_dir / "public" / "feed.xml"
        output_path.parent.mkdir(exist_ok=True)

        xml = generate_rss_feed(sample_trends, output_path)

        assert output_path.exists()
        assert '<?xml' in xml
        assert '<rss' in xml


class TestKeywordTrackerIntegration:
    """Integration tests for keyword tracking with pipeline."""

    def test_keyword_recording_persistence(self, temp_dir):
        """Test that keywords persist across tracker instances."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"

        # First instance
        tracker1 = KeywordTracker(history_file)
        tracker1.record_keywords(['python', 'ai', 'rust'])

        # Second instance (simulating restart)
        tracker2 = KeywordTracker(history_file)

        summary = tracker2.get_summary()
        assert summary['total_unique_keywords'] >= 3

    def test_trending_detection(self, temp_dir):
        """Test trending keyword detection over time."""
        from keyword_tracker import KeywordTracker
        from datetime import datetime, timedelta

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        today = datetime.now()

        # Record "ai" increasingly over past week
        for i in range(7):
            date = (today - timedelta(days=6-i)).strftime("%Y-%m-%d")
            # More "ai" mentions as we get closer to today
            keywords = ['ai'] * (i + 1) + ['python']
            tracker.record_keywords(keywords, date=date)

        trending = tracker.get_trending_keywords(10)

        # AI should be trending (rising)
        ai_trend = next((t for t in trending if t.keyword == 'ai'), None)
        assert ai_trend is not None


class TestImageFetcherIntegration:
    """Integration tests for image fetching with caching."""

    def test_cache_persistence(self, temp_dir, sample_images):
        """Test that image cache persists across instances."""
        from fetch_images import ImageCache, Image

        cache1 = ImageCache(temp_dir)
        images = [Image(**img) for img in sample_images]
        cache1.cache_results("technology", images)

        # Create new instance
        cache2 = ImageCache(temp_dir)

        assert cache2.is_cached("technology")
        cached = cache2.get_cached("technology")
        assert len(cached) == len(images)

    def test_cache_atomic_operations(self, temp_dir):
        """Test that cache uses atomic file operations."""
        from fetch_images import ImageCache

        cache = ImageCache(temp_dir)
        cache.index = {"queries": {"test": {"timestamp": "2024-01-01"}}, "images": {}}

        # Save should use atomic operations
        cache._save_index()

        # No temp files should remain
        temp_files = list(temp_dir.glob('.cache_index_*.tmp'))
        assert len(temp_files) == 0

        # Index file should exist
        assert (temp_dir / "cache_index.json").exists()
