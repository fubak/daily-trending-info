#!/usr/bin/env python3
"""
Image utilities for validating and sanitizing image URLs.
Improves reliability of article images in story cards.
"""

import re
from urllib.parse import urlparse, urljoin
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Known problematic image domains that frequently fail or have CORS issues
BLOCKED_DOMAINS = {
    'pixel.quantserve.com',
    'sb.scorecardresearch.com',
    'b.scorecardresearch.com',
    'secure-us.imrworldwide.com',
    'pixel.wp.com',
    'stats.wp.com',
    'www.google-analytics.com',
    'www.facebook.com',
    's.yimg.com',  # Yahoo tracking
}

# Domains known to have reliable, CORS-friendly images
TRUSTED_DOMAINS = {
    'i.imgur.com',
    'upload.wikimedia.org',
    'images.unsplash.com',
    'images.pexels.com',
    'cdn.pixabay.com',
    'media.npr.org',
    'ichef.bbci.co.uk',
    'static01.nyt.com',
    'static.independent.co.uk',
    'i.guim.co.uk',
    'cdn.cnn.com',
    'www.reuters.com',
    'assets.bwbx.io',
    'github.com',
    'avatars.githubusercontent.com',
    'raw.githubusercontent.com',
    'opengraph.githubassets.com',
}

# Minimum dimensions to filter out tracking pixels
MIN_IMAGE_WIDTH = 100
MIN_IMAGE_HEIGHT = 100


def validate_image_url(url: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate and sanitize an image URL.

    Args:
        url: The image URL to validate

    Returns:
        Tuple of (is_valid, sanitized_url or None)
    """
    if not url or not isinstance(url, str):
        return False, None

    url = url.strip()

    # Handle protocol-relative URLs
    if url.startswith('//'):
        url = 'https:' + url

    # Reject relative URLs without base
    if url.startswith('/') and not url.startswith('//'):
        return False, None

    # Must be HTTP or HTTPS
    if not url.startswith(('http://', 'https://')):
        return False, None

    try:
        parsed = urlparse(url)

        # Must have valid scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False, None

        # Check for blocked domains
        domain = parsed.netloc.lower()
        if any(blocked in domain for blocked in BLOCKED_DOMAINS):
            logger.debug(f"Blocked domain: {domain}")
            return False, None

        # Check for tracking pixel patterns in URL
        url_lower = url.lower()
        tracking_patterns = [
            'pixel', 'tracking', 'beacon', '1x1', 'spacer',
            'clear.gif', 'blank.gif', 'shim.gif', 't.gif',
            'analytics', 'stat', 'count'
        ]
        if any(pattern in url_lower for pattern in tracking_patterns):
            logger.debug(f"Tracking pixel pattern detected: {url}")
            return False, None

        # Check file extension (if present)
        path_lower = parsed.path.lower()
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg']
        has_extension = any(path_lower.endswith(ext) for ext in valid_extensions)

        # URLs without extensions may still be valid (CDN URLs often don't have extensions)
        # But we should be more cautious
        if not has_extension:
            # Check if URL looks like a CDN or image service
            cdn_patterns = [
                'cdn', 'images', 'img', 'media', 'static',
                'uploads', 'assets', 'photo', 'picture'
            ]
            if not any(pattern in url_lower for pattern in cdn_patterns):
                # No extension and doesn't look like an image URL
                # Still accept if from trusted domain
                if not any(trusted in domain for trusted in TRUSTED_DOMAINS):
                    logger.debug(f"No extension and not trusted: {url}")
                    return False, None

        # URL looks valid
        return True, url

    except (requests.RequestException, ValueError, AttributeError) as e:
        logger.debug(f"URL validation error for {url}: {e}")
        return False, None


def sanitize_image_url(url: str, base_url: Optional[str] = None) -> Optional[str]:
    """
    Sanitize an image URL, handling relative URLs if base is provided.

    Args:
        url: The image URL to sanitize
        base_url: Optional base URL for resolving relative URLs

    Returns:
        Sanitized absolute URL or None if invalid
    """
    if not url:
        return None

    url = url.strip()

    # Handle protocol-relative URLs
    if url.startswith('//'):
        url = 'https:' + url

    # Handle relative URLs
    if base_url and not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)

    # Validate the result
    is_valid, sanitized = validate_image_url(url)
    return sanitized if is_valid else None


def get_image_quality_score(url: str) -> int:
    """
    Score an image URL based on likely quality/reliability.
    Higher scores indicate more reliable sources.

    Args:
        url: The image URL to score

    Returns:
        Score from 0-100
    """
    if not url:
        return 0

    score = 50  # Base score

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        # Bonus for trusted domains
        if any(trusted in domain for trusted in TRUSTED_DOMAINS):
            score += 30

        # Bonus for HTTPS
        if parsed.scheme == 'https':
            score += 10

        # Bonus for known good image extensions
        if any(path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            score += 10

        # Penalty for query strings (often tracking or dynamic)
        if parsed.query:
            score -= 10

        # Penalty for very long URLs (often tracking)
        if len(url) > 500:
            score -= 20

        # Bonus for CDN patterns
        cdn_indicators = ['cdn', 'static', 'assets', 'media']
        if any(ind in domain for ind in cdn_indicators):
            score += 10

    except (KeyError, ValueError, TypeError, AttributeError):
        score = 30  # Default low score on error

    return max(0, min(100, score))


def select_best_image(image_urls: list) -> Optional[str]:
    """
    Select the best image URL from a list based on quality scoring.

    Args:
        image_urls: List of potential image URLs

    Returns:
        Best image URL or None if no valid images
    """
    if not image_urls:
        return None

    valid_images = []
    for url in image_urls:
        is_valid, sanitized = validate_image_url(url)
        if is_valid and sanitized:
            score = get_image_quality_score(sanitized)
            valid_images.append((sanitized, score))

    if not valid_images:
        return None

    # Sort by score descending and return best
    valid_images.sort(key=lambda x: x[1], reverse=True)
    return valid_images[0][0]


def get_fallback_gradient_css(seed: str = '') -> str:
    """
    Generate a CSS gradient as fallback when no image is available.

    Args:
        seed: Optional seed string for deterministic gradient selection

    Returns:
        CSS gradient string
    """
    gradients = [
        'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
        'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
        'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
        'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
        'linear-gradient(135deg, #d299c2 0%, #fef9d7 100%)',
        'linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)',
        'linear-gradient(135deg, #cd9cf2 0%, #f6f3ff 100%)',
        'linear-gradient(135deg, #37ecba 0%, #72afd3 100%)',
        'linear-gradient(135deg, #feada6 0%, #f5efef 100%)',
        'linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)',
    ]

    if seed:
        # Deterministic selection based on seed
        index = sum(ord(c) for c in seed) % len(gradients)
    else:
        import random
        index = random.randint(0, len(gradients) - 1)

    return gradients[index]
