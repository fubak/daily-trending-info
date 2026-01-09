# /preview-site - Preview Generated Site

Preview the generated static site locally.

## Input - Use AskUserQuestion Tool

### Required: Preview Mode

**question**: "How should I preview the site?"
**options**:
- label: "Start local server (Recommended)"
  description: "Serve public/ directory on localhost"
- label: "Check file sizes"
  description: "Analyze bundle sizes and assets"
- label: "Validate HTML"
  description: "Check HTML structure and links"

## Execution

### Local Server
```bash
# Serve the public directory
cd public && python3 -m http.server 8000
```

### File Size Check
```bash
ls -lh public/index.html
ls -lh public/feed.xml
ls -lh public/sitemap.xml
du -sh public/archive/
du -sh public/articles/
```

### HTML Validation
```bash
# Check critical files exist
test -f public/index.html && echo "index.html: OK"
test -f public/feed.xml && echo "RSS feed: OK"
test -f public/sitemap.xml && echo "Sitemap: OK"
test -f public/manifest.json && echo "PWA manifest: OK"
test -f public/sw.js && echo "Service worker: OK"
```

## Output

Report preview status and any issues found.
