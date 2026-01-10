# Config Rules

## Environment Variables
Required in `.env` or GitHub Secrets:
- `GROQ_API_KEY` - Primary AI
- `OPENROUTER_API_KEY` - Backup AI
- `PEXELS_API_KEY` - Primary images
- `UNSPLASH_ACCESS_KEY` - Backup images

## Config Constants (`config.py`)
- `LIMITS` - Per-source fetch limits
- `TIMEOUTS` - HTTP timeouts by operation
- `DELAYS` - Rate limiting delays
- `IMAGE_CACHE_MAX_AGE_DAYS = 7`
- `ARCHIVE_KEEP_DAYS = 30`
- `DEDUP_SIMILARITY_THRESHOLD = 0.8`

## GitHub Actions
- `daily-regenerate.yml` - Daily 6AM EST
- `auto-merge-claude.yml` - Auto PR merge for `claude/**` branches
- `update-readme.yml` - Changelog updates
