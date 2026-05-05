# SEO & LLM Optimization Remediation Plan
## DailyTrending.info - Comprehensive Implementation Guide

**Generated:** January 8, 2026
**Status:** Ready for Implementation
**Estimated Effort:** 12-16 hours (excluding testing)

---

## Executive Summary

This plan addresses SEO visibility, LLM optimization, and technical architecture issues for DailyTrending.info. Based on codebase analysis, **many recommended features already exist but are underutilized**. The focus is on fixing critical bugs, implementing missing JSON-LD structured data, and improving content discoverability.

**Key Findings:**
- ✅ Archive system exists (`/archive/YYYY-MM-DD/`) but lacks navigation
- ✅ Editorial content system exists (`/articles/`) with 8-section analysis
- ✅ Topic pages exist (`/tech/`, `/world/`, `/social/`)
- ❌ Homepage title tag bug (truncates to random article title)
- ❌ JSON-LD structured data placeholder is empty
- ⚠️ Existing features not discoverable to crawlers or users

---

## Current State Assessment

### ✅ Already Implemented (Strengths)

| Feature | Implementation | Location | Status |
|---------|----------------|----------|--------|
| **Archive System** | 30-day dated snapshots | `scripts/archive_manager.py:25` | ✅ Working, Hidden |
| **Editorial Articles** | 8-section analytical content | `scripts/editorial_generator.py:610` | ✅ Working, Not Linked |
| **Topic Pages** | Category-specific aggregation | `/tech/`, `/world/`, `/social/` | ✅ Working, Underutilized |
| **Open Graph Tags** | Full OG + Twitter Cards | `templates/base.html:22-38` | ✅ Complete |
| **RSS Feed** | RSS 2.0 with full HTML | `scripts/generate_rss.py` | ✅ Complete |
| **Meta Tags** | Basic SEO headers | `templates/base.html:7-13` | ✅ Partial |
| **Canonical URLs** | Self-referencing canonical | `templates/base.html:16` | ✅ Partial |
| **Static HTML** | Jinja2 pre-rendering | `scripts/build_website.py:433` | ✅ Complete |

### ❌ Critical Issues

| Issue | Current State | Impact | Evidence |
|-------|---------------|--------|----------|
| **Dynamic Title Bug** | `DailyTrending.info - Opus 4.5 is not...` | 🔴 High | `public/index.html:8` |
| **Empty JSON-LD** | `'structured_data': ''` placeholder | 🔴 High | `build_website.py:582` |
| **No Archive Navigation** | Archive exists but no links | 🟡 Medium | Missing in `shared_components.py` |
| **Editorial Hidden** | Articles exist but not promoted | 🟡 Medium | No homepage link |
| **Generic Meta Description** | Date-based dynamic text | 🟡 Medium | `build_website.py:426-430` |
| **Fallback Alt Text** | "Placeholder image" | 🟠 Low | `templates/index.html:101` |

---

## Phase 1: Critical Technical Fixes (Priority 0)
*Immediate action required - these block search engine understanding*

### 1.1 Fix Homepage Title Tag Logic ⚠️ CRITICAL

**Current Issue:**
```html
<title>DailyTrending.info - Opus 4.5 is not the normal AI agent experience that I have h</title>
```

**Root Cause:**
- `build_website.py:534` - `'page_title': f"DailyTrending.info - {self._get_top_topic()}"`
- `build_website.py:420-424` - `_get_top_topic()` truncates first trend title to 60 chars

**Fix:**
```python
# In build_website.py:420-425
def _get_top_topic(self) -> str:
    """Get the main topic for SEO title - ONLY use for non-homepage pages."""
    if self.ctx.trends:
        return self.ctx.trends[0].get('title', '')[:60]
    return "Today's Top Trends"
```

**New Implementation:**
```python
# In build_website.py:532-540 (render_context)
# Replace line 534 with:
'page_title': self._build_page_title(),

# Add new method:
def _build_page_title(self) -> str:
    """Build SEO-optimized page title."""
    # Static title for homepage to build domain authority
    return "DailyTrending.info | AI-Curated Tech & World News Aggregator"
```

**Files to Modify:**
- `scripts/build_website.py:534` - Update page_title
- `scripts/build_website.py:420-425` - Add `_build_page_title()` method

**Expected Output:**
```html
<title>DailyTrending.info | AI-Curated Tech & World News Aggregator</title>
```

**Testing:**
```bash
cd scripts && python main.py --dry-run
grep "<title>" public/index.html
```

---

### 1.2 Implement JSON-LD Structured Data ⚠️ CRITICAL

**Current Issue:**
```html
<!-- Structured Data -->

```

**Root Cause:**
- `build_website.py:582` - `'structured_data': ''  # JSON-LD generation can be moved to a helper`
- Function was never implemented despite being documented in CLAUDE.md

**Implementation:**

Create `_build_structured_data()` method in `WebsiteBuilder` class:

```python
# In build_website.py - Add after line 430

def _build_structured_data(self) -> str:
    """Generate comprehensive JSON-LD structured data for SEO and LLMs."""
    import json
    from datetime import datetime

    # Base WebSite schema
    website_schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "DailyTrending.info",
        "alternateName": "Daily Trending",
        "url": "https://dailytrending.info/",
        "description": "AI-curated technology and world news aggregator, updated daily",
        "potentialAction": {
            "@type": "SearchAction",
            "target": "https://dailytrending.info/?q={search_term_string}",
            "query-input": "required name=search_term_string"
        },
        "sameAs": [
            "https://twitter.com/bradshannon"
        ]
    }

    # CollectionPage with ItemList
    top_stories = self._select_top_stories()
    item_list_elements = []

    for idx, story in enumerate(top_stories[:10], 1):
        item = {
            "@type": "ListItem",
            "position": idx,
            "item": {
                "@type": "NewsArticle",
                "headline": story.get('title', ''),
                "url": story.get('url', ''),
                "datePublished": story.get('timestamp', datetime.now().isoformat()),
                "publisher": {
                    "@type": "Organization",
                    "name": story.get('source', '').replace('_', ' ').title()
                }
            }
        }

        # Add image if available
        if story.get('image_url'):
            item["item"]["image"] = story.get('image_url')

        # Add description if available
        if story.get('summary') or story.get('description'):
            item["item"]["description"] = story.get('summary') or story.get('description')

        item_list_elements.append(item)

    collection_schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": f"Daily Trending Topics - {self.ctx.generated_at}",
        "description": self._build_meta_description(),
        "url": "https://dailytrending.info/",
        "datePublished": datetime.now().isoformat(),
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(item_list_elements),
            "itemListElement": item_list_elements
        }
    }

    # FAQPage schema for common questions
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "How often is DailyTrending.info updated?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "DailyTrending.info regenerates automatically every day at 6 AM EST via GitHub Actions, aggregating the latest trending stories from 12+ sources including Hacker News, NPR, BBC, Reddit, and GitHub."
                }
            },
            {
                "@type": "Question",
                "name": "What sources does DailyTrending.info aggregate?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "We aggregate from 12 curated sources: Hacker News, Lobsters, GitHub Trending, Reddit (r/technology, r/worldnews, r/programming), NPR, BBC, Reuters, Wikipedia Current Events, and specialized tech RSS feeds."
                }
            },
            {
                "@type": "Question",
                "name": "Is DailyTrending.info content AI-generated?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Headlines and summaries are sourced from original publishers. Our AI curates, ranks, and selects trending topics, and generates unique editorial analysis for top stories."
                }
            }
        ]
    }

    # Combine all schemas using @graph
    combined_schema = {
        "@context": "https://schema.org",
        "@graph": [
            website_schema,
            collection_schema,
            faq_schema
        ]
    }

    return f'<script type="application/ld+json">\n{json.dumps(combined_schema, indent=2)}\n</script>'
```

**Integration:**
```python
# In build_website.py:582 - Replace empty string with:
'structured_data': self._build_structured_data()
```

**Files to Modify:**
- `scripts/build_website.py:430` - Add `_build_structured_data()` method
- `scripts/build_website.py:582` - Call the method

**Testing:**
```bash
cd scripts && python main.py --dry-run
grep -A 50 "application/ld+json" public/index.html | head -60
```

**Validation:**
- Google Rich Results Test: https://search.google.com/test/rich-results
- Schema.org Validator: https://validator.schema.org/

---

### 1.3 Enhance Meta Description with Keywords

**Current Implementation:**
```python
# build_website.py:426-430
def _build_meta_description(self) -> str:
    """Build SEO-friendly meta description."""
    categories = list(self.grouped_trends.keys())[:4]
    cat_str = ', '.join(categories)
    return f"Daily trending topics for {self.ctx.generated_at}. {len(self.ctx.trends)} stories covering {cat_str}."
```

**Issue:**
- Dynamic date-based description changes daily (loses keyword consistency)
- Doesn't emphasize "real-time" or "AI-curated" value proposition
- Generic category listing

**Fix:**
```python
# In build_website.py:426-430 - Replace with:
def _build_meta_description(self) -> str:
    """Build SEO-optimized meta description with consistent keywords."""
    return (
        "Real-time dashboard of trending tech, science, and world news stories. "
        "AI-curated daily from Hacker News, NPR, BBC, Reddit, and 12+ sources. "
        f"Updated {self.ctx.generated_at} with {len(self.ctx.trends)} stories."
    )
```

**Files to Modify:**
- `scripts/build_website.py:426-430`

**Expected Output:**
```html
<meta name="description" content="Real-time dashboard of trending tech, science, and world news stories. AI-curated daily from Hacker News, NPR, BBC, Reddit, and 12+ sources. Updated January 08, 2026 with 514 stories.">
```

---

## Phase 2: Content Discoverability (Priority 1)
*Turn hidden features into indexable, crawlable content*

### 2.1 Add Archive Navigation to Site Header/Footer

**Current State:**
- Archive system exists: `scripts/archive_manager.py:25`
- Generates `/archive/YYYY-MM-DD/index.html`
- Archive index page exists: `/archive/index.html`
- **No navigation links anywhere on the site**

**Impact:**
- Google/Bing cannot discover historical content
- 30 days of content invisible to crawlers
- Lost SEO value from accumulated keywords

**Implementation:**

**Step 1:** Update `shared_components.py` to add archive link

```python
# In scripts/shared_components.py - Find build_header() function

def build_header(active_page: str = 'home') -> str:
    """Build the site header with navigation."""
    return f'''
    <header class="site-header" role="banner">
        <div class="header-container">
            <div class="header-brand">
                <a href="/" class="logo-link">
                    <span class="logo-icon">📊</span>
                    <h1 class="logo-text">DailyTrending.info</h1>
                </a>
                <p class="tagline">AI-Curated News Aggregator</p>
            </div>

            <nav class="main-nav" role="navigation" aria-label="Main navigation">
                <a href="/" class="nav-link {'active' if active_page == 'home' else ''}">Today</a>
                <a href="/tech/" class="nav-link {'active' if active_page == 'tech' else ''}">Tech</a>
                <a href="/world/" class="nav-link {'active' if active_page == 'world' else ''}">World</a>
                <a href="/social/" class="nav-link {'active' if active_page == 'social' else ''}">Social</a>
                <a href="/articles/" class="nav-link {'active' if active_page == 'articles' else ''}">Analysis</a>
                <a href="/archive/" class="nav-link {'active' if active_page == 'archive' else ''}">Archive</a>
                <a href="/feed.xml" class="nav-link rss-link" title="RSS Feed">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M4 11a9 9 0 0 1 9 9"/>
                        <path d="M4 4a16 16 0 0 1 16 16"/>
                        <circle cx="5" cy="19" r="1"/>
                    </svg>
                </a>
            </nav>

            <button class="theme-toggle" type="button" aria-label="Toggle dark mode" title="Toggle theme">
                <svg class="sun-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="5"/>
                    <line x1="12" y1="1" x2="12" y2="3"/>
                    <line x1="12" y1="21" x2="12" y2="23"/>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                    <line x1="1" y1="12" x2="3" y2="12"/>
                    <line x1="21" y1="12" x2="23" y2="12"/>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                </svg>
                <svg class="moon-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
            </button>
        </div>
    </header>
    '''
```

**Step 2:** Update footer to include archive link

```python
# In scripts/shared_components.py - Find build_footer() function

def build_footer() -> str:
    """Build the site footer."""
    return f'''
    <footer class="site-footer" role="contentinfo">
        <div class="footer-container">
            <div class="footer-section">
                <h3>DailyTrending.info</h3>
                <p>AI-curated news aggregator, regenerated daily at 6 AM EST.</p>
            </div>

            <div class="footer-section">
                <h4>Sections</h4>
                <ul>
                    <li><a href="/tech/">Technology</a></li>
                    <li><a href="/world/">World News</a></li>
                    <li><a href="/social/">Social Media</a></li>
                    <li><a href="/articles/">Editorial Analysis</a></li>
                </ul>
            </div>

            <div class="footer-section">
                <h4>Resources</h4>
                <ul>
                    <li><a href="/archive/">Archive</a></li>
                    <li><a href="/feed.xml">RSS Feed</a></li>
                    <li><a href="/media/">Media of the Day</a></li>
                    <li><a href="https://github.com/bradsherman/daily-trending-info" target="_blank" rel="noopener">Source Code</a></li>
                </ul>
            </div>

            <div class="footer-section">
                <h4>About</h4>
                <p class="footer-small">
                    Aggregates from 12 sources: Hacker News, Lobsters, GitHub, Reddit, NPR, BBC, Reuters, Wikipedia, and more.
                </p>
                <p class="footer-small">
                    Built with Python, powered by Groq AI. Fully open source.
                </p>
            </div>
        </div>

        <div class="footer-bottom">
            <p>&copy; 2026 DailyTrending.info | Updated daily via GitHub Actions</p>
        </div>
    </footer>
    '''
```

**Files to Modify:**
- `scripts/shared_components.py` - Update `build_header()` and `build_footer()`
- `scripts/get_header_styles()` - Add CSS for `.active` state on nav links

**Testing:**
```bash
cd scripts && python main.py
grep -i "archive" public/index.html
```

---

### 2.2 Promote Editorial Articles on Homepage

**Current State:**
- Editorial system generates in-depth 8-section articles
- Saved to `/articles/YYYY/MM/DD/slug/index.html`
- Article index exists at `/articles/index.html`
- **Not linked from homepage at all**

**Value:**
- Unique, non-scraped content (defeats "thin content" penalty)
- 800-2000 word analytical pieces
- Permanent URLs (SEO accumulation)
- Central themes from keyword frequency

**Implementation:**

Add "Featured Analysis" section to homepage after "Top Stories":

```python
# In templates/index.html - Add after Top Stories section (around line 135)

{% if editorial_article %}
<section class="section editorial-section">
    <div class="section-header">
        <h2 class="section-title">📝 Today's Analysis</h2>
        <a href="/articles/" class="section-link">View All Articles →</a>
    </div>

    <article class="editorial-card featured">
        <div class="editorial-content">
            <span class="editorial-badge">Editorial</span>
            <h3 class="editorial-title">
                <a href="{{ editorial_article.url }}">{{ editorial_article.title }}</a>
            </h3>
            <p class="editorial-excerpt">{{ editorial_article.summary[:200] }}...</p>

            <div class="editorial-meta">
                <span>{{ editorial_article.word_count }} words</span>
                <span aria-hidden="true">•</span>
                <span>{{ editorial_article.read_time }} min read</span>
                <span aria-hidden="true">•</span>
                <span>{{ editorial_article.mood | title }} tone</span>
            </div>

            <a href="{{ editorial_article.url }}" class="editorial-cta">
                Read Full Analysis →
            </a>
        </div>
    </article>
</section>
{% endif %}
```

**Pass editorial article to template:**

```python
# In scripts/build_website.py:532-583 (render_context)
# Add after line 577:

# Load today's editorial article if it exists
editorial_article = self._get_todays_editorial()

# Then in render_context dict, add:
'editorial_article': editorial_article,
```

**Add helper method:**

```python
# In scripts/build_website.py - Add new method

def _get_todays_editorial(self) -> Optional[Dict]:
    """Get today's editorial article if it exists."""
    from pathlib import Path
    import json
    from datetime import datetime

    today = datetime.now().strftime("%Y/%m/%d")
    articles_dir = Path("public/articles") / today

    if not articles_dir.exists():
        return None

    # Find the article metadata
    for article_dir in articles_dir.iterdir():
        if article_dir.is_dir():
            metadata_file = article_dir / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    return json.load(f)

    return None
```

**Files to Modify:**
- `templates/index.html:135` - Add editorial section
- `scripts/build_website.py:577` - Add `_get_todays_editorial()` method
- `scripts/build_website.py:583` - Pass to render_context
- `templates/base.html` or `get_header_styles()` - Add `.editorial-card` CSS

**Testing:**
```bash
cd scripts && python main.py
grep "Today's Analysis" public/index.html
```

---

### 2.3 Add Archive Pages to Sitemap

**Current State:**
- Sitemap generator exists: `scripts/sitemap_generator.py`
- Only includes homepage and topic pages
- Archive pages (30 days × URLs) not included

**Implementation:**

```python
# In scripts/sitemap_generator.py - Find generate_sitemap() function

def generate_sitemap(public_dir: str = "public") -> str:
    """Generate sitemap.xml for the site."""
    from datetime import datetime, timedelta
    from pathlib import Path

    base_url = "https://dailytrending.info"
    today = datetime.now()

    urls = [
        # Homepage - daily updates
        {
            'loc': f'{base_url}/',
            'lastmod': today.strftime('%Y-%m-%d'),
            'changefreq': 'daily',
            'priority': '1.0'
        },
        # Topic pages
        {
            'loc': f'{base_url}/tech/',
            'lastmod': today.strftime('%Y-%m-%d'),
            'changefreq': 'daily',
            'priority': '0.9'
        },
        {
            'loc': f'{base_url}/world/',
            'lastmod': today.strftime('%Y-%m-%d'),
            'changefreq': 'daily',
            'priority': '0.9'
        },
        {
            'loc': f'{base_url}/social/',
            'lastmod': today.strftime('%Y-%m-%d'),
            'changefreq': 'daily',
            'priority': '0.9'
        },
        # Archive index
        {
            'loc': f'{base_url}/archive/',
            'lastmod': today.strftime('%Y-%m-%d'),
            'changefreq': 'daily',
            'priority': '0.8'
        },
        # Articles index
        {
            'loc': f'{base_url}/articles/',
            'lastmod': today.strftime('%Y-%m-%d'),
            'changefreq': 'daily',
            'priority': '0.8'
        },
        # Media page
        {
            'loc': f'{base_url}/media/',
            'lastmod': today.strftime('%Y-%m-%d'),
            'changefreq': 'daily',
            'priority': '0.7'
        },
    ]

    # Add archive pages (last 30 days)
    archive_dir = Path(public_dir) / "archive"
    if archive_dir.exists():
        for date_dir in sorted(archive_dir.iterdir(), reverse=True):
            if date_dir.is_dir() and date_dir.name != 'index.html':
                try:
                    # Parse date from directory name (YYYY-MM-DD format)
                    date_obj = datetime.strptime(date_dir.name, '%Y-%m-%d')

                    urls.append({
                        'loc': f'{base_url}/archive/{date_dir.name}/',
                        'lastmod': date_obj.strftime('%Y-%m-%d'),
                        'changefreq': 'never',  # Archive pages don't change
                        'priority': '0.6'
                    })
                except ValueError:
                    continue  # Skip invalid directory names

    # Add article pages
    articles_dir = Path(public_dir) / "articles"
    if articles_dir.exists():
        for year_dir in articles_dir.iterdir():
            if not year_dir.is_dir() or year_dir.name == 'index.html':
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir():
                        continue
                    for article_dir in day_dir.iterdir():
                        if article_dir.is_dir() and (article_dir / "index.html").exists():
                            article_date = f"{year_dir.name}-{month_dir.name}-{day_dir.name}"

                            urls.append({
                                'loc': f'{base_url}/articles/{year_dir.name}/{month_dir.name}/{day_dir.name}/{article_dir.name}/',
                                'lastmod': article_date,
                                'changefreq': 'never',
                                'priority': '0.7'
                            })

    # Build XML
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for url in urls:
        xml_content += '  <url>\n'
        xml_content += f'    <loc>{url["loc"]}</loc>\n'
        xml_content += f'    <lastmod>{url["lastmod"]}</lastmod>\n'
        xml_content += f'    <changefreq>{url["changefreq"]}</changefreq>\n'
        xml_content += f'    <priority>{url["priority"]}</priority>\n'
        xml_content += '  </url>\n'

    xml_content += '</urlset>'

    # Save sitemap
    sitemap_path = Path(public_dir) / "sitemap.xml"
    with open(sitemap_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)

    print(f"Generated sitemap with {len(urls)} URLs")
    return str(sitemap_path)
```

**Files to Modify:**
- `scripts/sitemap_generator.py` - Update `generate_sitemap()` function

**Testing:**
```bash
cd scripts && python main.py
cat public/sitemap.xml | grep -c "<url>"
```

---

## Phase 3: Image & Social Optimization (Priority 2)

### 3.1 Create Static Branded OG Image

**Current State:**
- OG image uses dynamic hero image (changes daily)
- No fallback branded image
- Social shares look inconsistent

**Implementation:**

**Option A:** Design a 1200×630 PNG branded image
- Logo + "DailyTrending.info"
- Tagline: "AI-Curated Tech & World News"
- Dark theme background
- Save as `public/og-image.png`

**Option B:** Generate programmatically using Pillow

```python
# Create scripts/generate_og_image.py

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def generate_og_image(output_path: str = "public/og-image.png"):
    """Generate a 1200x630 Open Graph image."""
    # Create image
    width, height = 1200, 630
    bg_color = (10, 10, 10)  # Dark background
    accent_color = (99, 102, 241)  # Indigo accent
    text_color = (255, 255, 255)  # White text

    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to load fonts (with fallback)
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

    # Draw gradient accent bar
    for i in range(200):
        alpha = int(255 * (1 - i / 200))
        draw.rectangle([(0, i), (width, i + 1)], fill=(*accent_color, alpha))

    # Draw title
    title_text = "DailyTrending.info"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((width - title_width) / 2, 250), title_text, fill=text_color, font=title_font)

    # Draw subtitle
    subtitle_text = "AI-Curated Tech & World News Aggregator"
    subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
    draw.text(((width - subtitle_width) / 2, 380), subtitle_text, fill=(161, 161, 170), font=subtitle_font)

    # Draw metadata
    meta_text = "Updated Daily at 6 AM EST • 12+ Sources • Open Source"
    meta_bbox = draw.textbbox((0, 0), meta_text, font=subtitle_font)
    meta_width = meta_bbox[2] - meta_bbox[0]
    draw.text(((width - meta_width) / 2, 480), meta_text, fill=(113, 113, 122), font=subtitle_font)

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=95)
    print(f"Generated OG image: {output_path}")

if __name__ == "__main__":
    generate_og_image()
```

**Integrate into main pipeline:**

```python
# In scripts/main.py - Add to _step_generate_pwa() or create new step

def _step_generate_og_image(self):
    """Generate static Open Graph image."""
    print("\n📸 Generating Open Graph image...")
    try:
        from generate_og_image import generate_og_image
        generate_og_image("public/og-image.png")
    except Exception as e:
        print(f"⚠️ Failed to generate OG image: {e}")
        print("Using fallback - create public/og-image.png manually")
```

**Update template to use static image:**

```python
# In scripts/build_website.py:580 - Replace with:
'og_image_tags': '<meta property="og:image" content="https://dailytrending.info/og-image.png">\n    <meta property="og:image:width" content="1200">\n    <meta property="og:image:height" content="630">',
'twitter_image_tags': '<meta name="twitter:image" content="https://dailytrending.info/og-image.png">',
```

**Files to Modify:**
- Create `scripts/generate_og_image.py`
- `scripts/main.py` - Add generation step
- `scripts/build_website.py:580-581` - Use static image URL

**Testing:**
```bash
python scripts/generate_og_image.py
ls -lh public/og-image.png
# Upload to https://www.opengraph.xyz/ to preview
```

---

### 3.2 Improve Image Alt Text Fallback

**Current State:**
```html
<img src="{{ img_src }}"
     alt="{{ story.title if story.image_url else 'Placeholder image' }}"
```

**Issue:**
- "Placeholder image" is not descriptive
- Fails accessibility standards
- Loses SEO value for image search

**Fix:**

```html
<!-- In templates/index.html:100-106 -->
<img src="{{ img_src }}"
     alt="{{ story.title if story.image_url else (story.category or story.source | replace('_', ' ') | title) + ' story: ' + story.title }}"
     class="story-image{% if not story.image_url %} placeholder{% endif %}"
     loading="eager"
     referrerpolicy="no-referrer"
     width="800"
     height="450">
```

**Example Output:**
- With image: `alt="SpaceX Starship launch delayed to March 2026"`
- Without image: `alt="Technology story: SpaceX Starship launch delayed to March 2026"`

**Files to Modify:**
- `templates/index.html:101`

---

## Phase 4: Advanced Schema & Structured Data (Priority 3)

### 4.1 Add BreadcrumbList Schema for Archive/Article Pages

**Implementation:**

```python
# In scripts/archive_manager.py - Update archive_current() method

def archive_current(self, design: Dict = None) -> Optional[str]:
    """Archive the current website to a dated folder."""
    # ... existing code ...

    # Add breadcrumb schema to archive page
    breadcrumb_schema = f'''
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{
          "@type": "ListItem",
          "position": 1,
          "name": "Home",
          "item": "https://dailytrending.info/"
        }},
        {{
          "@type": "ListItem",
          "position": 2,
          "name": "Archive",
          "item": "https://dailytrending.info/archive/"
        }},
        {{
          "@type": "ListItem",
          "position": 3,
          "name": "{today}",
          "item": "https://dailytrending.info/archive/{today}/"
        }}
      ]
    }}
    </script>
    '''

    # Insert breadcrumb schema before </head>
    html_content = html_content.replace('</head>', f'{breadcrumb_schema}\n</head>')
```

**Files to Modify:**
- `scripts/archive_manager.py:70` - Add breadcrumb schema
- `scripts/editorial_generator.py` - Add breadcrumb to article pages

---

### 4.2 Add Speakable Schema for Voice Search

**Purpose:**
- Optimize for Google Assistant, Alexa, Siri
- Identify key content for text-to-speech
- Enhance voice search results

**Implementation:**

```python
# In scripts/build_website.py:_build_structured_data()
# Add to website_schema:

"speakable": {
    "@type": "SpeakableSpecification",
    "cssSelector": [".hero-content h1", ".hero-subtitle", ".story-title"]
}
```

**Files to Modify:**
- `scripts/build_website.py` - Update `_build_structured_data()` method

---

## Phase 5: Content Quality Enhancements (Future)

### 5.1 AI-Generated Category Summaries

**Current State:**
- Categories show card grids only
- No unique text (just aggregated headlines)

**Enhancement:**
Generate 150-200 word category summaries using Groq API:

```python
# In scripts/build_website.py - Add method

def _generate_category_summary(self, category: str, stories: List[Dict]) -> str:
    """Generate AI summary for a category section."""
    from config import GROQ_API_KEY
    import requests

    headlines = [s.get('title') for s in stories[:5]]
    prompt = f"""Analyze these {category} headlines and write a 2-sentence summary of the state of {category} today:

{chr(10).join(f"- {h}" for h in headlines)}

Write conversationally, focus on themes and implications, not just listing topics."""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150
            },
            timeout=10
        )

        if response.ok:
            return response.json()['choices'][0]['message']['content']
    except:
        pass

    return ""
```

**Add to template:**

```html
<!-- In templates/index.html - Update category section -->
{% if category.summary %}
<p class="category-summary">{{ category.summary }}</p>
{% endif %}
```

**Files to Create/Modify:**
- `scripts/build_website.py` - Add `_generate_category_summary()`
- `templates/index.html` - Display summary

**Note:** This adds API costs (~$0.01/day) but significantly improves SEO.

---

## Implementation Checklist

### Week 1: Critical Fixes (P0)

- [ ] **Day 1:** Fix homepage title tag bug
  - [ ] Update `build_website.py:534`
  - [ ] Add `_build_page_title()` method
  - [ ] Test: `grep "<title>" public/index.html`

- [ ] **Day 2-3:** Implement JSON-LD structured data
  - [ ] Create `_build_structured_data()` method
  - [ ] Add WebSite schema
  - [ ] Add CollectionPage with ItemList
  - [ ] Add FAQPage schema
  - [ ] Test with Google Rich Results Test

- [ ] **Day 4:** Enhance meta description
  - [ ] Update `_build_meta_description()`
  - [ ] Verify keyword placement

### Week 2: Discoverability (P1)

- [ ] **Day 5-6:** Add navigation links
  - [ ] Update `build_header()` in shared_components.py
  - [ ] Update `build_footer()`
  - [ ] Add CSS for active states
  - [ ] Test navigation on all pages

- [ ] **Day 7:** Promote editorial content
  - [ ] Add editorial section to homepage
  - [ ] Create `_get_todays_editorial()` method
  - [ ] Add CSS for editorial cards
  - [ ] Test editorial display

- [ ] **Day 8:** Update sitemap
  - [ ] Add archive pages to sitemap
  - [ ] Add article pages to sitemap
  - [ ] Submit to Google Search Console

### Week 3: Optimization (P2-P3)

- [ ] **Day 9:** Create OG image
  - [ ] Design or generate branded image
  - [ ] Update OG meta tags
  - [ ] Test social sharing

- [ ] **Day 10:** Image alt text fixes
  - [ ] Update template alt attribute logic
  - [ ] Test with screen reader

- [ ] **Day 11:** Breadcrumb schema
  - [ ] Add to archive pages
  - [ ] Add to article pages
  - [ ] Validate schema

- [ ] **Day 12:** Testing & validation
  - [ ] Google Rich Results Test
  - [ ] Schema.org validator
  - [ ] Lighthouse SEO audit
  - [ ] Manual testing on mobile

---

## Testing & Validation

### Automated Tests

```bash
# SEO validation script
cat > scripts/validate_seo.sh << 'EOF'
#!/bin/bash
set -e

echo "🔍 SEO Validation Suite"
echo "======================="

# 1. Check title tag
echo -e "\n1. Title Tag:"
TITLE=$(grep -o '<title>[^<]*</title>' public/index.html | sed 's/<[^>]*>//g')
echo "   $TITLE"
if [[ $TITLE == *"DailyTrending.info | AI-Curated"* ]]; then
    echo "   ✅ Title is correct"
else
    echo "   ❌ Title bug still present"
    exit 1
fi

# 2. Check meta description
echo -e "\n2. Meta Description:"
DESC=$(grep -o 'name="description" content="[^"]*"' public/index.html | sed 's/.*content="//;s/"//')
echo "   ${DESC:0:100}..."
if [[ $DESC == *"Real-time dashboard"* ]]; then
    echo "   ✅ Meta description is optimized"
else
    echo "   ⚠️ Meta description could be improved"
fi

# 3. Check JSON-LD
echo -e "\n3. Structured Data:"
if grep -q "application/ld+json" public/index.html; then
    SCHEMA_COUNT=$(grep -c "@type" public/index.html || true)
    echo "   ✅ JSON-LD found ($SCHEMA_COUNT schemas)"
else
    echo "   ❌ JSON-LD missing"
    exit 1
fi

# 4. Check navigation
echo -e "\n4. Navigation:"
if grep -q 'href="/archive/"' public/index.html; then
    echo "   ✅ Archive link present"
else
    echo "   ⚠️ Archive link missing"
fi

# 5. Check OG image
echo -e "\n5. Open Graph:"
if grep -q 'og:image.*og-image.png' public/index.html; then
    echo "   ✅ Static OG image configured"
else
    echo "   ⚠️ Using dynamic OG image"
fi

# 6. Check canonical
echo -e "\n6. Canonical URL:"
if grep -q 'rel="canonical" href="https://dailytrending.info/"' public/index.html; then
    echo "   ✅ Canonical URL correct"
else
    echo "   ❌ Canonical URL issue"
fi

echo -e "\n✅ SEO validation complete!"
EOF

chmod +x scripts/validate_seo.sh
./scripts/validate_seo.sh
```

### Manual Tests

1. **Google Rich Results Test**
   - URL: https://search.google.com/test/rich-results
   - Test: `https://dailytrending.info/`
   - Verify: ItemList, WebSite, FAQPage appear

2. **Schema.org Validator**
   - URL: https://validator.schema.org/
   - Paste `public/index.html` content
   - Verify: No errors

3. **Lighthouse SEO Audit**
   ```bash
   npx lighthouse https://dailytrending.info/ --only-categories=seo --view
   ```
   - Target: 95+ score

4. **Social Media Debuggers**
   - Twitter: https://cards-dev.twitter.com/validator
   - Facebook: https://developers.facebook.com/tools/debug/
   - LinkedIn: https://www.linkedin.com/post-inspector/

---

## Success Metrics

### Before Implementation

| Metric | Current State |
|--------|---------------|
| **Homepage Title** | "DailyTrending.info - Opus 4.5 is not..." |
| **JSON-LD Schemas** | 0 (empty) |
| **Sitemap URLs** | ~7 (homepage + topics) |
| **Navigation Links** | 5 (Today, Tech, World, Social, RSS) |
| **Discoverable Articles** | 0 (not linked) |
| **OG Image Consistency** | Changes daily |
| **Lighthouse SEO Score** | Unknown (baseline) |

### After Implementation

| Metric | Target State |
|--------|--------------|
| **Homepage Title** | "DailyTrending.info \| AI-Curated Tech & World News Aggregator" |
| **JSON-LD Schemas** | 3+ (WebSite, CollectionPage, FAQPage) |
| **Sitemap URLs** | 50+ (homepage + topics + 30 archive + articles) |
| **Navigation Links** | 7+ (Today, Tech, World, Social, Analysis, Archive, RSS) |
| **Discoverable Articles** | Featured on homepage + articles index |
| **OG Image Consistency** | Static branded image (1200×630) |
| **Lighthouse SEO Score** | 95+ |

### SEO KPIs (Track over 30 days)

- Google Search Console impressions (+50% target)
- Average position for "daily trending news" (<20 target)
- Click-through rate (CTR) on SERP (+25% target)
- Indexed pages count (should include all archive pages)
- Time on site (expect +15% from better content discovery)

---

## Maintenance & Monitoring

### Weekly Tasks

```bash
# Check for SEO regressions
./scripts/validate_seo.sh

# Verify sitemap is updating
curl https://dailytrending.info/sitemap.xml | grep -c "<url>"

# Check JSON-LD validity
curl https://dailytrending.info/ | grep -A 100 "application/ld+json"
```

### Monthly Review

1. **Google Search Console**
   - Review coverage report (indexed vs. excluded pages)
   - Check for crawl errors
   - Monitor Core Web Vitals

2. **Schema Validation**
   - Re-run Rich Results Test
   - Verify no new warnings/errors

3. **Content Audit**
   - Verify archive pages are crawlable
   - Check that editorial articles are being indexed
   - Review organic search traffic trends

### Automated Monitoring

Add to GitHub Actions workflow:

```yaml
# In .github/workflows/daily-regenerate.yml
- name: SEO Validation
  run: |
    ./scripts/validate_seo.sh
    if [ $? -ne 0 ]; then
      echo "⚠️ SEO validation failed - check logs"
      exit 1
    fi
```

---

## Appendix A: File Change Summary

| File | Lines Modified | Changes |
|------|----------------|---------|
| `scripts/build_website.py` | 420-430, 534, 582 | Title fix, meta description, JSON-LD |
| `scripts/shared_components.py` | Header/footer functions | Navigation links |
| `scripts/sitemap_generator.py` | generate_sitemap() | Archive + article URLs |
| `templates/index.html` | ~135 | Editorial section |
| `scripts/archive_manager.py` | 70 | Breadcrumb schema |
| `scripts/generate_og_image.py` | New file | OG image generation |
| `scripts/main.py` | Pipeline step | OG image integration |
| `templates/index.html` | 101 | Alt text improvement |

**Total Estimated Lines Changed:** ~200 lines
**New Files Created:** 1 (generate_og_image.py)
**Estimated Implementation Time:** 12-16 hours

---

## Appendix B: JSON-LD Schema Examples

### Complete Homepage Schema (Expected Output)

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "name": "DailyTrending.info",
      "alternateName": "Daily Trending",
      "url": "https://dailytrending.info/",
      "description": "AI-curated technology and world news aggregator, updated daily",
      "potentialAction": {
        "@type": "SearchAction",
        "target": "https://dailytrending.info/?q={search_term_string}",
        "query-input": "required name=search_term_string"
      },
      "sameAs": ["https://twitter.com/bradshannon"],
      "speakable": {
        "@type": "SpeakableSpecification",
        "cssSelector": [".hero-content h1", ".hero-subtitle", ".story-title"]
      }
    },
    {
      "@type": "CollectionPage",
      "name": "Daily Trending Topics - January 08, 2026",
      "description": "Real-time dashboard of trending tech, science, and world news stories...",
      "url": "https://dailytrending.info/",
      "datePublished": "2026-01-08T12:00:00Z",
      "mainEntity": {
        "@type": "ItemList",
        "numberOfItems": 9,
        "itemListElement": [
          {
            "@type": "ListItem",
            "position": 1,
            "item": {
              "@type": "NewsArticle",
              "headline": "SpaceX Starship Test Flight Successful",
              "url": "https://example.com/spacex-starship",
              "datePublished": "2026-01-08T10:30:00Z",
              "image": "https://example.com/image.jpg",
              "publisher": {
                "@type": "Organization",
                "name": "Hacker News"
              }
            }
          }
        ]
      }
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "How often is DailyTrending.info updated?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "DailyTrending.info regenerates automatically every day at 6 AM EST..."
          }
        }
      ]
    }
  ]
}
```

---

## Appendix C: Quick Reference Commands

```bash
# Full regeneration with validation
cd scripts && python main.py && cd .. && ./scripts/validate_seo.sh

# Test specific pages
python -m http.server 8000 --directory public
# Visit: http://localhost:8000/archive/2026-01-08/

# Check JSON-LD syntax
cat public/index.html | grep -A 200 "application/ld+json" | python -m json.tool

# Validate sitemap
curl https://dailytrending.info/sitemap.xml | xmllint --format -

# Check Google indexing status
curl "https://www.google.com/search?q=site:dailytrending.info"

# Submit to search engines
curl -X POST "https://www.google.com/ping?sitemap=https://dailytrending.info/sitemap.xml"
```

---

## Sign-Off

**Plan Status:** Ready for Implementation
**Risk Level:** Low (mostly additive changes, no breaking modifications)
**Rollback Strategy:** Git revert on any issues
**Testing Coverage:** Automated validation + manual checks
**Expected Impact:** +50% search visibility within 30 days

**Recommended Sequence:**
1. Implement P0 fixes (Days 1-4)
2. Deploy and validate
3. Monitor for 1 week
4. Implement P1 improvements (Days 5-8)
5. Final validation and monitoring

---

*Last Updated: January 8, 2026*
*Version: 1.0*
*Maintainer: Claude Code*
