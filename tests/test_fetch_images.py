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


class TestProviderParsers:
    """The provider-specific photo→Image mappers used by _search_provider.

    Unsplash and Pixabay had no parse coverage before search_* was unified; the
    field mappings differ per API and are easy to get subtly wrong.
    """

    def test_parse_unsplash_maps_nested_fields(self):
        from fetch_images import _parse_unsplash

        photo = {
            "id": "abc123",
            "urls": {"small": "s.jpg", "regular": "r.jpg", "full": "f.jpg", "raw": "raw.jpg"},
            "user": {"name": "Ansel", "links": {"html": "https://unsplash.com/@ansel"}},
            "alt_description": "a mountain",
            "color": "#abcdef",
            "width": 4000,
            "height": 3000,
        }
        img = _parse_unsplash(photo, "fallback query")
        assert img is not None
        assert img.id == "unsplash_abc123"
        assert img.source == "unsplash"
        assert img.url_medium == "r.jpg"  # 'regular' is the medium size
        assert img.photographer == "Ansel"
        assert img.photographer_url == "https://unsplash.com/@ansel"
        assert img.alt_text == "a mountain"

    def test_parse_unsplash_falls_back_to_query_for_alt(self):
        from fetch_images import _parse_unsplash

        photo = {"id": "x", "urls": {}, "user": {}}
        img = _parse_unsplash(photo, "sunset over water")
        assert img.alt_text == "sunset over water"

    def test_parse_pixabay_builds_attribution_url(self):
        from fetch_images import _parse_pixabay

        photo = {
            "id": 77,
            "previewURL": "p.jpg",
            "webformatURL": "w.jpg",
            "largeImageURL": "l.jpg",
            "fullHDURL": "hd.jpg",
            "user": "jane",
            "user_id": 42,
            "tags": "city, night",
            "imageWidth": 1920,
            "imageHeight": 1080,
        }
        img = _parse_pixabay(photo, "q")
        assert img.id == "pixabay_77"
        assert img.photographer_url == "https://pixabay.com/users/jane-42"
        assert img.url_large == "l.jpg"
        assert img.color is None  # Pixabay supplies no dominant color

    def test_parsers_skip_text_heavy_images(self):
        # is_text_heavy_image gates every provider; a text-heavy alt/tags must
        # cause the mapper to return None so it's dropped from results.
        from fetch_images import _parse_pexels, is_text_heavy_image

        text_heavy = "infographic chart with quarterly sales data and statistics text"
        assert is_text_heavy_image(text_heavy)  # precondition for the test
        photo = {"id": 1, "src": {}, "alt": text_heavy}
        assert _parse_pexels(photo, "q") is None
