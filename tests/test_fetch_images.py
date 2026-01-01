#!/usr/bin/env python3
"""Tests for image fetching functionality."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestImageCache:
    """Tests for the image cache system."""

    def test_cache_init(self, temp_dir):
        """Test ImageCache initialization."""
        from fetch_images import ImageCache

        cache = ImageCache(temp_dir)
        assert cache.cache_dir == temp_dir
        assert (temp_dir / "cache_index.json").parent.exists()

    def test_cache_query_key(self, temp_dir):
        """Test cache key generation is deterministic."""
        from fetch_images import ImageCache

        cache = ImageCache(temp_dir)

        key1 = cache._query_key("technology")
        key2 = cache._query_key("Technology")
        key3 = cache._query_key("  technology  ")

        # Should normalize to same key
        assert key1 == key2
        assert key1 == key3

    def test_cache_results(self, temp_dir, sample_images):
        """Test caching search results."""
        from fetch_images import ImageCache, Image

        cache = ImageCache(temp_dir)

        # Create Image objects
        images = [Image(**img) for img in sample_images]

        # Cache them
        cache.cache_results("technology", images)

        # Verify cached
        assert cache.is_cached("technology")

        # Retrieve
        cached = cache.get_cached("technology")
        assert len(cached) == len(images)

    def test_cache_not_found(self, temp_dir):
        """Test cache miss."""
        from fetch_images import ImageCache

        cache = ImageCache(temp_dir)

        assert not cache.is_cached("nonexistent_query")
        assert cache.get_cached("nonexistent_query") == []


class TestImageFetcher:
    """Tests for the ImageFetcher class."""

    def test_fetcher_init(self):
        """Test ImageFetcher initialization."""
        from fetch_images import ImageFetcher

        fetcher = ImageFetcher(use_cache=False)

        assert fetcher.images == []
        assert fetcher.used_ids == set()

    def test_fetcher_rate_limiting(self):
        """Test rate limiting is applied."""
        from fetch_images import ImageFetcher
        import time

        fetcher = ImageFetcher(use_cache=False)

        start = time.time()
        fetcher._rate_limit()
        fetcher._rate_limit()
        elapsed = time.time() - start

        # Should have waited at least one interval
        assert elapsed >= fetcher._min_request_interval

    @patch('fetch_images.ImageFetcher._request_with_retry')
    def test_search_pexels_success(self, mock_request):
        """Test successful Pexels search."""
        from fetch_images import ImageFetcher

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "photos": [
                {
                    "id": 12345,
                    "src": {
                        "small": "https://example.com/small.jpg",
                        "medium": "https://example.com/medium.jpg",
                        "large": "https://example.com/large.jpg",
                        "original": "https://example.com/original.jpg"
                    },
                    "photographer": "Test User",
                    "photographer_url": "https://pexels.com/test",
                    "alt": "Test image",
                    "avg_color": "#ffffff",
                    "width": 1920,
                    "height": 1080
                }
            ]
        }
        mock_request.return_value = mock_response

        fetcher = ImageFetcher(pexels_key="test_key", use_cache=False)
        images = fetcher.search_pexels("test")

        assert len(images) == 1
        assert images[0].source == "pexels"

    def test_search_pexels_no_key(self):
        """Test Pexels search without API key."""
        from fetch_images import ImageFetcher

        fetcher = ImageFetcher(pexels_key=None, unsplash_key=None, use_cache=False)
        images = fetcher.search_pexels("test")

        assert images == []


class TestFallbackImageGenerator:
    """Tests for fallback gradient generator."""

    def test_get_gradient(self):
        """Test gradient generation."""
        from fetch_images import FallbackImageGenerator

        gradient = FallbackImageGenerator.get_gradient()

        assert len(gradient) == 3
        assert gradient[0].endswith("deg")
        assert gradient[1].startswith("#")
        assert gradient[2].startswith("#")

    def test_get_gradient_css(self):
        """Test CSS gradient generation."""
        from fetch_images import FallbackImageGenerator

        css = FallbackImageGenerator.get_gradient_css()

        assert "linear-gradient" in css
        assert "#" in css

    def test_get_mesh_gradient_css(self):
        """Test mesh gradient generation."""
        from fetch_images import FallbackImageGenerator

        css = FallbackImageGenerator.get_mesh_gradient_css()

        assert "radial-gradient" in css
