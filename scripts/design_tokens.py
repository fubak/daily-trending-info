"""Validation helpers for design tokens before they are inlined into CSS.

LLM-generated design data could contain values that break out of a CSS
block (e.g. `red}body{display:none}`) or trigger expression-style
injection. These helpers normalise the token values so renderers can
safely f-string them into <style> sections.
"""

import re
from typing import Dict, Optional


# CSS color literals: hex, rgb(a), hsl(a), or a small allowlist of named values.
_COLOR_RE = re.compile(
    r"^("
    r"#[0-9a-fA-F]{3,8}"                 # #fff, #ffffff, #ffffffff
    r"|rgba?\([\d\s.,%/-]+\)"           # rgb(...) / rgba(...)
    r"|hsla?\([\d\s.,%/-]+\)"           # hsl(...) / hsla(...)
    r"|transparent|inherit|currentColor"
    r")$"
)
# Font family token (a single CSS identifier or quoted family).
_FONT_RE = re.compile(r"^[A-Za-z0-9 _-]{1,60}$")
# Generic CSS mode keyword (light-mode, dark-mode, dim-mode).
_MODE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]{1,30}$")


_COLOR_FALLBACK = "#000000"
_FONT_FALLBACK = "Inter"
_MODE_FALLBACK = "dark-mode"


def safe_color(value: Optional[str], fallback: str = _COLOR_FALLBACK) -> str:
    """Return value if it parses as a CSS color literal; otherwise fallback."""
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if _COLOR_RE.match(value):
        return value
    return fallback


def safe_font(value: Optional[str], fallback: str = _FONT_FALLBACK) -> str:
    """Return value if it looks like a plain font-family name; otherwise fallback."""
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if _FONT_RE.match(value):
        return value
    return fallback


def safe_mode(value: Optional[str], fallback: str = _MODE_FALLBACK) -> str:
    """Return value if it looks like a CSS class identifier; otherwise fallback."""
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if _MODE_RE.match(value):
        return value
    return fallback


# Mapping: token-key → (validator, fallback). Color keys fall back to a
# sensible default so a missing/invalid value still produces valid CSS.
_TOKEN_RULES = {
    "primary_color": (safe_color, "#667eea"),
    "accent_color": (safe_color, "#4facfe"),
    "bg_color": (safe_color, "#0f0f23"),
    "text_color": (safe_color, "#ffffff"),
    "muted_color": (safe_color, "#a1a1aa"),
    "border_color": (safe_color, "#27272a"),
    "card_bg": (safe_color, "#18181b"),
    "font_primary": (safe_font, "Inter"),
    "font_secondary": (safe_font, "Inter"),
    "base_mode": (safe_mode, "dark-mode"),
}


def validate_design_tokens(tokens: Dict) -> Dict:
    """Return a new dict with each known token coerced to a CSS-safe value.

    Unknown keys are passed through unchanged so callers can pile extra
    metadata onto the dict without losing it.
    """
    if not isinstance(tokens, dict):
        return {key: fallback for key, (_, fallback) in _TOKEN_RULES.items()}

    cleaned = dict(tokens)
    for key, (validator, fallback) in _TOKEN_RULES.items():
        cleaned[key] = validator(tokens.get(key), fallback)
    return cleaned
