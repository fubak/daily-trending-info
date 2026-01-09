# /archive-status - Check Archive Status

Check the status of archived content and snapshots.

## Input - Use AskUserQuestion Tool

### Required: Archive Check Type

**question**: "What archive information do you need?"
**options**:
- label: "Full archive overview (Recommended)"
  description: "List all archives with dates and sizes"
- label: "Recent archives only"
  description: "Show last 7 days of archives"
- label: "Archive cleanup check"
  description: "Identify archives older than 30 days"
- label: "Article archives"
  description: "Check permanent article storage"

## Key Directories

- `public/archive/` - 30-day rolling snapshots
- `public/articles/` - Permanent article storage (YYYY/MM/DD/slug/)

## Configuration

- `ARCHIVE_KEEP_DAYS = 30` (from config.py)

## Execution

```bash
# Count archives
echo "Archive snapshots: $(ls -d public/archive/*/ 2>/dev/null | wc -l)"

# Show recent archives
ls -lt public/archive/ | head -10

# Total archive size
du -sh public/archive/

# Article count
echo "Permanent articles: $(find public/articles -name 'index.html' 2>/dev/null | wc -l)"

# Check for old archives (>30 days)
find public/archive -maxdepth 1 -type d -mtime +30 2>/dev/null | wc -l
```

## Output

Report archive status including counts, sizes, and cleanup recommendations.
