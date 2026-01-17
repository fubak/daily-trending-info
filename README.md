# CMMC Watch

A CMMC compliance and Defense Industrial Base news aggregator that regenerates daily at 6 AM EST via GitHub Actions, delivering curated news from trusted federal and cybersecurity sources.

**Live:** https://cmmcwatch.com

## Features

### Trend Aggregation
Collects and processes real-time trending data from 15+ sources:

| Category | Sources |
|----------|---------|
| **News** | RSS feeds (BBC, Reuters, AP, NPR, Al Jazeera, The Guardian) |
| **Tech** | Hacker News, Lobsters, GitHub Trending, Dev.to, Product Hunt, Tech RSS |
| **Reddit** | 20+ subreddits (news, technology, science, politics, finance, sports, entertainment) |
| **Reference** | Wikipedia Current Events |
| **Specialized** | Science RSS, Politics RSS, Finance RSS, Sports RSS, Entertainment RSS |

### AI-Powered Design System
Each daily generation features a unique design created by AI:
- **9 Design Personalities:** Brutalist, Editorial, Minimal, Corporate, Playful, Tech, News, Magazine, Dashboard
- **12 Hero Styles:** Cinematic, Glassmorphism, Neon, Duotone, Particles, Waves, Geometric, Spotlight, Glitch, Aurora, Mesh, Retro
- **20+ Color Schemes** with dynamic accent colors
- **Typography Scales** with Google Fonts integration

### Editorial Articles
Daily long-form editorial content with 8 structured sections:
1. **Lead** - Hook and thesis
2. **What People Think** - Public sentiment analysis
3. **What's Happening** - Current facts and context
4. **Hidden Tradeoffs** - Deeper analysis
5. **Counterarguments** - Alternative perspectives
6. **What's Next** - Future implications
7. **Framework** - Mental model for understanding
8. **Conclusion** - Summary and takeaways

Articles are permanently archived at `/articles/YYYY/MM/DD/slug/`

### Topic Pages
Dedicated pages for major categories:
- `/tech/` - Technology, startups, developer news
- `/world/` - International news and events
- `/science/` - Scientific discoveries and research
- `/politics/` - Political news and analysis
- `/finance/` - Markets, business, economics
- `/media/` - Entertainment and media
- `/sports/` - Sports news and scores
- `/business/` - Business and corporate news

### CMMC Watch
Standalone page focused on CMMC (Cybersecurity Maturity Model Certification) compliance news at `/cmmc/`:

**Sources:**
- Federal IT news (FedScoop, DefenseScoop, Federal News Network, Nextgov)
- Defense industry (Breaking Defense, Defense One, Defense News, ExecutiveGov)
- Cybersecurity (SecurityWeek, Cyberscoop, GovCon Wire)
- Reddit communities (r/CMMC, r/NISTControls, r/FederalEmployees)

**Features:**
- **4 Priority Categories:**
  - 🎯 CMMC Program News - Direct certification and assessment updates
  - 📋 NIST & Compliance - NIST 800-171/172, DFARS, FedRAMP
  - 🛡️ Defense Industrial Base - DoD contractors and DIB news
  - 🔒 Federal Cybersecurity - Related government IT news
- Separate RSS feed at `/cmmc/feed.xml`
- Publication dates in MM/DD/YYYY format
- Standalone branding (no main site navigation)

### User Preferences
All settings persist in localStorage:
- **Theme:** Dark mode (default) / Light mode
- **Density:** Compact (default) / Comfortable / Spacious
- **View:** Grid (default) / List (plain text links)
- **Saved Stories:** Bookmark articles for later reading

### Archive System
- 30-day rolling archive at `/archive/`
- Each day's snapshot preserved with original design
- Browse historical trending topics

### Technical Features
- **PWA Support:** Installable as a mobile/desktop app
- **RSS Feed:** Full-content RSS 2.0 at `/feed.xml`
- **Sitemap:** Auto-generated XML sitemap for SEO
- **Offline Page:** Graceful offline handling
- **Responsive Design:** Mobile-first, works on all devices
- **Accessibility:** Skip links, ARIA labels, keyboard navigation

## Architecture

### Pipeline (14 Steps)
```
Archive → Collect → Images → Enrich → Load Yesterday →
AI Design → Editorial → Topics → Build HTML → RSS →
PWA → Sitemap → Cleanup → Save
```

### Key Modules
| Module | Purpose |
|--------|---------|
| `main.py` | Pipeline orchestrator with quality gates |
| `collect_trends.py` | 15+ source collectors, deduplication |
| `fetch_images.py` | Pexels/Unsplash with 7-day cache |
| `generate_design.py` | AI-driven design generation |
| `build_website.py` | Jinja2-based HTML builder |
| `editorial_generator.py` | 8-section article generator |
| `cmmc_page_generator.py` | CMMC Watch standalone page |
| `archive_manager.py` | 30-day snapshot management |
| `generate_rss.py` | RSS 2.0 feed generation |
| `sitemap_generator.py` | XML sitemap generation |
| `shared_components.py` | Consistent header/footer/nav |

### Data Flow
```
15+ Sources → trends.json → images.json → design.json → public/index.html
```

### Output Structure
```
public/
├── index.html          # Main page (self-contained)
├── feed.xml            # RSS 2.0 feed
├── sitemap.xml         # XML sitemap
├── manifest.json       # PWA manifest
├── sw.js               # Service worker
├── offline.html        # Offline fallback
├── ads.txt             # AdSense verification
├── archive/            # 30-day snapshots
├── articles/           # Permanent editorials
├── tech/               # Topic page
├── world/              # Topic page
├── science/            # Topic page
├── politics/           # Topic page
├── finance/            # Topic page
├── media/              # Topic page
├── sports/             # Topic page
├── business/           # Topic page
└── cmmc/               # CMMC Watch (standalone)
    ├── index.html      # CMMC compliance news
    └── feed.xml        # CMMC-specific RSS feed
```

## Setup

### Requirements
- Python 3.11+
- Dependencies in `requirements.txt`

### Environment Variables
```bash
GROQ_API_KEY=           # Primary AI (required)
OPENROUTER_API_KEY=     # Backup AI (optional)
PEXELS_API_KEY=         # Primary images (required)
UNSPLASH_ACCESS_KEY=    # Backup images (optional)
```

### Local Development
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the pipeline
cd scripts && python main.py

# Run with options
python main.py --no-archive    # Skip archiving
python main.py --dry-run       # Preview without saving
```

### Testing
```bash
pytest tests/                  # Run all tests
pytest tests/ --cov=scripts    # With coverage
pytest tests/test_design_system.py  # Single test file
```

## GitHub Actions

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `daily-regenerate.yml` | Daily 6 AM EST, push to main, manual | Main pipeline |
| `auto-merge-claude.yml` | Push to `claude/**` branches | Auto PR merge |
| `update-readme.yml` | Push to main | Changelog updates |

## Quality Gates

- **MIN_TRENDS = 5** - Pipeline aborts if fewer than 5 trends collected
- **MIN_FRESH_RATIO = 0.5** - Warning if less than 50% fresh content in 24h
- **DEDUP_SIMILARITY_THRESHOLD = 0.8** - Duplicate detection threshold

## SEO & Structured Data

- JSON-LD schemas: WebSite, WebPage, ItemList, FAQPage, Article
- Open Graph and Twitter Card meta tags
- Speakable specification for voice assistants
- Canonical URLs for all pages

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read the [CLAUDE.md](CLAUDE.md) for development guidelines.
