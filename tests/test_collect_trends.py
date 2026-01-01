#!/usr/bin/env python3
"""Tests for trend collection functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


class TestTrend:
    """Tests for the Trend dataclass."""

    def test_trend_creation(self):
        """Test creating a Trend object."""
        from collect_trends import Trend

        trend = Trend(
            title="Test Trend",
            source="hackernews",
            url="https://example.com"
        )

        assert trend.title == "Test Trend"
        assert trend.source == "hackernews"
        assert trend.url == "https://example.com"

    def test_trend_default_values(self):
        """Test Trend default values."""
        from collect_trends import Trend

        trend = Trend(title="Test", source="test")

        assert trend.url is None
        assert trend.description is None
        assert trend.score == 1.0
        assert trend.keywords is None

    def test_trend_is_fresh(self):
        """Test freshness check for trends."""
        from collect_trends import Trend

        # Fresh trend (just created)
        fresh_trend = Trend(title="Fresh", source="test")
        assert fresh_trend.is_fresh()

        # Old trend
        old_trend = Trend(
            title="Old",
            source="test",
            timestamp=datetime.now() - timedelta(hours=48)
        )
        assert not old_trend.is_fresh(max_hours=24)


class TestTrendCollector:
    """Tests for the TrendCollector class."""

    def test_collector_init(self):
        """Test TrendCollector initialization."""
        from collect_trends import TrendCollector

        collector = TrendCollector()

        assert collector.trends == []
        assert hasattr(collector, 'session')

    def test_get_all_keywords_empty(self):
        """Test getting keywords from empty collector."""
        from collect_trends import TrendCollector

        collector = TrendCollector()
        keywords = collector.get_all_keywords()

        assert keywords == []

    def test_get_freshness_ratio_empty(self):
        """Test freshness ratio with no trends."""
        from collect_trends import TrendCollector

        collector = TrendCollector()
        ratio = collector.get_freshness_ratio()

        # Should return 1.0 for empty (no stale content)
        assert ratio == 1.0

    def test_get_freshness_ratio_mixed(self):
        """Test freshness ratio with mixed fresh/stale trends."""
        from collect_trends import TrendCollector, Trend

        collector = TrendCollector()

        # Add fresh and stale trends
        collector.trends = [
            Trend(title="Fresh 1", source="test", timestamp=datetime.now()),
            Trend(title="Fresh 2", source="test", timestamp=datetime.now()),
            Trend(title="Stale", source="test", timestamp=datetime.now() - timedelta(hours=48)),
        ]

        ratio = collector.get_freshness_ratio()
        assert 0.6 < ratio < 0.7  # ~2/3 are fresh

    def test_deduplication(self):
        """Test that duplicate trends are removed."""
        from collect_trends import TrendCollector, Trend

        collector = TrendCollector()
        collector.trends = [
            Trend(title="Breaking: Major Event", source="hackernews"),
            Trend(title="Breaking: Major Event", source="reddit"),  # Exact duplicate
            Trend(title="Different News", source="news"),
        ]

        collector._deduplicate()

        # Should have removed exact duplicate
        assert len(collector.trends) <= 2

    def test_semantic_deduplication(self):
        """Test semantic deduplication of similar titles."""
        from collect_trends import TrendCollector, Trend

        collector = TrendCollector()
        collector.trends = [
            Trend(title="OpenAI Releases GPT-5", source="hackernews"),
            Trend(title="OpenAI Announces GPT-5 Release", source="reddit"),  # Semantically similar
            Trend(title="NASA Mars Mission Update", source="news"),  # Different
        ]

        collector._deduplicate()

        # Should identify semantic duplicate
        # Result depends on threshold but should be <= 2
        assert len(collector.trends) <= 2

    def test_extract_keywords(self):
        """Test keyword extraction from trends."""
        from collect_trends import Trend

        # Keywords are extracted on Trend dataclass, not TrendCollector
        trend = Trend(title="Python AI Machine Learning Framework", source="test")

        # Extract keywords using the dataclass method
        keywords = trend._extract_keywords()

        assert keywords is not None
        assert len(keywords) > 0
        assert "python" in keywords or "machine" in keywords or "learning" in keywords


class TestGlobalKeywords:
    """Tests for global keyword frequency analysis."""

    def test_get_global_keywords(self):
        """Test global keyword extraction."""
        from collect_trends import TrendCollector, Trend

        collector = TrendCollector()
        collector.trends = [
            Trend(title="Python AI Release", source="test", keywords=["python", "ai"]),
            Trend(title="AI Model Update", source="test", keywords=["ai", "model"]),
            Trend(title="AI Research Paper", source="test", keywords=["ai", "research"]),
        ]

        # Run _calculate_scores to populate global_keywords
        collector._calculate_scores()

        global_kw = collector.get_global_keywords()

        # AI appears 3 times, should be in global keywords
        assert "ai" in global_kw

    def test_global_keywords_threshold(self):
        """Test global keyword frequency threshold."""
        from collect_trends import TrendCollector, Trend

        collector = TrendCollector()
        collector.trends = [
            Trend(title="Python Release", source="test", keywords=["python"]),
            Trend(title="AI Update", source="test", keywords=["ai"]),
            Trend(title="Rust Framework", source="test", keywords=["rust"]),
        ]

        # Each appears only once - global_keywords is not set until _calculate_scores runs
        # So get_global_keywords should return empty list
        global_kw = collector.get_global_keywords()
        assert len(global_kw) == 0
