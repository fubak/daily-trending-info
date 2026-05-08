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
