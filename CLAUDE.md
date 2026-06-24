# CLAUDE.md

Claude Code guidance for DailyTrending.info - AI-curated tech, science, and world news aggregator regenerating daily at 6 AM EST via GitHub Actions.

**Live:** https://dailytrending.info

## Commands

**Run:** `cd scripts && python main.py` | **No archive:** `--no-archive` | **Dry run:** `--dry-run`
**Test:** `pytest tests/` | **Coverage:** `--cov=scripts` | **Single:** `pytest tests/test_design_system.py`

## Tool Usage

Use `sg -l python` for code searches, `rg` for text/config, `fdfind` for file finding. See `~/.claude/CLAUDE.md`.

## Environment Variables

Required in `.env` or GitHub Secrets:
`GROQ_API_KEY` (primary AI) | `OPENROUTER_API_KEY` (backup) | `PEXELS_API_KEY` (primary images) | `UNSPLASH_ACCESS_KEY` (backup)

## Architecture

**Pipeline (16 steps in `main.py`):** Archive → Load yesterday → Collect (15+ sources) → Images → Enrich → Fixed design → Editorial → Topics → CMMC Watch → Media → Build HTML → RSS → PWA → Sitemap → Cleanup → Save

| Module | Purpose |
|--------|---------|
| `main.py` | Orchestrator, quality gates |
| `collect_trends.py` | 15+ source collectors |
| `trend_deduplicator.py` | Token + semantic dedup clustering |
| `keyword_extraction.py` | Stop-word filter for trend titles |
| `fetch_images.py` | Pexels/Unsplash, 7-day cache |
| `fixed_design.py` | Fixed deterministic design profile |
| `build_website.py` | Single-file HTML/CSS/JS builder |
| `enrich_content.py` | Word of Day, Grokipedia |
| `editorial_generator.py` | 8-section articles |
| `editorial_renderer.py` | Article + AMP HTML renderers |
| `articles_index_renderer.py` | /articles/ index page renderer |
| `topic_page_generator.py` | /tech/, /world/, etc. sub-pages |
| `media_page_generator.py` | /media/ daily image+video page |
| `cmmc_page_generator.py` | CMMC Watch standalone page |
| `generate_rss.py` | RSS 2.0, content:encoded |
| `sitemap_generator.py` | XML sitemap |
| `archive_manager.py` | 30-day snapshots |
| `config.py` | All limits, timeouts, constants, STRING_LIMITS |
| `llm_client.py` | OpenAI-compatible HTTP client (Groq/OpenRouter/OpenCode/Mistral) + `LLMClientBase` (shared provider routing, Google AI/HuggingFace callers, JSON repair/parse) inherited by `EditorialGenerator` and `ContentEnricher` |
| `rate_limiter.py` | Per-provider 429 / quota tracking |
| `html_sanitizer.py` | Strips script/iframe/event handlers from LLM HTML |
| `url_safety.py` | `safe_href` / `safe_image_src` scheme allowlists; `safe_css_url` for CSS `url()` contexts |
| `design_tokens.py` | Color/font/mode validators (CSS injection defence) |
| `pipeline_types.py` | TypedDict schemas (TrendDict, ImageDict, DesignTokens, MediaData) |
| `json_utils.py` | Escape control chars in LLM-emitted JSON |
| `date_utils.py` | Shared `format_long_date()` |
| `shared_components.py` | Header/footer HTML + theme toggle script + `build_google_fonts_link` (shared Google Fonts `<link>` builder) |
| `source_catalog.py` | Canonical source list shared by collectors + health checks |
| `source_registry.py` | Source metadata for ranking + label formatting |
| `keyword_tracker.py` | Tracks keyword frequency over time |
| `metrics_collector.py` | Persists per-run pipeline metrics + timings |
| `fetch_media_of_day.py` | Fetches daily curated image + video |
| `pwa_generator.py` | Generates PWA assets (manifest, service worker) |
| `image_utils.py` | Validates / sanitizes image URLs |
| `logging_utils.py` | Structured contextual logging |
| `source_health_check.py` | Daily source endpoint health checks (CI standalone) |
| `competitor_monitor.py` | Weekly competitor/algorithm monitor (CI standalone) |
| `fetch_linkedin_posts.py` | LinkedIn scraper for CMMC influencers (Apify, optional) |

**Data Flow:** `15+ Sources → trends.json → images.json → design.json → public/index.html` | Cache: `data/image_cache/` (7-day TTL)

**Output (`public/`):** `index.html` (self-contained) | `feed.xml` | `sitemap.xml` | `manifest.json` + `sw.js` | `archive/` (30-day) | `articles/` (permanent: index, YYYY/MM/DD/slug/) | Topic pages: `tech/`, `world/`, `science/`, `politics/`, `finance/`, `business/`, `sports/` | CMMC Watch: `cmmc/` (standalone)

## Quality Gates

`_step_collect_trends()`: **MIN_TRENDS = 5** (abort if <5) | **MIN_FRESH_RATIO = 0.5** (warn if <50% fresh in 24h, flagged via `low_freshness` metric)

**Step criticality (`_run_step(..., critical=)`):** collect/design/build are critical (abort run). Auxiliary steps (enrich, editorial, topic/cmmc/media pages, RSS, PWA, sitemap, cleanup, save) are `critical=False` — they log + record the failure and continue so one broken sub-feature can't block the deploy. Degraded steps are surfaced at end of run + counted in the `degraded_step_count` metric. Pipeline JSON writes are atomic (tempfile + `os.replace`).

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

**CI gate (`ci.yml`):** every PR + push to `main` runs `py_compile` + `pytest` + `mypy` on a Python **3.11 / 3.12** matrix; `test (py3.11)` and `test (py3.12)` are **required status checks** on `main`. **Runtime gotcha:** `.venv` is 3.12 but the pipeline deploys on **3.11** — PEP 701 f-string features (backslashes / quote reuse) compile locally yet break CI. Verify with `uv run --python 3.11 --no-project -- python -m py_compile scripts/*.py`. Tests reading gitignored `data/` runtime files must skip when absent.

## GitHub Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | PR, push main, manual | `py_compile` + `pytest` + `mypy` on Python 3.11 & 3.12; required status checks on `main` |
| `daily-regenerate.yml` | Daily 6AM EST, push main, manual | Main pipeline → deploy to Pages; opens issue on failure |
| `auto-merge-claude.yml` | Push `claude/**` | Auto-creates PR and squash-merges (no `--admin`; respects branch protection — now gated by the required CI checks) |
| `update-readme.yml` | Push main | Changelog update |
| `source-health.yml` | Daily 11:30 UTC, manual | Runs `source_health_check.py`, commits `data/source_health.json` |
| `competitor-monitor.yml` | Weekly Mon 9 UTC, manual | Runs `competitor_monitor.py`, opens issue on high-priority alerts |
| `lighthouse-audit.yml` | After daily regen, manual | Lighthouse CI; SEO assertion hard-fails below 0.9 |

## Critical Patterns

**Dataclass to dict:** `asdict(t) if hasattr(t, '__dataclass_fields__') else t`
**Font whitelist:** `config.py::ALLOWED_FONTS` (prevent injection)
**Image fallbacks:** Persistent cache → gradient placeholders

## Config (`config.py`)

`LIMITS` (per-source fetch) | `TIMEOUTS` (HTTP by operation) | `DELAYS` (rate limiting) | `IMAGE_CACHE_MAX_AGE_DAYS = 7` | `ARCHIVE_KEEP_DAYS = 30` | `DEDUP_SIMILARITY_THRESHOLD = 0.8`

**Site identity (single source of truth):** `SITE_URL` (canonical base URL) and `SITE_NAME` (brand). `RSS_FEED_LINK`/`RSS_FEED_TITLE` derive from them. Use these instead of hardcoding the domain.
