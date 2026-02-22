#!/usr/bin/env python3
"""Canonical source catalog shared by collectors, health checks, and metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HEADER_PROFILES: Dict[str, Dict[str, str]] = {
    "default": {},
    "reddit": {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
            "DailyTrendingBot/1.0"
        ),
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    },
    "cmmc_reddit": {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
            "CMMCWatch/1.0"
        ),
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    },
    # Breaking Defense blocks some automated user agents but allows simple browser-like strings.
    "breaking_defense": {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    },
}

# Transport tuning used by both runtime collection and health checks.
DOMAIN_FETCH_PROFILES: Dict[str, Dict[str, object]] = {
    "feeds.washingtonpost.com": {
        "attempts": 3,
        "retry_delay": 0.8,
        "timeout": 20.0,
    },
    "breakingdefense.com": {
        "attempts": 2,
        "retry_delay": 0.6,
        "headers_profile": "breaking_defense",
        "timeout": 15.0,
    },
}


@dataclass(frozen=True)
class SourceSpec:
    key: str
    name: str
    url: str
    category: str
    kind: str  # rss | json | html
    source_key: Optional[str] = None  # Trend.source key
    collector: Optional[str] = None
    selector: Optional[str] = None
    json_count_path: Optional[str] = None
    timeout_seconds: Optional[float] = None
    headers_profile: str = "default"
    fallback_url: Optional[str] = None
    tier: int = 4
    source_type: str = "other"
    risk: str = "medium"
    language: str = "en"
    parser: str = "rss"
    healthcheck: bool = True


def _rss(
    key: str,
    name: str,
    url: str,
    category: str,
    collector: str,
    *,
    source_key: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    headers_profile: str = "default",
    fallback_url: Optional[str] = None,
    tier: int = 2,
    source_type: str = "news",
    risk: str = "low",
    parser: str = "rss",
) -> SourceSpec:
    return SourceSpec(
        key=key,
        name=name,
        url=url,
        category=category,
        kind="rss",
        source_key=source_key or key,
        collector=collector,
        timeout_seconds=timeout_seconds,
        headers_profile=headers_profile,
        fallback_url=fallback_url,
        tier=tier,
        source_type=source_type,
        risk=risk,
        parser=parser,
    )


def _json(
    key: str,
    name: str,
    url: str,
    category: str,
    *,
    source_key: Optional[str] = None,
    collector: Optional[str] = None,
    json_count_path: Optional[str] = None,
    tier: int = 3,
    source_type: str = "community",
    risk: str = "low",
    fallback_url: Optional[str] = None,
) -> SourceSpec:
    return SourceSpec(
        key=key,
        name=name,
        url=url,
        category=category,
        kind="json",
        source_key=source_key,
        collector=collector,
        json_count_path=json_count_path,
        fallback_url=fallback_url,
        tier=tier,
        source_type=source_type,
        risk=risk,
        parser="json_api",
    )


def _html(
    key: str,
    name: str,
    url: str,
    category: str,
    *,
    source_key: Optional[str] = None,
    collector: Optional[str] = None,
    selector: Optional[str] = None,
    tier: int = 3,
    source_type: str = "reference",
    risk: str = "low",
    fallback_url: Optional[str] = None,
) -> SourceSpec:
    return SourceSpec(
        key=key,
        name=name,
        url=url,
        category=category,
        kind="html",
        source_key=source_key,
        collector=collector,
        selector=selector,
        fallback_url=fallback_url,
        tier=tier,
        source_type=source_type,
        risk=risk,
        parser="html_scrape",
    )


# Canonical collector inputs.
COLLECTOR_SOURCES: List[SourceSpec] = [
    _rss(
        "google_trends",
        "Google Trends",
        "https://trends.google.com/trending/rss?geo=US",
        "general",
        "google_trends",
        tier=3,
        source_type="search",
        risk="medium",
    ),
    # News
    _rss("news_npr", "NPR", "https://feeds.npr.org/1001/rss.xml", "news", "news_rss", tier=1),
    _rss("news_nyt", "NYT", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "news", "news_rss", tier=1),
    _rss("news_bbc", "BBC", "https://feeds.bbci.co.uk/news/rss.xml", "news", "news_rss", tier=1),
    _rss("news_bbc_world", "BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "news", "news_rss", tier=1),
    _rss("news_guardian", "Guardian", "https://www.theguardian.com/world/rss", "news", "news_rss", tier=1),
    _rss("news_guardian_us", "Guardian US", "https://www.theguardian.com/us-news/rss", "news", "news_rss", tier=1),
    _rss("news_abc", "ABC News", "https://abcnews.go.com/abcnews/topstories", "news", "news_rss", tier=2),
    _rss("news_cbs", "CBS News", "https://www.cbsnews.com/latest/rss/main", "news", "news_rss", tier=2),
    _rss("news_upi", "UPI", "https://rss.upi.com/news/news.rss", "news", "news_rss", tier=2),
    _rss(
        "news_wapo",
        "Washington Post",
        "https://feeds.washingtonpost.com/rss/national",
        "news",
        "news_rss",
        timeout_seconds=20.0,
        fallback_url=(
            "https://news.google.com/rss/search?"
            "q=site:washingtonpost.com+when:2d&hl=en-US&gl=US&ceid=US:en"
        ),
        tier=1,
    ),
    _rss("news_aljazeera", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "news", "news_rss", tier=2, risk="medium"),
    _rss("news_pbs", "PBS NewsHour", "https://www.pbs.org/newshour/feeds/rss/headlines", "news", "news_rss", tier=1),
    # Tech
    _rss("tech_verge", "Verge", "https://www.theverge.com/rss/index.xml", "tech", "tech_rss", tier=2, source_type="tech"),
    _rss("tech_ars", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "tech", "tech_rss", tier=2, source_type="tech"),
    _rss("tech_wired", "Wired", "https://www.wired.com/feed/rss", "tech", "tech_rss", tier=2, source_type="tech"),
    _rss("tech_techcrunch", "TechCrunch", "https://techcrunch.com/feed/", "tech", "tech_rss", tier=2, source_type="tech"),
    _rss("tech_engadget", "Engadget", "https://www.engadget.com/rss.xml", "tech", "tech_rss", tier=3, source_type="tech"),
    _rss("tech_mit", "MIT Tech Review", "https://www.technologyreview.com/feed/", "tech", "tech_rss", tier=2, source_type="tech"),
    _rss("tech_gizmodo", "Gizmodo", "https://gizmodo.com/rss", "tech", "tech_rss", tier=3, source_type="tech"),
    _rss("tech_cnet", "CNET", "https://www.cnet.com/rss/news/", "tech", "tech_rss", tier=3, source_type="tech"),
    _rss("tech_mashable", "Mashable", "https://mashable.com/feeds/rss/all", "tech", "tech_rss", tier=3, source_type="tech"),
    _rss("tech_venturebeat", "VentureBeat", "https://venturebeat.com/feed/", "tech", "tech_rss", tier=3, source_type="tech"),
    # Science
    _rss("science_sciencedaily", "Science Daily", "https://www.sciencedaily.com/rss/all.xml", "science", "science_rss", tier=2),
    _rss("science_nature", "Nature", "https://www.nature.com/nature.rss", "science", "science_rss", tier=1),
    _rss("science_newscientist", "New Scientist", "https://www.newscientist.com/feed/home/", "science", "science_rss", tier=2),
    _rss("science_phys", "Phys.org", "https://phys.org/rss-feed/", "science", "science_rss", tier=2),
    _rss("science_livescience", "Live Science", "https://www.livescience.com/feeds/all", "science", "science_rss", tier=2),
    _rss("science_space", "Space.com", "https://www.space.com/feeds/all", "science", "science_rss", tier=2),
    _rss("science_sciencenews", "ScienceNews", "https://www.sciencenews.org/feed", "science", "science_rss", tier=2),
    _rss("science_ars", "Ars Science", "https://feeds.arstechnica.com/arstechnica/science", "science", "science_rss", tier=2),
    _rss("science_quanta", "Quanta", "https://api.quantamagazine.org/feed/", "science", "science_rss", tier=1),
    _rss("science_mit", "MIT Tech Review", "https://www.technologyreview.com/feed/", "science", "science_rss", tier=2),
    # Politics
    _rss("politics_hill", "The Hill", "https://thehill.com/feed/", "politics", "politics_rss", tier=2),
    _rss("politics_rollcall", "Roll Call", "https://rollcall.com/feed/", "politics", "politics_rss", tier=2),
    _rss("politics_nyt", "NYT Politics", "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml", "politics", "politics_rss", tier=1),
    _rss(
        "politics_wapo",
        "WaPo Politics",
        "https://feeds.washingtonpost.com/rss/politics",
        "politics",
        "politics_rss",
        timeout_seconds=20.0,
        fallback_url=(
            "https://news.google.com/rss/search?"
            "q=site:washingtonpost.com+politics+when:2d&hl=en-US&gl=US&ceid=US:en"
        ),
        tier=1,
    ),
    _rss("politics_guardian", "Guardian Politics", "https://www.theguardian.com/us-news/us-politics/rss", "politics", "politics_rss", tier=1),
    _rss("politics_bbc", "BBC Politics", "https://feeds.bbci.co.uk/news/politics/rss.xml", "politics", "politics_rss", tier=1),
    _rss("politics_axios", "Axios", "https://api.axios.com/feed/", "politics", "politics_rss", tier=2),
    _rss("politics_npr", "NPR Politics", "https://feeds.npr.org/1014/rss.xml", "politics", "politics_rss", tier=1),
    _rss("politics_slate", "Slate", "https://slate.com/feeds/all.rss", "politics", "politics_rss", tier=3),
    # Finance
    _rss("finance_cnbc", "CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "finance", "finance_rss", tier=2),
    _rss(
        "finance_marketwatch",
        "MarketWatch",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "finance",
        "finance_rss",
        fallback_url=(
            "https://news.google.com/rss/search?"
            "q=site:marketwatch.com+markets+when:1d&hl=en-US&gl=US&ceid=US:en"
        ),
        tier=2,
    ),
    _rss("finance_ft", "Financial Times", "https://www.ft.com/rss/home", "finance", "finance_rss", tier=1),
    _rss("finance_yahoo", "Yahoo Finance", "https://finance.yahoo.com/news/rssindex", "finance", "finance_rss", tier=3),
    _rss("finance_wsj", "WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "finance", "finance_rss", tier=1),
    _rss("finance_economist", "Economist", "https://www.economist.com/finance-and-economics/rss.xml", "finance", "finance_rss", tier=1),
    _rss("finance_fortune", "Fortune", "https://fortune.com/feed/", "finance", "finance_rss", tier=2),
    _rss("finance_bi", "Business Insider", "https://www.businessinsider.com/rss", "finance", "finance_rss", tier=3),
    _rss("finance_seekingalpha", "Seeking Alpha", "https://seekingalpha.com/market_currents.xml", "finance", "finance_rss", tier=3),
    # Sports
    _rss("sports_espn", "ESPN", "https://www.espn.com/espn/rss/news", "sports", "sports_rss", tier=3),
    _rss("sports_bbc", "BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml", "sports", "sports_rss", tier=3),
    _rss("sports_cbs", "CBS Sports", "https://www.cbssports.com/rss/headlines/", "sports", "sports_rss", tier=3),
    _rss("sports_yahoo", "Yahoo Sports", "https://sports.yahoo.com/rss/", "sports", "sports_rss", tier=3),
    # Entertainment
    _rss("ent_variety", "Variety", "https://variety.com/feed/", "entertainment", "entertainment_rss", tier=3),
    _rss("ent_thr", "Hollywood Reporter", "https://www.hollywoodreporter.com/feed/", "entertainment", "entertainment_rss", tier=3),
    _rss("ent_billboard", "Billboard", "https://www.billboard.com/feed/", "entertainment", "entertainment_rss", tier=3),
    _rss("ent_eonline", "E! Online", "https://www.eonline.com/syndication/rss/top_stories/en_us", "entertainment", "entertainment_rss", tier=3),
    # Community + reference
    _rss("lobsters", "Lobsters", "https://lobste.rs/rss", "community", "lobsters", tier=2, source_type="community"),
    _rss("product_hunt", "Product Hunt", "https://www.producthunt.com/feed", "community", "product_hunt", tier=3, source_type="product"),
    _rss("slashdot", "Slashdot", "https://rss.slashdot.org/Slashdot/slashdotMain", "community", "slashdot", tier=3, source_type="community"),
    _rss("ars_features", "Ars Features", "https://feeds.arstechnica.com/arstechnica/features", "community", "ars_features", tier=2, source_type="tech"),
    # Reddit (general)
    _rss("reddit_news", "Reddit News", "https://www.reddit.com/r/news/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_worldnews", "Reddit WorldNews", "https://www.reddit.com/r/worldnews/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_politics", "Reddit Politics", "https://www.reddit.com/r/politics/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_upliftingnews", "Reddit UpliftingNews", "https://www.reddit.com/r/upliftingnews/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_technology", "Reddit Technology", "https://www.reddit.com/r/technology/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_science", "Reddit Science", "https://www.reddit.com/r/science/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_space", "Reddit Space", "https://www.reddit.com/r/space/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_business", "Reddit Business", "https://www.reddit.com/r/business/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_economics", "Reddit Economics", "https://www.reddit.com/r/economics/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_personalfinance", "Reddit PersonalFinance", "https://www.reddit.com/r/personalfinance/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_movies", "Reddit Movies", "https://www.reddit.com/r/movies/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_television", "Reddit Television", "https://www.reddit.com/r/television/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_music", "Reddit Music", "https://www.reddit.com/r/music/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_books", "Reddit Books", "https://www.reddit.com/r/books/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_sports", "Reddit Sports", "https://www.reddit.com/r/sports/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_nba", "Reddit NBA", "https://www.reddit.com/r/nba/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_soccer", "Reddit Soccer", "https://www.reddit.com/r/soccer/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_health", "Reddit Health", "https://www.reddit.com/r/health/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_food", "Reddit Food", "https://www.reddit.com/r/food/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    _rss("reddit_todayilearned", "Reddit TodayILearned", "https://www.reddit.com/r/todayilearned/.rss", "reddit", "reddit", headers_profile="reddit", tier=4, source_type="social", risk="medium"),
    # CMMC RSS
    _rss("cmmc_fedscoop", "FedScoop", "https://fedscoop.com/feed/", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    _rss("cmmc_defensescoop", "DefenseScoop", "https://defensescoop.com/feed/", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    _rss("cmmc_fnn", "Federal News Network", "https://federalnewsnetwork.com/category/technology-main/cybersecurity/feed/", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    _rss("cmmc_nextgov", "Nextgov Cybersecurity", "https://www.nextgov.com/rss/cybersecurity/", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    _rss("cmmc_govcon", "GovCon Wire", "https://www.govconwire.com/feed/", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    _rss("cmmc_securityweek", "SecurityWeek", "https://www.securityweek.com/feed/", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    _rss("cmmc_cyberscoop", "Cyberscoop", "https://cyberscoop.com/feed/", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    _rss(
        "cmmc_breakingdefense",
        "Breaking Defense",
        "https://breakingdefense.com/feed/",
        "cmmc",
        "cmmc_rss",
        headers_profile="breaking_defense",
        fallback_url=(
            "https://news.google.com/rss/search?"
            "q=site:breakingdefense.com+(CMMC+OR+defense+cybersecurity)+when:7d&hl=en-US&gl=US&ceid=US:en"
        ),
        tier=2,
        source_type="compliance",
    ),
    _rss("cmmc_defenseone", "Defense One", "https://www.defenseone.com/rss/all/", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    _rss("cmmc_defensenews", "Defense News", "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    _rss("cmmc_executivegov", "ExecutiveGov", "https://executivegov.com/feed/", "cmmc", "cmmc_rss", tier=2, source_type="compliance"),
    # CMMC Reddit
    _rss("cmmc_reddit_cmmc", "Reddit CMMC", "https://www.reddit.com/r/CMMC/.rss", "cmmc", "cmmc_reddit", headers_profile="cmmc_reddit", tier=4, source_type="social", risk="medium"),
    _rss("cmmc_reddit_nistcontrols", "Reddit NISTControls", "https://www.reddit.com/r/NISTControls/.rss", "cmmc", "cmmc_reddit", headers_profile="cmmc_reddit", tier=4, source_type="social", risk="medium"),
    _rss("cmmc_reddit_federalemployees", "Reddit FederalEmployees", "https://www.reddit.com/r/FederalEmployees/.rss", "cmmc", "cmmc_reddit", headers_profile="cmmc_reddit", tier=4, source_type="social", risk="medium"),
    # Non-RSS collectors with source keys used for metadata.
    _json(
        "hackernews_topstories",
        "Hacker News Top Stories",
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        "community",
        source_key="hackernews",
        collector="hackernews",
        json_count_path="",
        fallback_url="https://hnrss.org/frontpage",
        tier=2,
        source_type="community",
    ),
    _json(
        "devto_api",
        "Dev.to API",
        "https://dev.to/api/articles?top=1&per_page=15",
        "community",
        source_key="devto",
        collector="devto",
        json_count_path="",
        fallback_url="https://dev.to/api/articles?top=1&per_page=15",
        tier=3,
        source_type="community",
    ),
    _json(
        "github_search_api",
        "GitHub Search API",
        "https://api.github.com/search/repositories?q=created:%3E2026-01-01&sort=stars&order=desc&per_page=10",
        "community",
        source_key="github_trending",
        json_count_path="items",
        fallback_url="https://github.com/trending?since=daily&spoken_language_code=en",
        tier=3,
        source_type="community",
    ),
    _json(
        "wikipedia_parse_api",
        "Wikipedia Parse API",
        "https://en.wikipedia.org/w/api.php?action=parse&page=Portal:Current_events&prop=text&format=json&formatversion=2",
        "reference",
        source_key="wikipedia_current",
        json_count_path="parse",
        fallback_url="https://en.wikipedia.org/wiki/Portal:Current_events",
        tier=3,
        source_type="reference",
    ),
    _html(
        "github_trending_html",
        "GitHub Trending HTML",
        "https://github.com/trending?since=daily&spoken_language_code=en",
        "community",
        source_key="github_trending",
        collector="github_trending",
        selector="article.Box-row",
        fallback_url="https://api.github.com/search/repositories?q=created:%3E2026-01-01&sort=stars&order=desc&per_page=10",
        tier=3,
        source_type="community",
    ),
    _html(
        "wikipedia_current_html",
        "Wikipedia Current Events HTML",
        "https://en.wikipedia.org/wiki/Portal:Current_events",
        "reference",
        source_key="wikipedia_current",
        collector="wikipedia_current",
        selector=".current-events-content li, .vevent li",
        fallback_url="https://en.wikipedia.org/w/api.php?action=parse&page=Portal:Current_events&prop=text&format=json&formatversion=2",
        tier=3,
        source_type="reference",
    ),
]


COLLECTOR_SOURCES_BY_GROUP: Dict[str, List[SourceSpec]] = {}
SOURCE_BY_KEY: Dict[str, SourceSpec] = {}
SOURCE_BY_SOURCE_KEY: Dict[str, SourceSpec] = {}

for source in COLLECTOR_SOURCES:
    SOURCE_BY_KEY[source.key] = source
    if source.collector:
        COLLECTOR_SOURCES_BY_GROUP.setdefault(source.collector, []).append(source)
    if source.source_key and source.source_key not in SOURCE_BY_SOURCE_KEY:
        SOURCE_BY_SOURCE_KEY[source.source_key] = source


def get_collector_sources(group: str) -> List[SourceSpec]:
    """Return sources used by a collector group."""
    return list(COLLECTOR_SOURCES_BY_GROUP.get(group, []))


def get_health_sources() -> List[SourceSpec]:
    """Return all sources included in health checks."""
    return [source for source in COLLECTOR_SOURCES if source.healthcheck]


def get_source_by_key(key: str) -> Optional[SourceSpec]:
    return SOURCE_BY_KEY.get(key)


def get_source_by_source_key(source_key: str) -> Optional[SourceSpec]:
    return SOURCE_BY_SOURCE_KEY.get(source_key)
