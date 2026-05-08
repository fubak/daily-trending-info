"""Tests for design_tokens validators (CSS injection defence)."""

import pytest

from scripts.design_tokens import (
    safe_color,
    safe_font,
    safe_mode,
    validate_design_tokens,
)


class TestSafeColor:
    """Tests for the safe_color validator."""

    def test_hex_3_digit(self):
        assert safe_color("#fff") == "#fff"

    def test_hex_6_digit(self):
        assert safe_color("#0f0f23") == "#0f0f23"

    def test_hex_8_digit_with_alpha(self):
        assert safe_color("#0f0f23aa") == "#0f0f23aa"

    def test_rgb(self):
        assert safe_color("rgb(255, 0, 128)") == "rgb(255, 0, 128)"

    def test_rgba(self):
        assert safe_color("rgba(0, 0, 0, 0.5)") == "rgba(0, 0, 0, 0.5)"

    def test_hsl(self):
        assert safe_color("hsl(120, 50%, 50%)") == "hsl(120, 50%, 50%)"

    def test_named_keyword(self):
        assert safe_color("transparent") == "transparent"
        assert safe_color("currentColor") == "currentColor"

    def test_strips_whitespace(self):
        assert safe_color("  #fff  ") == "#fff"

    def test_blocks_css_breakout(self):
        attack = "#fff}body{background:url(javascript:alert(1))}"
        assert safe_color(attack) == "#000000"

    def test_blocks_url_function(self):
        # url() is not a color literal — must be rejected.
        assert safe_color("url(http://evil.com/x.css)") == "#000000"

    def test_blocks_expression(self):
        assert safe_color("expression(alert(1))") == "#000000"

    def test_blocks_arbitrary_text(self):
        assert safe_color("red; background: url(x)") == "#000000"

    def test_uses_custom_fallback(self):
        assert safe_color("invalid", fallback="#abcdef") == "#abcdef"

    def test_none_input(self):
        assert safe_color(None) == "#000000"

    def test_non_string_input(self):
        assert safe_color(123) == "#000000"
        assert safe_color({"x": 1}) == "#000000"


class TestSafeFont:
    """Tests for the safe_font validator."""

    def test_simple_font_name(self):
        assert safe_font("Inter") == "Inter"

    def test_multi_word_font(self):
        assert safe_font("Space Grotesk") == "Space Grotesk"

    def test_hyphenated_font(self):
        assert safe_font("Roboto-Bold") == "Roboto-Bold"

    def test_blocks_css_breakout(self):
        # If a font name contained `}` or `;`, it would break out of CSS.
        assert safe_font("Inter}body{display:none}") == "Inter"

    def test_blocks_quotes(self):
        assert safe_font('Inter"></style><script>') == "Inter"

    def test_uses_custom_fallback(self):
        assert safe_font("inv;alid", fallback="MyFont") == "MyFont"

    def test_none_input(self):
        assert safe_font(None) == "Inter"


class TestSafeMode:
    """Tests for the safe_mode validator."""

    def test_dark_mode(self):
        assert safe_mode("dark-mode") == "dark-mode"

    def test_light_mode(self):
        assert safe_mode("light-mode") == "light-mode"

    def test_blocks_quote(self):
        assert safe_mode('"><script>alert(1)</script>') == "dark-mode"

    def test_blocks_space(self):
        # Spaces are not allowed in a single class identifier.
        assert safe_mode("dark mode") == "dark-mode"

    def test_none_input(self):
        assert safe_mode(None) == "dark-mode"


class TestValidateDesignTokens:
    """Tests for the dict-level validator."""

    def test_valid_tokens_pass_through(self):
        tokens = {
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
        result = validate_design_tokens(tokens)
        assert result["primary_color"] == "#667eea"
        assert result["font_primary"] == "Space Grotesk"

    def test_replaces_malicious_color(self):
        tokens = {"primary_color": "red}body{display:none"}
        result = validate_design_tokens(tokens)
        assert "}" not in result["primary_color"]
        assert "display:none" not in result["primary_color"]

    def test_replaces_malicious_font(self):
        tokens = {"font_primary": "Inter; background: url(evil.com)"}
        result = validate_design_tokens(tokens)
        assert ";" not in result["font_primary"]

    def test_missing_keys_get_fallback(self):
        result = validate_design_tokens({})
        assert result["primary_color"] == "#667eea"
        assert result["font_primary"] == "Inter"
        assert result["base_mode"] == "dark-mode"

    def test_unknown_keys_pass_through(self):
        tokens = {"primary_color": "#fff", "extra_metadata": "anything goes"}
        result = validate_design_tokens(tokens)
        assert result["extra_metadata"] == "anything goes"

    def test_non_dict_input_returns_safe_defaults(self):
        result = validate_design_tokens(None)
        assert result["primary_color"] == "#667eea"
        result = validate_design_tokens("not a dict")
        assert result["font_primary"] == "Inter"
