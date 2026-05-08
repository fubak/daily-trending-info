"""Tests for pipeline_types TypedDict schemas.

These are mostly structural — TypedDicts don't enforce at runtime, so the
tests verify (a) the schemas are importable, (b) they accept reasonable
data shapes, and (c) `total=False` allows partial dicts (the way the
pipeline actually uses them).
"""

from scripts.pipeline_types import (
    DesignTokens,
    ImageDict,
    MediaData,
    MediaItemDict,
    TrendDict,
)


class TestTrendDict:
    def test_accepts_full_trend(self):
        # All fields present — typical post-collection state.
        trend: TrendDict = {
            "title": "AI Breakthrough",
            "source": "hackernews",
            "url": "https://example.com/x",
            "description": "Summary",
            "category": "tech",
            "score": 80.0,
            "keywords": ["ai", "breakthrough"],
            "timestamp": "2026-05-08T12:00:00",
            "image_url": None,
            "source_metadata": {},
            "source_label": "Hacker News",
            "corroborating_sources": ["hackernews"],
            "corroborating_urls": ["https://example.com/x"],
            "source_diversity": 1,
        }
        # If we got here without error, the dict is structurally valid.
        assert trend["title"] == "AI Breakthrough"
        assert trend["score"] == 80.0

    def test_accepts_partial_trend(self):
        # total=False means callers can pass minimal dicts.
        trend: TrendDict = {"title": "x", "source": "rss"}
        assert trend["source"] == "rss"


class TestImageDict:
    def test_accepts_full_image(self):
        img: ImageDict = {
            "id": "pexels_1",
            "url_small": "https://x/s.jpg",
            "url_medium": "https://x/m.jpg",
            "url_large": "https://x/l.jpg",
            "url_original": "https://x/o.jpg",
            "photographer": "A",
            "photographer_url": "https://x/a",
            "source": "pexels",
            "alt_text": "tech abstract",
            "color": "#444",
            "width": 1920,
            "height": 1080,
        }
        assert img["source"] == "pexels"

    def test_partial_image(self):
        img: ImageDict = {"id": "x", "url_large": "https://x/l.jpg"}
        assert img["id"] == "x"


class TestDesignTokens:
    def test_accepts_design_tokens(self):
        tokens: DesignTokens = {
            "primary_color": "#667eea",
            "accent_color": "#4facfe",
            "bg_color": "#0f0f23",
            "text_color": "#ffffff",
            "muted_color": "#a1a1aa",
            "border_color": "#27272a",
            "card_bg": "#18181b",
            "font_primary": "Space Grotesk",
            "font_secondary": "Inter",
            "base_mode": "dark-mode",
        }
        assert tokens["base_mode"] == "dark-mode"


class TestMediaShapes:
    def test_media_item(self):
        item: MediaItemDict = {
            "title": "APOD",
            "url": "https://apod.example.com/x.jpg",
            "creator": "NASA",
        }
        assert item["title"] == "APOD"

    def test_media_data_with_both_items(self):
        data: MediaData = {
            "image_of_day": {"title": "img", "url": "https://x.jpg"},
            "video_of_day": {"title": "vid", "url": "https://y"},
        }
        assert data["image_of_day"]["title"] == "img"
        assert data["video_of_day"]["title"] == "vid"

    def test_media_data_partial(self):
        # MediaData should also accept just one key.
        data: MediaData = {"image_of_day": {"title": "img"}}
        assert "image_of_day" in data
