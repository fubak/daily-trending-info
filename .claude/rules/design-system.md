# Design System Rules

## AI-Generated Designs
- 9 personalities: brutalist, editorial, minimal, corporate, playful, tech, news, magazine, dashboard
- 12 hero styles: cinematic, glassmorphism, neon, particles, etc.
- 20+ color schemes
- Groq API (primary) with preset fallback

## Font Security
- Whitelist in `config.py::ALLOWED_FONTS`
- Prevent font injection attacks
- Validated before use

## Image Sources
- Primary: Pexels API
- Backup: Unsplash API
- Cache: 7-day TTL in `data/image_cache/`
- Fallback: Gradient placeholders

## Velocity Badges
- HOT (red): 80+ score, 4+ sources
- RISING (yellow): 50-79, 2-3 sources
- STEADY (accent): 30-49

## Comparison Indicators
- New today
- Trending up
- Continuing
- Based on fuzzy title matching with yesterday
