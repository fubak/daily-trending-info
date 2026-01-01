# DailyTrending.info

[![Daily Regeneration](https://github.com/fubak/daily-trending-info/actions/workflows/daily-regenerate.yml/badge.svg)](https://github.com/fubak/daily-trending-info/actions/workflows/daily-regenerate.yml)
[![Auto-merge](https://github.com/fubak/daily-trending-info/actions/workflows/auto-merge-claude.yml/badge.svg)](https://github.com/fubak/daily-trending-info/actions/workflows/auto-merge-claude.yml)

A fully autonomous trend aggregation website that regenerates daily with unique designs, English-only content from 12+ sources, and SEO-optimized pages.

**Live Site:** [https://dailytrending.info](https://dailytrending.info)

## Recent Changes

<!-- CHANGELOG_START -->
| Date | Change |
|------|--------|
| 2025-12-31 22:37 UTC | [Enhance Groq design generation and surface AI CTA copy (#17)](https://github.com/fubak/daily-trending-info/commit/aae4ffc85223d450649b4534b4bbdc7aacddf6c1) |
<!-- CHANGELOG_END -->

## Features

### Content Aggregation
- **12 English-Only Sources**: Google Trends, News RSS (12 outlets), Tech RSS (10 sites), Hacker News, Lobsters, Reddit RSS (13 subreddits), Product Hunt, Dev.to, Slashdot, Ars Technica Features, GitHub Trending, Wikipedia Current Events
- **Smart Filtering**: Automatic non-English content detection and filtering
- **Keyword Extraction**: AI-powered keyword analysis with word cloud visualization
- **Source Categorization**: Stories grouped by World News, Technology, Science, Entertainment, etc.
- **Minimum Content Gate**: Requires 5+ trends before deployment to prevent broken sites

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
- **Keyboard Accessibility**: Skip-to-content link, visible focus indicators
- **Touch-Friendly**: Minimum 44x44px touch targets for mobile

### SEO & Analytics
- **Dynamic Titles**: `DailyTrending.info - [Top Story]`
- **Open Graph & Twitter Cards**: Rich social media previews
- **Schema.org JSON-LD**: Structured data for search engines and AI
- **Google Analytics**: Built-in tracking support
- **Semantic HTML**: Proper heading hierarchy and ARIA labels

### Automation
- **Daily Regeneration**: GitHub Actions runs at 6 AM UTC and on every push to main
- **Auto-merge PRs**: Claude branches automatically create and merge PRs
- **Persistent Image Cache**: 7-day cache reduces API calls and provides fallback
- **30-Day Archive**: Browse previous designs
- **Zero Cost**: Runs entirely on free-tier services

## Quick Start

### 1. Get API Keys

**For AI Design (at least one):**
- [Groq](https://console.groq.com) - Recommended, fastest
- [OpenRouter](https://openrouter.ai) - Backup option

**For Images (recommended):**
- [Pexels](https://www.pexels.com/api/) - 200 requests/hour free
- [Unsplash](https://unsplash.com/developers) - 50 requests/hour free

### 2. Deploy to GitHub

1. Fork or clone this repository
2. Go to **Settings > Pages** and set Source to **GitHub Actions**
3. Go to **Settings > Secrets and variables > Actions**
4. Add your API keys as secrets:
   - `GROQ_API_KEY`
   - `OPENROUTER_API_KEY` (optional)
   - `PEXELS_API_KEY`
   - `UNSPLASH_ACCESS_KEY` (optional)

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
│   ├── collect_trends.py         # 12-source trend aggregator
│   ├── fetch_images.py           # Pexels + Unsplash with persistent cache
│   ├── generate_design.py        # Design system with 9 personalities
│   ├── build_website.py          # HTML/CSS/JS builder with theming
│   ├── archive_manager.py        # 30-day archive system
│   └── main.py                   # Pipeline orchestrator with quality gates
├── public/                       # Generated website (created by workflow)
├── data/
│   ├── image_cache/              # Persistent image cache (7-day TTL)
│   └── *.json                    # Pipeline data
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
| Groq | ~6,000 req/day | 1-3 requests | 2000x |
| Pexels | 200 req/hour | ~10 requests | 20x |
| Unsplash | 50 req/hour | Backup only | N/A |
| GitHub Actions | 2,000 min/month | ~150 min/month | 13x |
| GitHub Pages | 100 GB/month | ~5 MB/month | 20,000x |

## License

MIT License - Feel free to use and modify.

## Credits

- Trend data from various public APIs and RSS feeds
- Images from [Pexels](https://pexels.com) and [Unsplash](https://unsplash.com)
- AI design generation via [Groq](https://groq.com) and [OpenRouter](https://openrouter.ai)
- Built with [Claude Code](https://claude.ai)
