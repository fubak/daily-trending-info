#!/usr/bin/env python3
"""Tests for keyword tracking functionality."""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path


class TestKeywordTracker:
    """Tests for keyword trend tracking."""

    def test_tracker_init(self, temp_dir):
        """Test KeywordTracker initialization."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        assert tracker.history_file == history_file

    def test_record_keywords(self, temp_dir):
        """Test recording keywords."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        keywords = ["python", "javascript", "ai", "machine learning"]
        tracker.record_keywords(keywords)

        assert history_file.exists()

        # Check saved data
        with open(history_file) as f:
            data = json.load(f)

        today = datetime.now().strftime("%Y-%m-%d")
        assert today in data.get("daily", {})

    def test_record_multiple_days(self, temp_dir):
        """Test recording keywords over multiple days."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        # Record for different dates
        tracker.record_keywords(["python", "ai"], date="2024-01-01")
        tracker.record_keywords(["python", "rust"], date="2024-01-02")
        tracker.record_keywords(["python", "go"], date="2024-01-03")

        with open(history_file) as f:
            data = json.load(f)

        assert len(data.get("daily", {})) == 3

    def test_get_trending_keywords(self, temp_dir):
        """Test getting trending keywords."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        # Record some keywords
        today = datetime.now()
        for i in range(7):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            keywords = ["python"] * 5 + ["ai"] * (7 - i)  # AI increasing
            tracker.record_keywords(keywords, date=date)

        trending = tracker.get_trending_keywords(10)
        assert len(trending) > 0

        # Check trending structure
        trend = trending[0]
        assert hasattr(trend, "keyword")
        assert hasattr(trend, "trend")
        assert hasattr(trend, "change_percent")

    def test_get_persistent_keywords(self, temp_dir):
        """Test getting persistent keywords."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        # Record same keyword over multiple days
        today = datetime.now()
        for i in range(10):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            tracker.record_keywords(["python", "stable"], date=date)

        persistent = tracker.get_persistent_keywords(min_days=5)
        assert len(persistent) > 0
        assert "python" in persistent or "stable" in persistent

    def test_get_summary(self, temp_dir):
        """Test getting tracker summary."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        tracker.record_keywords(["python", "ai"])
        summary = tracker.get_summary()

        assert "total_days" in summary
        assert "total_unique_keywords" in summary
        assert summary["total_days"] >= 1

    def test_keyword_normalization(self, temp_dir):
        """Test that keywords are normalized."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        # Record with different cases
        tracker.record_keywords(["Python", "PYTHON", "python"])

        with open(history_file) as f:
            data = json.load(f)

        today = datetime.now().strftime("%Y-%m-%d")
        counts = data["daily"][today]

        # Should be normalized to lowercase
        assert "python" in counts
        assert counts["python"] == 3
