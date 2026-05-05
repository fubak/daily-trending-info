"""HTML renderers for individual editorial articles and their AMP counterparts."""

import html
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from shared_components import (
        build_header,
        build_footer,
        get_header_styles,
        get_footer_styles,
        get_theme_script,
    )
except ImportError:
    from scripts.shared_components import (
        build_header,
        build_footer,
        get_header_styles,
        get_footer_styles,
        get_theme_script,
    )

logger = __import__("logging").getLogger("pipeline")

_SAFE_URL_SCHEMES = {"http", "https", "mailto"}


def _safe_href(url: str) -> str:
    """Return an HTML-attribute-safe URL, blocking dangerous schemes."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme and parsed.scheme.lower() not in _SAFE_URL_SCHEMES:
            return "#"
    except Exception:
        return "#"
    return html.escape(url, quote=True)


def generate_article_html(
    article: Any,
    tokens: Dict,
    related_articles: Optional[List[Dict]] = None,
) -> str:
    """Generate full HTML page for an editorial article."""
    date_formatted = datetime.strptime(article.date, "%Y-%m-%d").strftime(
        "%B %d, %Y"
    )

    # Escape for HTML attributes
    title_escaped = article.title.replace('"', "&quot;")
    summary_escaped = article.summary.replace('"', "&quot;")

    # Build related articles HTML
    related_html = ""
    if related_articles:
        related_cards = []
        for rel in related_articles:
            rel_date = datetime.strptime(rel["date"], "%Y-%m-%d").strftime(
                "%B %d, %Y"
            )
            rel_title = (
                rel.get("title", "").replace("<", "&lt;").replace(">", "&gt;")
            )
            rel_summary = (rel.get("summary", "") or "")[:100]
            if len(rel.get("summary", "")) > 100:
                rel_summary += "..."
            rel_href = _safe_href(rel.get("url", ""))
            rel_date_attr = html.escape(rel.get("date", ""), quote=True)
            rel_summary = html.escape(rel_summary)
            related_cards.append(
                f"""
            <a href="{rel_href}" class="related-card">
                <time datetime="{rel_date_attr}">{rel_date}</time>
                <h4>{rel_title}</h4>
                <p>{rel_summary}</p>
            </a>"""
            )
        related_html = f"""
        <div class="related-articles">
            <h3>More Analysis</h3>
            <div class="related-grid">
                {''.join(related_cards)}
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{article.title} | DailyTrending.info</title>
<meta name="description" content="{summary_escaped}">
<meta name="keywords" content="{', '.join(article.keywords)}">
<link rel="canonical" href="https://dailytrending.info{article.url}">
<link rel="amphtml" href="https://dailytrending.info/amp{article.url}">

<!-- Open Graph -->
<meta property="og:title" content="{title_escaped}">
<meta property="og:description" content="{summary_escaped}">
<meta property="og:type" content="article">
<meta property="og:url" content="https://dailytrending.info{article.url}">
<meta property="og:site_name" content="DailyTrending.info">
<meta property="og:image" content="https://dailytrending.info/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="article:published_time" content="{article.date}T06:00:00Z">
<meta property="article:author" content="https://twitter.com/bradshannon">
<meta property="article:section" content="Analysis">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@bradshannon">
<meta name="twitter:creator" content="@bradshannon">
<meta name="twitter:title" content="{title_escaped}">
<meta name="twitter:description" content="{summary_escaped}">
<meta name="twitter:image" content="https://dailytrending.info/og-image.png">

<!-- Google AdSense -->
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2196222970720414"
     crossorigin="anonymous"></script>

<!-- JSON-LD Structured Data -->
<script type="application/ld+json">
{{
    "@context": "https://schema.org",
    "@graph": [
        {{
            "@type": "NewsArticle",
            "@id": "https://dailytrending.info{article.url}#article",
            "headline": "{title_escaped}",
            "description": "{summary_escaped}",
            "datePublished": "{article.date}T06:00:00Z",
            "dateModified": "{article.date}T06:00:00Z",
            "author": {{
                "@type": "Person",
                "name": "Brad Shannon",
                "url": "https://twitter.com/bradshannon",
                "sameAs": ["https://twitter.com/bradshannon"]
            }},
            "publisher": {{
                "@type": "Organization",
                "name": "DailyTrending.info",
                "url": "https://dailytrending.info",
                "logo": {{
                    "@type": "ImageObject",
                    "url": "https://dailytrending.info/icons/icon-512.png"
                }}
            }},
            "mainEntityOfPage": {{
                "@type": "WebPage",
                "@id": "https://dailytrending.info{article.url}"
            }},
            "wordCount": {article.word_count},
            "keywords": {json.dumps(article.keywords)},
            "articleSection": "Analysis",
            "inLanguage": "en-US"
        }},
        {{
            "@type": "BreadcrumbList",
            "itemListElement": [
                {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://dailytrending.info/"}},
                {{"@type": "ListItem", "position": 2, "name": "Articles", "item": "https://dailytrending.info/articles/"}},
                {{"@type": "ListItem", "position": 3, "name": "{title_escaped}"}}
            ]
        }}
    ]
}}
</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family={tokens['font_secondary'].replace(' ', '+')}:wght@400;500;600;700&family={tokens['font_primary'].replace(' ', '+')}:wght@600;700&display=swap" rel="stylesheet">

<style>
    :root {{
        --primary: {tokens['primary_color']};
        --accent: {tokens['accent_color']};
        --bg: {tokens['bg_color']};
        --text: {tokens['text_color']};
        --text-muted: {tokens['muted_color']};
        --border: {tokens['border_color']};
        --card-bg: {tokens['card_bg']};
        --font-primary: '{tokens['font_primary']}', system-ui, sans-serif;
        --font-secondary: '{tokens['font_secondary']}', system-ui, sans-serif;
        /* Shared component color mappings */
        --color-text: var(--text);
        --color-muted: var(--text-muted);
        --color-bg: var(--bg);
        --color-accent: var(--accent);
        --color-border: var(--border);
        --color-card-bg: var(--card-bg);
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
        font-family: var(--font-secondary);
        background: var(--bg);
        color: var(--text);
        line-height: 1.7;
        min-height: 100vh;
    }}

    body.light-mode {{
        --bg: #ffffff;
        --text: #1a1a2e;
        --text-muted: #64748b;
        --border: #e2e8f0;
        --card-bg: #f8fafc;
        --color-text: var(--text);
        --color-muted: var(--text-muted);
        --color-bg: var(--bg);
        --color-border: var(--border);
        --color-card-bg: var(--card-bg);
    }}

    body.dark-mode {{
        --bg: #0a0a0a;
        --text: #ffffff;
        --text-muted: #a1a1aa;
        --border: #27272a;
        --card-bg: #18181b;
        --color-text: var(--text);
        --color-muted: var(--text-muted);
        --color-bg: var(--bg);
        --color-border: var(--border);
        --color-card-bg: var(--card-bg);
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

    .container {{
        max-width: 720px;
        margin: 0 auto;
        padding: 2rem 1.5rem;
    }}

    .breadcrumb {{
        font-size: 0.875rem;
        color: var(--text-muted);
        margin-bottom: 2rem;
    }}

    .breadcrumb a {{
        color: var(--accent);
        text-decoration: none;
    }}

    .breadcrumb a:hover {{
        text-decoration: underline;
    }}

    .article-header {{
        margin-bottom: 2.5rem;
        padding-bottom: 2rem;
        border-bottom: 1px solid var(--border);
    }}

    .article-meta {{
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
        font-size: 0.875rem;
        color: var(--text-muted);
    }}

    .mood-badge {{
        background: var(--primary);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    h1 {{
        font-family: var(--font-primary);
        font-size: clamp(2rem, 5vw, 3rem);
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 1rem;
        background: linear-gradient(135deg, var(--text), var(--accent));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}

    .article-summary {{
        font-size: 1.25rem;
        color: var(--text-muted);
        font-weight: 400;
    }}

    .article-content {{
        font-size: 1.125rem;
    }}

    .article-content p {{
        margin-bottom: 1.5rem;
    }}

    .article-content h2 {{
        font-family: var(--font-primary);
        font-size: 1.5rem;
        margin: 2.5rem 0 1rem;
        color: var(--accent);
    }}

    .article-content blockquote {{
        border-left: 4px solid var(--primary);
        padding-left: 1.5rem;
        margin: 2rem 0;
        font-style: italic;
        color: var(--text-muted);
    }}

    .article-content strong {{
        color: var(--accent);
        font-weight: 600;
    }}

    .article-footer {{
        margin-top: 3rem;
        padding-top: 2rem;
        border-top: 1px solid var(--border);
    }}

    .sources-section {{
        background: rgba(255,255,255,0.03);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 2rem;
    }}

    .sources-section h3 {{
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        margin-bottom: 1rem;
    }}

    .sources-section ul {{
        list-style: none;
    }}

    .sources-section li {{
        padding: 0.5rem 0;
        font-size: 0.9rem;
        color: var(--text-muted);
        border-bottom: 1px solid var(--border);
    }}

    .sources-section li:last-child {{
        border-bottom: none;
    }}

    .back-link {{
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        color: var(--accent);
        text-decoration: none;
        font-weight: 500;
        transition: opacity 0.2s;
    }}

    .back-link:hover {{
        opacity: 0.8;
    }}

    .keywords {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
    }}

    .keyword {{
        background: rgba(255,255,255,0.05);
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.8rem;
        color: var(--text-muted);
    }}

    /* Related Articles */
    .related-articles {{
        margin-top: 2.5rem;
        padding-top: 2rem;
        border-top: 1px solid var(--border);
    }}

    .related-articles h3 {{
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        margin-bottom: 1.5rem;
    }}

    .related-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
    }}

    .related-card {{
        display: block;
        padding: 1rem;
        background: rgba(255,255,255,0.03);
        border: 1px solid var(--border);
        border-radius: 8px;
        text-decoration: none;
        transition: all 0.2s ease;
    }}

    .related-card:hover {{
        border-color: var(--primary);
        transform: translateY(-2px);
    }}

    .related-card time {{
        font-size: 0.75rem;
        color: var(--text-muted);
    }}

    .related-card h4 {{
        font-size: 0.95rem;
        margin: 0.5rem 0;
        color: var(--text);
        line-height: 1.4;
    }}

    .related-card p {{
        font-size: 0.8rem;
        color: var(--text-muted);
        margin: 0;
        line-height: 1.5;
    }}

    @media (max-width: 768px) {{
        .container {{
            padding: 1rem;
        }}

        h1 {{
            font-size: clamp(1.75rem, 5vw, 2.5rem);
        }}

        .article-summary {{
            font-size: 1rem;
        }}

        .article-content {{
            font-size: 1rem;
        }}

        .article-content h2 {{
            font-size: 1.25rem;
        }}

        .article-content blockquote {{
            padding-left: 1rem;
            margin: 1.5rem 0;
        }}

        .sources-section {{
            padding: 1rem;
        }}

        .related-articles {{
            grid-template-columns: 1fr;
        }}

        .breadcrumb {{
            font-size: 0.8rem;
        }}

        .article-meta {{
            flex-wrap: wrap;
        }}
    }}

    @media (max-width: 480px) {{
        .container {{
            padding: 0.75rem;
        }}

        h1 {{
            font-size: 1.5rem;
        }}

        .article-meta {{
            font-size: 0.75rem;
            gap: 0.5rem;
        }}

        .keywords {{
            gap: 0.375rem;
        }}

        .keyword {{
            font-size: 0.7rem;
            padding: 0.2rem 0.5rem;
        }}
    }}

    body.light-mode h1 {{
        background: linear-gradient(135deg, var(--text), var(--primary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}

    {get_header_styles()}
    {get_footer_styles()}
</style>
</head>
<body class="{tokens['base_mode']} editorial-mode">
{build_header('articles', date_formatted)}

<article class="container">
    <nav class="breadcrumb">
        <a href="/">Home</a> / <a href="/articles/">Articles</a> / {date_formatted}
    </nav>

    <header class="article-header">
        <div class="article-meta">
            <time datetime="{article.date}">{date_formatted}</time>
            <span class="mood-badge">{article.mood}</span>
            <span>{article.word_count} words</span>
        </div>
        <h1>{article.title}</h1>
        <p class="article-summary">{article.summary}</p>
    </header>

    <div class="article-content">
        {article.content}
    </div>

    <footer class="article-footer">
        <div class="sources-section">
            <h3>Stories Referenced</h3>
            <ul>
                {''.join(f'<li>{story}</li>' for story in article.top_stories)}
            </ul>
        </div>

        <div class="keywords">
            {''.join(f'<span class="keyword">{kw}</span>' for kw in article.keywords)}
        </div>

        {related_html}

        <p style="margin-top: 2rem;">
            <a href="/" class="back-link">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M19 12H5M12 19l-7-7 7-7"/>
                </svg>
                Back to Today's Trends
            </a>
        </p>
    </footer>
</article>

{build_footer(date_formatted)}

{get_theme_script()}
</body>
</html>"""



def generate_amp_html(
    article: Any,
    tokens: Dict,
) -> str:
    """Generate AMP HTML page for an editorial article."""
    date_formatted = datetime.strptime(article.date, "%Y-%m-%d").strftime(
        "%B %d, %Y"
    )

    # Escape for HTML attributes
    title_escaped = article.title.replace('"', "&quot;")
    summary_escaped = article.summary.replace('"', "&quot;")

    # AMP requires inline styles under 75KB and no external stylesheets except fonts
    amp_styles = f"""
    body {{
        font-family: 'Inter', system-ui, sans-serif;
        background: {tokens['bg_color']};
        color: {tokens['text_color']};
        margin: 0;
        padding: 0;
        line-height: 1.7;
    }}
    .container {{
        max-width: 720px;
        margin: 0 auto;
        padding: 1rem 1.5rem 3rem;
    }}
    header {{
        text-align: center;
        padding: 2rem 0;
        border-bottom: 1px solid {tokens['border_color']};
        margin-bottom: 2rem;
    }}
    .logo {{
        font-size: 1.25rem;
        font-weight: 700;
        color: {tokens['accent_color']};
        text-decoration: none;
    }}
    .article-meta {{
        display: flex;
        gap: 1rem;
        justify-content: center;
        font-size: 0.875rem;
        color: {tokens['muted_color']};
        margin-bottom: 1rem;
    }}
    h1 {{
        font-size: 2rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 1rem;
        color: {tokens['text_color']};
    }}
    .summary {{
        font-size: 1.125rem;
        color: {tokens['muted_color']};
    }}
    .content {{
        font-size: 1.0625rem;
    }}
    .content p {{
        margin-bottom: 1.5rem;
    }}
    .content h2 {{
        font-size: 1.375rem;
        margin: 2rem 0 1rem;
        color: {tokens['accent_color']};
    }}
    .content blockquote {{
        border-left: 4px solid {tokens['primary_color']};
        padding-left: 1rem;
        margin: 1.5rem 0;
        font-style: italic;
        color: {tokens['muted_color']};
    }}
    .content strong {{
        color: {tokens['accent_color']};
    }}
    .sources {{
        background: rgba(255,255,255,0.03);
        border-radius: 8px;
        padding: 1rem;
        margin: 2rem 0;
    }}
    .sources h3 {{
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: {tokens['muted_color']};
        margin-bottom: 0.75rem;
    }}
    .sources ul {{
        list-style: none;
        padding: 0;
        margin: 0;
    }}
    .sources li {{
        padding: 0.5rem 0;
        font-size: 0.875rem;
        color: {tokens['muted_color']};
        border-bottom: 1px solid {tokens['border_color']};
    }}
    .sources li:last-child {{
        border-bottom: none;
    }}
    .keywords {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 1.5rem 0;
    }}
    .keyword {{
        background: rgba(255,255,255,0.05);
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.75rem;
        color: {tokens['muted_color']};
    }}
    footer {{
        margin-top: 3rem;
        padding-top: 2rem;
        border-top: 1px solid {tokens['border_color']};
        text-align: center;
    }}
    .back-link {{
        color: {tokens['accent_color']};
        text-decoration: none;
    }}
    """

    return f"""<!doctype html>
<html amp lang="en">
<head>
<meta charset="utf-8">
<script async src="https://cdn.ampproject.org/v0.js"></script>
<title>{article.title} | DailyTrending.info</title>
<link rel="canonical" href="https://dailytrending.info{article.url}">
<meta name="viewport" content="width=device-width,minimum-scale=1,initial-scale=1">
<meta name="description" content="{summary_escaped}">

<!-- AMP Boilerplate -->
<style amp-boilerplate>body{{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}}@-webkit-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-moz-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-ms-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-o-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}</style><noscript><style amp-boilerplate>body{{-webkit-animation:none;-moz-animation:none;-ms-animation:none;animation:none}}</style></noscript>

<!-- AMP Analytics -->
<script async custom-element="amp-analytics" src="https://cdn.ampproject.org/v0/amp-analytics-0.1.js"></script>

<!-- JSON-LD -->
<script type="application/ld+json">
{{
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "{title_escaped}",
    "description": "{summary_escaped}",
    "datePublished": "{article.date}T06:00:00Z",
    "dateModified": "{article.date}T06:00:00Z",
    "author": {{
        "@type": "Person",
        "name": "Brad Shannon"
    }},
    "publisher": {{
        "@type": "Organization",
        "name": "DailyTrending.info",
        "logo": {{
            "@type": "ImageObject",
            "url": "https://dailytrending.info/icons/icon-512.png"
        }}
    }},
    "mainEntityOfPage": "https://dailytrending.info{article.url}"
}}
</script>

<style amp-custom>
    {amp_styles}
</style>
</head>
<body>
<amp-analytics type="gtag" data-credentials="include">
    <script type="application/json">
    {{
        "vars": {{
            "gtag_id": "G-XZNXRW8S7L",
            "config": {{
                "G-XZNXRW8S7L": {{"groups": "default"}}
            }}
        }}
    }}
    </script>
</amp-analytics>

<header>
    <a href="/" class="logo">DailyTrending.info</a>
</header>

<article class="container">
    <div class="article-meta">
        <time datetime="{article.date}">{date_formatted}</time>
        <span>{article.word_count} words</span>
    </div>

    <h1>{article.title}</h1>
    <p class="summary">{article.summary}</p>

    <div class="content">
        {article.content}
    </div>

    <div class="sources">
        <h3>Stories Referenced</h3>
        <ul>
            {''.join(f'<li>{story}</li>' for story in article.top_stories[:5])}
        </ul>
    </div>

    <div class="keywords">
        {''.join(f'<span class="keyword">{kw}</span>' for kw in article.keywords[:8])}
    </div>

    <footer>
        <a href="/" class="back-link">Back to Today's Trends</a>
        <p style="margin-top: 1rem; font-size: 0.875rem; color: {tokens['muted_color']};">
            <a href="https://dailytrending.info{article.url}" style="color: {tokens['accent_color']};">View full version</a>
        </p>
    </footer>
</article>
</body>
</html>"""

