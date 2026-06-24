"""URL safety helpers used across all HTML renderers.

`safe_href()` returns a value safe to interpolate into an `href` or `src`
attribute. It blocks dangerous schemes (`javascript:`, `data:`, `vbscript:`,
`file:`) so an attacker-controlled URL cannot execute script, while
preserving normal HTTP/HTTPS/mailto links and relative paths.

`safe_image_src()` is a stricter variant intended for `<img src="...">`
where only http/https/data:image and relative URLs are acceptable.
"""

import html
from typing import Optional
from urllib.parse import urlparse


_SAFE_LINK_SCHEMES = {"http", "https", "mailto"}
_SAFE_IMAGE_SCHEMES = {"http", "https"}

# Characters that could terminate a CSS url() or its surrounding style="..."
# attribute. We strip rather than entity-encode these: a style attribute is
# HTML-decoded by the browser before the CSS is parsed, so an entity-escaped
# quote would decode back into a real quote and re-open the injection.
_CSS_URL_FORBIDDEN = ('"', "'", "(", ")", "\\", "<", ">", " ", "\t", "\n", "\r")


def safe_href(url: Optional[str]) -> str:
    """Return an HTML-attribute-safe URL for `<a href="...">`.

    Falls back to `#` when the URL is empty, malformed, or has a scheme
    outside the allowlist (`javascript:`, `data:`, etc.).
    """
    if not url:
        return "#"
    try:
        parsed = urlparse(str(url).strip())
    except (ValueError, AttributeError):
        return "#"
    # Relative URLs (no scheme) are safe; absolute ones must use an
    # allowlisted scheme.
    if parsed.scheme and parsed.scheme.lower() not in _SAFE_LINK_SCHEMES:
        return "#"
    return html.escape(str(url), quote=True)


def safe_image_src(url: Optional[str]) -> str:
    """Return an HTML-attribute-safe URL for `<img src="...">` / `<iframe src>`.

    Stricter than `safe_href()`: only http/https or relative paths pass
    through. Anything else (`javascript:`, `data:`, `mailto:`) becomes
    an empty string so callers can omit the element rather than emit a
    broken attribute.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(str(url).strip())
    except (ValueError, AttributeError):
        return ""
    if parsed.scheme and parsed.scheme.lower() not in _SAFE_IMAGE_SCHEMES:
        return ""
    return html.escape(str(url), quote=True)


def safe_css_url(url: Optional[str]) -> str:
    """Return a URL safe to embed inside a quoted CSS ``url("...")``.

    Applies the same http/https scheme allowlist as `safe_image_src`, then
    strips characters that could break out of the ``url()`` function or the
    enclosing ``style`` attribute (see `_CSS_URL_FORBIDDEN`). Always wrap the
    result in quotes at the call site: ``url("{safe_css_url(x)}")``. Returns ""
    for empty or disallowed-scheme URLs so callers can omit the element.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(str(url).strip())
    except (ValueError, AttributeError):
        return ""
    if parsed.scheme and parsed.scheme.lower() not in _SAFE_IMAGE_SCHEMES:
        return ""
    cleaned = str(url).strip()
    for ch in _CSS_URL_FORBIDDEN:
        cleaned = cleaned.replace(ch, "")
    return cleaned
