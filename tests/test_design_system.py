#!/usr/bin/env python3
"""
Tests for the design system features including:
- WCAG contrast validation
- Content sentiment analysis
- Personality-hero alignment
- CSS/JS generation modules
- PWA and sitemap generation
"""

import pytest
import json
from pathlib import Path
from datetime import datetime


class TestWCAGContrastValidation:
    """Tests for WCAG color contrast validation functions."""

    def test_hex_to_rgb_basic(self):
        """Test basic hex to RGB conversion."""
        from generate_design import hex_to_rgb

        assert hex_to_rgb("#ffffff") == (255, 255, 255)
        assert hex_to_rgb("#000000") == (0, 0, 0)
        assert hex_to_rgb("#ff0000") == (255, 0, 0)
        assert hex_to_rgb("#00ff00") == (0, 255, 0)
        assert hex_to_rgb("#0000ff") == (0, 0, 255)

    def test_hex_to_rgb_shorthand(self):
        """Test shorthand hex conversion."""
        from generate_design import hex_to_rgb

        assert hex_to_rgb("#fff") == (255, 255, 255)
        assert hex_to_rgb("#000") == (0, 0, 0)
        assert hex_to_rgb("#f00") == (255, 0, 0)

    def test_hex_to_rgb_without_hash(self):
        """Test hex conversion without hash prefix."""
        from generate_design import hex_to_rgb

        assert hex_to_rgb("ffffff") == (255, 255, 255)
        assert hex_to_rgb("000000") == (0, 0, 0)

    def test_get_relative_luminance(self):
        """Test relative luminance calculation."""
        from generate_design import get_relative_luminance

        # White should have luminance close to 1
        white_lum = get_relative_luminance((255, 255, 255))
        assert 0.99 < white_lum <= 1.0

        # Black should have luminance close to 0
        black_lum = get_relative_luminance((0, 0, 0))
        assert black_lum == 0.0

    def test_calculate_contrast_ratio_extremes(self):
        """Test contrast ratio calculation for extreme cases."""
        from generate_design import calculate_contrast_ratio

        # Black on white should be 21:1
        ratio = calculate_contrast_ratio("#000000", "#ffffff")
        assert 20.9 < ratio <= 21.0

        # Same colors should be 1:1
        ratio = calculate_contrast_ratio("#ffffff", "#ffffff")
        assert ratio == 1.0

    def test_validate_color_contrast_wcag_aa(self):
        """Test WCAG AA contrast validation (4.5:1 for normal text)."""
        from generate_design import validate_color_contrast

        # High contrast: should pass
        assert validate_color_contrast("#000000", "#ffffff") is True

        # Low contrast: should fail
        assert validate_color_contrast("#777777", "#888888") is False

        # Borderline cases with accent colors
        assert validate_color_contrast("#ffffff", "#0a0a0a") is True

    def test_adjust_color_for_contrast(self):
        """Test automatic color adjustment for contrast."""
        from generate_design import adjust_color_for_contrast

        # Low contrast text should be adjusted
        adjusted = adjust_color_for_contrast("#555555", "#666666")
        # Should return white or black for sufficient contrast
        assert adjusted in ["#ffffff", "#1a1a1a"]

        # High contrast should remain unchanged
        adjusted = adjust_color_for_contrast("#ffffff", "#000000")
        assert adjusted == "#ffffff"


class TestContentSentimentAnalysis:
    """Tests for content sentiment analysis functions."""

    def test_analyze_content_sentiment_breaking(self):
        """Test detection of breaking news sentiment."""
        from generate_design import analyze_content_sentiment

        trends = [
            {
                "title": "BREAKING: Major event happening",
                "description": "Urgent developing story",
            },
            {"title": "Just In: Alert issued", "description": None},
        ]
        keywords = ["breaking", "urgent"]

        result = analyze_content_sentiment(trends, keywords)
        assert result == "breaking"

    def test_analyze_content_sentiment_entertainment(self):
        """Test detection of entertainment content."""
        from generate_design import analyze_content_sentiment

        trends = [
            {
                "title": "New Movie Released",
                "description": "Celebrity stars in blockbuster",
            },
            {
                "title": "Music Awards Ceremony",
                "description": "Entertainment highlights",
            },
            {"title": "Game of the Year", "description": "Sports championship"},
        ]
        keywords = ["movie", "music", "game"]

        result = analyze_content_sentiment(trends, keywords)
        assert result == "entertainment"

    def test_analyze_content_sentiment_positive(self):
        """Test detection of positive news."""
        from generate_design import analyze_content_sentiment

        trends = [
            {"title": "Team Wins Championship", "description": "Success celebrated"},
            {"title": "Breakthrough in Medicine", "description": "Achieves milestone"},
        ]
        keywords = ["success", "wins", "breakthrough"]

        result = analyze_content_sentiment(trends, keywords)
        assert result == "positive"

    def test_analyze_content_sentiment_negative(self):
        """Test detection of negative/serious news."""
        from generate_design import analyze_content_sentiment

        trends = [
            {"title": "Crisis Deepens", "description": "Disaster warning issued"},
            {"title": "Market Crash Continues", "description": "Threat of failure"},
        ]
        keywords = ["crisis", "disaster", "crash"]

        result = analyze_content_sentiment(trends, keywords)
        assert result == "negative"

    def test_analyze_content_sentiment_neutral(self):
        """Test neutral sentiment for mixed content."""
        from generate_design import analyze_content_sentiment

        trends = [
            {"title": "Tech Update Released", "description": "New features available"},
            {"title": "Policy Change Announced", "description": "Government proposal"},
        ]
        keywords = ["tech", "policy", "update"]

        result = analyze_content_sentiment(trends, keywords)
        assert result == "neutral"

    def test_analyze_content_sentiment_handles_none(self):
        """Test that None values in trends are handled gracefully."""
        from generate_design import analyze_content_sentiment

        trends = [
            {"title": "Test Story", "description": None},
            {"title": None, "description": "Some description"},
            {"title": "Another Story", "description": "More content"},
        ]
        keywords = [None, "test", None]

        # Should not raise an error
        result = analyze_content_sentiment(trends, keywords)
        assert result in [
            "breaking",
            "entertainment",
            "positive",
            "negative",
            "neutral",
        ]

    def test_get_content_aware_animation(self):
        """Test content-aware animation selection."""
        from generate_design import get_content_aware_animation

        # Breaking news should get moderate animation
        trends = [{"title": "BREAKING: Event", "description": "Urgent alert"}]
        result = get_content_aware_animation(trends, ["breaking"], "subtle")
        assert result in ["subtle", "moderate"]

        # Entertainment should get playful animation
        trends = [{"title": "Movie Released", "description": "Celebrity entertainment"}]
        result = get_content_aware_animation(
            trends, ["movie", "entertainment"], "subtle"
        )
        # Should lean toward playful
        assert result in ["subtle", "moderate", "playful"]


class TestPersonalityHeroAlignment:
    """Tests for personality-hero style alignment."""

    def test_all_personalities_have_hero_alignment(self):
        """Test that all personalities have hero style mappings."""
        from generate_design import PERSONALITIES, PERSONALITY_HERO_ALIGNMENT

        for personality in PERSONALITIES.keys():
            assert (
                personality in PERSONALITY_HERO_ALIGNMENT
            ), f"Personality '{personality}' missing from PERSONALITY_HERO_ALIGNMENT"
            assert (
                len(PERSONALITY_HERO_ALIGNMENT[personality]) > 0
            ), f"Personality '{personality}' has empty hero alignment"

    def test_hero_styles_are_valid(self):
        """Test that all aligned hero styles have CSS implementations."""
        from generate_design import PERSONALITY_HERO_ALIGNMENT, HERO_STYLES_WITH_CSS

        for personality, hero_styles in PERSONALITY_HERO_ALIGNMENT.items():
            for style in hero_styles:
                assert (
                    style in HERO_STYLES_WITH_CSS
                ), f"Hero style '{style}' for '{personality}' not in HERO_STYLES_WITH_CSS"

    def test_brutalist_hero_styles(self):
        """Test brutalist personality has appropriate hero styles."""
        from generate_design import PERSONALITY_HERO_ALIGNMENT

        brutalist_styles = PERSONALITY_HERO_ALIGNMENT["brutalist"]
        # Brutalist should have bold, raw styles
        assert "glitch" in brutalist_styles or "geometric" in brutalist_styles

    def test_playful_hero_styles(self):
        """Test playful personality has fun hero styles."""
        from generate_design import PERSONALITY_HERO_ALIGNMENT

        playful_styles = PERSONALITY_HERO_ALIGNMENT["playful"]
        # Playful should have animated, energetic styles
        fun_styles = {"particles", "waves", "aurora", "neon", "retro"}
        assert any(style in playful_styles for style in fun_styles)


class TestImageTreatments:
    """Tests for image treatment system."""

    def test_all_personalities_have_treatments(self):
        """Test that all personalities have image treatments."""
        from generate_design import PERSONALITIES, PERSONALITY_IMAGE_TREATMENTS

        for personality in PERSONALITIES.keys():
            assert (
                personality in PERSONALITY_IMAGE_TREATMENTS
            ), f"Personality '{personality}' missing from PERSONALITY_IMAGE_TREATMENTS"

    def test_image_treatments_are_valid(self):
        """Test that all personality treatments are defined."""
        from generate_design import IMAGE_TREATMENTS, PERSONALITY_IMAGE_TREATMENTS

        for personality, treatments in PERSONALITY_IMAGE_TREATMENTS.items():
            for treatment in treatments:
                assert (
                    treatment in IMAGE_TREATMENTS
                ), f"Treatment '{treatment}' for '{personality}' not defined in IMAGE_TREATMENTS"


class TestTypographyScales:
    """Tests for typography scale system."""

    def test_all_personalities_have_scales(self):
        """Test that all personalities have typography scales."""
        from generate_design import PERSONALITIES, TYPOGRAPHY_SCALES

        for personality in PERSONALITIES.keys():
            assert (
                personality in TYPOGRAPHY_SCALES
            ), f"Personality '{personality}' missing from TYPOGRAPHY_SCALES"

    def test_typography_scale_properties(self):
        """Test that typography scales have required properties."""
        from generate_design import TYPOGRAPHY_SCALES

        required_keys = [
            "scale_ratio",
            "base_size",
            "headline_xl",
            "headline_lg",
            "headline_md",
        ]

        for personality, scale in TYPOGRAPHY_SCALES.items():
            for key in required_keys:
                assert (
                    key in scale
                ), f"Typography scale for '{personality}' missing '{key}'"

    def test_typography_scale_ratios(self):
        """Test that scale ratios are valid."""
        from generate_design import TYPOGRAPHY_SCALES

        for personality, scale in TYPOGRAPHY_SCALES.items():
            ratio = scale["scale_ratio"]
            assert (
                1.0 < ratio < 2.0
            ), f"Scale ratio {ratio} for '{personality}' is out of reasonable range"


class TestCSSGenerator:
    """Tests for CSS generator module."""

    def test_minify_css_removes_comments(self):
        """Test that CSS minification removes comments."""
        from css_generator import minify_css

        css = """
        /* This is a comment */
        .class {
            color: red; /* inline comment */
        }
        """
        result = minify_css(css)
        assert "/*" not in result
        assert "*/" not in result

    def test_minify_css_removes_whitespace(self):
        """Test that CSS minification removes extra whitespace."""
        from css_generator import minify_css

        css = """
        .class {
            color:    red;
            padding:  10px;
        }
        """
        result = minify_css(css)
        assert "\n" not in result
        assert "  " not in result

    def test_get_base_css_includes_variables(self):
        """Test that base CSS includes custom properties."""
        from css_generator import get_base_css

        design = {
            "color_accent": "#ff0000",
            "font_primary": "Arial",
        }
        result = get_base_css(design, "linear-gradient(red, blue)")
        assert "--color-accent" in result
        assert "--font-primary" in result

    def test_get_accessibility_css_includes_skip_link(self):
        """Test that accessibility CSS includes skip link."""
        from css_generator import get_accessibility_css

        result = get_accessibility_css()
        assert ".skip-link" in result
        assert ":focus-visible" in result


class TestJSGenerator:
    """Tests for JavaScript generator module."""

    def test_get_theme_toggle_js(self):
        """Test theme toggle JavaScript generation."""
        from js_generator import get_theme_toggle_js

        result = get_theme_toggle_js()
        assert "localStorage" in result
        assert "theme-toggle" in result
        assert "light-mode" in result
        assert "dark-mode" in result

    def test_get_lazy_loading_js(self):
        """Test lazy loading JavaScript generation."""
        from js_generator import get_lazy_loading_js

        result = get_lazy_loading_js()
        assert "IntersectionObserver" in result
        assert "data-src" in result
        assert "lazy-loaded" in result

    def test_get_web_vitals_js(self):
        """Test Web Vitals tracking JavaScript."""
        from js_generator import get_web_vitals_js

        result = get_web_vitals_js()
        assert "PerformanceObserver" in result
        assert "LCP" in result
        assert "FID" in result
        assert "CLS" in result

    def test_generate_complete_js(self):
        """Test complete JavaScript generation."""
        from js_generator import generate_complete_js

        result = generate_complete_js(
            enable_lazy_loading=True, enable_web_vitals=True, enable_pwa=True
        )
        assert "<script>" in result
        assert "</script>" in result
        assert "serviceWorker" in result


class TestPWAGenerator:
    """Tests for PWA asset generation."""

    def test_generate_manifest(self):
        """Test PWA manifest generation."""
        from pwa_generator import generate_manifest

        result = generate_manifest()
        manifest = json.loads(result)

        assert manifest["name"] == "CMMC Watch"
        assert manifest["display"] == "standalone"
        assert len(manifest["icons"]) > 0
        assert manifest["start_url"] == "/"

    def test_generate_service_worker(self):
        """Test service worker generation."""
        from pwa_generator import generate_service_worker

        result = generate_service_worker()

        assert "CACHE_NAME" in result
        assert "install" in result
        assert "activate" in result
        assert "fetch" in result

    def test_generate_offline_page(self):
        """Test offline page generation."""
        from pwa_generator import generate_offline_page

        result = generate_offline_page()

        assert "<!DOCTYPE html>" in result
        assert "Offline" in result
        assert "Try Again" in result


class TestSitemapGenerator:
    """Tests for sitemap generation."""

    def test_generate_sitemap_basic(self):
        """Test basic sitemap generation."""
        from sitemap_generator import generate_sitemap

        result = generate_sitemap()

        assert '<?xml version="1.0"' in result
        assert "urlset" in result
        assert "https://cmmcwatch.com/" in result

    def test_generate_sitemap_with_archives(self):
        """Test sitemap with archive dates."""
        from sitemap_generator import generate_sitemap

        archive_dates = ["2025-12-30", "2025-12-29"]
        result = generate_sitemap(archive_dates=archive_dates)

        for date in archive_dates:
            assert date in result

    def test_generate_robots_txt(self):
        """Test robots.txt generation."""
        from sitemap_generator import generate_robots_txt

        result = generate_robots_txt()

        assert "User-agent: *" in result
        assert "Sitemap:" in result
        assert "sitemap.xml" in result


class TestDesignGenerator:
    """Tests for design generator integration."""

    def test_design_spec_has_new_fields(self):
        """Test that DesignSpec includes new dimension fields."""
        from generate_design import DesignSpec

        spec = DesignSpec()

        assert hasattr(spec, "image_treatment")
        assert hasattr(spec, "typography_scale")
        assert hasattr(spec, "section_divider")
        assert hasattr(spec, "card_aspect_ratio")
        assert hasattr(spec, "content_sentiment")
        assert hasattr(spec, "contrast_validated")

    def test_design_spec_defaults(self):
        """Test DesignSpec default values."""
        from generate_design import DesignSpec

        spec = DesignSpec()

        assert spec.image_treatment == "none"
        assert spec.section_divider == "none"
        assert spec.card_aspect_ratio == "auto"
        assert spec.content_sentiment == "neutral"
        assert spec.contrast_validated is True
