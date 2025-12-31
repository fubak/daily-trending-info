# Autonomous Trend Website

A fully autonomous website that regenerates daily with trending topics, dynamic images, and AI-generated designs.

## Features

- **Daily Regeneration**: Automatically rebuilds every day at 6 AM UTC
- **Multi-Source Trends**: Aggregates from Google Trends, RSS feeds, Hacker News, Reddit
- **Dynamic Images**: Fetches relevant images from Pexels/Unsplash based on keywords
- **AI Design Generation**: Creates unique color schemes and typography using Groq/OpenRouter
- **Modern Responsive Design**: Bento grid layout, fluid typography, mobile-first
- **Archive System**: Keeps 30 days of previous designs for browsing
- **Zero Cost**: Runs entirely on free-tier services

## Quick Start

### 1. Get API Keys (10 minutes)

**For AI Design (at least one):**
- [Groq](https://console.groq.com) - Recommended, fastest
- [OpenRouter](https://openrouter.ai) - Backup

**For Images (recommended):**
- [Pexels](https://www.pexels.com/api/) - 200 requests/hour free
- [Unsplash](https://unsplash.com/developers) - 50 requests/hour free

### 2. Deploy to GitHub

1. Create a new repository on GitHub
2. Push this code to your repository
3. Go to **Settings > Pages** and set Source to **GitHub Actions**
4. Go to **Settings > Secrets and variables > Actions**
5. Add your API keys as secrets:
   - `GROQ_API_KEY`
   - `OPENROUTER_API_KEY` (optional)
   - `PEXELS_API_KEY`
   - `UNSPLASH_ACCESS_KEY` (optional)

### 3. Trigger First Build

1. Go to **Actions** tab
2. Click **Daily Website Regeneration**
3. Click **Run workflow**
4. Wait ~2 minutes for completion
5. Visit `https://yourusername.github.io/repo-name/`

## Project Structure

```
trend-website/
├── .github/workflows/
│   └── daily-regenerate.yml    # GitHub Actions automation
├── scripts/
│   ├── collect_trends.py       # 5-source trend aggregator
│   ├── fetch_images.py         # Pexels + Unsplash integration
│   ├── generate_design.py      # AI design with fallbacks
│   ├── build_website.py        # HTML/CSS builder
│   ├── archive_manager.py      # Archive system
│   └── main.py                 # Pipeline orchestrator
├── public/                     # Generated website (gitignored)
├── data/                       # Pipeline data (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

## Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/trend-website.git
cd trend-website

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
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

### Multiple Daily Updates

```yaml
schedule:
  - cron: '0 6 * * *'   # 6 AM UTC
  - cron: '0 18 * * *'  # 6 PM UTC
```

### Archive Retention

In `scripts/main.py`, modify the cleanup call:

```python
self.archive_manager.cleanup_old(keep_days=90)  # Keep 90 days
```

### Custom Design Style

Modify the AI prompt in `scripts/generate_design.py` to change the design direction.

## API Rate Limits

| Service | Free Limit | Daily Usage | Safety Margin |
|---------|-----------|-------------|---------------|
| Groq | ~6,000 req/day | 1-3 requests | 2000x |
| Pexels | 200 req/hour | ~10 requests | 20x |
| Unsplash | 50 req/hour | Backup only | N/A |
| GitHub Actions | 2,000 min/month | ~150 min/month | 13x |
| GitHub Pages | 100 GB/month | ~5 MB/month | 20,000x |

## Troubleshooting

### Pipeline fails to collect trends
- Check internet connectivity
- Some RSS feeds may be temporarily unavailable
- The system will continue with available sources

### No images displayed
- Verify API keys are set correctly
- Check Pexels/Unsplash API quotas
- Site will use gradient fallbacks automatically

### Design looks the same every day
- Ensure at least one AI API key is configured
- Check Groq/OpenRouter API quotas
- Preset designs are used as fallback

## License

MIT License - Feel free to use and modify.

## Credits

- Trend data from various public APIs and RSS feeds
- Images from [Pexels](https://pexels.com) and [Unsplash](https://unsplash.com)
- AI design generation via [Groq](https://groq.com) and [OpenRouter](https://openrouter.ai)
