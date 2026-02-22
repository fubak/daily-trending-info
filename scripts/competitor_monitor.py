#!/usr/bin/env python3
"""
Competitor & Algorithm Monitoring Script for DailyTrending.info

Monitors:
- Google News algorithm changes (via Search Engine Land, Search Engine Journal)
- Competitor features and updates
- Industry news aggregator trends

Usage:
    python competitor_monitor.py [--output json|markdown] [--save]
"""

import argparse
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup

# Monitoring sources
MONITORING_SOURCES: Dict[str, Dict[str, Any]] = {
    "search_engine_land": {
        "name": "Search Engine Land",
        "url": "https://searchengineland.com/library/google/google-news",
        "rss": "https://searchengineland.com/feed",
        "keywords": ["google news", "news algorithm", "discover", "top stories"],
    },
    "search_engine_journal": {
        "name": "Search Engine Journal",
        "url": "https://www.searchenginejournal.com/category/google-algorithm-updates/",
        "rss": "https://www.searchenginejournal.com/feed/",
        "keywords": ["google news", "algorithm update", "news seo"],
    },
    "google_search_central": {
        "name": "Google Search Central Blog",
        "url": "https://developers.google.com/search/blog",
        "rss": "https://developers.google.com/search/blog/feed.xml",
        "keywords": ["news", "structured data", "discover"],
    },
}

# Competitors to monitor
COMPETITORS: Dict[str, Dict[str, Any]] = {
    "theresanaiforthat": {
        "name": "There's An AI For That",
        "url": "https://theresanaiforthat.com/",
        "check_features": ["trending", "new tools", "categories"],
    },
    "product_hunt": {
        "name": "Product Hunt",
        "url": "https://www.producthunt.com/",
        "check_features": ["daily ranking", "topics", "collections"],
    },
    "hacker_news": {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/",
        "check_features": ["ranking algorithm", "front page"],
    },
    "techmeme": {
        "name": "Techmeme",
        "url": "https://www.techmeme.com/",
        "check_features": ["river of news", "leaderboard", "topics"],
    },
}


@dataclass
class MonitoringAlert:
    """Represents a monitoring alert."""

    source: str
    title: str
    url: str
    summary: str
    relevance: str  # high, medium, low
    detected_at: str
    keywords_matched: List[str]


class CompetitorMonitor:
    """Monitors competitors and algorithm changes."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = (
            cache_dir or Path(__file__).parent.parent / "data" / "monitor_cache"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "DailyTrending Monitor Bot/1.0 (+https://dailytrending.info)"
            }
        )
        self.alerts: List[MonitoringAlert] = []

    def _get_cache_path(self, source_id: str) -> Path:
        """Get cache file path for a source."""
        return self.cache_dir / f"{source_id}_cache.json"

    def _load_cache(self, source_id: str) -> Dict[str, Any]:
        """Load cached data for a source."""
        cache_path = self._get_cache_path(source_id)
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text())
            except Exception:
                pass
        return {"seen_urls": [], "last_check": None}

    def _save_cache(self, source_id: str, cache_data: Dict[str, Any]) -> None:
        """Save cache data for a source."""
        cache_path = self._get_cache_path(source_id)
        cache_path.write_text(json.dumps(cache_data, indent=2))

    def _fetch_rss(self, url: str) -> List[Dict[str, str]]:
        """Fetch and parse RSS feed."""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "xml")

            items = []
            for item in soup.find_all("item")[:20]:  # Last 20 items
                title = item.find("title")
                link = item.find("link")
                description = item.find("description")
                pub_date = item.find("pubDate")

                items.append(
                    {
                        "title": title.get_text() if title else "",
                        "url": link.get_text() if link else "",
                        "description": description.get_text() if description else "",
                        "pub_date": pub_date.get_text() if pub_date else "",
                    }
                )

            return items
        except Exception as e:
            print(f"  Error fetching RSS {url}: {e}")
            return []

    def _check_relevance(self, text: str, keywords: List[str]) -> tuple[str, List[str]]:
        """Check text relevance based on keywords."""
        text_lower = text.lower()
        matched = [kw for kw in keywords if kw.lower() in text_lower]

        if len(matched) >= 2:
            return "high", matched
        elif len(matched) == 1:
            return "medium", matched
        return "low", []

    def monitor_seo_sources(self) -> List[MonitoringAlert]:
        """Monitor SEO/algorithm news sources."""
        print("Monitoring SEO and algorithm news sources...")
        alerts = []

        for source_id, source_config in MONITORING_SOURCES.items():
            print(f"  Checking {source_config['name']}...")
            cache = self._load_cache(source_id)
            seen_urls = set(cache.get("seen_urls", []))

            if source_config.get("rss"):
                items = self._fetch_rss(source_config["rss"])

                for item in items:
                    url = item.get("url", "")
                    if not url or url in seen_urls:
                        continue

                    # Check relevance
                    combined_text = (
                        f"{item.get('title', '')} {item.get('description', '')}"
                    )
                    relevance, matched_keywords = self._check_relevance(
                        combined_text, source_config["keywords"]
                    )

                    if relevance in ["high", "medium"]:
                        alert = MonitoringAlert(
                            source=source_config["name"],
                            title=item.get("title", ""),
                            url=url,
                            summary=item.get("description", "")[:300],
                            relevance=relevance,
                            detected_at=datetime.now().isoformat(),
                            keywords_matched=matched_keywords,
                        )
                        alerts.append(alert)
                        print(
                            f"    [{relevance.upper()}] {item.get('title', '')[:60]}..."
                        )

                    seen_urls.add(url)

            # Update cache
            cache["seen_urls"] = list(seen_urls)[-100:]  # Keep last 100
            cache["last_check"] = datetime.now().isoformat()
            self._save_cache(source_id, cache)

        return alerts

    def check_competitor_status(self) -> Dict[str, Dict[str, Any]]:
        """Check competitor websites for availability and basic metrics."""
        print("\nChecking competitor status...")
        results = {}

        for comp_id, comp_config in COMPETITORS.items():
            print(f"  Checking {comp_config['name']}...")
            try:
                response = self.session.get(comp_config["url"], timeout=10)
                results[comp_id] = {
                    "name": comp_config["name"],
                    "url": comp_config["url"],
                    "status": response.status_code,
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "checked_at": datetime.now().isoformat(),
                    "available": response.status_code == 200,
                }
                print(
                    f"    Status: {response.status_code}, Response: {results[comp_id]['response_time_ms']}ms"
                )
            except Exception as e:
                results[comp_id] = {
                    "name": comp_config["name"],
                    "url": comp_config["url"],
                    "status": 0,
                    "error": str(e),
                    "checked_at": datetime.now().isoformat(),
                    "available": False,
                }
                print(f"    Error: {e}")

        return results

    def generate_report(
        self,
        alerts: List[MonitoringAlert],
        competitor_status: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate monitoring report."""
        high_priority = [a for a in alerts if a.relevance == "high"]
        medium_priority = [a for a in alerts if a.relevance == "medium"]

        return {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_alerts": len(alerts),
                "high_priority": len(high_priority),
                "medium_priority": len(medium_priority),
                "competitors_checked": len(competitor_status),
                "competitors_available": sum(
                    1 for c in competitor_status.values() if c.get("available")
                ),
            },
            "alerts": {
                "high_priority": [asdict(a) for a in high_priority],
                "medium_priority": [asdict(a) for a in medium_priority],
            },
            "competitor_status": competitor_status,
        }

    def format_markdown_report(self, report: Dict) -> str:
        """Format report as Markdown."""
        lines = [
            "# Competitor & Algorithm Monitoring Report",
            f"\n**Generated:** {report['generated_at']}",
            "\n## Summary",
            f"- **Total Alerts:** {report['summary']['total_alerts']}",
            f"- **High Priority:** {report['summary']['high_priority']}",
            f"- **Medium Priority:** {report['summary']['medium_priority']}",
            f"- **Competitors Available:** {report['summary']['competitors_available']}/{report['summary']['competitors_checked']}",
        ]

        if report["alerts"]["high_priority"]:
            lines.append("\n## High Priority Alerts")
            for alert in report["alerts"]["high_priority"]:
                lines.append(f"\n### {alert['title'][:80]}")
                lines.append(f"- **Source:** {alert['source']}")
                lines.append(f"- **URL:** {alert['url']}")
                lines.append(f"- **Keywords:** {', '.join(alert['keywords_matched'])}")
                lines.append(f"- **Summary:** {alert['summary'][:200]}...")

        if report["alerts"]["medium_priority"]:
            lines.append("\n## Medium Priority Alerts")
            for alert in report["alerts"]["medium_priority"]:
                lines.append(f"\n- **{alert['title'][:60]}** ({alert['source']})")
                lines.append(f"  - URL: {alert['url']}")

        lines.append("\n## Competitor Status")
        for comp_id, status in report["competitor_status"].items():
            emoji = "✅" if status.get("available") else "❌"
            lines.append(
                f"- {emoji} **{status['name']}**: {status.get('status', 'N/A')} ({status.get('response_time_ms', 'N/A')}ms)"
            )

        return "\n".join(lines)

    def run(self, output_format: str = "json", save: bool = False) -> Dict:
        """Run full monitoring cycle."""
        print("=" * 60)
        print("DailyTrending.info Competitor & Algorithm Monitor")
        print("=" * 60)

        alerts = self.monitor_seo_sources()
        competitor_status = self.check_competitor_status()
        report = self.generate_report(alerts, competitor_status)

        if output_format == "markdown":
            output = self.format_markdown_report(report)
        else:
            output = json.dumps(report, indent=2)

        if save:
            output_dir = Path(__file__).parent.parent / "data" / "monitoring_reports"
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = f"monitor_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ext = ".md" if output_format == "markdown" else ".json"
            output_path = output_dir / f"{filename}{ext}"
            output_path.write_text(output)
            print(f"\nReport saved to: {output_path}")

        print("\n" + "=" * 60)
        print("Monitoring Complete")
        print("=" * 60)

        return report


def main():
    parser = argparse.ArgumentParser(description="Competitor & Algorithm Monitor")
    parser.add_argument(
        "--output",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save report to file",
    )
    args = parser.parse_args()

    monitor = CompetitorMonitor()
    report = monitor.run(output_format=args.output, save=args.save)

    if not args.save:
        if args.output == "markdown":
            print(monitor.format_markdown_report(report))
        else:
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
