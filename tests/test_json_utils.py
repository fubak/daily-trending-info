"""Tests for json_utils.escape_control_chars_in_strings()."""

import json

from scripts.json_utils import escape_control_chars_in_strings


class TestEscapeControlChars:
    """Verify control-char escaping inside JSON string values."""

    def test_clean_json_unchanged(self):
        original = '{"key": "value", "n": 42}'
        assert escape_control_chars_in_strings(original) == original

    def test_escapes_raw_newline_inside_string(self):
        # An LLM might emit "summary": "first line\nsecond line" with a raw
        # newline character — invalid JSON. The util should escape it.
        broken = '{"summary": "first\nsecond"}'
        fixed = escape_control_chars_in_strings(broken)
        assert "\n" not in fixed
        assert "\\n" in fixed
        # Result is now valid JSON.
        parsed = json.loads(fixed)
        assert parsed["summary"] == "first\nsecond"

    def test_escapes_raw_tab(self):
        broken = '{"k": "a\tb"}'
        fixed = escape_control_chars_in_strings(broken)
        assert json.loads(fixed)["k"] == "a\tb"

    def test_escapes_raw_carriage_return(self):
        broken = '{"k": "a\rb"}'
        fixed = escape_control_chars_in_strings(broken)
        assert json.loads(fixed)["k"] == "a\rb"

    def test_escapes_low_control_char(self):
        # \x07 (BEL) is a control char that breaks json.loads if raw.
        broken = '{"k": "a\x07b"}'
        fixed = escape_control_chars_in_strings(broken)
        parsed = json.loads(fixed)
        assert parsed["k"] == "a\x07b"

    def test_does_not_corrupt_existing_escape_sequences(self):
        original = '{"k": "already \\n escaped"}'
        # The string already has \n escaped properly; result should still
        # parse to "already \n escaped".
        fixed = escape_control_chars_in_strings(original)
        assert json.loads(fixed)["k"] == "already \n escaped"

    def test_preserves_structural_whitespace(self):
        # Whitespace outside string literals (including raw newlines)
        # is left alone — only inside-quotes whitespace is escaped.
        original = '{\n  "key": "value"\n}'
        fixed = escape_control_chars_in_strings(original)
        # Newlines outside the string are still there.
        assert fixed.count("\n") == 2
        # Parses cleanly.
        assert json.loads(fixed) == {"key": "value"}

    def test_handles_empty_string(self):
        assert escape_control_chars_in_strings("") == ""

    def test_handles_quoted_empty_string(self):
        assert escape_control_chars_in_strings('""') == '""'

    def test_handles_multiple_strings(self):
        broken = '{"a": "x\ny", "b": "p\tq"}'
        fixed = escape_control_chars_in_strings(broken)
        parsed = json.loads(fixed)
        assert parsed == {"a": "x\ny", "b": "p\tq"}

    def test_does_not_break_escaped_quotes(self):
        # Make sure a \" inside a string isn't treated as a string boundary.
        original = '{"k": "she said \\"hi\\""}'
        fixed = escape_control_chars_in_strings(original)
        assert json.loads(fixed)["k"] == 'she said "hi"'
