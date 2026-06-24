"""Tests for shared_components HTML builders."""

import pytest

from scripts.shared_components import (
    build_footer,
    build_google_fonts_link,
    build_header,
    get_footer_styles,
    get_header_styles,
    get_nav_links,
    get_theme_script,
)


class TestGetNavLinks:
    """Nav link builder."""

    def test_returns_string(self):
        result = get_nav_links()
        assert isinstance(result, str)

    def test_contains_home_link(self):
        result = get_nav_links()
        assert 'href="/"' in result
        assert ">Home<" in result

    def test_contains_articles_link(self):
        result = get_nav_links("articles")
        assert 'href="/articles/"' in result

    def test_active_class_applied_to_active_page(self):
        result = get_nav_links("tech")
        # The tech link should carry class="active".
        assert 'href="/tech/"' in result
        # Find the tech <li> and verify it has the active class.
        import re
        tech_match = re.search(r'<li><a href="/tech/"([^>]*)>', result)
        assert tech_match is not None
        assert 'class="active"' in tech_match.group(1)

    def test_no_active_class_when_no_match(self):
        result = get_nav_links()
        assert 'class="active"' not in result

    def test_includes_archive_link(self):
        result = get_nav_links()
        assert 'href="/archive/"' in result


class TestBuildHeader:
    """Header builder with nav + branding."""

    def test_returns_string(self):
        result = build_header()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_nav(self):
        result = build_header()
        assert "<nav" in result

    def test_contains_logo(self):
        result = build_header()
        assert "DailyTrending.info" in result

    def test_accepts_date_str_kwarg(self):
        # date_str is accepted for API compatibility (footer uses it).
        # Smoke test: no crash, returns valid HTML.
        result = build_header(date_str="May 8, 2026")
        assert "<nav" in result

    def test_xss_in_date_str_does_not_crash(self):
        # Defensive: malicious date_str shouldn't propagate raw into the page.
        result = build_header(date_str='<script>alert(1)</script>')
        assert "<script>alert(1)</script>" not in result

    def test_active_page_marks_correct_link(self):
        result = build_header(active_page="tech")
        import re
        tech_match = re.search(r'<li><a href="/tech/"([^>]*)>', result)
        assert tech_match
        assert "active" in tech_match.group(1)


class TestBuildFooter:
    """Footer builder."""

    def test_returns_string(self):
        assert isinstance(build_footer(), str)

    def test_contains_footer_tag(self):
        result = build_footer()
        assert "<footer" in result

    def test_default_date_present(self):
        from datetime import datetime
        today = datetime.now().strftime("%B %d, %Y")
        assert today in build_footer()

    def test_style_info_rendered(self):
        result = build_footer(style_info="Built with Python")
        assert "Built with Python" in result

    def test_style_info_passed_through(self):
        # When style_info is provided it appears as an extra paragraph.
        with_style = build_footer(style_info="Built with Python")
        without_style = build_footer()
        # The "Built with Python" text only appears when style_info is set.
        assert "Built with Python" in with_style
        assert "Built with Python" not in without_style

    def test_xss_in_style_info_escaped(self):
        result = build_footer(style_info='<img src=x onerror=alert(1)>')
        assert "<img src=x" not in result

    def test_xss_in_date_str_escaped(self):
        result = build_footer(date_str='<script>alert(1)</script>')
        assert "<script>alert(1)</script>" not in result


class TestStyleAndScriptHelpers:
    """Smoke tests for the style/script helper getters."""

    def test_header_styles_returns_string(self):
        result = get_header_styles()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_footer_styles_returns_string(self):
        result = get_footer_styles()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_theme_script_returns_string(self):
        result = get_theme_script()
        assert isinstance(result, str)
        assert "<script>" in result


class TestBuildGoogleFontsLink:
    """The font-link helper must reproduce, byte-for-byte, the links the
    renderers previously inlined — otherwise adopting it would silently break
    web-font loading on those pages."""

    def test_articles_and_editorial_pattern(self):
        # secondary-first, primary at 600;700
        link = build_google_fonts_link(
            [("Inter", "400;500;600;700"), ("Newsreader", "600;700")]
        )
        assert link == (
            '<link href="https://fonts.googleapis.com/css2?'
            "family=Inter:wght@400;500;600;700&family=Newsreader:wght@600;700"
            '&display=swap" rel="stylesheet">'
        )

    def test_topic_and_media_pattern(self):
        # primary-first, primary includes weight 800
        link = build_google_fonts_link(
            [("Newsreader", "400;500;600;700;800"), ("Inter", "400;500;600;700")]
        )
        assert link == (
            '<link href="https://fonts.googleapis.com/css2?'
            "family=Newsreader:wght@400;500;600;700;800"
            "&family=Inter:wght@400;500;600;700"
            '&display=swap" rel="stylesheet">'
        )

    def test_multiword_font_name_uses_plus(self):
        # Spaces in font names must become '+' (Google Fonts API requirement).
        link = build_google_fonts_link([("Space Grotesk", "400;500;600;700")])
        assert "family=Space+Grotesk:wght@400;500;600;700" in link
        # No raw space in the query/family portion (it would break the URL).
        family_part = link.split("css2?")[1].split("&display")[0]
        assert " " not in family_part
