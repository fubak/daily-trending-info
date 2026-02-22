#!/usr/bin/env python3
"""
Archive Manager - Manages daily archives of generated websites.
Features: Daily snapshots, browsable index, retention policy.
"""

import os
import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import html

# Import shared components for consistent header/footer
from shared_components import (
    build_header,
    build_footer,
    get_header_styles,
    get_footer_styles,
    get_theme_script,
)


class ArchiveManager:
    """Manages the archive of daily website generations."""

    def __init__(self, public_dir: str = "public", archive_subdir: str = "archive"):
        self.public_dir = Path(public_dir)
        self.archive_dir = self.public_dir / archive_subdir
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def archive_current(self, design: Optional[Dict] = None) -> Optional[str]:
        """
        Archive the current website to a dated folder.
        Returns the archive path if successful.
        """
        current_index = self.public_dir / "index.html"

        if not current_index.exists():
            print("No current website to archive")
            return None

        # Create dated archive folder
        today = datetime.now().strftime("%Y-%m-%d")
        archive_path = self.archive_dir / today

        # Don't overwrite existing archive, but always regenerate index
        if archive_path.exists():
            print(f"Archive for {today} already exists, skipping")
            # Still regenerate the index in case template changed
            self.generate_index()
            return str(archive_path)

        archive_path.mkdir(parents=True, exist_ok=True)

        # Copy the current index.html and add canonical URL
        with open(current_index, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Add canonical URL for the archive page
        canonical_url = f"https://dailytrending.info/archive/{today}/"
        canonical_tag = f'<link rel="canonical" href="{canonical_url}">'

        # Replace existing canonical or add new one
        if '<link rel="canonical"' in html_content:
            html_content = re.sub(
                r'<link rel="canonical"[^>]*>', canonical_tag, html_content
            )
        else:
            # Insert after <head>
            html_content = html_content.replace(
                "<head>", f"<head>\n    {canonical_tag}", 1
            )

        # Write the modified HTML
        with open(archive_path / "index.html", "w", encoding="utf-8") as f:
            f.write(html_content)

        # Save metadata
        metadata = {
            "date": today,
            "archived_at": datetime.now().isoformat(),
            "design": design or {},
        }

        with open(archive_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"Archived current site to {archive_path}")

        # Regenerate the archive index
        self.generate_index()

        return str(archive_path)

    def list_archives(self) -> List[Dict]:
        """List all archived websites with their metadata."""
        archives = []

        for item in sorted(self.archive_dir.iterdir(), reverse=True):
            if item.is_dir() and (item / "index.html").exists():
                metadata_file = item / "metadata.json"

                metadata = {"date": item.name}
                if metadata_file.exists():
                    try:
                        with open(metadata_file) as f:
                            metadata.update(json.load(f))
                    except json.JSONDecodeError:
                        pass

                archives.append(
                    {
                        "path": str(item),
                        "folder": item.name,
                        "url": f"./{item.name}/",
                        **metadata,
                    }
                )

        return archives

    def cleanup_old(self, keep_days: int = 30) -> int:
        """
        Remove archives older than keep_days.
        Returns number of archives removed.
        """
        cutoff = datetime.now() - timedelta(days=keep_days)
        removed = 0

        for item in self.archive_dir.iterdir():
            if item.is_dir():
                try:
                    # Parse date from folder name
                    folder_date = datetime.strptime(item.name, "%Y-%m-%d")
                    if folder_date < cutoff:
                        shutil.rmtree(item)
                        removed += 1
                        print(f"Removed old archive: {item.name}")
                except ValueError:
                    # Not a date-formatted folder, skip
                    continue

        if removed > 0:
            # Regenerate index after cleanup
            self.generate_index()

        print(f"Cleaned up {removed} old archives")
        return removed

    def generate_index(self) -> str:
        """Generate the archive index page with consistent header/footer."""
        archives = self.list_archives()
        date_str = datetime.now().strftime("%B %d, %Y")

        # Build archive cards
        cards_html = []
        for archive in archives:
            date = archive.get("date", "Unknown")
            design = archive.get("design", {})
            theme = design.get("theme_name", "Auto-generated")
            headline = design.get("headline", "Trending")
            accent = design.get("color_accent", "#6366f1")
            url = archive.get("url", "#")

            # Parse date for display
            try:
                parsed_date = datetime.strptime(date, "%Y-%m-%d")
                display_date = parsed_date.strftime("%B %d, %Y")
                day_of_week = parsed_date.strftime("%A")
            except ValueError:
                display_date = date
                day_of_week = ""

            card = f"""
            <a href="{html.escape(url)}" class="archive-card" style="--card-accent: {accent}">
                <div class="archive-card-header">
                    <span class="archive-day">{day_of_week}</span>
                    <span class="archive-date">{display_date}</span>
                </div>
                <h3 class="archive-headline">{html.escape(headline[:50])}</h3>
                <span class="archive-theme">{html.escape(theme)}</span>
            </a>"""
            cards_html.append(card)

        # Get shared styles
        header_styles = get_header_styles()
        footer_styles = get_footer_styles()

        # Build the full index HTML with shared header/footer
        index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark-mode">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archive | DailyTrending.info</title>
    <meta name="description" content="Browse the archive of daily CMMC and compliance news. Each day features curated content from trusted federal and cybersecurity sources.">
    <link rel="canonical" href="https://dailytrending.info/archive/">
    <meta property="og:title" content="Archive | DailyTrending.info">
    <meta property="og:description" content="Browse previous daily DailyTrending.info snapshots with curated compliance news.">
    <meta property="og:image" content="https://dailytrending.info/og-image.png">
    <meta property="og:url" content="https://dailytrending.info/archive/">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --color-bg: #0a0a0a;
            --color-text: #ffffff;
            --color-muted: #a1a1aa;
            --color-card-bg: #18181b;
            --color-border: #27272a;
            --color-accent: #6366f1;
            --font-primary: 'Space Grotesk', system-ui, sans-serif;
            --font-secondary: 'Inter', system-ui, sans-serif;
            --radius: 1rem;
        }}

        /* Light mode */
        body.light-mode {{
            --color-bg: #fafafa;
            --color-text: #18181b;
            --color-muted: #71717a;
            --color-card-bg: #ffffff;
            --color-border: #e4e4e7;
        }}

        /* Dark mode */
        body.dark-mode {{
            --color-bg: #0a0a0a;
            --color-text: #ffffff;
            --color-muted: #a1a1aa;
            --color-card-bg: #18181b;
            --color-border: #27272a;
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
        body.view-list .archive-grid {{
            display: flex;
            flex-direction: column;
            gap: 0;
        }}
        body.view-list .archive-card {{
            background: transparent;
            border: none;
            border-bottom: 1px solid var(--color-border);
            border-radius: 0;
            padding: 0.5rem 0;
            padding-left: 1.5rem;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: var(--font-secondary);
            background: var(--color-bg);
            color: var(--color-text);
            min-height: 100vh;
            line-height: 1.6;
        }}

        /* Shared navigation styles */
        {header_styles}

        /* Shared footer styles */
        {footer_styles}

        /* Archive page specific styles */
        .archive-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}

        .archive-header {{
            text-align: center;
            padding: 3rem 0 2rem;
        }}

        .archive-header h1 {{
            font-family: var(--font-primary);
            font-size: clamp(2rem, 5vw, 3rem);
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}

        .archive-header p {{
            color: var(--color-muted);
            font-size: 1.1rem;
        }}

        .archive-stats {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1.5rem;
            padding: 1rem;
            background: var(--color-card-bg);
            border-radius: var(--radius);
            border: 1px solid var(--color-border);
        }}

        .archive-stat {{
            text-align: center;
        }}

        .archive-stat-value {{
            font-family: var(--font-primary);
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--color-accent);
        }}

        .archive-stat-label {{
            font-size: 0.8rem;
            color: var(--color-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .archive-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-top: 2rem;
        }}

        .archive-card {{
            display: flex;
            flex-direction: column;
            background: var(--color-card-bg);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            padding: 1.5rem;
            text-decoration: none;
            color: inherit;
            transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
        }}

        .archive-card:hover {{
            transform: translateY(-4px);
            border-color: var(--card-accent, var(--color-accent));
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
        }}

        .archive-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }}

        .archive-day {{
            font-size: 0.8rem;
            color: var(--card-accent, var(--color-accent));
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }}

        .archive-date {{
            font-size: 0.85rem;
            color: var(--color-muted);
        }}

        .archive-headline {{
            font-family: var(--font-primary);
            font-size: 1.25rem;
            font-weight: 600;
            line-height: 1.3;
            margin-bottom: 0.75rem;
            flex-grow: 1;
        }}

        .archive-theme {{
            font-size: 0.8rem;
            color: var(--color-muted);
            padding-top: 0.75rem;
            border-top: 1px solid var(--color-border);
        }}

        .empty-state {{
            text-align: center;
            padding: 4rem 2rem;
            color: var(--color-muted);
        }}

        .empty-state svg {{
            width: 64px;
            height: 64px;
            margin-bottom: 1rem;
            opacity: 0.5;
        }}

        @media (max-width: 640px) {{
            .archive-grid {{
                grid-template-columns: 1fr;
            }}

            .archive-header {{
                padding: 2rem 0;
            }}

            .archive-stats {{
                flex-direction: column;
                gap: 1rem;
            }}
        }}
    </style>
</head>
<body class="dark-mode">
    {build_header(active_page='archive', date_str=date_str)}

    <main class="archive-container">
        <div class="archive-header">
            <h1>Archive</h1>
            <p>Browse previous daily trend snapshots</p>
            <div class="archive-stats">
                <div class="archive-stat">
                    <div class="archive-stat-value">{len(archives)}</div>
                    <div class="archive-stat-label">{'Snapshot' if len(archives) == 1 else 'Snapshots'}</div>
                </div>
                <div class="archive-stat">
                    <div class="archive-stat-value">30</div>
                    <div class="archive-stat-label">Day Retention</div>
                </div>
            </div>
        </div>

        {self._build_archive_content(cards_html)}
    </main>

    {build_footer(date_str=date_str)}

    {get_theme_script()}
</body>
</html>"""

        # Save the index
        index_path = self.archive_dir / "index.html"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_html)

        print(f"Generated archive index with {len(archives)} entries")
        return str(index_path)

    def _build_archive_content(self, cards_html: List[str]) -> str:
        """Build the archive content section."""
        if not cards_html:
            return """
        <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M3 3h18v18H3z"></path>
                <path d="M21 9H3"></path>
                <path d="M9 21V9"></path>
            </svg>
            <h3>No Archives Yet</h3>
            <p>Archives will appear here after the first daily regeneration.</p>
        </div>"""

        return f"""
        <div class="archive-grid">
            {''.join(cards_html)}
        </div>"""


def main():
    """Main entry point for testing archive manager."""
    import sys

    # Get the project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    manager = ArchiveManager(public_dir=str(project_root / "public"))

    # Command line interface
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "archive":
            manager.archive_current()
        elif command == "list":
            archives = manager.list_archives()
            print(f"\nFound {len(archives)} archives:")
            for arch in archives:
                print(
                    f"  {arch['folder']}: {arch.get('design', {}).get('theme_name', 'Unknown')}"
                )
        elif command == "cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            manager.cleanup_old(keep_days=days)
        elif command == "index":
            manager.generate_index()
        else:
            print(f"Unknown command: {command}")
            print("Usage: archive_manager.py [archive|list|cleanup|index]")
    else:
        # Default: show status
        archives = manager.list_archives()
        print(f"Archive Status:")
        print(f"  Location: {manager.archive_dir}")
        print(f"  Archives: {len(archives)}")

        if archives:
            print(f"  Latest: {archives[0]['folder']}")
            oldest = (
                archives[-1]["folder"] if len(archives) > 1 else archives[0]["folder"]
            )
            print(f"  Oldest: {oldest}")


if __name__ == "__main__":
    main()
