"""Tests for media_page_generator (build_media_page + generate_media_page)."""

import pytest

from scripts.media_page_generator import (
    _safe_str,
    build_media_page,
    generate_media_page,
)


@pytest.fixture
def minimal_design():
    return {
        "color_bg": "#0a0a0a",
        "color_card_bg": "#18181b",
        "color_text": "#ffffff",
        "color_muted": "#a1a1aa",
        "color_border": "#27272a",
        "color_accent": "#6366f1",
        "color_accent_secondary": "#8b5cf6",
        "font_primary": "Space Grotesk",
        "font_secondary": "Inter",
        "is_dark_mode": True,
    }


@pytest.fixture
def sample_media_data():
    return {
        "image_of_day": {
            "title": "Andromeda Galaxy",
            "description": "Our nearest spiral neighbour.",
            "url": "https://apod.nasa.gov/apod/image/andromeda.jpg",
            "credit": "NASA",
            "source": "nasa_apod",
            "date": "2026-05-08",
        },
        "video_of_day": {
            "title": "Vimeo Staff Pick",
            "description": "Short film of the day.",
            "url": "https://vimeo.com/12345",
            "thumbnail": "https://i.vimeocdn.com/12345.jpg",
            "creator": "A. Filmmaker",
            "source": "vimeo_staff_picks",
        },
    }


class TestSafeStr:
    """Tests for the _safe_str() helper."""

    def test_none_returns_default(self):
        assert _safe_str(None) == ""
        assert _safe_str(None, "fallback") == "fallback"

    def test_string_passthrough(self):
        assert _safe_str("hello") == "hello"

    def test_first_element_of_list(self):
        assert _safe_str(["a", "b", "c"]) == "a"

    def test_empty_list_returns_default(self):
        assert _safe_str([], "default") == "default"

    def test_coerces_int_to_string(self):
        assert _safe_str(42) == "42"


class TestBuildMediaPage:
    """Tests for build_media_page() HTML generation."""

    def test_returns_non_empty_string(self, sample_media_data, minimal_design):
        html = build_media_page(sample_media_data, minimal_design)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_doctype_present(self, sample_media_data, minimal_design):
        html = build_media_page(sample_media_data, minimal_design)
        assert "<!DOCTYPE html>" in html

    def test_image_title_appears(self, sample_media_data, minimal_design):
        html = build_media_page(sample_media_data, minimal_design)
        assert "Andromeda Galaxy" in html

    def test_video_title_appears(self, sample_media_data, minimal_design):
        html = build_media_page(sample_media_data, minimal_design)
        assert "Vimeo Staff Pick" in html

    def test_empty_media_data_renders(self, minimal_design):
        html = build_media_page({}, minimal_design)
        assert "<!DOCTYPE html>" in html

    def test_handles_missing_image_fields(self, minimal_design):
        media = {"image_of_day": {}, "video_of_day": {}}
        html = build_media_page(media, minimal_design)
        assert "<!DOCTYPE html>" in html

    def test_xss_in_image_title_escaped(self, minimal_design):
        media = {
            "image_of_day": {
                "title": '<script>alert(1)</script>',
                "url": "https://example.com/x.jpg",
            }
        }
        html = build_media_page(media, minimal_design)
        # The literal <script> tag must not survive into the rendered output.
        assert "<script>alert(1)</script>" not in html

    def test_malicious_color_token_neutralised(self, sample_media_data):
        # CSS injection via design tokens is blocked by design_tokens.safe_color.
        bad_design = {"color_bg": "red}body{display:none}"}
        html = build_media_page(sample_media_data, bad_design)
        assert "display:none" not in html

    def test_uses_default_colors_for_invalid_input(self, sample_media_data):
        html = build_media_page(sample_media_data, {})
        assert "<!DOCTYPE html>" in html

    def test_dark_mode_class(self, sample_media_data, minimal_design):
        html = build_media_page(sample_media_data, minimal_design)
        assert "dark-mode" in html

    def test_light_mode_class(self, sample_media_data):
        design = {"is_dark_mode": False}
        html = build_media_page(sample_media_data, design)
        assert "light-mode" in html


class TestGenerateMediaPage:
    """Tests for generate_media_page() file output."""

    def test_writes_index_html(self, tmp_path, sample_media_data, minimal_design):
        result = generate_media_page(tmp_path, sample_media_data, minimal_design)
        assert result is True
        index_file = tmp_path / "media" / "index.html"
        assert index_file.exists()
        content = index_file.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Andromeda Galaxy" in content

    def test_creates_media_directory(self, tmp_path, sample_media_data, minimal_design):
        # Make sure /media is created even if it didn't exist.
        result = generate_media_page(tmp_path, sample_media_data, minimal_design)
        assert result is True
        assert (tmp_path / "media").is_dir()

    def test_returns_false_on_unwritable_path(
        self, sample_media_data, minimal_design
    ):
        # Pointing at a path inside a non-existent root that can't be created
        # should be caught and return False.
        from pathlib import Path
        bogus = Path("/proc/1/nope_unwritable")
        result = generate_media_page(bogus, sample_media_data, minimal_design)
        assert result is False
