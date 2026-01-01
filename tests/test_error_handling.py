#!/usr/bin/env python3
"""Tests for error handling across the codebase."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import requests


class TestImageFetcherErrors:
    """Tests for image fetcher error handling."""

    def test_pexels_api_error(self):
        """Test handling of Pexels API errors."""
        from fetch_images import ImageFetcher

        with patch.object(ImageFetcher, '_request_with_retry', return_value=None):
            fetcher = ImageFetcher(pexels_key='test', use_cache=False)
            images = fetcher.search_pexels('test')

            assert images == []

    def test_unsplash_api_error(self):
        """Test handling of Unsplash API errors."""
        from fetch_images import ImageFetcher

        with patch.object(ImageFetcher, '_request_with_retry', return_value=None):
            fetcher = ImageFetcher(unsplash_key='test', use_cache=False)
            images = fetcher.search_unsplash('test')

            assert images == []

    def test_malformed_json_response(self):
        """Test handling of malformed JSON responses."""
        from fetch_images import ImageFetcher

        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError('error', '', 0)

        with patch.object(ImageFetcher, '_request_with_retry', return_value=mock_response):
            fetcher = ImageFetcher(pexels_key='test', use_cache=False)
            images = fetcher.search_pexels('test')

            # Should return empty list, not crash
            assert images == []

    def test_retry_on_timeout(self):
        """Test retry behavior on timeout."""
        from fetch_images import ImageFetcher

        fetcher = ImageFetcher(pexels_key='test', use_cache=False)

        call_count = [0]
        def mock_get(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise requests.exceptions.Timeout()
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {'photos': []}
            return response

        with patch.object(fetcher.session, 'get', side_effect=mock_get):
            fetcher._request_with_retry(
                'https://api.pexels.com/test',
                {'Authorization': 'test'},
                {'query': 'test'},
                'Pexels'
            )

        # Should have retried
        assert call_count[0] >= 2


class TestCacheErrors:
    """Tests for cache error handling."""

    def test_cache_corrupted_json(self, temp_dir):
        """Test handling of corrupted cache JSON."""
        from fetch_images import ImageCache

        # Create corrupted cache file
        cache_file = temp_dir / "cache_index.json"
        cache_file.write_text("not valid json {{{")

        # Should not crash, should return empty cache
        cache = ImageCache(temp_dir)
        assert cache.index == {"queries": {}, "images": {}}

    def test_cache_missing_directory(self, temp_dir):
        """Test cache creation with missing directory."""
        from fetch_images import ImageCache

        new_dir = temp_dir / "new_cache_dir"
        cache = ImageCache(new_dir)

        # Should create directory
        assert new_dir.exists()

    def test_cache_save_permission_error(self, temp_dir):
        """Test handling of cache save permission errors."""
        from fetch_images import ImageCache
        import os

        cache = ImageCache(temp_dir)
        cache.index = {"queries": {"test": {}}, "images": {}}

        # Patch os.fdopen to raise permission error
        with patch('os.fdopen', side_effect=PermissionError("Permission denied")):
            # Should not crash, just log warning
            cache._save_index()


class TestRSSErrors:
    """Tests for RSS feed error handling."""

    def test_rss_empty_trends(self, temp_dir):
        """Test RSS generation with empty trends."""
        from generate_rss import generate_rss_feed

        output_path = temp_dir / "feed.xml"
        xml = generate_rss_feed([], output_path)

        # Should still generate valid RSS
        assert '<?xml' in xml
        assert '<rss' in xml

    def test_rss_missing_fields(self, temp_dir):
        """Test RSS generation with trends missing required fields."""
        from generate_rss import generate_rss_feed

        trends = [
            {},  # Empty trend
            {'title': 'Only Title'},  # Missing url
            {'url': 'https://example.com'},  # Missing title
            {'title': 'Full Trend', 'url': 'https://example.com', 'description': 'Desc'},
        ]

        output_path = temp_dir / "feed.xml"
        xml = generate_rss_feed(trends, output_path)

        # Should only include valid items
        assert 'Full Trend' in xml

    def test_rss_special_characters(self, temp_dir):
        """Test RSS generation with special XML characters."""
        from generate_rss import generate_rss_feed

        trends = [
            {
                'title': 'Test <script>alert("xss")</script> & more',
                'url': 'https://example.com/test?a=1&b=2',
                'description': 'Description with "quotes" and \'apostrophes\''
            }
        ]

        output_path = temp_dir / "feed.xml"
        xml = generate_rss_feed(trends, output_path)

        # Should escape special characters
        assert '<script>' not in xml or '&lt;script&gt;' in xml


class TestKeywordTrackerErrors:
    """Tests for keyword tracker error handling."""

    def test_tracker_corrupted_history(self, temp_dir):
        """Test handling of corrupted history file."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        history_file.write_text("invalid json content")

        # Should not crash
        tracker = KeywordTracker(history_file)
        assert "daily" in tracker.history

    def test_tracker_empty_keywords(self, temp_dir):
        """Test recording empty keyword list."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        # Should not crash
        tracker.record_keywords([])
        tracker.record_keywords([''])  # Empty string
        tracker.record_keywords(['a'])  # Single char (filtered out)

    def test_tracker_trending_no_data(self, temp_dir):
        """Test trending keywords with no historical data."""
        from keyword_tracker import KeywordTracker

        history_file = temp_dir / "keyword_history.json"
        tracker = KeywordTracker(history_file)

        trending = tracker.get_trending_keywords()
        assert trending == []


class TestCollectorErrors:
    """Tests for trend collector error handling."""

    def test_collector_network_error(self):
        """Test handling of network errors in collector."""
        from collect_trends import TrendCollector

        collector = TrendCollector()

        # Mock session to raise network error
        with patch.object(collector.session, 'get', side_effect=requests.exceptions.ConnectionError()):
            trends = collector._collect_hackernews()
            assert trends == []

    def test_collector_malformed_response(self):
        """Test handling of malformed API responses."""
        from collect_trends import TrendCollector

        collector = TrendCollector()

        mock_response = MagicMock()
        mock_response.json.return_value = "not a list"  # Should be list
        mock_response.raise_for_status = MagicMock()

        with patch.object(collector.session, 'get', return_value=mock_response):
            # Should not crash
            trends = collector._collect_hackernews()


class TestBuildErrors:
    """Tests for website build error handling."""

    def test_build_missing_trends(self):
        """Test building with no trends."""
        from build_website import WebsiteBuilder, BuildContext

        context = BuildContext(
            trends=[],
            images=[],
            design={
                'theme_name': 'Test',
                'headline': 'Test',
                'subheadline': 'Test',
                'personality': 'modern'
            },
            keywords=[]
        )

        builder = WebsiteBuilder(context)
        html = builder.build()

        # Should still generate valid HTML
        assert '<!DOCTYPE html>' in html

    def test_build_xss_prevention(self):
        """Test that XSS attacks are prevented."""
        from build_website import WebsiteBuilder, BuildContext

        malicious_trends = [
            {
                'title': '<script>alert("xss")</script>',
                'source': '<img src=x onerror=alert(1)>',
                'url': 'javascript:alert(1)',
                'description': '<iframe src="evil.com"></iframe>'
            }
        ]

        context = BuildContext(
            trends=malicious_trends,
            images=[],
            design={
                'theme_name': 'Test',
                'headline': 'Test',
                'subheadline': 'Test',
                'personality': 'modern'
            },
            keywords=['<script>']
        )

        builder = WebsiteBuilder(context)
        html = builder.build()

        # Scripts should be escaped
        assert '<script>alert' not in html
        assert 'onerror=alert' not in html
