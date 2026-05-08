#!/usr/bin/env python3
"""
Media of the Day Page Generator.

Builds the /media/ page showing the daily curated image (NASA APOD) and
video (Vimeo Staff Picks). Extracted from main.py to keep Pipeline as a
thin orchestrator.
"""

import html as html_module
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

try:
    from design_tokens import safe_color, safe_font, safe_mode
except ImportError:
    from scripts.design_tokens import safe_color, safe_font, safe_mode

from shared_components import (
    build_header,
    build_footer,
    get_header_styles,
    get_footer_styles,
    get_theme_script,
)

logger = logging.getLogger("media_page_generator")

_SOURCE_NAMES: Dict[str, str] = {
    "nasa_apod": "NASA Astronomy Picture of the Day",
    "bing": "Bing Image of the Day",
    "vimeo_staff_picks": "Vimeo Staff Picks",
}


def _safe_str(val: Any, default: str = "") -> str:
    """Coerce val to str, collapsing lists to their first element."""
    if val is None:
        return default
    if isinstance(val, list):
        return val[0] if val else default
    return str(val)


def build_media_page(media_data: Dict, design: Dict) -> str:
    """Build and return the HTML string for the Media of the Day page."""
    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")

    # Validate every CSS-bound design token before inlining into <style>.
    # LLM-generated design data could otherwise contain values that break
    # out of CSS and inject rules.
    colors = {
        "bg": safe_color(design.get("color_bg"), "#0a0a0a"),
        "card_bg": safe_color(design.get("color_card_bg"), "#18181b"),
        "text": safe_color(design.get("color_text"), "#ffffff"),
        "muted": safe_color(design.get("color_muted"), "#a1a1aa"),
        "border": safe_color(design.get("color_border"), "#27272a"),
        "accent": safe_color(design.get("color_accent"), "#6366f1"),
        "accent_secondary": safe_color(
            design.get("color_accent_secondary"), "#8b5cf6"
        ),
    }
    font_primary = safe_font(design.get("font_primary"), "Space Grotesk")
    font_secondary = safe_font(design.get("font_secondary"), "Inter")
    radius = design.get("card_radius", "1rem")
    transition = design.get("transition_speed", "200ms")
    base_mode = "dark-mode" if design.get("is_dark_mode", True) else "light-mode"
    base_mode = safe_mode(base_mode, "dark-mode")

    image = media_data.get("image_of_day") or {}
    image_title = html_module.escape(_safe_str(image.get("title"), "Image of the Day"))
    image_url = html_module.escape(_safe_str(image.get("url")))
    image_hd_url = html_module.escape(_safe_str(image.get("url_hd")))
    image_explanation = html_module.escape(_safe_str(image.get("explanation")))
    image_source = _safe_str(image.get("source"))
    image_source_url = html_module.escape(_safe_str(image.get("source_url")))
    image_copyright = html_module.escape(_safe_str(image.get("copyright")))
    image_date = _safe_str(image.get("date"))

    video = media_data.get("video_of_day") or {}
    video_title = html_module.escape(_safe_str(video.get("title"), "Video of the Day"))
    video_description = html_module.escape(_safe_str(video.get("description")))
    video_embed_url = html_module.escape(_safe_str(video.get("embed_url")))
    video_url = html_module.escape(_safe_str(video.get("video_url")))
    video_author = html_module.escape(_safe_str(video.get("author")))

    image_source_name = _SOURCE_NAMES.get(image_source, image_source)
    video_source_name = _SOURCE_NAMES.get(video.get("source", ""), "Vimeo Staff Picks")

    copyright_html = ""
    if image_copyright:
        copyright_html = f"""<span class="meta-item">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <path d="M14.31 8l5.74 9.94M9.69 8h11.48M7.38 12l5.74-9.94M9.69 16L3.95 6.06M14.31 16H2.83M16.62 12l-5.74 9.94"/>
                        </svg>
                        © {image_copyright}
                    </span>"""

    hd_link_html = ""
    if image_hd_url:
        hd_link_html = f"""<a href="{image_hd_url}" target="_blank" rel="noopener" class="action-btn secondary">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                        HD Version
                    </a>"""

    author_html = ""
    if video_author:
        author_initial = video_author[0].upper()
        author_html = f"""<div class="author-info">
                    <div class="author-avatar">{author_initial}</div>
                    <div><span class="author-name">{video_author}</span></div>
                </div>"""

    explanation_truncated = (
        image_explanation[:800] + "..." if len(image_explanation) > 800 else image_explanation
    )
    image_source_short = image_source_name.split()[0] if image_source_name else "Source"

    if image:
        image_section = f"""<section class="media-section">
        <div class="section-header">
            <h2 class="section-title">
                <span class="section-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <polyline points="21 15 16 10 5 21"/>
                    </svg>
                </span>
                Image of the Day
            </h2>
            <a href="{image_source_url}" target="_blank" rel="noopener" class="source-link">
                {image_source_name}
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
            </a>
        </div>
        <div class="image-container">
            <img src="{image_url}" alt="{image_title}" class="featured-image" loading="lazy">
            <div class="image-info">
                <h3 class="media-title">{image_title}</h3>
                <p class="media-description">{explanation_truncated}</p>
                <div class="media-meta">
                    <span class="meta-item">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                            <line x1="16" y1="2" x2="16" y2="6"/>
                            <line x1="8" y1="2" x2="8" y2="6"/>
                            <line x1="3" y1="10" x2="21" y2="10"/>
                        </svg>
                        {image_date}
                    </span>
                    {copyright_html}
                </div>
                <div class="image-actions">
                    <a href="{image_source_url}" target="_blank" rel="noopener" class="action-btn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                            <polyline points="15 3 21 3 21 9"/>
                            <line x1="10" y1="14" x2="21" y2="3"/>
                        </svg>
                        View on {image_source_short}
                    </a>
                    {hd_link_html}
                </div>
            </div>
        </div>
    </section>"""
    else:
        image_section = '<p style="color: var(--color-muted); text-align: center; padding: 2rem;">Image of the Day is temporarily unavailable.</p>'

    description_truncated = (
        video_description[:500] + "..." if len(video_description) > 500 else video_description
    )
    if video:
        video_section = f"""<section class="media-section">
        <div class="section-header">
            <h2 class="section-title">
                <span class="section-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2">
                        <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                </span>
                Video of the Day
            </h2>
            <a href="https://vimeo.com/channels/staffpicks" target="_blank" rel="noopener" class="source-link">
                {video_source_name}
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
            </a>
        </div>
        <div class="video-container">
            <div class="video-embed">
                <iframe src="{video_embed_url}?title=0&byline=0&portrait=0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>
            </div>
            <div class="video-info">
                <h3 class="media-title">{video_title}</h3>
                <p class="media-description">{description_truncated}</p>
                {author_html}
                <div class="image-actions">
                    <a href="{video_url}" target="_blank" rel="noopener" class="action-btn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                            <polyline points="15 3 21 3 21 9"/>
                            <line x1="10" y1="14" x2="21" y2="3"/>
                        </svg>
                        Watch on Vimeo
                    </a>
                </div>
            </div>
        </div>
    </section>"""
    else:
        video_section = '<p style="color: var(--color-muted); text-align: center; padding: 2rem;">Video of the Day is temporarily unavailable.</p>'

    og_image_tag = f'<meta property="og:image" content="{image_url}">' if image_url else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Media of the Day | DailyTrending.info</title>
    <meta name="description" content="Daily curated image and video content - featuring NASA's Astronomy Picture of the Day and Vimeo Staff Picks.">
    <link rel="canonical" href="https://dailytrending.info/media/">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">

    <meta property="og:title" content="Media of the Day | DailyTrending.info">
    <meta property="og:description" content="Daily curated image and video content">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://dailytrending.info/media/">
    {og_image_tag}

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Media of the Day | DailyTrending.info">
    <meta name="twitter:description" content="Daily curated image and video content">

    <!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2196222970720414"
         crossorigin="anonymous"></script>

    <link href="https://fonts.googleapis.com/css2?family={font_primary.replace(' ', '+')}:wght@400;500;600;700;800&family={font_secondary.replace(' ', '+')}:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --color-bg: {colors['bg']};
            --color-card-bg: {colors['card_bg']};
            --color-text: {colors['text']};
            --color-muted: {colors['muted']};
            --color-border: {colors['border']};
            --color-accent: {colors['accent']};
            --color-accent-secondary: {colors['accent_secondary']};
            --radius: {radius};
            --transition: {transition} ease;
            --font-primary: '{font_primary}', system-ui, sans-serif;
            --font-secondary: '{font_secondary}', system-ui, sans-serif;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: var(--font-secondary);
            background: var(--color-bg);
            color: var(--color-text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        body.light-mode {{
            --color-bg: #ffffff; --color-card-bg: #f8fafc;
            --color-text: #1a1a2e; --color-muted: #64748b;
            --color-border: #e2e8f0; background: var(--color-bg);
        }}
        body.dark-mode {{
            --color-bg: #0a0a0a; --color-card-bg: #18181b;
            --color-text: #ffffff; --color-muted: #a1a1aa;
            --color-border: #27272a; background: var(--color-bg);
        }}

        body.density-compact {{ --section-gap: 1.5rem; --card-gap: 0.75rem; --card-padding: 0.75rem; }}
        body.density-comfortable {{ --section-gap: 2.5rem; --card-gap: 1.25rem; --card-padding: 1.25rem; }}
        body.density-spacious {{ --section-gap: 4rem; --card-gap: 2rem; --card-padding: 1.75rem; }}

        body.view-list .stories-grid, body.view-list .trend-grid {{ display: flex; flex-direction: column; gap: 0; }}
        body.view-list .story-card, body.view-list .trend-card {{
            background: transparent; border: none;
            border-bottom: 1px solid var(--color-border);
            border-radius: 0; padding: 0.5rem 0; padding-left: 1.5rem;
        }}
        body.view-list .story-card img, body.view-list .trend-card img, body.view-list .card-image {{ display: none; }}

        {get_header_styles()}

        .page-header {{
            text-align: center;
            padding: 4rem 2rem 3rem;
            border-bottom: 1px solid var(--color-border);
        }}
        .page-title {{
            font-family: var(--font-primary);
            font-size: clamp(2rem, 5vw, 3.5rem);
            font-weight: 700;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .page-subtitle {{ font-size: 1.1rem; color: var(--color-muted); max-width: 600px; margin: 0 auto; }}

        .main-content {{ max-width: 1200px; margin: 0 auto; padding: 3rem 2rem; }}

        .media-section {{ margin-bottom: 4rem; }}

        .section-header {{
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 1.5rem; padding-bottom: 1rem;
            border-bottom: 1px solid var(--color-border);
        }}
        .section-title {{
            font-family: var(--font-primary); font-size: 1.5rem; font-weight: 600;
            display: flex; align-items: center; gap: 0.75rem;
        }}
        .section-icon {{
            width: 32px; height: 32px; display: flex; align-items: center;
            justify-content: center; background: var(--color-accent); border-radius: 8px;
        }}
        .source-link {{
            font-size: 0.85rem; color: var(--color-accent); text-decoration: none;
            display: flex; align-items: center; gap: 0.5rem;
            transition: color var(--transition);
        }}
        .source-link:hover {{ color: var(--color-accent-secondary); }}

        .image-container {{
            background: var(--color-card-bg); border: 1px solid var(--color-border);
            border-radius: var(--radius); overflow: hidden;
        }}
        .featured-image {{ width: 100%; max-height: 70vh; object-fit: contain; background: #000; display: block; }}
        .image-info {{ padding: 1.5rem; }}

        .media-title {{ font-family: 'Space Grotesk', sans-serif; font-size: 1.3rem; font-weight: 600; margin-bottom: 0.75rem; }}
        .media-description {{ color: var(--color-muted); font-size: 0.95rem; line-height: 1.7; margin-bottom: 1rem; }}

        .media-meta {{ display: flex; flex-wrap: wrap; gap: 1.5rem; font-size: 0.85rem; color: var(--color-muted); }}
        .meta-item {{ display: flex; align-items: center; gap: 0.5rem; }}

        .image-actions {{ display: flex; gap: 1rem; margin-top: 1rem; }}
        .action-btn {{
            display: inline-flex; align-items: center; gap: 0.5rem;
            padding: 0.75rem 1.25rem; background: var(--color-accent); color: #000;
            font-weight: 600; border-radius: var(--radius); text-decoration: none;
            transition: transform var(--transition), box-shadow var(--transition);
        }}
        .action-btn:hover {{ transform: translateY(-2px); box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
        .action-btn.secondary {{ background: var(--color-card-bg); color: var(--color-text); border: 1px solid var(--color-border); }}

        .video-container {{
            background: var(--color-card-bg); border: 1px solid var(--color-border);
            border-radius: var(--radius); overflow: hidden;
        }}
        .video-embed {{ position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; }}
        .video-embed iframe {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; }}
        .video-info {{ padding: 1.5rem; }}

        .author-info {{ display: flex; align-items: center; gap: 0.75rem; margin-top: 0.75rem; }}
        .author-avatar {{
            width: 40px; height: 40px; border-radius: 50%;
            background: var(--color-accent); display: flex;
            align-items: center; justify-content: center; font-weight: 600;
        }}
        .author-name {{ color: var(--color-text); text-decoration: none; font-weight: 500; }}
        .author-name:hover {{ color: var(--color-accent); }}

        .about-section {{
            background: var(--color-card-bg); border: 1px solid var(--color-border);
            border-radius: var(--radius); padding: 2rem; margin-top: 3rem;
        }}
        .about-title {{ font-family: 'Space Grotesk', sans-serif; font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem; }}
        .about-text {{ color: var(--color-muted); line-height: 1.7; }}
        .about-text a {{ color: var(--color-accent); text-decoration: none; }}
        .about-text a:hover {{ text-decoration: underline; }}

        .source-list {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin-top: 1.5rem; }}
        .source-card {{ background: rgba(255,255,255,0.02); border: 1px solid var(--color-border); border-radius: 0.75rem; padding: 1.25rem; }}
        .source-card h4 {{ font-size: 1rem; margin-bottom: 0.5rem; }}
        .source-card p {{ font-size: 0.85rem; color: var(--color-muted); }}

        {get_footer_styles()}

        @media (max-width: 768px) {{
            .page-header {{ padding: 3rem 1rem 2rem; }}
            .main-content {{ padding: 2rem 1rem; }}
            .section-header {{ flex-direction: column; align-items: flex-start; gap: 0.75rem; }}
            .image-actions {{ flex-direction: column; }}
        }}
    </style>
</head>
<body class="{base_mode}">
    {build_header('media', date_str)}

    <header class="page-header">
        <h1 class="page-title">Media of the Day</h1>
        <p class="page-subtitle">Curated daily content featuring stunning space imagery from NASA and award-winning short films from Vimeo's finest creators.</p>
    </header>

    <main class="main-content">
        {image_section}
        {video_section}

        <div class="about-section">
            <h3 class="about-title">About Media of the Day</h3>
            <p class="about-text">
                Every day, we curate the best visual content from trusted sources across the web.
                Our selections feature stunning space imagery and thought-provoking short films
                that inspire curiosity and creativity.
            </p>
            <div class="source-list">
                <div class="source-card">
                    <h4>🚀 NASA APOD</h4>
                    <p>The Astronomy Picture of the Day features a different image or photograph of our universe each day, along with a brief explanation by a professional astronomer.</p>
                </div>
                <div class="source-card">
                    <h4>🎬 Vimeo Staff Picks</h4>
                    <p>Hand-picked by Vimeo's curation team, Staff Picks showcase the best short films, documentaries, and creative videos from filmmakers around the world.</p>
                </div>
            </div>
        </div>
    </main>

    {build_footer(date_str)}

    {get_theme_script()}
</body>
</html>"""


def generate_media_page(
    public_dir: Path,
    media_data: Dict,
    design_data: Dict,
) -> bool:
    """Build and write the /media/index.html page.

    Returns True on success, False on failure.
    """
    try:
        media_dir = public_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        page_html = build_media_page(media_data, design_data)
        (media_dir / "index.html").write_text(page_html, encoding="utf-8")
        logger.info(f"Media page saved to {media_dir / 'index.html'}")
        return True
    except Exception as e:
        logger.warning(f"Failed to generate media page: {e}")
        return False
