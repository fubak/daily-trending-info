# DailyTrending.info - Architecture Documentation

**Version:** 1.0.0
**Last Updated:** January 7, 2026

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Component Architecture](#component-architecture)
4. [Data Flow](#data-flow)
5. [Module Descriptions](#module-descriptions)
6. [Design Patterns](#design-patterns)
7. [Security Architecture](#security-architecture)
8. [Performance Architecture](#performance-architecture)
9. [Deployment Architecture](#deployment-architecture)
10. [Future Considerations](#future-considerations)

---

## System Overview

DailyTrending.info is a **fully autonomous trend aggregation system** that regenerates daily at 6 AM EST via GitHub Actions. It collects trending tech, science, and world news from 15+ sources, generates unique AI-driven designs, and deploys to GitHub Pages at zero cost.

### Key Characteristics

- **Stateless Architecture**: No database, file-based caching only
- **Zero-Cost Operation**: Leverages free tiers of multiple services
- **Fully Automated**: No manual intervention required
- **Resilient**: Multiple fallback mechanisms at every layer
- **Scalable**: Can handle 100+ concurrent sources

---

## Architecture Principles

### 1. **Graceful Degradation**
Every component has multiple fallback layers:
- **AI Design**: Groq → OpenRouter → Google → Preset themes
- **Images**: Pexels → Unsplash → Cache → Gradient placeholders
- **Content**: Multiple RSS feeds per category

### 2. **Configuration Over Code**
All magic numbers, limits, and timeouts centralized in `config.py`:
```python
LIMITS = {"hackernews": 25, "reddit": 8, "product_hunt": 15}
TIMEOUTS = {"default": 15, "ai_api": 30, "image_api": 15}
```

### 3. **Pipeline Pattern**
16-step pipeline with clear stage boundaries:
```
Archive → Collect → Images → Enrich → Design → Build → Deploy
```

### 4. **Fail-Fast Quality Gates**
- MIN_TRENDS = 5 (abort if < 5 trends collected)
- MIN_FRESH_RATIO = 0.5 (warn if < 50% fresh content)

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      GitHub Actions                          │
│              (Scheduler + CI/CD Orchestrator)                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     main.py (Pipeline)                       │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────┐ │
│  │Archive   │Collect   │Fetch     │Generate  │Build      │ │
│  │Manager   │Trends    │Images    │Design    │Website    │ │
│  └──────────┴──────────┴──────────┴──────────┴───────────┘ │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   External Services                          │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────┐ │
│  │12 Trend  │Pexels/   │Groq/     │GitHub    │GitHub     │ │
│  │Sources   │Unsplash  │OpenRouter│Workflows │Pages      │ │
│  └──────────┴──────────┴──────────┴──────────┴───────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Input Sources → Trends Collection
```
Google Trends ─┐
News RSS (12)  ├─► collect_trends.py ──► trends.json
Tech RSS (10)  │                          (deduplicated,
HackerNews    ─┤                           scored, filtered)
Lobsters      ─┤
Reddit (13)   ─┤
Product Hunt  ─┤
Dev.to        ─┤
Slashdot      ─┤
GitHub        ─┤
Wikipedia     ─┘
```

### Trends → Images
```
trends.json ──► fetch_images.py ──► images.json
    │              │
    │              ├─► Pexels API
    │              ├─► Unsplash API
    │              └─► 7-day cache (data/image_cache/)
    │
    └─► Keywords extracted for image search
```

### Data → Design → Website
```
trends.json  ─┐
images.json  ─┼─► fixed_design.py ──► design.json
content.json ─┘        (deterministic)

design.json  ─┐
trends.json  ─┼─► build_website.py ──► public/index.html
images.json  ─┤                         (single-file, inline CSS/JS)
content.json ─┘

public/
├── index.html        (main site)
├── feed.xml          (RSS with content:encoded)
├── sitemap.xml       (SEO sitemap)
├── manifest.json     (PWA)
├── sw.js             (Service Worker)
├── articles/         (permanent editorial)
│   └── YYYY/MM/DD/slug/
└── archive/          (30-day snapshots)
    └── YYYY-MM-DD/
```

---

## Module Descriptions

### Core Modules

#### `main.py` (Pipeline Orchestrator)
**Purpose**: Coordinates all pipeline steps with error handling and quality gates

**Responsibilities**:
- Environment validation
- Step orchestration (16 steps)
- Quality gate enforcement
- Error reporting and recovery

**Key Methods**:
- `run()` - Main pipeline entry point
- `_step_collect_trends()` - Trend aggregation
- `_step_generate_topic_pages()` - Topic page generation
- `_validate_environment()` - Pre-flight checks

---

#### `collect_trends.py` (Trend Aggregation)
**Purpose**: Collect and deduplicate trends from 12+ sources

**Responsibilities**:
- Multi-source data collection
- English-only filtering
- Deduplication (0.8 similarity threshold)
- Keyword extraction
- Freshness scoring

**Key Features**:
- **Source Diversity**: 12 independent sources
- **Rate Limiting**: 0.15s between requests
- **Retry Logic**: 3 attempts with exponential backoff
- **Timeout Protection**: Per-source timeout configuration

**Data Structures**:
```python
@dataclass
class Trend:
    title: str
    source: str
    url: Optional[str]
    score: float
    keywords: List[str]
    timestamp: datetime
    image_url: Optional[str]  # From RSS feed
```

---

#### `fetch_images.py` (Image Management)
**Purpose**: Fetch and cache images from multiple sources

**Responsibilities**:
- Multi-provider image fetching (Pexels, Unsplash)
- 7-day TTL cache management
- Query optimization with AI
- Fallback to cached images

**Cache Architecture**:
```
data/image_cache/
├── query_mappings.json       # Query → Cache key mapping
└── <hash>.json               # Cached image metadata
```

**Key Features**:
- **Persistent Cache**: 7-day TTL, 500 entry limit
- **AI Query Optimization**: Groq refines search queries
- **Multi-Provider**: Pexels primary, Unsplash backup
- **Graceful Degradation**: Cache → Gradient placeholders

---

#### `fixed_design.py` (Fixed Design System)
**Purpose**: Provide one deterministic design spec for all builds

**Responsibilities**:
- Single modern news profile
- Stable typography and color tokens
- Deterministic layout and hero style
- WCAG AA contrast validation

**Design Dimensions**:
```python
FIXED_DESIGN_BASE = {
    "theme_name": "Signal Desk",
    "layout_style": "newspaper",
    "hero_style": "glassmorphism",
    "font_primary": "Newsreader",
    "font_secondary": "Inter",
    ...
}
```

---

#### `build_website.py` (Website Builder)
**Purpose**: Generate single-file HTML with inline CSS/JS

**Responsibilities**:
- Template rendering
- CSS generation from design spec
- JavaScript bundling
- HTML optimization

**Key Features**:
- **Single File Output**: All CSS/JS inline
- **Responsive Design**: Mobile-first approach
- **Accessibility**: WCAG AA compliant
- **Performance**: Lazy loading, image optimization

---

#### `editorial_generator.py` (Content Generation)
**Purpose**: Generate daily editorial articles

**Responsibilities**:
- 8-section article structure
- Theme identification
- "Why This Matters" context
- Permanent article storage

**Article Structure**:
1. The Lead (hook + thesis)
2. What People Think (conventional wisdom)
3. What's Actually Happening (deeper analysis)
4. Hidden Tradeoffs (unspoken costs)
5. Best Counterarguments (steelman objection)
6. What This Means Next (predictions)
7. Practical Framework (mental model)
8. Conclusion (circle back to hook)

---

### Supporting Modules

#### `topic_page_generator.py` (NEW - Refactored)
**Purpose**: Modular functions for topic page generation

**Functions**:
- `get_topic_configurations()` - Topic definitions
- `find_topic_hero_image()` - Image selection
- `filter_trends_by_topic()` - Trend filtering
- `matches_topic_source()` - Source matching

---

#### `logging_utils.py` (NEW - Enhanced Logging)
**Purpose**: Structured logging with correlation IDs

**Features**:
- `StructuredLogger` - Context-aware logging
- `log_operation()` - Operation timing
- `log_api_call()` - API call decorator
- `ErrorCollector` - Batch error reporting

---

#### `rate_limiter.py` (Rate Limiting)
**Purpose**: Multi-provider rate limit management

**Features**:
- Per-provider quota tracking
- Exponential backoff
- Provider exhaustion detection
- Automatic fallback switching

---

#### `config.py` (Configuration)
**Purpose**: Centralized configuration management

**Configuration Categories**:
- **Limits**: Per-source fetch limits
- **Timeouts**: HTTP timeout by operation type
- **Delays**: Rate limiting delays
- **Quality Gates**: MIN_TRENDS, MIN_FRESH_RATIO
- **Cache Settings**: TTL, max entries

---

## Design Patterns

### 1. **Pipeline Pattern**
Sequential processing with clear stage boundaries:
```python
def run(self):
    self._step_archive()
    self._step_collect_trends()
    self._step_fetch_images()
    self._step_apply_fixed_design()
    self._step_build_website()
    self._step_deploy()
```

### 2. **Factory Pattern**
Multiple AI providers with common interface:
```python
def _call_groq_api() -> Optional[str]
def _call_openrouter_api() -> Optional[str]
def _call_google_api() -> Optional[str]
```

### 3. **Strategy Pattern**
Different caching strategies:
- Image cache: 7-day TTL
- Design history: Permanent
- Keyword history: 30-day rolling

### 4. **Decorator Pattern**
Logging and timing decorators:
```python
@log_api_call(logger)
def fetch_from_api(url, params):
    ...
```

### 5. **Builder Pattern**
Fluent website building:
```python
builder = WebsiteBuilder(design, trends, images)
builder.build_header()
builder.build_hero()
builder.build_stories()
html = builder.finalize()
```

---

## Security Architecture

### Input Validation
- **Font Whitelist**: Prevents CSS injection
- **HTML Escaping**: All user content escaped
- **URL Validation**: External URLs validated
- **English-Only Filter**: Non-English content rejected

### API Security
- **Environment Variables**: All secrets in env vars
- **No Hardcoded Keys**: Zero secrets in code
- **Rate Limiting**: Prevents API abuse
- **Timeout Protection**: All requests have timeouts

### File System Security
- **Pathlib Usage**: Prevents directory traversal
- **Controlled Directories**: Limited write locations
- **Permission Validation**: Pre-flight directory checks

---

## Performance Architecture

### Caching Strategy
```
┌─────────────┐      ┌──────────────┐      ┌──────────┐
│ API Request │ ───► │ Cache Check  │ ───► │ Fresh    │
└─────────────┘      │ (7-day TTL)  │      │ API Call │
                     └──────────────┘      └──────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ Return Cache │
                     └──────────────┘
```

### Rate Limiting
- **Between Sources**: 0.5s delay
- **Between Requests**: 0.15s delay
- **Between Images**: 0.3s delay
- **AI API**: 1.0s minimum interval

### Optimization Techniques
1. **Persistent Cache**: Reduces API calls by ~75%
2. **Batch Processing**: Process trends in groups
3. **Lazy Loading**: Images loaded on scroll
4. **Single File Output**: Reduces HTTP requests
5. **Inline CSS/JS**: Eliminates render-blocking

---

## Deployment Architecture

### GitHub Actions Workflow
```
┌──────────────┐
│ Cron: 6AM EST│
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ Run Pipeline     │
│ (main.py)        │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Build Website    │
│ (public/)        │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Deploy to Pages  │
│ (gh-pages branch)│
└──────────────────┘
```

### Zero-Cost Infrastructure
- **Hosting**: GitHub Pages (free)
- **CI/CD**: GitHub Actions (2,000 min/month free)
- **Images**: Pexels/Unsplash (free tier)
- **AI**: Groq/OpenRouter/Google (free tier)
- **Domain**: Custom domain supported

---

## Future Considerations

### Scalability
- **Horizontal Scaling**: Add more sources
- **Vertical Scaling**: Increase per-source limits
- **Distributed Caching**: Redis for shared cache
- **CDN Integration**: CloudFlare for global delivery

### Features
- **User Accounts**: Save preferences, bookmarks
- **Real-time Updates**: WebSocket integration
- **Mobile App**: React Native implementation
- **Analytics**: Privacy-respecting analytics

### Technical Debt
- Complete function refactoring (in progress)
- Comprehensive type hints
- Performance monitoring
- Automated security scanning

---

*This architecture document is maintained as the system evolves. Last updated: January 7, 2026*
