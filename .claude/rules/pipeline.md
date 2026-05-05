# Pipeline Rules

## Main Pipeline (16 steps)
1. Archive previous day
2. Load yesterday's trends
3. Collect trends (15+ sources)
4. Fetch images
5. Enrich content
6. Apply fixed design
7. Generate editorial content
8. Build website
9. Generate topic sub-pages (+ CMMC Watch sub-step)
10. Fetch Media of the Day
11. Generate Media of the Day page
12. Generate RSS feed
13. Generate PWA assets
14. Generate sitemap
15. Cleanup old archives
16. Save pipeline data

## Quality Gates
- MIN_TRENDS = 5 (abort if fewer)
- MIN_FRESH_RATIO = 0.5 (warn if <50% fresh in 24h)

## Data Flow
```
15+ Sources → trends.json → images.json → design.json → public/index.html
```

## Output Structure
- `public/index.html` - Self-contained single file
- `public/feed.xml` - RSS 2.0
- `public/sitemap.xml` - XML sitemap
- `public/archive/` - 30-day snapshots
- `public/articles/` - Permanent articles
