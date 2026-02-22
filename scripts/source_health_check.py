#!/usr/bin/env python3
"""Daily source health checks for trend collection endpoints."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup

from config import DATA_DIR, setup_logging

logger = setup_logging("source_health_check")


@dataclass(frozen=True)
class SourceSpec:
    key: str
    name: str
    url: str
    category: str
    kind: str  # rss | json | html
    selector: Optional[str] = None
    json_count_path: Optional[str] = None


RSS_SOURCES: List[SourceSpec] = [
    SourceSpec("google_trends", "Google Trends", "https://trends.google.com/trending/rss?geo=US", "general", "rss"),
    SourceSpec("news_npr", "NPR", "https://feeds.npr.org/1001/rss.xml", "news", "rss"),
    SourceSpec("news_nyt", "NYT", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "news", "rss"),
    SourceSpec("news_bbc", "BBC", "https://feeds.bbci.co.uk/news/rss.xml", "news", "rss"),
    SourceSpec("news_bbc_world", "BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "news", "rss"),
    SourceSpec("news_guardian", "Guardian", "https://www.theguardian.com/world/rss", "news", "rss"),
    SourceSpec("news_guardian_us", "Guardian US", "https://www.theguardian.com/us-news/rss", "news", "rss"),
    SourceSpec("news_abc", "ABC News", "https://abcnews.go.com/abcnews/topstories", "news", "rss"),
    SourceSpec("news_cbs", "CBS News", "https://www.cbsnews.com/latest/rss/main", "news", "rss"),
    SourceSpec("news_upi", "UPI", "https://rss.upi.com/news/news.rss", "news", "rss"),
    SourceSpec("news_wapo", "Washington Post", "https://feeds.washingtonpost.com/rss/national", "news", "rss"),
    SourceSpec("news_aljazeera", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "news", "rss"),
    SourceSpec("news_pbs", "PBS NewsHour", "https://www.pbs.org/newshour/feeds/rss/headlines", "news", "rss"),
    SourceSpec("tech_verge", "Verge", "https://www.theverge.com/rss/index.xml", "tech", "rss"),
    SourceSpec("tech_ars", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "tech", "rss"),
    SourceSpec("tech_wired", "Wired", "https://www.wired.com/feed/rss", "tech", "rss"),
    SourceSpec("tech_techcrunch", "TechCrunch", "https://techcrunch.com/feed/", "tech", "rss"),
    SourceSpec("tech_engadget", "Engadget", "https://www.engadget.com/rss.xml", "tech", "rss"),
    SourceSpec("tech_mit", "MIT Tech Review", "https://www.technologyreview.com/feed/", "tech", "rss"),
    SourceSpec("tech_gizmodo", "Gizmodo", "https://gizmodo.com/rss", "tech", "rss"),
    SourceSpec("tech_cnet", "CNET", "https://www.cnet.com/rss/news/", "tech", "rss"),
    SourceSpec("tech_mashable", "Mashable", "https://mashable.com/feeds/rss/all", "tech", "rss"),
    SourceSpec("tech_venturebeat", "VentureBeat", "https://venturebeat.com/feed/", "tech", "rss"),
    SourceSpec("science_sciencedaily", "Science Daily", "https://www.sciencedaily.com/rss/all.xml", "science", "rss"),
    SourceSpec("science_nature", "Nature", "https://www.nature.com/nature.rss", "science", "rss"),
    SourceSpec("science_newscientist", "New Scientist", "https://www.newscientist.com/feed/home/", "science", "rss"),
    SourceSpec("science_phys", "Phys.org", "https://phys.org/rss-feed/", "science", "rss"),
    SourceSpec("science_livescience", "Live Science", "https://www.livescience.com/feeds/all", "science", "rss"),
    SourceSpec("science_space", "Space.com", "https://www.space.com/feeds/all", "science", "rss"),
    SourceSpec("science_sciencenews", "ScienceNews", "https://www.sciencenews.org/feed", "science", "rss"),
    SourceSpec("science_ars", "Ars Science", "https://feeds.arstechnica.com/arstechnica/science", "science", "rss"),
    SourceSpec("science_quanta", "Quanta", "https://api.quantamagazine.org/feed/", "science", "rss"),
    SourceSpec("politics_hill", "The Hill", "https://thehill.com/feed/", "politics", "rss"),
    SourceSpec("politics_rollcall", "Roll Call", "https://rollcall.com/feed/", "politics", "rss"),
    SourceSpec("politics_nyt", "NYT Politics", "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml", "politics", "rss"),
    SourceSpec("politics_wapo", "WaPo Politics", "https://feeds.washingtonpost.com/rss/politics", "politics", "rss"),
    SourceSpec("politics_guardian", "Guardian Politics", "https://www.theguardian.com/us-news/us-politics/rss", "politics", "rss"),
    SourceSpec("politics_bbc", "BBC Politics", "https://feeds.bbci.co.uk/news/politics/rss.xml", "politics", "rss"),
    SourceSpec("politics_axios", "Axios", "https://api.axios.com/feed/", "politics", "rss"),
    SourceSpec("politics_npr", "NPR Politics", "https://feeds.npr.org/1014/rss.xml", "politics", "rss"),
    SourceSpec("politics_slate", "Slate", "https://slate.com/feeds/all.rss", "politics", "rss"),
    SourceSpec("finance_cnbc", "CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "finance", "rss"),
    SourceSpec("finance_marketwatch", "MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/", "finance", "rss"),
    SourceSpec("finance_ft", "Financial Times", "https://www.ft.com/rss/home", "finance", "rss"),
    SourceSpec("finance_yahoo", "Yahoo Finance", "https://finance.yahoo.com/news/rssindex", "finance", "rss"),
    SourceSpec("finance_wsj", "WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "finance", "rss"),
    SourceSpec("finance_economist", "Economist", "https://www.economist.com/finance-and-economics/rss.xml", "finance", "rss"),
    SourceSpec("finance_fortune", "Fortune", "https://fortune.com/feed/", "finance", "rss"),
    SourceSpec("finance_bi", "Business Insider", "https://www.businessinsider.com/rss", "finance", "rss"),
    SourceSpec("finance_seekingalpha", "Seeking Alpha", "https://seekingalpha.com/market_currents.xml", "finance", "rss"),
    SourceSpec("sports_espn", "ESPN", "https://www.espn.com/espn/rss/news", "sports", "rss"),
    SourceSpec("sports_bbc", "BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml", "sports", "rss"),
    SourceSpec("sports_cbs", "CBS Sports", "https://www.cbssports.com/rss/headlines/", "sports", "rss"),
    SourceSpec("sports_yahoo", "Yahoo Sports", "https://sports.yahoo.com/rss/", "sports", "rss"),
    SourceSpec("ent_variety", "Variety", "https://variety.com/feed/", "entertainment", "rss"),
    SourceSpec("ent_thr", "Hollywood Reporter", "https://www.hollywoodreporter.com/feed/", "entertainment", "rss"),
    SourceSpec("ent_billboard", "Billboard", "https://www.billboard.com/feed/", "entertainment", "rss"),
    SourceSpec("ent_eonline", "E! Online", "https://www.eonline.com/syndication/rss/top_stories/en_us", "entertainment", "rss"),
    SourceSpec("lobsters", "Lobsters", "https://lobste.rs/rss", "community", "rss"),
    SourceSpec("product_hunt", "Product Hunt", "https://www.producthunt.com/feed", "community", "rss"),
    SourceSpec("slashdot", "Slashdot", "https://rss.slashdot.org/Slashdot/slashdotMain", "community", "rss"),
    SourceSpec("ars_features", "Ars Features", "https://feeds.arstechnica.com/arstechnica/features", "community", "rss"),
    SourceSpec("reddit_news", "Reddit News", "https://www.reddit.com/r/news/.rss", "reddit", "rss"),
    SourceSpec("reddit_worldnews", "Reddit WorldNews", "https://www.reddit.com/r/worldnews/.rss", "reddit", "rss"),
    SourceSpec("reddit_technology", "Reddit Technology", "https://www.reddit.com/r/technology/.rss", "reddit", "rss"),
    SourceSpec("reddit_science", "Reddit Science", "https://www.reddit.com/r/science/.rss", "reddit", "rss"),
    SourceSpec("reddit_business", "Reddit Business", "https://www.reddit.com/r/business/.rss", "reddit", "rss"),
    SourceSpec("reddit_movies", "Reddit Movies", "https://www.reddit.com/r/movies/.rss", "reddit", "rss"),
    SourceSpec("reddit_sports", "Reddit Sports", "https://www.reddit.com/r/sports/.rss", "reddit", "rss"),
    SourceSpec("cmmc_fedscoop", "FedScoop", "https://fedscoop.com/feed/", "cmmc", "rss"),
    SourceSpec("cmmc_defensescoop", "DefenseScoop", "https://defensescoop.com/feed/", "cmmc", "rss"),
    SourceSpec("cmmc_fnn", "Federal News Network", "https://federalnewsnetwork.com/category/technology-main/cybersecurity/feed/", "cmmc", "rss"),
    SourceSpec("cmmc_nextgov", "Nextgov Cybersecurity", "https://www.nextgov.com/rss/cybersecurity/", "cmmc", "rss"),
    SourceSpec("cmmc_govcon", "GovCon Wire", "https://www.govconwire.com/feed/", "cmmc", "rss"),
    SourceSpec("cmmc_securityweek", "SecurityWeek", "https://www.securityweek.com/feed/", "cmmc", "rss"),
    SourceSpec("cmmc_cyberscoop", "Cyberscoop", "https://cyberscoop.com/feed/", "cmmc", "rss"),
    SourceSpec("cmmc_breakingdefense", "Breaking Defense", "https://breakingdefense.com/feed/", "cmmc", "rss"),
    SourceSpec("cmmc_defenseone", "Defense One", "https://www.defenseone.com/rss/all/", "cmmc", "rss"),
    SourceSpec("cmmc_defensenews", "Defense News", "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", "cmmc", "rss"),
    SourceSpec("cmmc_executivegov", "ExecutiveGov", "https://executivegov.com/feed/", "cmmc", "rss"),
    SourceSpec("cmmc_reddit_cmmc", "Reddit CMMC", "https://www.reddit.com/r/CMMC/.rss", "cmmc", "rss"),
    SourceSpec("cmmc_reddit_nistcontrols", "Reddit NISTControls", "https://www.reddit.com/r/NISTControls/.rss", "cmmc", "rss"),
    SourceSpec("cmmc_reddit_federalemployees", "Reddit FederalEmployees", "https://www.reddit.com/r/FederalEmployees/.rss", "cmmc", "rss"),
]

JSON_SOURCES: List[SourceSpec] = [
    SourceSpec(
        "hackernews_topstories",
        "Hacker News Top Stories",
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        "community",
        "json",
        json_count_path="",
    ),
    SourceSpec(
        "devto_api",
        "Dev.to API",
        "https://dev.to/api/articles?top=1&per_page=15",
        "community",
        "json",
        json_count_path="",
    ),
    SourceSpec(
        "github_search_api",
        "GitHub Search API",
        "https://api.github.com/search/repositories?q=created:%3E2026-01-01&sort=stars&order=desc&per_page=10",
        "community",
        "json",
        json_count_path="items",
    ),
    SourceSpec(
        "wikipedia_parse_api",
        "Wikipedia Parse API",
        "https://en.wikipedia.org/w/api.php?action=parse&page=Portal:Current_events&prop=text&format=json&formatversion=2",
        "reference",
        "json",
        json_count_path="parse",
    ),
]

HTML_SOURCES: List[SourceSpec] = [
    SourceSpec(
        "github_trending_html",
        "GitHub Trending HTML",
        "https://github.com/trending?since=daily&spoken_language_code=en",
        "community",
        "html",
        selector="article.Box-row",
    ),
    SourceSpec(
        "wikipedia_current_html",
        "Wikipedia Current Events HTML",
        "https://en.wikipedia.org/wiki/Portal:Current_events",
        "reference",
        "html",
        selector=".current-events-content li, .vevent li",
    ),
]

ALL_SOURCES: List[SourceSpec] = RSS_SOURCES + JSON_SOURCES + HTML_SOURCES


def _get_nested_value(payload: Any, path: str) -> Any:
    if not path:
        return payload
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _base_result(source: SourceSpec) -> Dict[str, Any]:
    return {
        "key": source.key,
        "name": source.name,
        "category": source.category,
        "kind": source.kind,
        "url": source.url,
        "status": "down",
        "http_status": None,
        "latency_ms": None,
        "entry_count": 0,
        "content_type": "",
        "error": "",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _check_rss(response: requests.Response) -> Dict[str, Any]:
    feed = feedparser.parse(response.content)
    entry_count = len(feed.entries)

    status = "healthy" if entry_count > 0 else "degraded"
    error = ""

    if feed.bozo and entry_count == 0:
        status = "down"
        error = str(feed.bozo_exception)
    elif feed.bozo:
        status = "degraded"
        error = str(feed.bozo_exception)

    return {"status": status, "entry_count": entry_count, "error": error}


def _check_json(response: requests.Response, count_path: Optional[str]) -> Dict[str, Any]:
    payload = response.json()
    target = _get_nested_value(payload, count_path or "")

    if isinstance(target, list):
        entry_count = len(target)
    elif isinstance(target, dict):
        entry_count = len(target.keys())
    elif target is None:
        entry_count = 0
    else:
        entry_count = 1

    status = "healthy" if entry_count > 0 else "degraded"
    return {"status": status, "entry_count": entry_count, "error": ""}


def _check_html(response: requests.Response, selector: Optional[str]) -> Dict[str, Any]:
    if not selector:
        return {"status": "healthy", "entry_count": 1, "error": ""}

    soup = BeautifulSoup(response.text, "html.parser")
    matches = soup.select(selector)
    entry_count = len(matches)
    status = "healthy" if entry_count > 0 else "down"
    error = "" if entry_count > 0 else f"No matches for selector: {selector}"
    return {"status": status, "entry_count": entry_count, "error": error}


def check_source(session: requests.Session, source: SourceSpec, timeout: float) -> Dict[str, Any]:
    result = _base_result(source)
    start = time.perf_counter()

    headers: Dict[str, str] = {}
    if "reddit.com" in source.url:
        headers["User-Agent"] = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
            "DailyTrendingHealthCheck/1.0"
        )

    try:
        response = session.get(source.url, timeout=timeout, headers=headers or None)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)

        result["http_status"] = response.status_code
        result["latency_ms"] = latency_ms
        result["content_type"] = response.headers.get("content-type", "")

        if response.status_code >= 400:
            result["status"] = "down"
            result["error"] = f"HTTP {response.status_code}"
            return result

        if source.kind == "rss":
            check = _check_rss(response)
        elif source.kind == "json":
            check = _check_json(response, source.json_count_path)
        else:
            check = _check_html(response, source.selector)

        result.update(check)
        return result

    except Exception as exc:
        result["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        result["status"] = "down"
        result["error"] = str(exc)
        return result


def run_health_check(timeout: float, workers: int) -> Dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
                "DailyTrendingHealthCheck/1.0"
            )
        }
    )

    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(check_source, session, source, timeout): source
            for source in ALL_SOURCES
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    {
                        "key": source.key,
                        "name": source.name,
                        "category": source.category,
                        "kind": source.kind,
                        "url": source.url,
                        "status": "down",
                        "http_status": None,
                        "latency_ms": None,
                        "entry_count": 0,
                        "content_type": "",
                        "error": str(exc),
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

    results.sort(key=lambda row: (row["category"], row["name"]))

    summary = {
        "total": len(results),
        "healthy": sum(1 for r in results if r["status"] == "healthy"),
        "degraded": sum(1 for r in results if r["status"] == "degraded"),
        "down": sum(1 for r in results if r["status"] == "down"),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": timeout,
        "workers": workers,
        "summary": summary,
        "sources": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check source health for DailyTrending collectors")
    parser.add_argument(
        "--output",
        type=Path,
        default=DATA_DIR / "source_health.json",
        help="Output JSON path (default: data/source_health.json)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="Per-source HTTP timeout in seconds",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Parallel worker count",
    )
    parser.add_argument(
        "--fail-on-down",
        action="store_true",
        help="Exit non-zero when any source is down",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_health_check(timeout=args.timeout, workers=args.workers)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    summary = report["summary"]
    logger.info(
        "Source health: %s total, %s healthy, %s degraded, %s down",
        summary["total"],
        summary["healthy"],
        summary["degraded"],
        summary["down"],
    )
    logger.info("Saved source health report to %s", args.output)

    if args.fail_on_down and summary["down"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
