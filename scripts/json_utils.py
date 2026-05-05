"""Shared JSON-parsing utilities used by AI-content generators.

LLM responses occasionally contain raw control characters or minor structural
issues that break ``json.loads``. The helpers here implement small, well-scoped
repairs so the parsing fallback chain in ``editorial_generator`` and
``enrich_content`` can share the same logic.
"""

import re


_QUOTED_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
_LOW_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _escape_quoted_match(match: "re.Match[str]") -> str:
    """Escape raw control characters that appear inside a quoted JSON string."""
    s = match.group(0)
    inner = s[1:-1]  # Strip surrounding quotes
    inner = inner.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    inner = _LOW_CONTROL_RE.sub(
        lambda m: f"\\u{ord(m.group()):04x}",
        inner,
    )
    return f'"{inner}"'


def escape_control_chars_in_strings(json_str: str) -> str:
    """Return ``json_str`` with raw control chars inside quoted strings escaped.

    Preserves structural whitespace and escape sequences outside string literals,
    so the result remains parseable JSON whenever the only defect was unescaped
    control characters within string values (a common LLM output flaw).
    """
    return _QUOTED_STRING_RE.sub(_escape_quoted_match, json_str)
