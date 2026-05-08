"""Tests for url_safety.safe_href() and safe_image_src()."""

import pytest

from scripts.url_safety import safe_href, safe_image_src


class TestSafeHref:
    """`safe_href()` allows http/https/mailto and relative paths only."""

    def test_https_url(self):
        assert safe_href("https://example.com/article") == (
            "https://example.com/article"
        )

    def test_http_url(self):
        assert safe_href("http://example.com") == "http://example.com"

    def test_mailto(self):
        assert safe_href("mailto:test@example.com") == "mailto:test@example.com"

    def test_relative_path(self):
        assert safe_href("/articles/2026/05/08/") == "/articles/2026/05/08/"

    def test_javascript_blocked(self):
        assert safe_href("javascript:alert(1)") == "#"

    def test_javascript_uppercase_blocked(self):
        assert safe_href("JavaScript:alert(1)") == "#"

    def test_javascript_with_whitespace_blocked(self):
        # urlparse strips leading whitespace; the strip() call inside
        # safe_href further normalises this.
        assert safe_href("  javascript:alert(1)  ") == "#"

    def test_data_url_blocked(self):
        assert safe_href("data:text/html,<h1>x</h1>") == "#"

    def test_vbscript_blocked(self):
        assert safe_href("vbscript:msgbox(1)") == "#"

    def test_file_url_blocked(self):
        assert safe_href("file:///etc/passwd") == "#"

    def test_empty_string(self):
        assert safe_href("") == "#"

    def test_none(self):
        assert safe_href(None) == "#"

    def test_html_escaping_applied(self):
        # Quote characters must be escaped so the URL stays inside its
        # attribute even after concatenation.
        result = safe_href('https://example.com/?q="><script>')
        assert "<script>" not in result
        assert "&quot;" in result or "&gt;" in result

    def test_ampersand_escaped(self):
        result = safe_href("https://example.com/?a=1&b=2")
        assert "&amp;" in result

    def test_non_string_coerced(self):
        # A weird input type shouldn't crash — gets coerced via str().
        assert safe_href(12345) == "#" or "12345" in safe_href(12345)


class TestSafeImageSrc:
    """`safe_image_src()` is stricter — only http/https/relative pass."""

    def test_https_passes(self):
        assert safe_image_src("https://images.example.com/x.jpg") == (
            "https://images.example.com/x.jpg"
        )

    def test_http_passes(self):
        assert safe_image_src("http://x.com/y.jpg") == "http://x.com/y.jpg"

    def test_relative_path_passes(self):
        assert safe_image_src("/img/photo.jpg") == "/img/photo.jpg"

    def test_javascript_returns_empty(self):
        # Stricter than safe_href — empty string so callers can omit the
        # element rather than emit a broken `src=""`.
        assert safe_image_src("javascript:alert(1)") == ""

    def test_data_url_returns_empty(self):
        # Even data:image/* is rejected here; callers using inline data
        # URLs would build their own attribute.
        assert safe_image_src("data:image/png;base64,iVBORw0KG") == ""

    def test_mailto_returns_empty(self):
        # mailto is fine for href but meaningless for an image src.
        assert safe_image_src("mailto:x@y.com") == ""

    def test_empty_string_returns_empty(self):
        assert safe_image_src("") == ""

    def test_none_returns_empty(self):
        assert safe_image_src(None) == ""

    def test_quote_escaped(self):
        # Defensive: still escape attribute-breakers even on http(s).
        result = safe_image_src('https://example.com/x.jpg"><script>')
        assert "<script>" not in result


class TestRegressions:
    """Specific attack payloads from past CVE patterns."""

    def test_unicode_homograph_javascript_still_blocked(self):
        # Most parsers normalise this to ASCII before scheme parsing,
        # but urlparse doesn't — so the literal string "javascript" is
        # what we check. Confirm that the simple ascii form is blocked.
        for variant in [
            "javascript:alert(1)",
            "JAVASCRIPT:alert(1)",
            "JaVaScRiPt:alert(1)",
        ]:
            assert safe_href(variant) == "#", f"Failed to block: {variant}"

    def test_padded_javascript_blocked(self):
        # Some browsers tolerate a leading tab/newline in href schemes.
        # Our strip() handles the whitespace; this is a regression guard.
        for variant in ["\tjavascript:alert(1)", "\njavascript:alert(1)"]:
            assert safe_href(variant) == "#", f"Failed to block: {variant!r}"
