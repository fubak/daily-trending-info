"""Tests for html_sanitizer.sanitize_article_html()."""

import pytest
from scripts.html_sanitizer import sanitize_article_html


class TestSanitizeArticleHtml:
    """Verify the LLM-content sanitizer strips dangerous markup."""

    def test_empty_string(self):
        assert sanitize_article_html("") == ""

    def test_safe_paragraph_preserved(self):
        result = sanitize_article_html("<p>Hello, world.</p>")
        assert "<p>" in result
        assert "Hello, world." in result

    def test_strips_script_block_with_content(self):
        result = sanitize_article_html("Before<script>alert(1)</script>After")
        assert "<script>" not in result
        assert "alert(1)" not in result
        assert "Before" in result
        assert "After" in result

    def test_strips_iframe(self):
        result = sanitize_article_html(
            '<p>Hi</p><iframe src="https://evil.com"></iframe>'
        )
        assert "<iframe" not in result
        assert "evil.com" not in result

    def test_strips_style_block(self):
        result = sanitize_article_html("<style>body{display:none}</style><p>x</p>")
        assert "<style>" not in result
        assert "display:none" not in result
        assert "<p>x</p>" in result

    def test_strips_event_handler_attribute(self):
        result = sanitize_article_html('<p onclick="alert(1)">Hi</p>')
        assert "onclick" not in result
        assert "alert(1)" not in result
        assert "Hi" in result

    def test_javascript_url_in_href_blocked(self):
        result = sanitize_article_html('<a href="javascript:alert(1)">click</a>')
        assert "javascript:" not in result

    def test_data_url_in_href_blocked(self):
        result = sanitize_article_html('<a href="data:text/plain,hello">x</a>')
        assert 'href="data:' not in result

    def test_https_url_in_href_preserved(self):
        result = sanitize_article_html('<a href="https://example.com">link</a>')
        assert 'href="https://example.com"' in result

    def test_disallowed_tag_dropped_text_kept(self):
        result = sanitize_article_html("<marquee>Hello</marquee>")
        assert "<marquee>" not in result
        assert "Hello" in result

    def test_allowed_formatting_preserved(self):
        result = sanitize_article_html(
            "<p><strong>bold</strong> and <em>italic</em></p>"
        )
        assert "<strong>" in result
        assert "</strong>" in result
        assert "<em>" in result
        assert "bold" in result
        assert "italic" in result

    def test_allowed_blockquote_preserved(self):
        result = sanitize_article_html("<blockquote>Quote</blockquote>")
        assert "<blockquote>" in result
        assert "Quote" in result

    def test_allowed_lists_preserved(self):
        result = sanitize_article_html("<ul><li>A</li><li>B</li></ul>")
        assert "<ul>" in result
        assert "<li>" in result
        assert "A" in result
        assert "B" in result

    def test_unknown_attribute_on_allowed_tag_stripped(self):
        # <p> has no allowed attributes — all attrs should be dropped.
        result = sanitize_article_html('<p style="color:red" id="x">Hi</p>')
        assert "style=" not in result
        assert "id=" not in result
        assert "<p>Hi</p>" in result

    def test_link_title_attribute_preserved(self):
        # <a> allows title and href.
        result = sanitize_article_html(
            '<a href="https://example.com" title="A site">link</a>'
        )
        assert 'title="A site"' in result

    def test_nested_script_in_blockquote_stripped(self):
        result = sanitize_article_html(
            "<blockquote><script>alert(1)</script>safe text</blockquote>"
        )
        assert "<script>" not in result
        assert "alert(1)" not in result
        assert "safe text" in result

    def test_self_closing_br_preserved(self):
        result = sanitize_article_html("Line1<br>Line2")
        assert "<br>" in result

    def test_uppercase_script_tag_stripped(self):
        result = sanitize_article_html("<SCRIPT>alert(1)</SCRIPT>")
        assert "alert(1)" not in result
