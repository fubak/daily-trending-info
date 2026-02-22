#!/usr/bin/env python3
"""
CMMC Watch Page Generator - Standalone page for CMMC compliance news.

Generates a standalone page focused on CMMC (Cybersecurity Maturity Model
Certification) news with its own branding, separate from the main site navigation.

Features:
- Standalone header with "CMMC Watch" branding
- Theme toggle (dark/light mode)
- Density settings (compact/comfortable/spacious)
- View toggle (grid/list)
- RSS feed at /cmmc/feed.xml
- Minimal footer with link back to main site
"""

import html as html_module
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set
import logging

from config import setup_logging, CMMC_KEYWORDS

logger = setup_logging("cmmc_page_generator")


def filter_cmmc_trends(trends: List[Dict]) -> List[Dict]:
    """
    Filter trends that are CMMC-related.

    Args:
        trends: List of trend objects (dataclass or dict)

    Returns:
        List of CMMC-related trends (source starts with 'cmmc_')
    """
    cmmc_trends = []
    for trend in trends:
        # Handle both dataclass and dict formats
        if hasattr(trend, "source"):
            source = trend.source
        elif isinstance(trend, dict):
            source = trend.get("source", "")
        else:
            source = ""
        if source.startswith("cmmc_"):
            cmmc_trends.append(trend)
    return cmmc_trends


# Keywords that indicate CMMC-specific content (highest priority)
CMMC_CORE_KEYWORDS = [
    "cmmc",
    "c3pao",
    "cyber-ab",
    "cyberab",
    "cmmc 2.0",
    "cmmc level",
    "cmmc certification",
    "cmmc assessment",
    "cmmc compliance",
]

# Keywords for NIST/Compliance content (second priority)
NIST_KEYWORDS = [
    "nist 800-171",
    "nist sp 800-171",
    "nist 800-172",
    "sp 800-172",
    "dfars",
    "dfars 252.204",
    "dfars 7012",
    "cui",
    "controlled unclassified",
    "fedramp",
    "fisma",
    "ato",
    "authority to operate",
]

# Keywords for Defense Industrial Base (third priority)
DIB_KEYWORDS = [
    "defense industrial base",
    "dib",
    "defense contractor",
    "dod contractor",
    "cleared contractor",
    "defense contract",
    "pentagon",
    "dod cybersecurity",
]


def categorize_trend(trend: Dict) -> str:
    """
    Categorize a trend into CMMC-specific, NIST/Compliance, DIB, or General.

    Returns: "cmmc", "nist", "dib", or "general"
    """
    title = trend.get("title", "").lower()
    desc = (trend.get("summary") or trend.get("description") or "").lower()
    content = title + " " + desc

    # Check CMMC-specific first (highest priority)
    for keyword in CMMC_CORE_KEYWORDS:
        if keyword in content:
            return "cmmc"

    # Check NIST/Compliance
    for keyword in NIST_KEYWORDS:
        if keyword in content:
            return "nist"

    # Check DIB
    for keyword in DIB_KEYWORDS:
        if keyword in content:
            return "dib"

    return "general"


def sort_trends_by_priority(trends: List[Dict]) -> List[Dict]:
    """
    Sort trends with CMMC-specific content first, then NIST, then DIB, then general.
    """
    priority_order = {"cmmc": 0, "nist": 1, "dib": 2, "general": 3}

    def sort_key(trend):
        category = categorize_trend(trend)
        return priority_order.get(category, 3)

    return sorted(trends, key=sort_key)


def get_cmmc_hero_image(
    images: List[Dict], headline: str, used_image_ids: Set[str]
) -> Dict:
    """
    Find an appropriate hero image for the CMMC page.

    Args:
        images: List of available images
        headline: Featured story headline
        used_image_ids: Set of already-used image IDs

    Returns:
        Best matching image dict
    """
    if not images:
        return {}

    # Keywords relevant to CMMC/cybersecurity
    cmmc_visual_keywords = [
        "cybersecurity",
        "security",
        "technology",
        "computer",
        "network",
        "data",
        "digital",
        "protection",
        "lock",
        "shield",
        "code",
        "government",
        "federal",
        "military",
        "defense",
        "office",
    ]

    # Filter out already-used images
    available = [img for img in images if img.get("id") not in used_image_ids]
    if not available:
        available = images

    # Score images by keyword relevance
    best_image = None
    best_score = 0.0

    for img in available:
        img_text = f"{img.get('query', '')} {img.get('description', '')} {img.get('alt', '')}".lower()
        score = float(sum(1 for kw in cmmc_visual_keywords if kw in img_text))
        if img.get("width", 0) >= 1200:
            score += 0.5
        if score > best_score:
            best_score = score
            best_image = img

    if best_image:
        if best_image.get("id"):
            used_image_ids.add(best_image["id"])
        return best_image

    # Fallback to first available
    selected = available[0]
    if selected.get("id"):
        used_image_ids.add(selected["id"])
    return selected


def build_cmmc_header(date_str: str) -> str:
    """
    Build standalone header for CMMC Watch page.

    No main site navigation - standalone branding with controls.
    """
    return f"""
    <header class="cmmc-header">
        <div class="cmmc-header-container">
            <div class="cmmc-brand">
                <a href="/cmmc/" class="cmmc-logo">
                    <svg class="cmmc-logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                        <path d="M9 12l2 2 4-4"/>
                    </svg>
                    <span class="cmmc-logo-text">CMMC Watch</span>
                </a>
                <span class="cmmc-tagline">CMMC Compliance & Certification News</span>
            </div>
            <div class="cmmc-header-controls">
                <span class="cmmc-date">{date_str}</span>
                <button class="theme-toggle" aria-label="Toggle theme" title="Toggle dark/light mode">
                    <svg class="sun-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="5"/>
                        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                    </svg>
                    <svg class="moon-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                    </svg>
                </button>
                <div class="density-controls">
                    <button class="density-btn" data-density="compact" title="Compact">
                        <svg viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="3"/><rect x="4" y="10" width="16" height="3"/><rect x="4" y="16" width="16" height="3"/></svg>
                    </button>
                    <button class="density-btn" data-density="comfortable" title="Comfortable">
                        <svg viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="3" width="16" height="4"/><rect x="4" y="10" width="16" height="4"/><rect x="4" y="17" width="16" height="4"/></svg>
                    </button>
                    <button class="density-btn" data-density="spacious" title="Spacious">
                        <svg viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="2" width="16" height="5"/><rect x="4" y="10" width="16" height="5"/><rect x="4" y="18" width="16" height="5"/></svg>
                    </button>
                </div>
            </div>
        </div>
    </header>"""


def build_cmmc_footer(date_str: str) -> str:
    """Build minimal footer for CMMC Watch page."""
    return f"""
    <footer class="cmmc-footer">
        <div class="cmmc-footer-container">
            <div class="cmmc-footer-brand">
                <span class="cmmc-footer-powered">A product of</span>
                <a href="https://cmmcwatch.com" class="cmmc-footer-link">CMMC Watch</a>
            </div>
            <div class="cmmc-footer-links">
                <a href="/cmmc/feed.xml" class="cmmc-footer-rss">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
                        <circle cx="6.18" cy="17.82" r="2.18"/>
                        <path d="M4 4.44v2.83c7.03 0 12.73 5.7 12.73 12.73h2.83c0-8.59-6.97-15.56-15.56-15.56zm0 5.66v2.83c3.9 0 7.07 3.17 7.07 7.07h2.83c0-5.47-4.43-9.9-9.9-9.9z"/>
                    </svg>
                    RSS Feed
                </a>
            </div>
            <div class="cmmc-footer-meta">
                <span>Updated: {date_str}</span>
            </div>
        </div>
    </footer>"""


def get_cmmc_styles(colors: Dict, fonts: Dict) -> str:
    """Generate CSS styles for CMMC Watch page."""
    return f"""
    :root {{
        --bg: {colors['bg']};
        --text: {colors['text']};
        --text-muted: {colors['muted']};
        --border: {colors['border']};
        --card-bg: {colors['card_bg']};
        --accent: {colors['accent']};
        --accent-secondary: {colors['accent_secondary']};
        --font-primary: '{fonts['primary']}', system-ui, sans-serif;
        --font-secondary: '{fonts['secondary']}', system-ui, sans-serif;
        --radius: 1rem;
        --transition: 200ms;
    }}

    /* Light mode */
    body.light-mode {{
        --bg: #fafafa;
        --text: #18181b;
        --text-muted: #71717a;
        --border: #e4e4e7;
        --card-bg: #ffffff;
    }}

    /* Dark mode */
    body.dark-mode {{
        --bg: #0a0a0a;
        --text: #ffffff;
        --text-muted: #a1a1aa;
        --border: #27272a;
        --card-bg: #18181b;
    }}

    /* Density settings */
    body.density-compact {{
        --section-gap: 1.5rem;
        --card-gap: 0.75rem;
        --card-padding: 0.75rem;
    }}
    body.density-comfortable {{
        --section-gap: 2.5rem;
        --card-gap: 1.25rem;
        --card-padding: 1.25rem;
    }}
    body.density-spacious {{
        --section-gap: 4rem;
        --card-gap: 2rem;
        --card-padding: 1.75rem;
    }}

    /* View list mode */
    body.view-list .stories-grid {{
        display: flex;
        flex-direction: column;
        gap: 0;
    }}
    body.view-list .story-card {{
        background: transparent;
        border: none;
        border-bottom: 1px solid var(--border);
        border-radius: 0;
        padding: 0.5rem 0;
        padding-left: 1.5rem;
    }}
    body.view-list .story-image,
    body.view-list .story-media,
    body.view-list .story-actions,
    body.view-list .story-meta {{
        display: none !important;
    }}

    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}

    body {{
        font-family: var(--font-secondary);
        background: var(--bg);
        color: var(--text);
        min-height: 100vh;
        line-height: 1.6;
    }}

    /* CMMC Header */
    .cmmc-header {{
        background: var(--card-bg);
        border-bottom: 1px solid var(--border);
        position: sticky;
        top: 0;
        z-index: 100;
    }}

    .cmmc-header-container {{
        max-width: 1400px;
        margin: 0 auto;
        padding: 1rem 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
    }}

    .cmmc-brand {{
        display: flex;
        align-items: center;
        gap: 1rem;
        flex-wrap: wrap;
    }}

    .cmmc-logo {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        text-decoration: none;
        color: var(--text);
    }}

    .cmmc-logo-icon {{
        width: 32px;
        height: 32px;
        color: var(--accent);
    }}

    .cmmc-logo-text {{
        font-family: var(--font-primary);
        font-size: 1.5rem;
        font-weight: 700;
    }}

    .cmmc-tagline {{
        font-size: 0.85rem;
        color: var(--text-muted);
    }}

    .cmmc-header-controls {{
        display: flex;
        align-items: center;
        gap: 1rem;
    }}

    .cmmc-date {{
        font-size: 0.85rem;
        color: var(--text-muted);
    }}

    .theme-toggle {{
        background: transparent;
        border: 1px solid var(--border);
        border-radius: 0.5rem;
        padding: 0.5rem;
        cursor: pointer;
        color: var(--text);
        display: flex;
        align-items: center;
        justify-content: center;
    }}

    .theme-toggle svg {{
        width: 18px;
        height: 18px;
    }}

    body.dark-mode .theme-toggle .sun-icon {{ display: block; }}
    body.dark-mode .theme-toggle .moon-icon {{ display: none; }}
    body.light-mode .theme-toggle .sun-icon {{ display: none; }}
    body.light-mode .theme-toggle .moon-icon {{ display: block; }}

    .density-controls {{
        display: flex;
        gap: 0.25rem;
        border: 1px solid var(--border);
        border-radius: 0.5rem;
        padding: 0.25rem;
    }}

    .density-btn {{
        background: transparent;
        border: none;
        padding: 0.35rem;
        cursor: pointer;
        color: var(--text-muted);
        border-radius: 0.25rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }}

    .density-btn.active {{
        background: var(--accent);
        color: white;
    }}

    .density-btn svg {{
        width: 16px;
        height: 16px;
    }}

    /* Hero Section */
    .cmmc-hero {{
        position: relative;
        min-height: 400px;
        display: flex;
        align-items: flex-end;
        background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
        overflow: hidden;
    }}

    .cmmc-hero-image {{
        position: absolute;
        inset: 0;
        background-size: cover;
        background-position: center;
        opacity: 0.3;
    }}

    .cmmc-hero-overlay {{
        position: absolute;
        inset: 0;
        background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.3) 100%);
    }}

    .cmmc-hero-content {{
        position: relative;
        z-index: 1;
        max-width: 1400px;
        margin: 0 auto;
        padding: 3rem 1.5rem;
        width: 100%;
    }}

    .cmmc-hero-badge {{
        display: inline-block;
        background: var(--accent);
        color: white;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.25rem 0.75rem;
        border-radius: 0.25rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
    }}

    .cmmc-hero-title {{
        font-family: var(--font-primary);
        font-size: clamp(1.75rem, 4vw, 2.5rem);
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 1rem;
        color: white;
    }}

    .cmmc-hero-desc {{
        font-size: 1rem;
        color: rgba(255,255,255,0.8);
        max-width: 600px;
        margin-bottom: 1.5rem;
    }}

    .cmmc-hero-meta {{
        display: flex;
        align-items: center;
        gap: 1rem;
        font-size: 0.85rem;
        color: rgba(255,255,255,0.6);
    }}

    .cmmc-hero-cta {{
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: var(--accent);
        color: white;
        text-decoration: none;
        padding: 0.75rem 1.5rem;
        border-radius: 0.5rem;
        font-weight: 600;
        margin-top: 1rem;
        transition: transform var(--transition), opacity var(--transition);
    }}

    .cmmc-hero-cta:hover {{
        opacity: 0.9;
        transform: translateY(-2px);
    }}

    /* Main Content */
    .cmmc-main {{
        max-width: 1400px;
        margin: 0 auto;
        padding: var(--section-gap, 2rem) 1.5rem;
    }}

    .category-section {{
        margin-bottom: 3rem;
    }}

    .category-section.cmmc-priority {{
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.05), rgba(59, 130, 246, 0.02));
        margin-left: -1.5rem;
        margin-right: -1.5rem;
        padding: 2rem 1.5rem;
        border-left: 4px solid var(--accent);
    }}

    .category-desc {{
        color: var(--text-muted);
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
        font-style: italic;
    }}

    .cmmc-section-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid var(--accent);
    }}

    .cmmc-section-title {{
        font-family: var(--font-primary);
        font-size: 1.25rem;
        font-weight: 700;
    }}

    .cmmc-story-count {{
        font-size: 0.85rem;
        color: var(--text-muted);
    }}

    /* Story Grid */
    .stories-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: var(--card-gap, 1.25rem);
    }}

    .story-card {{
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        overflow: hidden;
        transition: transform var(--transition), box-shadow var(--transition);
    }}

    .story-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
    }}

    .story-media {{
        position: relative;
        aspect-ratio: 16/9;
        overflow: hidden;
    }}

    .story-image {{
        width: 100%;
        height: 100%;
        object-fit: cover;
    }}

    .source-badge {{
        position: absolute;
        top: 0.75rem;
        left: 0.75rem;
        background: var(--accent);
        color: white;
        font-size: 0.7rem;
        font-weight: 600;
        padding: 0.2rem 0.5rem;
        border-radius: 0.25rem;
        text-transform: uppercase;
    }}

    .story-date {{
        position: absolute;
        top: 0.75rem;
        right: 0.75rem;
        background: rgba(0, 0, 0, 0.6);
        color: rgba(255, 255, 255, 0.9);
        font-size: 0.65rem;
        font-weight: 500;
        padding: 0.15rem 0.4rem;
        border-radius: 0.2rem;
        font-family: var(--font-secondary);
    }}

    .story-content {{
        padding: var(--card-padding, 1rem);
    }}

    .story-title {{
        font-family: var(--font-primary);
        font-size: 1rem;
        font-weight: 600;
        line-height: 1.4;
        margin-bottom: 0.5rem;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}

    .story-title a {{
        color: var(--text);
        text-decoration: none;
    }}

    .story-title a:hover {{
        color: var(--accent);
    }}

    .story-summary {{
        font-size: 0.85rem;
        color: var(--text-muted);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}

    /* Footer */
    .cmmc-footer {{
        background: var(--card-bg);
        border-top: 1px solid var(--border);
        margin-top: var(--section-gap, 2rem);
        padding: 2rem 1.5rem;
    }}

    .cmmc-footer-container {{
        max-width: 1400px;
        margin: 0 auto;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
    }}

    .cmmc-footer-brand {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.85rem;
        color: var(--text-muted);
    }}

    .cmmc-footer-link {{
        color: var(--accent);
        text-decoration: none;
    }}

    .cmmc-footer-link:hover {{
        text-decoration: underline;
    }}

    .cmmc-footer-links {{
        display: flex;
        gap: 1.5rem;
    }}

    .cmmc-footer-rss {{
        display: flex;
        align-items: center;
        gap: 0.35rem;
        color: var(--text-muted);
        text-decoration: none;
        font-size: 0.85rem;
    }}

    .cmmc-footer-rss:hover {{
        color: var(--accent);
    }}

    .cmmc-footer-meta {{
        font-size: 0.8rem;
        color: var(--text-muted);
    }}

    /* Responsive */
    @media (max-width: 768px) {{
        .cmmc-header-container {{
            flex-direction: column;
            align-items: flex-start;
        }}

        .cmmc-brand {{
            flex-direction: column;
            align-items: flex-start;
            gap: 0.25rem;
        }}

        .cmmc-hero {{
            min-height: 350px;
        }}

        .stories-grid {{
            grid-template-columns: 1fr;
        }}

        .cmmc-footer-container {{
            flex-direction: column;
            text-align: center;
        }}
    }}
    """


def get_cmmc_script() -> str:
    """Generate JavaScript for theme toggle and density controls."""
    return """
    <script>
    (function() {
        const body = document.body;

        // Theme toggle
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'light') {
            body.classList.remove('dark-mode');
            body.classList.add('light-mode');
        } else {
            body.classList.remove('light-mode');
            body.classList.add('dark-mode');
            if (!savedTheme) localStorage.setItem('theme', 'dark');
        }

        const themeBtn = document.querySelector('.theme-toggle');
        if (themeBtn) {
            themeBtn.addEventListener('click', function() {
                const isDark = body.classList.contains('dark-mode');
                body.classList.toggle('dark-mode', !isDark);
                body.classList.toggle('light-mode', isDark);
                localStorage.setItem('theme', isDark ? 'light' : 'dark');
            });
        }

        // Density controls
        const densityClasses = ['density-compact', 'density-comfortable', 'density-spacious'];
        const savedDensity = localStorage.getItem('reading_density') || 'compact';

        densityClasses.forEach(cls => body.classList.remove(cls));
        body.classList.add('density-' + savedDensity);

        document.querySelectorAll('.density-btn').forEach(btn => {
            const density = btn.dataset.density;
            if (density === savedDensity) btn.classList.add('active');

            btn.addEventListener('click', function() {
                document.querySelectorAll('.density-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                densityClasses.forEach(cls => body.classList.remove(cls));
                body.classList.add('density-' + density);
                localStorage.setItem('reading_density', density);
            });
        });

        // View mode
        const savedView = localStorage.getItem('reading_view') || 'grid';
        body.classList.toggle('view-list', savedView === 'list');
    })();
    </script>"""


def build_cmmc_page(trends: List[Dict], images: List[Dict], design: Dict) -> str:
    """
    Build the complete CMMC Watch HTML page.

    Args:
        trends: List of CMMC-related trends
        images: Available stock images
        design: Design configuration

    Returns:
        Complete HTML string for the page
    """
    # Filter to CMMC trends only and sort by priority
    cmmc_trends = filter_cmmc_trends(trends)
    cmmc_trends = sort_trends_by_priority(cmmc_trends)

    if not cmmc_trends:
        logger.warning("No CMMC trends found, generating empty page")
        cmmc_trends = []

    # Setup colors and fonts
    colors = {
        "bg": design.get("color_bg", "#0a0a0a"),
        "text": design.get("color_text", "#ffffff"),
        "muted": design.get("color_muted", "#a1a1aa"),
        "border": design.get("color_border", "#27272a"),
        "card_bg": design.get("color_card_bg", "#18181b"),
        "accent": design.get("color_accent", "#3b82f6"),  # Blue for CMMC
        "accent_secondary": design.get("color_accent_secondary", "#60a5fa"),
    }

    fonts = {
        "primary": design.get("font_primary", "Space Grotesk"),
        "secondary": design.get("font_secondary", "Inter"),
    }

    # Date info
    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")
    date_iso = now.isoformat()

    # Get hero image
    used_image_ids: Set[str] = set()
    featured_story = cmmc_trends[0] if cmmc_trends else {}
    hero_image = get_cmmc_hero_image(
        images, featured_story.get("title", "CMMC Cybersecurity"), used_image_ids
    )
    hero_image_url = hero_image.get("url_large", hero_image.get("url_medium", ""))

    # Featured story details
    featured_title = html_module.escape(
        featured_story.get("title", "CMMC Compliance News")[:100]
    )
    featured_url = html_module.escape(featured_story.get("url", "#"))
    featured_source_raw = featured_story.get("source_label")
    if not featured_source_raw:
        featured_source_raw = (
            featured_story.get("source", "")
            .replace("cmmc_", "")
            .replace("_", " ")
            .title()
        )
    featured_source = html_module.escape(featured_source_raw)
    featured_desc = html_module.escape(
        (featured_story.get("summary") or featured_story.get("description") or "")[:200]
    )

    # Helper function to build a story card
    def build_story_card(trend, images, used_image_ids):
        title = html_module.escape(trend.get("title", "")[:100])
        url = html_module.escape(trend.get("url", "#"))
        source_raw = trend.get("source_label")
        if not source_raw:
            source_raw = (
                trend.get("source", "").replace("cmmc_", "").replace("_", " ").title()
            )
        source = html_module.escape(source_raw)
        summary = html_module.escape(
            (trend.get("summary") or trend.get("description") or "")[:150]
        )

        # Format publication date as MM/DD/YYYY
        pub_date = ""
        timestamp = trend.get("timestamp")
        if timestamp:
            try:
                if isinstance(timestamp, datetime):
                    pub_date = timestamp.strftime("%m/%d/%Y")
                elif isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    pub_date = dt.strftime("%m/%d/%Y")
                elif isinstance(timestamp, (int, float)):
                    dt = datetime.fromtimestamp(timestamp)
                    pub_date = dt.strftime("%m/%d/%Y")
            except (ValueError, TypeError, OSError):
                pass

        # Get image for story
        story_image = trend.get("image_url", "")
        if not story_image and images:
            available = [img for img in images if img.get("id") not in used_image_ids]
            if available:
                img = available[0]
                story_image = img.get("url_medium", img.get("url", ""))
                if img.get("id"):
                    used_image_ids.add(img["id"])

        date_html = f'<span class="story-date">{pub_date}</span>' if pub_date else ""

        return f"""
        <article class="story-card">
            <div class="story-media">
                {"<img class='story-image' src='" + html_module.escape(story_image) + "' alt='' loading='lazy'>" if story_image else "<div class='story-image' style='background: linear-gradient(135deg, #1e3a5f, #0d1b2a);'></div>"}
                <span class="source-badge">{source}</span>
                {date_html}
            </div>
            <div class="story-content">
                <h3 class="story-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
                <p class="story-summary">{summary}</p>
            </div>
        </article>"""

    # Categorize stories (skip first since it's featured)
    remaining_trends = cmmc_trends[1:]
    cmmc_specific = []
    nist_compliance = []
    dib_stories = []
    general_stories = []

    for trend in remaining_trends:
        category = categorize_trend(trend)
        if category == "cmmc":
            cmmc_specific.append(trend)
        elif category == "nist":
            nist_compliance.append(trend)
        elif category == "dib":
            dib_stories.append(trend)
        else:
            general_stories.append(trend)

    # Build cards for each category
    cmmc_cards = [
        build_story_card(t, images, used_image_ids) for t in cmmc_specific[:10]
    ]
    nist_cards = [
        build_story_card(t, images, used_image_ids) for t in nist_compliance[:10]
    ]
    dib_cards = [build_story_card(t, images, used_image_ids) for t in dib_stories[:10]]
    general_cards = [
        build_story_card(t, images, used_image_ids) for t in general_stories[:10]
    ]

    # Category section labels and icons
    category_info = {
        "cmmc": (
            "CMMC Program News",
            "🎯",
            "Direct CMMC certification, assessment, and program updates",
        ),
        "nist": (
            "NIST & Compliance",
            "📋",
            "NIST 800-171/172, DFARS, FedRAMP, and regulatory updates",
        ),
        "dib": (
            "Defense Industrial Base",
            "🛡️",
            "Defense contractors, DoD cybersecurity, and DIB news",
        ),
        "general": (
            "Federal Cybersecurity",
            "🔒",
            "Related federal cybersecurity and government IT news",
        ),
    }

    # Build complete HTML
    html = f"""<!DOCTYPE html>
<html lang="en" class="dark-mode">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CMMC Watch | CMMC Compliance & Certification News</title>
    <meta name="description" content="Daily curated news on CMMC (Cybersecurity Maturity Model Certification), NIST 800-171 compliance, and Defense Industrial Base cybersecurity.">
    <link rel="canonical" href="https://cmmcwatch.com/cmmc/">
    <meta property="og:title" content="CMMC Watch | CMMC Compliance & Certification News">
    <meta property="og:description" content="Daily curated news on CMMC certification, NIST 800-171 compliance, and DIB cybersecurity.">
    <meta property="og:url" content="https://cmmcwatch.com/cmmc/">
    <meta property="og:type" content="website">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="alternate" type="application/rss+xml" title="CMMC Watch RSS" href="/cmmc/feed.xml">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family={fonts['primary'].replace(' ', '+')}:wght@400;500;600;700&family={fonts['secondary'].replace(' ', '+')}:wght@400;500&display=swap" rel="stylesheet">

    <!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2196222970720414"
         crossorigin="anonymous"></script>

    <style>
    {get_cmmc_styles(colors, fonts)}
    </style>
</head>
<body class="dark-mode density-compact">
    {build_cmmc_header(date_str)}

    <section class="cmmc-hero">
        {"<div class='cmmc-hero-image' style='background-image: url(" + html_module.escape(hero_image_url) + ");'></div>" if hero_image_url else ""}
        <div class="cmmc-hero-overlay"></div>
        <div class="cmmc-hero-content">
            <span class="cmmc-hero-badge">{featured_source or 'CMMC News'}</span>
            <h1 class="cmmc-hero-title">{featured_title}</h1>
            <p class="cmmc-hero-desc">{featured_desc}</p>
            <div class="cmmc-hero-meta">
                <span>{len(cmmc_trends)} stories today</span>
                <span>|</span>
                <span>Last updated: {now.strftime("%I:%M %p EST")}</span>
            </div>
            <a href="{featured_url}" class="cmmc-hero-cta" target="_blank" rel="noopener">
                Read Full Story
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
            </a>
        </div>
    </section>

    <main class="cmmc-main">
        {f'''<section class="category-section cmmc-priority">
            <div class="cmmc-section-header">
                <h2 class="cmmc-section-title">{category_info["cmmc"][1]} {category_info["cmmc"][0]}</h2>
                <span class="cmmc-story-count">{len(cmmc_specific)} stories</span>
            </div>
            <p class="category-desc">{category_info["cmmc"][2]}</p>
            <div class="stories-grid">{"".join(cmmc_cards)}</div>
        </section>''' if cmmc_cards else ""}

        {f'''<section class="category-section">
            <div class="cmmc-section-header">
                <h2 class="cmmc-section-title">{category_info["nist"][1]} {category_info["nist"][0]}</h2>
                <span class="cmmc-story-count">{len(nist_compliance)} stories</span>
            </div>
            <p class="category-desc">{category_info["nist"][2]}</p>
            <div class="stories-grid">{"".join(nist_cards)}</div>
        </section>''' if nist_cards else ""}

        {f'''<section class="category-section">
            <div class="cmmc-section-header">
                <h2 class="cmmc-section-title">{category_info["dib"][1]} {category_info["dib"][0]}</h2>
                <span class="cmmc-story-count">{len(dib_stories)} stories</span>
            </div>
            <p class="category-desc">{category_info["dib"][2]}</p>
            <div class="stories-grid">{"".join(dib_cards)}</div>
        </section>''' if dib_cards else ""}

        {f'''<section class="category-section">
            <div class="cmmc-section-header">
                <h2 class="cmmc-section-title">{category_info["general"][1]} {category_info["general"][0]}</h2>
                <span class="cmmc-story-count">{len(general_stories)} stories</span>
            </div>
            <p class="category-desc">{category_info["general"][2]}</p>
            <div class="stories-grid">{"".join(general_cards)}</div>
        </section>''' if general_cards else ""}
    </main>

    {build_cmmc_footer(date_str)}

    {get_cmmc_script()}
</body>
</html>"""

    return html


def generate_cmmc_page(
    trends: List[Dict], images: List[Dict], design: Dict, output_dir: Path
) -> Optional[str]:
    """
    Generate the CMMC Watch page and save it.

    Args:
        trends: All collected trends
        images: Available stock images
        design: Design configuration
        output_dir: Directory to save the page (e.g., public/)

    Returns:
        Path to generated page, or None if failed
    """
    try:
        # Ensure output directory exists
        cmmc_dir = output_dir / "cmmc"
        cmmc_dir.mkdir(parents=True, exist_ok=True)

        # Build the page
        html_content = build_cmmc_page(trends, images, design)

        # Save the page
        output_path = cmmc_dir / "index.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Count CMMC trends
        cmmc_count = len(filter_cmmc_trends(trends))
        logger.info(
            f"Generated CMMC Watch page with {cmmc_count} stories at {output_path}"
        )

        return str(output_path)

    except Exception as e:
        logger.error(f"Failed to generate CMMC page: {e}")
        return None


if __name__ == "__main__":
    # Test the generator
    print("CMMC Watch Page Generator")
    print("Run via main.py pipeline to generate the page.")
