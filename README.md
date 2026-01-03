# DailyTrending.info

[![Daily Regeneration](https://github.com/fubak/daily-trending-info/actions/workflows/daily-regenerate.yml/badge.svg)](https://github.com/fubak/daily-trending-info/actions/workflows/daily-regenerate.yml)
[![Auto-merge](https://github.com/fubak/daily-trending-info/actions/workflows/auto-merge-claude.yml/badge.svg)](https://github.com/fubak/daily-trending-info/actions/workflows/auto-merge-claude.yml)

A fully autonomous trend aggregation website that regenerates daily with unique designs, English-only content from 12+ sources, and SEO-optimized pages.

**Live Site:** [https://dailytrending.info](https://dailytrending.info)

## Recent Changes

<!-- CHANGELOG_START -->
| Date | Change |
|------|--------|
| 2026-01-03 00:20 UTC | [fix: Handle list-type author field from Vimeo RSS feed](https://github.com/fubak/daily-trending-info/commit/3266ed2110635c1170a7cfa689b0c8cf83242b0e) |
| 2026-01-03 00:16 UTC | [fix: Resolve f-string syntax error in media page template](https://github.com/fubak/daily-trending-info/commit/f2964c57308e2ffa61c619cc2a458bd4bd260e1e) |
| 2026-01-03 00:11 UTC | [feat: Add Media of the Day page and improve hero image sizing](https://github.com/fubak/daily-trending-info/commit/e49f58a033d7283a231fde6a474bac95c7ffc366) |
| 2026-01-02 23:50 UTC | [feat: Use article images from RSS feeds for hero sections](https://github.com/fubak/daily-trending-info/commit/fc56c55d6625a6009bf5083cd7d6c85c0e95792f) |
| 2026-01-02 22:17 UTC | [feat: Add Pixabay + Lorem Picsum image sources, prevent image reuse](https://github.com/fubak/daily-trending-info/commit/de124dc0d2df37067dc8fecbf06388f38bb4e5e8) |
| 2026-01-02 21:42 UTC | [fix: Include headline keywords when fetching images for topic pages](https://github.com/fubak/daily-trending-info/commit/0e943a29b9521e78050b397c6c7404875cf1590f) |
| 2026-01-02 21:34 UTC | [fix: Match topic hero images to headline keywords, not just category](https://github.com/fubak/daily-trending-info/commit/73765607e526837419118a415f78db6d873fb9a4) |
| 2026-01-02 21:13 UTC | [fix: Replace broken RSS feeds with working alternatives](https://github.com/fubak/daily-trending-info/commit/3ef1af2de119016a72994ca200abcb17258eb542) |
| 2026-01-02 20:58 UTC | [fix: Remove broken comment fragment in rate_limiter.py](https://github.com/fubak/daily-trending-info/commit/ca48f663be76963e4a666ff2aadccada0db8ce13) |
| 2026-01-02 20:48 UTC | [fix: Cap all API retry wait times to 10 seconds max](https://github.com/fubak/daily-trending-info/commit/55cb9b5b4a6088bd3f084e10f43d26ba6bdf550c) |
<!-- CHANGELOG_END -->

## Features

### Content Aggregation
- **12 English-Only Sources**: Google Trends, News RSS (12 outlets), Tech RSS (10 sites), Hacker News, Lobsters, Reddit RSS (13 subreddits), Product Hunt, Dev.to, Slashdot, Ars Technica Features, GitHub Trending, Wikipedia Current Events
- **Smart Filtering**: Automatic non-English content detection and filtering
- **Keyword Extraction**: AI-powered keyword analysis with word cloud visualization
- **Source Categorization**: Stories grouped by World News, Technology, Science, Entertainment, etc.
- **Minimum Content Gate**: Requires 5+ trends before deployment to prevent broken sites
- **Deduplication**: 80% similarity threshold prevents duplicate stories across sources

### Editorial Content
- **Daily Editorial Articles**: AI-generated 800-1200 word analysis synthesizing top stories
- **8-Section Structure**: The Lead, What People Think, What's Actually Happening, Hidden Tradeoffs, Best Counterarguments, What This Means Next, Practical Framework, Conclusion
- **Why This Matters**: Context explanations for top 3 stories
- **Word of the Day**: Daily vocabulary with etymology and trend connection
- **Grokipedia Integration**: Topic articles from Grok with excerpts
- **AI Story Summaries**: Brief descriptions for trending stories
- **Duplicate Prevention**: Only one editorial per day (prevents multiple articles on reruns)

### Topic Pages
- **/tech/**: Technology-focused trends (HackerNews, Lobsters, GitHub, tech RSS)
- **/world/**: World news trends (News RSS, Wikipedia current events)
- **/social/**: Viral and social content (Reddit, trending topics)
- **Consistent Design**: Topic pages inherit daily design system

### Design System
- **9 Design Personalities**: Brutalist, Editorial, Minimal, Corporate, Playful, Tech, News, Magazine, Dashboard
- **20+ Color Schemes**: From Midnight Indigo to Sunset Coral
- **6 Layout Templates**: Newspaper, Magazine, Dashboard, Minimal, Bold, Mosaic
- **12 Animated Hero Styles**: Cinematic, Glassmorphism, Neon, Duotone, Particles, Waves, Geometric, Spotlight, Glitch, Aurora, Mesh, Retro
- **Personality-Hero Alignment**: Hero styles matched to personalities for visual consistency
- **8 Image Treatments**: None, Grayscale, Sepia, Saturate, Contrast, Vignette, Duotone Warm, Duotone Cool
- **7 Section Dividers**: None, Line, Thick Line, Gradient Line, Dots, Fade, Wave
- **6 Card Aspect Ratios**: Auto, Landscape (16:9), Portrait (3:4), Square (1:1), Wide (21:9), Classic (4:3)
- **9 Typography Scales**: Different heading size ratios per personality for visual hierarchy
- **5 Background Patterns**: Dots, Grid, Lines, Cross, Noise (applied per personality)
- **Content-Aware Animations**: Animation intensity adjusts based on news sentiment (breaking, positive, negative, entertainment)
- **WCAG Contrast Validation**: Automatic color contrast checking and adjustment for accessibility
- **~50+ Million Combinations**: Unique design generated each build

### User Experience
- **Dark/Light Mode Toggle**: Persistent user preference with localStorage
- **Responsive Design**: Mobile-first with CSS Grid layouts
- **Breaking News Ticker**: Animated headline carousel
- **Smooth Animations**: Configurable animation levels (none, subtle, moderate, playful, energetic)
- **Scroll-Triggered Animations**: Cards animate in with staggered, varied effects (fade, slide, scale)
- **Reduced Motion Support**: Respects `prefers-reduced-motion` system preference
- **Keyboard Accessibility**: Skip-to-content link, visible focus indicators, arrow key navigation
- **Touch-Friendly**: Minimum 44x44px touch targets for mobile
- **Saved Stories**: Bookmark stories to localStorage for later reading
- **Social Sharing**: Web Share API with clipboard fallback
- **Reading Time**: Estimated reading time for story sections
- **Velocity Indicators**: HOT (4+ sources), RISING (2-3 sources), STEADY badges
- **Compare to Yesterday**: 🆕 New today, 🔥 Trending up, 📊 Continuing indicators
- **High Contrast Mode**: Adapts to `prefers-contrast: high` preference

### SEO & LLM Optimization
- **Dynamic Titles**: `DailyTrending.info - [Top Story]`
- **Open Graph & Twitter Cards**: Rich social media previews
- **Rich JSON-LD Schemas**: WebSite, WebPage, NewsArticle, ItemList, FAQPage, HowTo, BreadcrumbList
- **SpeakableSpecification**: Voice assistant optimization for headlines
- **Entity Linking**: Article mentions with structured entity data
- **llms.txt**: LLM-friendly site documentation at `/llms.txt`
- **RSS 2.0 Feed**: Full content with `content:encoded` and Dublin Core metadata
- **XML Sitemap**: Auto-generated with articles, archives, and topic pages
- **Google Analytics**: Built-in tracking support
- **Semantic HTML**: Proper heading hierarchy and ARIA labels

### Automation
- **Daily Regeneration**: GitHub Actions runs at 6 AM EST (11:00 UTC) and on every push to main
- **Auto-merge PRs**: Claude branches automatically create and merge PRs
- **Persistent Image Cache**: 7-day cache reduces API calls and provides fallback
- **30-Day Archive**: Browse previous daily snapshots
- **Permanent Article Archive**: Editorial articles retained indefinitely
- **Zero Cost**: Runs entirely on free-tier services

### PWA Support
- **Service Worker**: Offline caching with network-first strategy
- **Web App Manifest**: Installable as standalone app
- **Offline Page**: Graceful offline experience
- **App Shortcuts**: Quick access to Trends and Archive

### AI Providers
- **Google AI (Gemini)**: Primary provider with structured outputs for reliable JSON
- **Groq**: Fast inference for design generation
- **OpenRouter**: Backup provider with model flexibility
- **Rate Limit Tracking**: Automatic API rate limit monitoring and backoff
- **Multi-provider Fallback**: Automatic failover between providers

## Quick Start

### 1. Get API Keys

**For AI Content Generation (at least one):**
- [Google AI Studio](https://aistudio.google.com/apikey) - Recommended, structured outputs
- [Groq](https://console.groq.com) - Fast inference
- [OpenRouter](https://openrouter.ai) - Backup option with model flexibility

**For Images (recommended):**
- [Pexels](https://www.pexels.com/api/) - 200 requests/hour free
- [Unsplash](https://unsplash.com/developers) - 50 requests/hour free

### 2. Deploy to GitHub

1. Fork or clone this repository
2. Go to **Settings > Pages** and set Source to **GitHub Actions**
3. Go to **Settings > Secrets and variables > Actions**
4. Add your API keys as secrets:
   - `GOOGLE_AI_API_KEY` - Primary AI provider (recommended)
   - `GROQ_API_KEY` - Design generation
   - `OPENROUTER_API_KEY` (optional) - Backup AI provider
   - `PEXELS_API_KEY` - Image source
   - `UNSPLASH_ACCESS_KEY` (optional) - Backup image source

### 3. Configure Repository Settings

**For Auto-merge to work:**
1. **Settings > General > Pull Requests**: Enable "Allow auto-merge"
2. **Settings > Actions > General**: Set workflow permissions to "Read and write"
3. **Create a Personal Access Token (PAT)** with `contents`, `actions`, `pull-requests`, and `administration` permissions
4. **Settings > Secrets > Actions**: Add `PAT_TOKEN` secret with your PAT

**For Branch Protection (optional):**
1. **Settings > Branches > Add rule** for `main`
2. Require pull requests before merging
3. The auto-merge workflow uses `--admin` to bypass protection and merge PRs

### 4. Configure Custom Domain (Optional)

The CNAME file is automatically created during deployment. Just:
1. Configure DNS: CNAME record pointing to `username.github.io`
2. Enable HTTPS in GitHub Pages settings

### 5. Trigger First Build

1. Go to **Actions** tab
2. Click **Daily Website Regeneration**
3. Click **Run workflow**
4. Wait ~2 minutes for completion

## Project Structure

```
daily-trending-info/
├── .github/workflows/
│   ├── daily-regenerate.yml      # Daily build + deploy to Pages
│   ├── auto-merge-claude.yml     # Auto-merge Claude branches via PR
│   └── update-readme.yml         # Auto-update README changelog on push
├── scripts/
│   ├── main.py                   # Pipeline orchestrator (14 steps)
│   ├── collect_trends.py         # 12-source trend aggregator
│   ├── fetch_images.py           # Pexels + Unsplash with persistent cache
│   ├── generate_design.py        # Design system with 9 personalities
│   ├── build_website.py          # HTML/CSS/JS builder with theming
│   ├── enrich_content.py         # Word of Day, Grokipedia, summaries
│   ├── editorial_generator.py    # Daily editorial articles
│   ├── generate_rss.py           # RSS 2.0 with content:encoded
│   ├── sitemap_generator.py      # XML sitemap with articles
│   ├── pwa_generator.py          # Service worker, manifest, offline
│   ├── archive_manager.py        # 30-day archive system
│   └── config.py                 # All magic numbers, timeouts, limits
├── public/                       # Generated website
│   ├── index.html                # Self-contained single-file site
│   ├── articles/                 # Editorial articles (permanent)
│   ├── tech/, world/, social/    # Topic pages
│   ├── archive/                  # 30-day snapshots
│   ├── feed.xml                  # RSS feed
│   ├── sitemap.xml               # XML sitemap
│   ├── llms.txt                  # LLM-friendly documentation
│   ├── manifest.json             # PWA manifest
│   └── sw.js                     # Service worker
├── data/
│   ├── image_cache/              # Persistent image cache (7-day TTL)
│   └── *.json                    # Pipeline data
├── tests/                        # Test suite
├── CLAUDE.md                     # Claude Code instructions
├── requirements.txt
├── CNAME                         # Custom domain
└── README.md
```

## Data Sources

| Source | Content | Update Frequency |
|--------|---------|------------------|
| Google Trends | US daily trending searches | Real-time |
| News RSS | AP, BBC, NYT, NPR, Guardian, Reuters, USA Today, Washington Post | Hourly |
| Tech RSS | Verge, Ars Technica, Wired, TechCrunch, Engadget, MIT Tech Review, Gizmodo, CNET, Mashable, VentureBeat | Hourly |
| Hacker News | Top 25 stories by score | Real-time |
| Lobsters | High-quality tech discussions | Real-time |
| Reddit RSS | 13 subreddits (news, tech, science, worldnews, etc.) | Real-time |
| Product Hunt | New products and startups | Daily |
| Dev.to | Developer articles and tutorials | Daily |
| Slashdot | Classic tech news aggregator | Hourly |
| Ars Features | Long-form tech journalism | Daily |
| GitHub Trending | Daily trending repos (English only) | Daily |
| Wikipedia | Current events portal | Daily |

## Design Personalities

| Personality | Description |
|-------------|-------------|
| Brutalist | Raw, bold, high-contrast with sharp edges |
| Editorial | Classic newspaper feel with serif fonts |
| Minimal | Clean lines, lots of whitespace |
| Corporate | Professional, trustworthy blues and grays |
| Playful | Vibrant colors, rounded corners, fun animations |
| Tech | Dark mode default, neon accents, monospace fonts |
| News | Breaking news style, red accents, urgent feel |
| Magazine | Large images, editorial layouts |
| Dashboard | Data-dense, stats-focused, grid layouts |

## Hero Styles

Each page generation selects a hero style aligned with the chosen personality:

| Style | Effect | Best For |
|-------|--------|----------|
| Cinematic | Movie-poster with slow zoom animation | Brutalist, Editorial, News, Magazine |
| Glassmorphism | Frosted glass effect with backdrop blur | Magazine, Dashboard |
| Neon | Cyberpunk glow with flickering text | Tech, Playful |
| Duotone | Two-tone color overlay on grayscale | Editorial, Magazine |
| Particles | 30 floating animated particles rising upward | Tech, Playful |
| Waves | Animated wave pattern at the bottom | Playful |
| Geometric | Floating geometric shapes (circles, squares) | Brutalist, Playful, Tech, Dashboard |
| Spotlight | Moving lens flare/spotlight effect | Brutalist, Editorial, Corporate, News, Magazine |
| Glitch | Glitch art effect with text distortion | Brutalist, Tech |
| Aurora | Northern lights gradient animation | Minimal, Playful |
| Mesh | Gradient mesh background with shifting colors | Minimal, Corporate, Tech, Dashboard |
| Retro | Synthwave grid with horizon sun | Playful |

## New Design Dimensions

### Image Treatments
Filters applied to card images for visual variety:

| Treatment | Effect |
|-----------|--------|
| Grayscale | Black and white conversion |
| Sepia | Warm vintage tone |
| Saturate | Enhanced color vibrancy |
| Contrast | Increased contrast |
| Vignette | Darkened edges |
| Duotone Warm | Warm two-tone effect |
| Duotone Cool | Cool two-tone effect |

### Typography Scales
Each personality uses different heading size ratios:

| Personality | Scale Ratio | Effect |
|-------------|-------------|--------|
| Brutalist | 1.5 | Dramatic size jumps |
| Editorial | 1.25 | Classic proportions |
| Minimal | 1.2 | Subtle differences |
| Playful | 1.4 | Fun, bouncy |
| Dashboard | 1.15 | Compact, data-dense |

### Section Dividers
Visual separators between content sections:

| Divider | Style |
|---------|-------|
| Line | Simple 1px border |
| Thick Line | Bold 3px accent color |
| Gradient Line | Fading accent gradient |
| Dots | Dotted pattern |
| Fade | Soft gradient transition |
| Wave | SVG wave pattern |

### Content-Aware Animations
Animation intensity adjusts based on detected news sentiment:

| Content Type | Animation Level |
|--------------|-----------------|
| Breaking News | Moderate |
| Entertainment | Playful |
| Positive News | Playful |
| Serious/Negative | Subtle |
| Neutral | Subtle |

### Accessibility Features
- **WCAG AA Contrast**: Automatic validation and adjustment of text colors
- **Focus Indicators**: 3px accent-color outlines on interactive elements
- **Skip Link**: Hidden skip-to-content link for keyboard navigation
- **Touch Targets**: Minimum 44×44px interactive areas
- **Reduced Motion**: Respects system preference for reduced motion

## Editorial Articles

Each day, an AI-generated editorial article synthesizes the top stories into a cohesive analysis.

### Article Structure (8 Required Sections)

| Section | Purpose |
|---------|---------|
| **The Lead** | Hook with surprising insight + thesis statement |
| **What People Think** | Steelman the conventional wisdom |
| **What's Actually Happening** | Contrarian/deeper analysis with evidence |
| **The Hidden Tradeoffs** | Unspoken costs and who wins/loses |
| **The Best Counterarguments** | Steelman strongest objection |
| **What This Means Next** | Concrete predictions with timeframes |
| **Practical Framework** | Actionable mental model for readers |
| **Conclusion** | Circle back to hook with memorable takeaway |

### Article Features
- **URL Structure**: `/articles/YYYY/MM/DD/slug/`
- **Permanent Retention**: Articles never expire (unlike daily snapshots)
- **JSON-LD Schema**: NewsArticle structured data for SEO
- **Related Articles**: Links to previous editorials
- **Word Count**: 800-1200 words per article
- **Mood Indicator**: Transformative, Optimistic, Analytical, etc.

## Local Development

```bash
# Clone the repository
git clone https://github.com/fubak/daily-trending-info.git
cd daily-trending-info

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the pipeline
cd scripts
python main.py

# View the generated website
open ../public/index.html
```

## Configuration

### Change Regeneration Time

Edit `.github/workflows/daily-regenerate.yml`:

```yaml
schedule:
  - cron: '0 14 * * *'  # 2 PM UTC
```

### Archive Retention

In `scripts/main.py`:

```python
self.archive_manager.cleanup_old(keep_days=90)  # Keep 90 days
```

### Google Analytics

The site includes Google Analytics (G-XZNXRW8S7L). To use your own:
1. Edit `scripts/build_website.py`
2. Replace the GA tracking ID in the `<head>` section

## Troubleshooting

### Workflow doesn't trigger on merge
- Ensure "Allow auto-merge" is enabled in repository settings
- Check Actions tab for any failed workflow runs
- The daily-regenerate workflow should trigger on push to main

### Site shows README instead of generated content
- Ensure GitHub Pages source is set to "GitHub Actions" (not branch)
- Run the Daily Website Regeneration workflow manually

### Dark mode not working
- Clear localStorage: `localStorage.removeItem('theme')` in browser console
- The site defaults to dark mode; light mode is toggled via the moon/sun button

### No images displayed
- Verify Pexels/Unsplash API keys are set correctly
- Check API quotas haven't been exceeded
- Site uses persistent image cache (7-day TTL) to reduce API calls
- Cached images are used as fallback when APIs fail
- Gradient fallbacks are used when no images are available

### Build fails with "Insufficient content"
- The minimum content gate requires 5+ trends before deployment
- This prevents broken/empty sites from being deployed
- Check if data sources are accessible (some may be temporarily blocked)
- Most sources have fallbacks, so this error is rare

## API Rate Limits

| Service | Free Limit | Daily Usage | Safety Margin |
|---------|-----------|-------------|---------------|
| Google AI (Gemini) | 15 req/min | 5-10 requests | 90x |
| Groq | ~6,000 req/day | 1-3 requests | 2000x |
| OpenRouter | Varies by model | Backup only | N/A |
| Pexels | 200 req/hour | ~10 requests | 20x |
| Unsplash | 50 req/hour | Backup only | N/A |
| GitHub Actions | 2,000 min/month | ~150 min/month | 13x |
| GitHub Pages | 100 GB/month | ~5 MB/month | 20,000x |

## License

MIT License - Feel free to use and modify.

## Credits

- Trend data from various public APIs and RSS feeds
- Images from [Pexels](https://pexels.com) and [Unsplash](https://unsplash.com)
- AI content generation via [Google AI](https://ai.google.dev), [Groq](https://groq.com), and [OpenRouter](https://openrouter.ai)
- Built with [Claude Code](https://claude.ai)
