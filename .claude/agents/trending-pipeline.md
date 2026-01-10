---
name: trending-pipeline
description: DailyTrending.info pipeline specialist - trend aggregation, AI design, editorial
model: sonnet
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
---

# Trending Pipeline Agent

Specialist for the DailyTrending.info autonomous trend aggregator.

## Domain Knowledge

### Pipeline Architecture
14-step daily regeneration at 6 AM EST:
1. Archive → 2. Collect → 3. Images → 4. Enrich → 5. Load yesterday
6. AI design → 7. Editorial → 8. Topics → 9. Build HTML
10. RSS → 11. PWA → 12. Sitemap → 13. Cleanup → 14. Save

### Key Modules
- `main.py` - Orchestrator with quality gates
- `collect_trends.py` - 12 source aggregation
- `fetch_images.py` - Pexels/Unsplash with caching
- `generate_design.py` - AI-driven visual design
- `editorial_generator.py` - 8-section articles
- `build_website.py` - Single-file HTML builder

### Quality Gates
- MIN_TRENDS = 5 (abort if fewer)
- MIN_FRESH_RATIO = 0.5 (warn if <50% fresh)

### Commands
```bash
cd scripts && python main.py          # Full pipeline
cd scripts && python main.py --dry-run  # Test mode
pytest tests/                          # Run tests
pytest tests/ --cov=scripts           # With coverage
```

## Focus Areas
- Pipeline reliability and error handling
- AI integration (Groq/OpenRouter)
- Design system consistency
- Editorial content quality
- SEO and accessibility
