#!/usr/bin/env python3
"""Tests for configuration module."""

import pytest
import logging
from pathlib import Path


class TestConfig:
    """Tests for config.py settings and utilities."""

    def test_config_imports(self):
        """Test that all config values can be imported."""
        from config import (
            MIN_TRENDS, MIN_FRESH_RATIO, TREND_FRESHNESS_HOURS,
            LIMITS, TIMEOUTS, DELAYS, RETRY_MAX_ATTEMPTS,
            DEDUP_SIMILARITY_THRESHOLD, DEDUP_SEMANTIC_THRESHOLD,
            PROJECT_ROOT, DATA_DIR, PUBLIC_DIR
        )

        # Basic sanity checks
        assert MIN_TRENDS > 0
        assert 0 < MIN_FRESH_RATIO <= 1
        assert TREND_FRESHNESS_HOURS > 0
        assert RETRY_MAX_ATTEMPTS > 0

    def test_limits_dict_has_sources(self):
        """Test that LIMITS contains expected sources."""
        from config import LIMITS

        expected_sources = ["hackernews", "reddit", "google_trends"]
        for source in expected_sources:
            assert source in LIMITS
            assert LIMITS[source] > 0

    def test_timeouts_are_reasonable(self):
        """Test that timeouts are within reasonable bounds."""
        from config import TIMEOUTS

        for key, value in TIMEOUTS.items():
            assert 1 <= value <= 60, f"Timeout {key} = {value} seems unreasonable"

    def test_paths_exist_or_creatable(self):
        """Test that project paths are valid."""
        from config import PROJECT_ROOT, SCRIPTS_DIR

        assert PROJECT_ROOT.exists()
        assert SCRIPTS_DIR.exists()

    def test_setup_logging(self):
        """Test logger setup function."""
        from config import setup_logging

        logger = setup_logging("test_logger")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"
        assert len(logger.handlers) > 0

    def test_setup_logging_idempotent(self):
        """Test that setup_logging doesn't duplicate handlers."""
        from config import setup_logging

        logger1 = setup_logging("idempotent_test")
        handler_count1 = len(logger1.handlers)

        logger2 = setup_logging("idempotent_test")
        handler_count2 = len(logger2.handlers)

        assert handler_count1 == handler_count2

    def test_dedup_thresholds_valid(self):
        """Test deduplication thresholds are valid."""
        from config import DEDUP_SIMILARITY_THRESHOLD, DEDUP_SEMANTIC_THRESHOLD

        assert 0 < DEDUP_SIMILARITY_THRESHOLD <= 1
        assert 0 < DEDUP_SEMANTIC_THRESHOLD <= 1

    def test_rss_settings(self):
        """Test RSS feed settings."""
        from config import RSS_FEED_TITLE, RSS_FEED_LINK, RSS_FEED_MAX_ITEMS

        assert RSS_FEED_TITLE
        assert RSS_FEED_LINK.startswith("http")
        assert RSS_FEED_MAX_ITEMS > 0
