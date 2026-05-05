"""HTML sanitizer for LLM-generated article content.

The editorial pipeline asks the LLM to produce a small subset of safe HTML
tags (p, h2, h3, strong, em, blockquote, ul, ol, li, a, br). This module
strips anything outside that allowlist before the content is injected
into a page, defending against:

  * <script>, <style>, <iframe>, <object>, <embed>, <form>, <input>
  * inline event handlers (onclick, onerror, onload, etc.)
  * javascript:/data:/vbscript: URLs in href/src

Note: this is a defence-in-depth measure. The LLM is prompted to produce
safe HTML, but a hallucinated <script> tag must not reach the rendered page.
"""

import re
from typing import Set


_ALLOWED_TAGS: Set[str] = {
    "p", "h2", "h3", "h4", "strong", "em", "b", "i",
    "blockquote", "ul", "ol", "li", "a", "br", "hr",
}

_ALLOWED_ATTRS = {
    "a": {"href", "title"},
}

_SCRIPT_LIKE_TAGS = {
    "script", "style", "iframe", "object", "embed", "form", "input",
    "textarea", "select", "button", "link", "meta", "base", "frame",
    "frameset", "applet", "noscript",
}

# Match opening, closing, or self-closing tags.
_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*)>", re.DOTALL)
# Match attributes inside a tag.
_ATTR_RE = re.compile(
    r'([a-zA-Z][a-zA-Z0-9_:-]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]*))',
)
_DANGEROUS_URL_RE = re.compile(
    r"^\s*(javascript|data|vbscript|file):", re.IGNORECASE
)
# Match <script>...</script> blocks (and similar) including their content.
_SCRIPT_BLOCK_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)


def sanitize_article_html(content: str) -> str:
    """Strip dangerous HTML from LLM-generated article content.

    Removes <script>/<style>/<iframe> blocks (with their contents),
    drops disallowed tags (keeping inner text), and strips event handlers
    plus javascript:/data: URLs from allowed tags.
    """
    if not content:
        return ""

    # 1. Remove entire script-like blocks, including their contents.
    content = _SCRIPT_BLOCK_RE.sub("", content)

    # 2. Walk tags and either keep them (with cleaned attributes) or drop
    # the markup entirely (preserving inner text).
    def _replace_tag(match: "re.Match[str]") -> str:
        closing, tag, attrs = match.group(1), match.group(2).lower(), match.group(3)

        if tag in _SCRIPT_LIKE_TAGS:
            return ""
        if tag not in _ALLOWED_TAGS:
            return ""

        if closing:
            return f"</{tag}>"

        cleaned_attrs = _clean_attrs(tag, attrs)
        if cleaned_attrs:
            return f"<{tag} {cleaned_attrs}>"
        return f"<{tag}>"

    return _TAG_RE.sub(_replace_tag, content)


def _clean_attrs(tag: str, attr_text: str) -> str:
    """Return only the allowlisted attributes for a tag, with safe values."""
    allowed = _ALLOWED_ATTRS.get(tag, set())
    if not allowed:
        return ""

    out = []
    for match in _ATTR_RE.finditer(attr_text):
        name = match.group(1).lower()
        value = match.group(2) or match.group(3) or match.group(4) or ""

        if name not in allowed:
            continue
        if name in {"href", "src"} and _DANGEROUS_URL_RE.match(value):
            continue
        # Re-quote attribute value, escaping any embedded quotes.
        safe_value = value.replace('"', "&quot;")
        out.append(f'{name}="{safe_value}"')

    return " ".join(out)
