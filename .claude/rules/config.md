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
- `SITE_URL` / `SITE_NAME` - Canonical base URL + brand name (single source of truth; `RSS_FEED_LINK`/`RSS_FEED_TITLE` derive from them)

## GitHub Actions
- `ci.yml` - PR + push to main: py_compile + pytest + mypy on Python 3.11 & 3.12 (required status checks on `main`). CI runs 3.11; local `.venv` is 3.12 — verify f-string syntax under 3.11 before merging.
- `daily-regenerate.yml` - Daily 6AM EST
- `auto-merge-claude.yml` - Auto PR merge for `claude/**` branches
- `update-readme.yml` - Changelog updates
