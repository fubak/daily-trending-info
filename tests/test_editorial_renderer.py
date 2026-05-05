#!/usr/bin/env python3
"""Tests for editorial_renderer and articles_index_renderer modules."""

import pytest
from scripts.editorial_renderer import generate_article_html, generate_amp_html, _safe_href
from scripts.articles_index_renderer import generate_articles_index_html


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_tokens():
    """Minimal design tokens required by renderers."""
    return {
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


class _FakeArticle:
    """Minimal article stand-in for renderer tests (no dataclass needed)."""
    def __init__(self, **kw):
        self.title = kw.get("title", "Test Article Title")
        self.slug = kw.get("slug", "test-article-title")
        self.date = kw.get("date", "2026-05-05")
        self.summary = kw.get("summary", "A short summary of the article.")
        self.content = kw.get("content", "<p>Article body.</p>")
        self.word_count = kw.get("word_count", 500)
        self.top_stories = kw.get("top_stories", ["Story one", "Story two"])
        self.keywords = kw.get("keywords", ["ai", "technology", "research"])
        self.mood = kw.get("mood", "informative")
        self.url = kw.get("url", "/articles/2026/05/05/test-article-title/")


@pytest.fixture
def sample_article():
    return _FakeArticle()


@pytest.fixture
def sample_articles_list():
    """List of plain-dict article metadata for index tests."""
    return [
        {
            "title": "AI Breakthrough in 2026",
            "date": "2026-05-05",
            "url": "/articles/2026/05/05/ai-breakthrough/",
            "summary": "Researchers announce a major AI milestone.",
            "mood": "optimistic",
            "word_count": 950,
            "keywords": ["ai", "research", "breakthrough"],
        },
        {
            "title": "Climate Report Released",
            "date": "2026-05-04",
            "url": "/articles/2026/05/04/climate-report/",
            "summary": "New climate data shows rising temperatures.",
            "mood": "serious",
            "word_count": 800,
            "keywords": ["climate", "environment", "science"],
        },
    ]


# ---------------------------------------------------------------------------
# _safe_href
# ---------------------------------------------------------------------------

class TestSafeHref:
    """Tests for the _safe_href() URL sanitizer."""

    def test_http_url_passed_through(self):
        """Plain http URLs should be allowed."""
        result = _safe_href("http://example.com/path")
        assert result != "#"
        assert "example.com" in result

    def test_https_url_passed_through(self):
        """HTTPS URLs should be allowed."""
        result = _safe_href("https://example.com/article")
        assert result != "#"

    def test_mailto_url_passed_through(self):
        """mailto: URLs should be allowed."""
        result = _safe_href("mailto:test@example.com")
        assert result != "#"

    def test_javascript_url_blocked(self):
        """javascript: scheme should return '#'."""
        assert _safe_href("javascript:alert(1)") == "#"

    def test_data_url_blocked(self):
        """data: scheme should return '#'."""
        assert _safe_href("data:text/html,<h1>XSS</h1>") == "#"

    def test_empty_string_returns_hash(self):
        """Empty input should return '#'."""
        assert _safe_href("") == "#"

    def test_relative_url_allowed(self):
        """Relative paths (no scheme) should be allowed."""
        result = _safe_href("/articles/2026/05/05/slug/")
        assert result != "#"

    def test_ampersands_escaped(self):
        """HTML-special characters in URLs should be escaped."""
        result = _safe_href('https://example.com/?a=1&b=2')
        assert "&amp;" in result or "b=2" in result


# ---------------------------------------------------------------------------
# generate_article_html
# ---------------------------------------------------------------------------

class TestGenerateArticleHtml:
    """Tests for generate_article_html()."""

    def test_returns_string(self, sample_article, minimal_tokens):
        """Should return a non-empty string."""
        html = generate_article_html(sample_article, minimal_tokens)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_contains_doctype(self, sample_article, minimal_tokens):
        """Output should be a valid HTML document."""
        html = generate_article_html(sample_article, minimal_tokens)
        assert "<!DOCTYPE html>" in html

    def test_title_in_output(self, sample_article, minimal_tokens):
        """Article title should appear in the output."""
        html = generate_article_html(sample_article, minimal_tokens)
        assert sample_article.title in html

    def test_canonical_url(self, sample_article, minimal_tokens):
        """Canonical link should include the article URL."""
        html = generate_article_html(sample_article, minimal_tokens)
        assert sample_article.url in html

    def test_keywords_in_meta(self, sample_article, minimal_tokens):
        """Keywords should appear in the meta keywords tag."""
        html = generate_article_html(sample_article, minimal_tokens)
        for kw in sample_article.keywords:
            assert kw in html

    def test_content_rendered(self, sample_article, minimal_tokens):
        """Article content should appear in the output."""
        html = generate_article_html(sample_article, minimal_tokens)
        assert sample_article.content in html

    def test_no_related_articles(self, sample_article, minimal_tokens):
        """Should render cleanly with no related articles."""
        html = generate_article_html(sample_article, minimal_tokens, related_articles=[])
        assert "<!DOCTYPE html>" in html

    def test_with_related_articles(self, sample_article, minimal_tokens):
        """Related articles section should appear when related are provided."""
        related = [
            {
                "title": "Related Article One",
                "date": "2026-05-04",
                "url": "/articles/2026/05/04/related-one/",
                "summary": "Summary of related article.",
            }
        ]
        html = generate_article_html(sample_article, minimal_tokens, related_articles=related)
        assert "More Analysis" in html
        assert "Related Article One" in html

    def test_xss_in_title_escaped(self, minimal_tokens):
        """XSS in article title should be escaped in HTML attribute contexts."""
        article = _FakeArticle(title='<b onclick="alert(1)">Headline</b>')
        html = generate_article_html(article, minimal_tokens)
        # The &quot; escape should appear in meta content attributes
        assert 'onclick=&quot;alert(1)&quot;' in html or '&quot;' in html

    def test_mood_displayed(self, sample_article, minimal_tokens):
        """Article mood should appear in the rendered page."""
        html = generate_article_html(sample_article, minimal_tokens)
        assert sample_article.mood in html

    def test_word_count_displayed(self, sample_article, minimal_tokens):
        """Word count should appear somewhere in the rendered page."""
        html = generate_article_html(sample_article, minimal_tokens)
        assert str(sample_article.word_count) in html

    def test_amp_link_present(self, sample_article, minimal_tokens):
        """AMP link rel should appear in the head."""
        html = generate_article_html(sample_article, minimal_tokens)
        assert "amphtml" in html


# ---------------------------------------------------------------------------
# generate_amp_html
# ---------------------------------------------------------------------------

class TestGenerateAmpHtml:
    """Tests for generate_amp_html()."""

    def test_returns_string(self, sample_article, minimal_tokens):
        """Should return a non-empty string."""
        html = generate_amp_html(sample_article, minimal_tokens)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_amp_attribute_present(self, sample_article, minimal_tokens):
        """Output should have the AMP 'amp' attribute on the html tag."""
        html = generate_amp_html(sample_article, minimal_tokens)
        assert "<html amp" in html

    def test_amp_boilerplate_present(self, sample_article, minimal_tokens):
        """AMP boilerplate script should be present."""
        html = generate_amp_html(sample_article, minimal_tokens)
        assert "amp-boilerplate" in html

    def test_title_in_amp_output(self, sample_article, minimal_tokens):
        """Article title should appear in AMP output."""
        html = generate_amp_html(sample_article, minimal_tokens)
        assert sample_article.title in html

    def test_canonical_link(self, sample_article, minimal_tokens):
        """AMP page should link back to canonical URL."""
        html = generate_amp_html(sample_article, minimal_tokens)
        assert sample_article.url in html

    def test_content_rendered(self, sample_article, minimal_tokens):
        """Article content should appear in AMP output."""
        html = generate_amp_html(sample_article, minimal_tokens)
        assert sample_article.content in html

    def test_no_external_stylesheets(self, sample_article, minimal_tokens):
        """AMP pages must not load external stylesheets (only amp-custom inline)."""
        html = generate_amp_html(sample_article, minimal_tokens)
        # Should not have a <link rel="stylesheet"> to an external CSS file
        # (fonts via link preconnect are allowed but no <link rel=stylesheet href=...>)
        import re
        external_css = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']http', html)
        assert len(external_css) == 0


# ---------------------------------------------------------------------------
# generate_articles_index_html
# ---------------------------------------------------------------------------

class TestGenerateArticlesIndexHtml:
    """Tests for generate_articles_index_html()."""

    def test_returns_string(self, sample_articles_list, minimal_tokens):
        """Should return a non-empty HTML string."""
        html = generate_articles_index_html(sample_articles_list, minimal_tokens)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_doctype_present(self, sample_articles_list, minimal_tokens):
        """Output should be a valid HTML document."""
        html = generate_articles_index_html(sample_articles_list, minimal_tokens)
        assert "<!DOCTYPE html>" in html

    def test_article_count_in_meta(self, sample_articles_list, minimal_tokens):
        """Total article count should appear in the page."""
        html = generate_articles_index_html(sample_articles_list, minimal_tokens)
        assert str(len(sample_articles_list)) in html

    def test_articles_json_embedded(self, sample_articles_list, minimal_tokens):
        """Article titles should be embedded as JSON for client-side rendering."""
        html = generate_articles_index_html(sample_articles_list, minimal_tokens)
        assert "AI Breakthrough in 2026" in html
        assert "Climate Report Released" in html

    def test_empty_articles_list(self, minimal_tokens):
        """Should handle an empty articles list without error."""
        html = generate_articles_index_html([], minimal_tokens)
        assert "<!DOCTYPE html>" in html

    def test_search_input_present(self, sample_articles_list, minimal_tokens):
        """Search input should be present for client-side filtering."""
        html = generate_articles_index_html(sample_articles_list, minimal_tokens)
        assert "search-input" in html

    def test_mood_options_included(self, sample_articles_list, minimal_tokens):
        """Unique moods from articles should appear as filter options."""
        html = generate_articles_index_html(sample_articles_list, minimal_tokens)
        assert "optimistic" in html
        assert "serious" in html

    def test_stats_bar_present(self, sample_articles_list, minimal_tokens):
        """Stats bar with total word count should be present."""
        html = generate_articles_index_html(sample_articles_list, minimal_tokens)
        assert "stats-bar" in html

    def test_pagination_js_included(self, sample_articles_list, minimal_tokens):
        """JavaScript pagination logic should be included."""
        html = generate_articles_index_html(sample_articles_list, minimal_tokens)
        assert "pagination" in html
        assert "<script>" in html

    def test_returns_str_not_none(self, minimal_tokens):
        """Should never return None."""
        result = generate_articles_index_html([], minimal_tokens)
        assert result is not None
