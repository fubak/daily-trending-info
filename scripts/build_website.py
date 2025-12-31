#!/usr/bin/env python3
"""
Website Builder - Generates modern responsive HTML/CSS from design specs.
Features: Bento grid, fluid typography, dark mode, mobile-first.
"""

import os
import json
import html
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from fetch_images import FallbackImageGenerator


@dataclass
class BuildContext:
    """Context for building the website."""
    trends: List[Dict]
    images: List[Dict]
    design: Dict
    keywords: List[str]
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().strftime("%B %d, %Y")


class WebsiteBuilder:
    """Builds the final HTML/CSS website."""

    def __init__(self, context: BuildContext):
        self.ctx = context
        self.design = context.design

    def build(self) -> str:
        """Build the complete HTML page."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Today's trending topics - {self.design.get('subheadline', 'What the world is talking about')}">
    <meta name="theme-color" content="{self.design.get('color_bg', '#0a0a0a')}">
    <title>{html.escape(self.design.get('headline', "Today's Trends"))} | Trend Watch</title>

    {self._build_fonts()}
    {self._build_styles()}
</head>
<body>
    {self._build_hero()}
    {self._build_ticker()}
    {self._build_main_content()}
    {self._build_footer()}

    {self._build_scripts()}
</body>
</html>"""

    def _build_fonts(self) -> str:
        """Build Google Fonts link."""
        primary = self.design.get('font_primary', 'Space Grotesk').replace(' ', '+')
        secondary = self.design.get('font_secondary', 'Inter').replace(' ', '+')

        return f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family={primary}:wght@400;500;600;700&family={secondary}:wght@400;500;600&display=swap" rel="stylesheet">"""

    def _build_styles(self) -> str:
        """Build all CSS styles."""
        d = self.design

        # Get hero image if available
        hero_image = self.ctx.images[0] if self.ctx.images else None
        hero_bg = ""
        if hero_image:
            hero_bg = f"url('{hero_image.get('url_large', hero_image.get('url_medium', ''))}') center/cover"
        else:
            hero_bg = FallbackImageGenerator.get_gradient_css()

        return f"""
    <style>
        :root {{
            --color-bg: {d.get('color_bg', '#0a0a0a')};
            --color-text: {d.get('color_text', '#ffffff')};
            --color-accent: {d.get('color_accent', '#6366f1')};
            --color-accent-secondary: {d.get('color_accent_secondary', '#8b5cf6')};
            --color-muted: {d.get('color_muted', '#a1a1aa')};
            --color-card-bg: {d.get('color_card_bg', '#18181b')};
            --color-border: {d.get('color_border', '#27272a')};

            --font-primary: '{d.get('font_primary', 'Space Grotesk')}', system-ui, sans-serif;
            --font-secondary: '{d.get('font_secondary', 'Inter')}', system-ui, sans-serif;

            --font-size-hero: {d.get('font_size_hero', 'clamp(2.5rem, 8vw, 6rem)')};
            --font-size-h2: {d.get('font_size_h2', 'clamp(1.5rem, 4vw, 2.5rem)')};
            --font-size-body: {d.get('font_size_body', 'clamp(1rem, 2vw, 1.125rem)')};

            --radius: {d.get('card_radius', '1.5rem')};
            --padding: {d.get('card_padding', '1.5rem')};
            --gap: {d.get('section_gap', '1.5rem')};
            --max-width: {d.get('max_width', '1400px')};

            --transition: {d.get('transition_speed', '0.3s')} ease;
        }}

        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        html {{
            scroll-behavior: smooth;
        }}

        body {{
            font-family: var(--font-secondary);
            font-size: var(--font-size-body);
            line-height: 1.6;
            color: var(--color-text);
            background: var(--color-bg);
            min-height: 100vh;
            overflow-x: hidden;
        }}

        /* Hero Section */
        .hero {{
            position: relative;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 2rem;
            overflow: hidden;
        }}

        .hero::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: {hero_bg};
            opacity: 0.15;
            z-index: 0;
        }}

        .hero::after {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(
                180deg,
                transparent 0%,
                var(--color-bg) 100%
            );
            z-index: 1;
        }}

        .hero-content {{
            position: relative;
            z-index: 2;
            max-width: 900px;
            animation: fadeInUp 1s ease-out;
        }}

        .hero h1 {{
            font-family: var(--font-primary);
            font-size: var(--font-size-hero);
            font-weight: 700;
            line-height: 1.1;
            margin-bottom: 1.5rem;
            background: linear-gradient(135deg, var(--color-text), var(--color-accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .hero p {{
            font-size: clamp(1.1rem, 2.5vw, 1.5rem);
            color: var(--color-muted);
            margin-bottom: 2rem;
            max-width: 600px;
            margin-inline: auto;
        }}

        .hero-date {{
            display: inline-block;
            padding: 0.5rem 1.5rem;
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: 100px;
            font-size: 0.9rem;
            color: var(--color-muted);
        }}

        .scroll-indicator {{
            position: absolute;
            bottom: 2rem;
            left: 50%;
            transform: translateX(-50%);
            z-index: 2;
            animation: bounce 2s infinite;
        }}

        .scroll-indicator span {{
            display: block;
            width: 2px;
            height: 40px;
            background: linear-gradient(to bottom, var(--color-accent), transparent);
            margin: 0 auto 0.5rem;
        }}

        /* Ticker */
        .ticker-wrap {{
            overflow: hidden;
            background: var(--color-card-bg);
            border-top: 1px solid var(--color-border);
            border-bottom: 1px solid var(--color-border);
            padding: 1rem 0;
        }}

        .ticker {{
            display: flex;
            width: fit-content;
            animation: ticker 30s linear infinite;
        }}

        .ticker:hover {{
            animation-play-state: paused;
        }}

        .ticker-item {{
            flex-shrink: 0;
            padding: 0 2rem;
            font-family: var(--font-primary);
            font-size: 0.9rem;
            color: var(--color-muted);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .ticker-item::before {{
            content: '';
            width: 6px;
            height: 6px;
            background: var(--color-accent);
            border-radius: 50%;
        }}

        /* Main Content */
        main {{
            max-width: var(--max-width);
            margin: 0 auto;
            padding: 4rem 1.5rem;
        }}

        .section-header {{
            margin-bottom: 2rem;
        }}

        .section-header h2 {{
            font-family: var(--font-primary);
            font-size: var(--font-size-h2);
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}

        .section-header p {{
            color: var(--color-muted);
        }}

        /* Bento Grid */
        .bento-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            grid-auto-rows: minmax(200px, auto);
            gap: var(--gap);
        }}

        .card {{
            position: relative;
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            padding: var(--padding);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transition: transform var(--transition), box-shadow var(--transition);
        }}

        .card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 20px 40px -12px rgba(0, 0, 0, 0.3);
        }}

        .card::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: inherit;
            opacity: 0.5;
            z-index: 0;
        }}

        .card-content {{
            position: relative;
            z-index: 1;
            height: 100%;
            display: flex;
            flex-direction: column;
        }}

        .card-meta {{
            font-size: 0.8rem;
            color: var(--color-accent);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.75rem;
        }}

        .card h3 {{
            font-family: var(--font-primary);
            font-size: clamp(1.1rem, 2vw, 1.4rem);
            font-weight: 600;
            line-height: 1.3;
            margin-bottom: 0.75rem;
            flex-grow: 1;
        }}

        .card p {{
            font-size: 0.9rem;
            color: var(--color-muted);
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .card-link {{
            position: absolute;
            inset: 0;
            z-index: 2;
        }}

        /* Card Variants */
        .card.featured {{
            grid-column: span 2;
            grid-row: span 2;
        }}

        .card.wide {{
            grid-column: span 2;
        }}

        .card.tall {{
            grid-row: span 2;
        }}

        .card.has-image {{
            background-size: cover;
            background-position: center;
        }}

        .card.has-image::before {{
            background: linear-gradient(
                180deg,
                rgba(0, 0, 0, 0.3) 0%,
                rgba(0, 0, 0, 0.8) 100%
            );
            opacity: 1;
        }}

        .card.accent-bg {{
            background: linear-gradient(135deg, var(--color-accent), var(--color-accent-secondary));
            border-color: transparent;
        }}

        .card.accent-bg .card-meta {{
            color: rgba(255, 255, 255, 0.8);
        }}

        .card.accent-bg p {{
            color: rgba(255, 255, 255, 0.9);
        }}

        /* Keywords Section */
        .keywords {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-top: 2rem;
        }}

        .keyword {{
            padding: 0.5rem 1rem;
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: 100px;
            font-size: 0.85rem;
            color: var(--color-muted);
            transition: all var(--transition);
        }}

        .keyword:hover {{
            border-color: var(--color-accent);
            color: var(--color-accent);
        }}

        /* Footer */
        footer {{
            border-top: 1px solid var(--color-border);
            padding: 3rem 1.5rem;
            text-align: center;
        }}

        .footer-content {{
            max-width: var(--max-width);
            margin: 0 auto;
        }}

        .footer-logo {{
            font-family: var(--font-primary);
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }}

        .footer-meta {{
            font-size: 0.85rem;
            color: var(--color-muted);
            margin-bottom: 1.5rem;
        }}

        .credits {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 1rem;
            font-size: 0.8rem;
            color: var(--color-muted);
        }}

        .credits a {{
            color: var(--color-accent);
            text-decoration: none;
        }}

        .credits a:hover {{
            text-decoration: underline;
        }}

        /* Archive Link */
        .archive-link {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 2rem;
            padding: 0.75rem 1.5rem;
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            color: var(--color-text);
            text-decoration: none;
            font-size: 0.9rem;
            transition: all var(--transition);
        }}

        .archive-link:hover {{
            border-color: var(--color-accent);
            transform: translateY(-2px);
        }}

        /* Animations */
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        @keyframes bounce {{
            0%, 20%, 50%, 80%, 100% {{
                transform: translateX(-50%) translateY(0);
            }}
            40% {{
                transform: translateX(-50%) translateY(-10px);
            }}
            60% {{
                transform: translateX(-50%) translateY(-5px);
            }}
        }}

        @keyframes ticker {{
            0% {{
                transform: translateX(0);
            }}
            100% {{
                transform: translateX(-50%);
            }}
        }}

        /* Responsive */
        @media (max-width: 1024px) {{
            .bento-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .card.featured {{
                grid-column: span 2;
                grid-row: span 1;
            }}

            .card.tall {{
                grid-row: span 1;
            }}
        }}

        @media (max-width: 768px) {{
            :root {{
                --padding: 1.25rem;
                --gap: 1rem;
            }}

            .bento-grid {{
                grid-template-columns: 1fr;
            }}

            .card.featured,
            .card.wide {{
                grid-column: span 1;
            }}

            .hero {{
                min-height: 80vh;
                padding: 1.5rem;
            }}

            .ticker-item {{
                padding: 0 1.5rem;
            }}

            main {{
                padding: 2rem 1rem;
            }}
        }}

        /* Reduced Motion */
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }}
        }}
    </style>"""

    def _build_hero(self) -> str:
        """Build the hero section."""
        headline = html.escape(self.design.get('headline', "Today's Trends"))
        subheadline = html.escape(self.design.get('subheadline', 'What the world is talking about'))

        return f"""
    <section class="hero">
        <div class="hero-content">
            <h1>{headline}</h1>
            <p>{subheadline}</p>
            <span class="hero-date">{self.ctx.generated_at}</span>
        </div>
        <div class="scroll-indicator">
            <span></span>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
        </div>
    </section>"""

    def _build_ticker(self) -> str:
        """Build the trending ticker."""
        # Get keywords for ticker
        keywords = self.ctx.keywords[:20] if self.ctx.keywords else []

        if not keywords:
            keywords = ['trending', 'news', 'technology', 'world', 'today']

        # Double the keywords for seamless loop
        items = keywords + keywords

        ticker_items = '\n'.join(
            f'            <div class="ticker-item">{html.escape(kw.title())}</div>'
            for kw in items
        )

        return f"""
    <div class="ticker-wrap">
        <div class="ticker">
{ticker_items}
        </div>
    </div>"""

    def _build_main_content(self) -> str:
        """Build the main content section with bento grid."""
        trends = self.ctx.trends[:12]
        images = self.ctx.images[1:] if len(self.ctx.images) > 1 else []

        cards_html = []

        for i, trend in enumerate(trends):
            # Determine card variant
            variant = ""
            if i == 0:
                variant = "featured"
            elif i == 1:
                variant = "featured accent-bg"
            elif i == 3:
                variant = "wide"
            elif i == 5:
                variant = "tall"

            # Check for image
            image = images[i] if i < len(images) else None
            bg_style = ""
            if image and variant not in ["accent-bg"]:
                bg_style = f'style="background-image: url(\'{image.get("url_medium", "")}\');"'
                variant += " has-image"

            # Build card HTML
            title = html.escape(trend.get('title', 'Untitled'))
            source = trend.get('source', 'unknown').replace('_', ' ').title()
            desc = html.escape(trend.get('description', '')[:150]) if trend.get('description') else ''
            url = trend.get('url', '#')

            card_html = f"""
            <article class="card {variant}" {bg_style}>
                <div class="card-content">
                    <span class="card-meta">{source}</span>
                    <h3>{title}</h3>
                    {f'<p>{desc}</p>' if desc else ''}
                </div>
                <a href="{html.escape(url)}" class="card-link" target="_blank" rel="noopener" aria-label="Read more about {title}"></a>
            </article>"""

            cards_html.append(card_html)

        # Build keywords section
        keywords_html = '\n'.join(
            f'            <span class="keyword">{html.escape(kw.title())}</span>'
            for kw in self.ctx.keywords[:12]
        )

        return f"""
    <main>
        <div class="section-header">
            <h2>Trending Now</h2>
            <p>The stories shaping today's conversation</p>
        </div>

        <div class="bento-grid">
{''.join(cards_html)}
        </div>

        <div class="keywords">
{keywords_html}
        </div>
    </main>"""

    def _build_footer(self) -> str:
        """Build the footer with attributions."""
        # Build image credits
        credits_html = []

        photographers = set()
        for img in self.ctx.images[:5]:
            photographer = img.get('photographer', '')
            source = img.get('source', '').title()
            url = img.get('photographer_url', '#')

            if photographer and photographer not in photographers:
                photographers.add(photographer)
                credits_html.append(
                    f'<span>Photo by <a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(photographer)}</a> on {source}</span>'
                )

        credits = '\n            '.join(credits_html) if credits_html else '<span>Gradient backgrounds</span>'

        return f"""
    <footer>
        <div class="footer-content">
            <div class="footer-logo">Trend Watch</div>
            <p class="footer-meta">
                Generated on {self.ctx.generated_at}<br>
                Design: {html.escape(self.design.get('theme_name', 'Auto-generated'))}
            </p>

            <div class="credits">
                {credits}
            </div>

            <a href="./archive/" class="archive-link">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 3h18v18H3z"></path>
                    <path d="M21 9H3"></path>
                    <path d="M9 21V9"></path>
                </svg>
                View Archive
            </a>
        </div>
    </footer>"""

    def _build_scripts(self) -> str:
        """Build any necessary JavaScript."""
        return """
    <script>
        // Pause ticker on hover
        const ticker = document.querySelector('.ticker');
        if (ticker) {
            ticker.addEventListener('mouseenter', () => {
                ticker.style.animationPlayState = 'paused';
            });
            ticker.addEventListener('mouseleave', () => {
                ticker.style.animationPlayState = 'running';
            });
        }

        // Smooth scroll for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            });
        });
    </script>"""

    def save(self, filepath: str):
        """Save the built website to a file."""
        html_content = self.build()

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Website saved to {filepath}")
        return filepath


def main():
    """Main entry point for testing website building."""
    # Sample data for testing
    sample_trends = [
        {"title": "AI Revolution in Healthcare", "source": "google_trends", "description": "Artificial intelligence is transforming medical diagnostics and treatment planning.", "url": "#"},
        {"title": "Climate Summit Reaches Historic Agreement", "source": "rss_nyt", "description": "World leaders commit to ambitious carbon reduction targets.", "url": "#"},
        {"title": "SpaceX Starship Launch Success", "source": "hackernews", "description": "The largest rocket ever built completes its first orbital test flight.", "url": "#"},
        {"title": "New iPhone Features Leaked", "source": "rss_verge", "description": "Apple's next smartphone rumored to include revolutionary camera system.", "url": "#"},
        {"title": "Global Markets Rally", "source": "reddit_worldnews", "description": "Stock indices reach all-time highs on positive economic data.", "url": "#"},
        {"title": "Breakthrough in Quantum Computing", "source": "hackernews", "description": "Researchers achieve quantum advantage in practical applications.", "url": "#"},
        {"title": "Electric Vehicle Sales Surge", "source": "rss_techcrunch", "description": "EVs now account for 20% of global car sales.", "url": "#"},
        {"title": "Social Media Platform Launches New Feature", "source": "google_trends", "description": "Major platform introduces AI-powered content recommendations.", "url": "#"},
    ]

    sample_images = [
        {"url_large": "https://images.pexels.com/photos/373543/pexels-photo-373543.jpeg", "url_medium": "https://images.pexels.com/photos/373543/pexels-photo-373543.jpeg?w=800", "photographer": "Pixabay", "photographer_url": "https://pexels.com/@pixabay", "source": "pexels"},
    ]

    sample_design = {
        "theme_name": "Midnight Indigo",
        "mood": "professional",
        "font_primary": "Space Grotesk",
        "font_secondary": "Inter",
        "color_bg": "#0a0a0a",
        "color_text": "#ffffff",
        "color_accent": "#6366f1",
        "color_accent_secondary": "#8b5cf6",
        "color_muted": "#a1a1aa",
        "color_card_bg": "#18181b",
        "color_border": "#27272a",
        "headline": "Today's Pulse",
        "subheadline": "What the world is talking about"
    }

    sample_keywords = ["ai", "climate", "space", "technology", "markets", "quantum", "electric", "social"]

    ctx = BuildContext(
        trends=sample_trends,
        images=sample_images,
        design=sample_design,
        keywords=sample_keywords
    )

    builder = WebsiteBuilder(ctx)
    output_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'index.html')
    builder.save(output_path)

    print(f"\nWebsite built successfully!")
    print(f"Open {output_path} in a browser to view.")


if __name__ == "__main__":
    main()
