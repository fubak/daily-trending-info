# Pipeline Rules

## Main Pipeline (14 steps)
1. Archive previous day
2. Collect trends (12 sources)
3. Fetch images
4. Enrich content
5. Load yesterday's data
6. AI design generation
7. Editorial content
8. Topic pages
9. Build HTML
10. Generate RSS
11. PWA assets
12. Sitemap
13. Cleanup
14. Save state

## Quality Gates
- MIN_TRENDS = 5 (abort if fewer)
- MIN_FRESH_RATIO = 0.5 (warn if <50% fresh in 24h)

## Data Flow
```
12 Sources → trends.json → images.json → design.json → public/index.html
```

## Output Structure
- `public/index.html` - Self-contained single file
- `public/feed.xml` - RSS 2.0
- `public/sitemap.xml` - XML sitemap
- `public/archive/` - 30-day snapshots
- `public/articles/` - Permanent articles
