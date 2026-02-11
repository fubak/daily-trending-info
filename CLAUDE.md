# CLAUDE.md

Claude Code guidance for DailyTrending.info - AI-curated tech, science, and world news aggregator regenerating daily at 6 AM EST via GitHub Actions.

**Live:** https://dailytrending.info

## Commands

**Run:** `cd scripts && python main.py` | **No archive:** `--no-archive` | **Dry run:** `--dry-run`
**Test:** `pytest tests/` | **Coverage:** `--cov=scripts` | **Single:** `pytest tests/test_design_system.py`

## Environment Variables

Required in `.env` or GitHub Secrets:
`GROQ_API_KEY` (primary AI) | `OPENROUTER_API_KEY` (backup) | `PEXELS_API_KEY` (primary images) | `UNSPLASH_ACCESS_KEY` (backup)

## Architecture

**Pipeline (16 steps in `main.py`):** Archive → Load yesterday → Collect (15+ sources) → Images → Enrich → Fixed design → Editorial → Topics → CMMC Watch → Media → Build HTML → RSS → PWA → Sitemap → Cleanup → Save

| Module | Purpose |
|--------|---------|
| `main.py` | Orchestrator, quality gates |
| `collect_trends.py` | 15+ sources, deduplication |
| `fetch_images.py` | Pexels/Unsplash, 7-day cache |
| `fixed_design.py` | Fixed deterministic design profile |
| `build_website.py` | Single-file HTML/CSS/JS builder |
| `enrich_content.py` | Word of Day, Grokipedia |
| `editorial_generator.py` | 8-section articles |
| `cmmc_page_generator.py` | CMMC Watch standalone page |
| `generate_rss.py` | RSS 2.0, content:encoded |
| `sitemap_generator.py` | XML sitemap |
| `config.py` | All limits, timeouts, constants |
| `archive_manager.py` | 30-day snapshots |

**Data Flow:** `15+ Sources → trends.json → images.json → design.json → public/index.html` | Cache: `data/image_cache/` (7-day TTL)

**Output (`public/`):** `index.html` (self-contained) | `feed.xml` | `sitemap.xml` | `manifest.json` + `sw.js` | `archive/` (30-day) | `articles/` (permanent: index, YYYY/MM/DD/slug/) | Topic pages: `tech/`, `world/`, `science/`, `politics/`, `finance/`, `business/`, `sports/` | CMMC Watch: `cmmc/` (standalone)

## Quality Gates

`_step_collect_trends()`: **MIN_TRENDS = 5** (abort if <5) | **MIN_FRESH_RATIO = 0.5** (warn if <50% fresh in 24h)

## Design System

Single deterministic design profile ("Signal Desk") | Fixed layout (`newspaper`) | Fixed hero (`glassmorphism`) | Typography: Newsreader + Inter | Theme toggle supports dark/light

## Editorial Articles

**Module:** `editorial_generator.py` | **8 required sections:** Lead (hook+thesis) | What People Think | What's Happening | Hidden Tradeoffs | Counterarguments | What's Next | Framework | Conclusion

**Features:** Permanent retention | URL: `/articles/YYYY/MM/DD/slug/` | JSON-LD structured data | "Why This Matters" for top 3 | Central themes from keyword frequency

**Prompt location:** `editorial_generator.py::generate_editorial()` | Uses: `_build_editorial_context()`, `_identify_central_themes()`

## User Features

**Saved Stories:** localStorage key `dailytrending_saved` | Client-side only | Bookmark buttons

**Topics:** `/tech/` (HackerNews, Lobsters, GitHub, tech RSS) | `/world/` (news RSS, Wikipedia) | `/social/` (Reddit, viral)

**RSS:** RSS 2.0 | `content:encoded` (full HTML) | `dc:creator` | "Why This Matters" | Atom self-link

## CMMC Watch

**Module:** `cmmc_page_generator.py` | **URL:** `/cmmc/` | **RSS:** `/cmmc/feed.xml`

**Sources:** FedScoop, DefenseScoop, Federal News Network, Nextgov, Breaking Defense, Defense One, Defense News, ExecutiveGov, SecurityWeek, Cyberscoop, GovCon Wire | Reddit: r/CMMC, r/NISTControls, r/FederalEmployees

**Categories (priority order):**
1. 🎯 CMMC Program News - `CMMC_CORE_KEYWORDS` (cmmc, c3pao, cyber-ab, cmmc certification)
2. 📋 NIST & Compliance - `NIST_KEYWORDS` (nist 800-171, dfars, fedramp, fisma)
3. 🛡️ Defense Industrial Base - `DIB_KEYWORDS` (defense contractor, dod contractor, pentagon)
4. 🔒 Federal Cybersecurity - General federal cyber news

**Key functions:** `filter_cmmc_trends()` | `categorize_trend()` | `sort_trends_by_priority()` | `build_cmmc_page()`

**Date format:** MM/DD/YYYY | Standalone page (no main nav)

## Trending Indicators

**Velocity Badges:** HOT (red, 80+ score, 4+ sources) | RISING (yellow, 50-79, 2-3 sources) | STEADY (accent, 30-49) | Calc: `_calculate_velocity()` (keyword overlap)

**Compare Yesterday:** 🆕 New | 🔥 Trending up | 📊 Continuing | Calc: `_get_comparison_indicator()` (fuzzy title match)

**Reading Time:** 200 WPM | Methods: `_calculate_reading_time()`, `_get_total_reading_time()` | Shows in "Top Stories" header

## Social Sharing

`navigator.share()` → clipboard copy (toast) → prompt dialog | Buttons on story card hover

## Accessibility

**Features:** Skip link | Focus visible | ARIA labels | Screen reader (live regions) | Keyboard nav (↑/↓/←/→, Enter, Escape) | `prefers-reduced-motion` | `prefers-contrast: high`

## SEO

**JSON-LD (`_build_structured_data()`):** WebSite | WebPage | ItemList (top 10) | FAQPage | HowTo | SpeakableSpecification | Article with mentions

**Speakable:** `.headline-xl`, `.hero-subheadline`, `.story-title`

## Testing

Fixtures: `tests/conftest.py` (sample_trends, sample_images, sample_design) | APIs mocked | Extensive coverage in `test_design_system.py` | Run from project root

## GitHub Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `daily-regenerate.yml` | Daily 6AM EST, push main, manual | Main pipeline |
| `auto-merge-claude.yml` | Push `claude/**` | Auto PR merge |
| `update-readme.yml` | Push main | Changelog update |

## Critical Patterns

**Dataclass to dict:** `asdict(t) if hasattr(t, '__dataclass_fields__') else t`
**Font whitelist:** `config.py::ALLOWED_FONTS` (prevent injection)
**Image fallbacks:** Persistent cache → gradient placeholders

## Config (`config.py`)

`LIMITS` (per-source fetch) | `TIMEOUTS` (HTTP by operation) | `DELAYS` (rate limiting) | `IMAGE_CACHE_MAX_AGE_DAYS = 7` | `ARCHIVE_KEEP_DAYS = 30` | `DEDUP_SIMILARITY_THRESHOLD = 0.8`
