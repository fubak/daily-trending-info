#!/usr/bin/env python3
"""Tests for WebsiteBuilder."""

from unittest.mock import MagicMock, patch

import pytest


def make_build_context(trends=None, images=None, design=None):
    from build_website import BuildContext

    return BuildContext(
        trends=trends or [],
        images=images or [],
        design=design
        or {
            "layout_style": "newspaper",
            "hero_style": "glassmorphism",
            "primary_color": "#667eea",
            "secondary_color": "#764ba2",
            "accent_color": "#4facfe",
            "background_color": "#0f0f23",
            "text_color": "#ffffff",
            "font_heading": "Inter",
            "font_body": "Inter",
            "animation_level": "subtle",
        },
        keywords=["tech", "ai"],
    )


class TestWebsiteBuilderInit:
    def test_instantiates_with_empty_trends(self):
        from build_website import WebsiteBuilder

        ctx = make_build_context()
        builder = WebsiteBuilder(ctx)
        assert builder is not None

    def test_uses_default_layout_when_not_specified(self):
        from build_website import WebsiteBuilder, DEFAULT_LAYOUT

        ctx = make_build_context(design={})
        builder = WebsiteBuilder(ctx)
        assert builder.layout == DEFAULT_LAYOUT

    def test_uses_layout_from_design(self):
        from build_website import WebsiteBuilder

        ctx = make_build_context(design={"layout_style": "dashboard"})
        builder = WebsiteBuilder(ctx)
        assert builder.layout == "dashboard"

    def test_sanitizes_trend_titles(self, sample_trends):
        from build_website import WebsiteBuilder

        dirty = dict(sample_trends[0])
        dirty["title"] = "<script>alert('xss')</script>Real Title"
        ctx = make_build_context(trends=[dirty])
        builder = WebsiteBuilder(ctx)
        sanitized = builder.ctx.trends[0]["title"]
        assert "<script>" not in sanitized
        assert "Real Title" in sanitized

    def test_sanitizes_javascript_urls(self, sample_trends):
        from build_website import WebsiteBuilder

        dirty = dict(sample_trends[0])
        dirty["url"] = "javascript:alert(1)"
        ctx = make_build_context(trends=[dirty])
        builder = WebsiteBuilder(ctx)
        assert builder.ctx.trends[0]["url"] is None


class TestWebsiteBuild:
    def test_build_returns_string(self, sample_trends, sample_design):
        from build_website import WebsiteBuilder

        ctx = make_build_context(trends=sample_trends, design=sample_design)
        builder = WebsiteBuilder(ctx)
        result = builder.build()
        assert isinstance(result, str)

    def test_build_contains_doctype(self, sample_trends, sample_design):
        from build_website import WebsiteBuilder

        ctx = make_build_context(trends=sample_trends, design=sample_design)
        builder = WebsiteBuilder(ctx)
        html = builder.build()
        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()

    def test_build_empty_trends_does_not_raise(self, sample_design):
        from build_website import WebsiteBuilder

        ctx = make_build_context(trends=[], design=sample_design)
        builder = WebsiteBuilder(ctx)
        html = builder.build()
        assert isinstance(html, str)
        assert len(html) > 0

    def test_build_includes_trend_title(self, sample_trends, sample_design):
        from build_website import WebsiteBuilder

        ctx = make_build_context(trends=sample_trends[:1], design=sample_design)
        builder = WebsiteBuilder(ctx)
        html = builder.build()
        assert sample_trends[0]["title"] in html

    def test_sanitize_text_strips_tags(self):
        from build_website import WebsiteBuilder

        result = WebsiteBuilder._sanitize_text("<b>Hello</b> World")
        assert result == "Hello World"

    def test_sanitize_url_allows_https(self):
        from build_website import WebsiteBuilder

        assert (
            WebsiteBuilder._sanitize_url("https://example.com") == "https://example.com"
        )

    def test_sanitize_url_blocks_javascript(self):
        from build_website import WebsiteBuilder

        assert WebsiteBuilder._sanitize_url("javascript:void(0)") is None

    def test_sanitize_url_blocks_data_uri(self):
        from build_website import WebsiteBuilder

        assert WebsiteBuilder._sanitize_url("data:text/html,<h1>x</h1>") is None
