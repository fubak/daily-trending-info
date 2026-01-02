#!/usr/bin/env python3
"""
Editorial Article Generator for DailyTrending.info

Generates AI-written editorial articles that synthesize top stories into
cohesive narratives. Articles are permanently retained (not archived).

URL Structure: /articles/YYYY/MM/DD/slug/index.html
"""

import json
import logging
import os
import re
import time
import requests
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("pipeline")


@dataclass
class EditorialArticle:
    """Represents a generated editorial article."""
    title: str
    slug: str
    date: str  # YYYY-MM-DD
    summary: str  # 1-2 sentence summary for meta description
    content: str  # Full HTML content
    word_count: int
    top_stories: List[str]  # Titles of stories synthesized
    keywords: List[str]
    mood: str  # Overall mood/tone of the article
    url: str  # Full URL path


@dataclass
class WhyThisMatters:
    """Context explanation for a top story."""
    story_title: str
    story_url: str
    explanation: str  # 2-3 sentence explanation
    impact_areas: List[str]  # e.g., ["technology", "privacy", "business"]


class EditorialGenerator:
    """
    Generates editorial articles and 'Why This Matters' context.

    Uses Groq API for AI-powered content generation with rich context.
    """

    # Rate limiting: minimum seconds between API calls to stay under 30 req/min
    MIN_CALL_INTERVAL = 3.0

    def __init__(self, groq_key: Optional[str] = None, openrouter_key: Optional[str] = None, public_dir: Optional[Path] = None):
        self.groq_key = groq_key or os.getenv('GROQ_API_KEY')
        self.openrouter_key = openrouter_key or os.getenv('OPENROUTER_API_KEY')
        self.public_dir = public_dir or Path(__file__).parent.parent / "public"
        self.articles_dir = self.public_dir / "articles"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DailyTrending.info/1.0 (Editorial Generator)'
        })
        self._last_call_time = 0.0  # Track last API call for rate limiting

    def generate_editorial(
        self,
        trends: List[Dict],
        keywords: List[str],
        design: Optional[Dict] = None
    ) -> Optional[EditorialArticle]:
        """
        Generate a daily editorial article synthesizing top stories.

        Args:
            trends: List of trend dictionaries
            keywords: Extracted keywords
            design: Current design spec for styling

        Returns:
            EditorialArticle if successful, None otherwise
        """
        if not self.groq_key:
            logger.warning("No Groq API key - skipping editorial generation")
            return None

        if len(trends) < 3:
            logger.warning("Insufficient trends for editorial")
            return None

        # Build rich context from top stories
        top_stories = trends[:8]
        context = self._build_editorial_context(top_stories, keywords)

        # Extract a central question from the top stories
        central_themes = self._identify_central_themes(top_stories, keywords)

        prompt = f"""## ROLE
You're a senior editorial writer for DailyTrending.info, known for combining factual rigor with a whimsical, memorable voice. Your writing is:
- Evidence-based but never dry
- Structured but not formulaic
- Insightful but accessible
- Memorable without being gimmicky

## TASK
Write a daily editorial article (600-900 words) that synthesizes today's top trending stories into a cohesive narrative, analyzes patterns and connections, and provides actionable insights.

{context}

## CENTRAL QUESTION/THESIS
Based on these stories, address this central theme: {central_themes['question']}

Your thesis should take a clear stance on this question and defend it throughout the piece.

## SCOPE & BOUNDARIES
- Focus on the intersection of these stories and what they reveal about broader trends
- Do NOT simply summarize each story - synthesize and analyze
- Stay grounded in the evidence from today's stories
- Make specific, falsifiable claims rather than vague assertions
- Don't claim you don't know things, just use the context provided

## EVIDENCE REQUIREMENTS
- Reference specific stories from the provided list to support claims
- For each major claim, cite which story/stories provide evidence
- Distinguish between direct evidence, reasonable inference, and speculation
- If making predictions, state the confidence level and reasoning

## REQUIRED STRUCTURE (use these as <h2> sections):

1. **The Lead** (1 paragraph)
   - Hook readers with a surprising connection or insight
   - State your central thesis clearly
   - Preview what's at stake

2. **What People Think** (1-2 paragraphs)
   - Steelman the conventional wisdom or surface narrative
   - Show you understand the obvious interpretation
   - Use phrases like "The common view is..." or "Most coverage focuses on..."

3. **What's Actually Happening** (2-3 paragraphs)
   - Present your contrarian or deeper analysis
   - Connect dots between multiple stories
   - Use specific evidence from the stories provided
   - This is your main argument section

4. **The Hidden Tradeoffs** (1-2 paragraphs)
   - What costs or downsides aren't being discussed?
   - Who wins and who loses from current trends?
   - What are we optimizing for and what are we sacrificing?

5. **The Best Counterarguments** (1 paragraph)
   - Steelman the strongest objection to your thesis
   - Respond to it honestly - don't strawman
   - Acknowledge where your analysis might be wrong

6. **What This Means Next** (1-2 paragraphs)
   - Concrete predictions with timeframes
   - What to watch for that would confirm or refute your thesis
   - Second-order effects most people are missing

7. **Practical Framework** (1 paragraph)
   - How should readers think about or act on this?
   - A memorable mental model, heuristic, or framework
   - Make it specific and actionable

8. **Conclusion** (1 paragraph)
   - Circle back to your hook
   - Restate thesis in light of your argument
   - Leave readers with something memorable

## STYLE RULES
- Use active voice and strong verbs
- Vary sentence length for rhythm
- Include one memorable metaphor or analogy
- Write for smart readers who haven't followed every story
- Avoid jargon unless you define it

## RIGOR CHECKLIST (ensure all are true):
- [ ] Every major claim is supported by evidence from the stories
- [ ] The thesis is clear and could be disagreed with
- [ ] Counterarguments are addressed honestly
- [ ] Predictions are specific enough to be falsifiable
- [ ] The piece adds insight beyond summarizing headlines

Respond with ONLY a valid JSON object:
{{
  "title": "Compelling headline (6-12 words, intriguing but not clickbait)",
  "slug": "url-friendly-slug-with-dashes",
  "summary": "1-2 sentence meta description for SEO that captures the thesis",
  "mood": "One word describing the overall tone (e.g., hopeful, concerned, transformative, skeptical, optimistic)",
  "content": "Full article content with HTML formatting. Use <h2> for section headers (The Lead, What People Think, etc.), <p> for paragraphs, <strong> for emphasis, <blockquote> for key insights.",
  "key_themes": ["theme1", "theme2", "theme3"],
  "predictions": ["specific prediction 1", "specific prediction 2"]
}}"""

        try:
            response = self._call_groq(prompt, max_tokens=2000)  # Increased for longer format
            data = self._parse_json_response(response)

            if not data or not data.get('content'):
                logger.warning("Failed to parse editorial response")
                return None

            # Build article object
            today = datetime.now().strftime("%Y-%m-%d")
            slug = self._sanitize_slug(data.get('slug', 'daily-editorial'))
            content = data.get('content', '')

            article = EditorialArticle(
                title=data.get('title', 'Today\'s Analysis'),
                slug=slug,
                date=today,
                summary=data.get('summary', ''),
                content=content,
                word_count=len(content.split()),
                top_stories=[t.get('title', '') for t in top_stories[:5]],
                keywords=data.get('key_themes', keywords[:5]),
                mood=data.get('mood', 'informative'),
                url=f"/articles/{today.replace('-', '/')}/{slug}/"
            )

            # Save the article
            self._save_article(article, design)

            logger.info(f"Generated editorial: {article.title} ({article.word_count} words)")
            return article

        except Exception as e:
            logger.error(f"Editorial generation failed: {e}")
            return None

    def generate_why_this_matters(
        self,
        trends: List[Dict],
        count: int = 3
    ) -> List[WhyThisMatters]:
        """
        Generate 'Why This Matters' context for top stories (batched into single API call).

        Args:
            trends: List of trend dictionaries
            count: Number of stories to generate context for

        Returns:
            List of WhyThisMatters objects
        """
        if not self.groq_key:
            return []

        top_stories = trends[:count]
        if not top_stories:
            return []

        # Build batched prompt for all stories
        stories_data = []
        for i, story in enumerate(top_stories):
            title = story.get('title', '') or ''
            desc = (story.get('description') or '')[:200]
            stories_data.append(f"{i+1}. TITLE: {title}\n   CONTEXT: {desc}")

        stories_text = "\n\n".join(stories_data)

        prompt = f"""Analyze these news stories and explain why each matters to readers.

STORIES:
{stories_text}

For EACH story, write a brief "Why This Matters" explanation (2-3 sentences) that:
1. Explains the broader significance of this story
2. Connects it to readers' lives or larger trends
3. Is accessible to a general audience

Respond with ONLY a valid JSON object:
{{
  "stories": [
    {{
      "story_number": 1,
      "explanation": "2-3 sentence explanation of why story 1 matters",
      "impact_areas": ["area1", "area2"]
    }},
    {{
      "story_number": 2,
      "explanation": "2-3 sentence explanation of why story 2 matters",
      "impact_areas": ["area1", "area2"]
    }},
    {{
      "story_number": 3,
      "explanation": "2-3 sentence explanation of why story 3 matters",
      "impact_areas": ["area1", "area2"]
    }}
  ]
}}"""

        try:
            response = self._call_groq(prompt, max_tokens=600)
            data = self._parse_json_response(response)

            results = []
            if data and data.get('stories'):
                for i, item in enumerate(data['stories']):
                    if i < len(top_stories) and item.get('explanation'):
                        story = top_stories[i]
                        results.append(WhyThisMatters(
                            story_title=story.get('title', '') or '',
                            story_url=story.get('url', '') or '',
                            explanation=item.get('explanation', ''),
                            impact_areas=item.get('impact_areas', [])
                        ))
            return results
        except Exception as e:
            logger.warning(f"Why This Matters batch generation failed: {e}")
            return []

    def _build_editorial_context(self, stories: List[Dict], keywords: List[str]) -> str:
        """Build rich context for editorial generation."""
        story_lines = []
        for i, s in enumerate(stories):
            title = s.get('title') or ''
            source = (s.get('source') or 'unknown').replace('_', ' ').title()
            desc = (s.get('description') or '')[:200]
            story_lines.append(f"{i+1}. [{source}] {title}")
            if desc:
                story_lines.append(f"   Summary: {desc}")

        # Categorize stories
        categories = {}
        for s in stories:
            src = s.get('source', 'other')
            if src in ['hackernews', 'lobsters', 'tech_rss', 'github_trending']:
                cat = 'Technology'
            elif src in ['news_rss', 'wikipedia']:
                cat = 'World News'
            elif src == 'reddit':
                cat = 'Social/Viral'
            else:
                cat = 'General'
            categories[cat] = categories.get(cat, 0) + 1

        cat_summary = ", ".join(f"{v} {k}" for k, v in categories.items())

        return f"""TODAY'S TOP STORIES ({len(stories)} stories, {cat_summary}):
{chr(10).join(story_lines)}

TRENDING KEYWORDS: {', '.join(keywords[:20])}
DATE: {datetime.now().strftime('%B %d, %Y')}"""

    def _identify_central_themes(self, stories: List[Dict], keywords: List[str]) -> Dict:
        """
        Identify central themes and generate a thesis question from stories.

        Uses pattern matching and keyword analysis to find connective threads.
        """
        # Categorize stories by domain
        tech_count = 0
        social_count = 0
        business_count = 0
        science_count = 0

        for story in stories:
            source = (story.get('source') or '').lower()
            title = (story.get('title') or '').lower()

            if source in ['hackernews', 'lobsters', 'github_trending'] or any(
                kw in title for kw in ['ai', 'tech', 'software', 'code', 'app', 'google', 'apple', 'microsoft']
            ):
                tech_count += 1
            if source == 'reddit' or 'viral' in title or 'trend' in title:
                social_count += 1
            if any(kw in title for kw in ['market', 'stock', 'company', 'ceo', 'billion', 'deal', 'startup']):
                business_count += 1
            if any(kw in title for kw in ['study', 'research', 'science', 'space', 'health', 'climate']):
                science_count += 1

        # Detect recurring keywords
        keyword_freq = {}
        for kw in keywords[:30]:
            kw_lower = kw.lower()
            for story in stories:
                if kw_lower in (story.get('title') or '').lower() or kw_lower in (story.get('description') or '').lower():
                    keyword_freq[kw] = keyword_freq.get(kw, 0) + 1

        # Find most connected keywords (appear in multiple stories)
        connected_keywords = sorted(
            [(k, v) for k, v in keyword_freq.items() if v >= 2],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Generate central question based on dominant theme
        if tech_count >= 4:
            if any('ai' in kw.lower() for kw, _ in connected_keywords):
                question = "How is AI reshaping the technology landscape, and who stands to win or lose?"
            else:
                question = "What do today's tech stories reveal about where innovation is heading?"
        elif business_count >= 3:
            question = "What market forces are driving today's biggest business stories, and what do they signal?"
        elif science_count >= 3:
            question = "How might today's scientific developments change our understanding or daily lives?"
        elif social_count >= 3:
            question = "What are today's viral moments telling us about culture and public attention?"
        elif connected_keywords:
            top_keyword = connected_keywords[0][0]
            question = f"What does the prominence of '{top_keyword}' in today's news reveal about current priorities?"
        else:
            question = "What common thread connects today's seemingly disparate top stories?"

        return {
            'question': question,
            'dominant_category': max(
                [('technology', tech_count), ('business', business_count),
                 ('science', science_count), ('social', social_count)],
                key=lambda x: x[1]
            )[0],
            'connected_keywords': [kw for kw, _ in connected_keywords]
        }

    def _save_article(self, article: EditorialArticle, design: Optional[Dict] = None):
        """Save editorial article to permanent storage."""
        # Create directory structure: /articles/YYYY/MM/DD/slug/
        date_parts = article.date.split('-')
        article_dir = self.articles_dir / date_parts[0] / date_parts[1] / date_parts[2] / article.slug
        article_dir.mkdir(parents=True, exist_ok=True)

        # Get design colors (fallback to defaults)
        primary_color = design.get('primary_color', '#667eea') if design else '#667eea'
        accent_color = design.get('accent_color', '#4facfe') if design else '#4facfe'
        bg_color = design.get('background_color', '#0f0f23') if design else '#0f0f23'
        text_color = design.get('text_color', '#ffffff') if design else '#ffffff'

        # Generate HTML
        html = self._generate_article_html(article, primary_color, accent_color, bg_color, text_color)

        # Save index.html
        (article_dir / "index.html").write_text(html, encoding='utf-8')

        # Save metadata JSON for sitemap/index generation
        metadata = asdict(article)
        (article_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding='utf-8'
        )

        logger.info(f"Saved article to {article_dir}")

    def _generate_article_html(
        self,
        article: EditorialArticle,
        primary_color: str,
        accent_color: str,
        bg_color: str,
        text_color: str
    ) -> str:
        """Generate full HTML page for an editorial article."""
        date_formatted = datetime.strptime(article.date, "%Y-%m-%d").strftime("%B %d, %Y")

        # Escape for HTML attributes
        title_escaped = article.title.replace('"', '&quot;')
        summary_escaped = article.summary.replace('"', '&quot;')

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article.title} | DailyTrending.info</title>
    <meta name="description" content="{summary_escaped}">
    <meta name="keywords" content="{', '.join(article.keywords)}">
    <link rel="canonical" href="https://dailytrending.info{article.url}">

    <!-- Open Graph -->
    <meta property="og:title" content="{title_escaped}">
    <meta property="og:description" content="{summary_escaped}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://dailytrending.info{article.url}">
    <meta property="article:published_time" content="{article.date}T06:00:00Z">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title_escaped}">
    <meta name="twitter:description" content="{summary_escaped}">

    <!-- JSON-LD Structured Data -->
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{title_escaped}",
        "description": "{summary_escaped}",
        "datePublished": "{article.date}T06:00:00Z",
        "dateModified": "{article.date}T06:00:00Z",
        "author": {{
            "@type": "Organization",
            "name": "DailyTrending.info"
        }},
        "publisher": {{
            "@type": "Organization",
            "name": "DailyTrending.info",
            "url": "https://dailytrending.info"
        }},
        "mainEntityOfPage": {{
            "@type": "WebPage",
            "@id": "https://dailytrending.info{article.url}"
        }},
        "wordCount": {article.word_count},
        "keywords": {json.dumps(article.keywords)}
    }}
    </script>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">

    <style>
        :root {{
            --primary: {primary_color};
            --accent: {accent_color};
            --bg: {bg_color};
            --text: {text_color};
            --text-muted: rgba(255,255,255,0.7);
            --border: rgba(255,255,255,0.1);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            min-height: 100vh;
        }}

        .container {{
            max-width: 720px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}

        .breadcrumb {{
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-bottom: 2rem;
        }}

        .breadcrumb a {{
            color: var(--accent);
            text-decoration: none;
        }}

        .breadcrumb a:hover {{
            text-decoration: underline;
        }}

        .article-header {{
            margin-bottom: 2.5rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
        }}

        .article-meta {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .mood-badge {{
            background: var(--primary);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        h1 {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: clamp(2rem, 5vw, 3rem);
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, var(--text), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .article-summary {{
            font-size: 1.25rem;
            color: var(--text-muted);
            font-weight: 400;
        }}

        .article-content {{
            font-size: 1.125rem;
        }}

        .article-content p {{
            margin-bottom: 1.5rem;
        }}

        .article-content h2 {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 1.5rem;
            margin: 2.5rem 0 1rem;
            color: var(--accent);
        }}

        .article-content blockquote {{
            border-left: 4px solid var(--primary);
            padding-left: 1.5rem;
            margin: 2rem 0;
            font-style: italic;
            color: var(--text-muted);
        }}

        .article-content strong {{
            color: var(--accent);
            font-weight: 600;
        }}

        .article-footer {{
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
        }}

        .sources-section {{
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}

        .sources-section h3 {{
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 1rem;
        }}

        .sources-section ul {{
            list-style: none;
        }}

        .sources-section li {{
            padding: 0.5rem 0;
            font-size: 0.9rem;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border);
        }}

        .sources-section li:last-child {{
            border-bottom: none;
        }}

        .back-link {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
            transition: opacity 0.2s;
        }}

        .back-link:hover {{
            opacity: 0.8;
        }}

        .keywords {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }}

        .keyword {{
            background: rgba(255,255,255,0.05);
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        @media (max-width: 640px) {{
            .container {{
                padding: 1rem;
            }}

            .article-content {{
                font-size: 1rem;
            }}
        }}

        @media (prefers-color-scheme: light) {{
            :root {{
                --bg: #ffffff;
                --text: #1a1a2e;
                --text-muted: rgba(0,0,0,0.6);
                --border: rgba(0,0,0,0.1);
            }}

            h1 {{
                background: linear-gradient(135deg, var(--text), var(--primary));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
        }}
    </style>
</head>
<body>
    <article class="container">
        <nav class="breadcrumb">
            <a href="/">Home</a> / <a href="/articles/">Articles</a> / {date_formatted}
        </nav>

        <header class="article-header">
            <div class="article-meta">
                <time datetime="{article.date}">{date_formatted}</time>
                <span class="mood-badge">{article.mood}</span>
                <span>{article.word_count} words</span>
            </div>
            <h1>{article.title}</h1>
            <p class="article-summary">{article.summary}</p>
        </header>

        <div class="article-content">
            {article.content}
        </div>

        <footer class="article-footer">
            <div class="sources-section">
                <h3>Stories Referenced</h3>
                <ul>
                    {''.join(f'<li>{story}</li>' for story in article.top_stories)}
                </ul>
            </div>

            <div class="keywords">
                {''.join(f'<span class="keyword">{kw}</span>' for kw in article.keywords)}
            </div>

            <p style="margin-top: 2rem;">
                <a href="/" class="back-link">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M19 12H5M12 19l-7-7 7-7"/>
                    </svg>
                    Back to Today's Trends
                </a>
            </p>
        </footer>
    </article>
</body>
</html>'''

    def _call_groq(self, prompt: str, max_tokens: int = 800, max_retries: int = 5) -> Optional[str]:
        """Call Groq API for content generation with proactive rate limiting and retry logic."""
        if not self.groq_key:
            # No Groq key, try OpenRouter directly
            return self._call_openrouter(prompt, max_tokens)

        # Proactive rate limiting: wait if we're calling too fast
        elapsed = time.time() - self._last_call_time
        if elapsed < self.MIN_CALL_INTERVAL:
            sleep_time = self.MIN_CALL_INTERVAL - elapsed
            logger.info(f"Rate limiting: waiting {sleep_time:.1f}s before API call")
            time.sleep(sleep_time)

        for attempt in range(max_retries):
            try:
                self._last_call_time = time.time()
                response = self.session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.7
                    },
                    timeout=60
                )
                response.raise_for_status()
                return response.json().get('choices', [{}])[0].get('message', {}).get('content')
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait_time = (2 ** attempt) * 10  # 10, 20, 40, 80, 160 seconds
                    logger.warning(f"Groq rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                logger.error(f"Groq API error: {e}")
                return self._call_openrouter(prompt, max_tokens)
            except Exception as e:
                logger.error(f"Groq API error: {e}")
                return self._call_openrouter(prompt, max_tokens)

        logger.warning("Groq API: Max retries exceeded, falling back to OpenRouter")
        return self._call_openrouter(prompt, max_tokens)

    def _call_openrouter(self, prompt: str, max_tokens: int = 800) -> Optional[str]:
        """Call OpenRouter API with free models as fallback."""
        if not self.openrouter_key:
            logger.warning("No OpenRouter API key available for fallback")
            return None

        # Free models to try in order of preference
        free_models = [
            "google/gemini-2.0-flash-exp:free",
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "mistralai/devstral-2512:free",
        ]

        for model in free_models:
            try:
                logger.info(f"Trying OpenRouter model: {model}")
                response = self.session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://dailytrending.info",
                        "X-Title": "DailyTrending.info"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.7
                    },
                    timeout=60
                )
                response.raise_for_status()
                result = response.json().get('choices', [{}])[0].get('message', {}).get('content')
                if result:
                    logger.info(f"OpenRouter success with {model}")
                    return result
            except Exception as e:
                logger.warning(f"OpenRouter {model} failed: {e}")
                continue

        logger.error("All OpenRouter models failed")
        return None

    def _parse_json_response(self, response: Optional[str]) -> Optional[Dict]:
        """Parse JSON from LLM response."""
        if not response:
            return None

        try:
            # Try to find JSON in response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"JSON parse error: {e}")

        return None

    def _sanitize_slug(self, slug: str) -> str:
        """Sanitize slug for URL usage."""
        # Convert to lowercase, replace spaces with dashes
        slug = slug.lower().strip()
        slug = re.sub(r'[^a-z0-9\-]', '-', slug)
        slug = re.sub(r'-+', '-', slug)  # Remove duplicate dashes
        slug = slug.strip('-')
        return slug[:60] or 'daily-editorial'  # Max 60 chars

    def get_all_articles(self) -> List[Dict]:
        """Get metadata for all saved articles (for sitemap/index)."""
        articles = []

        if not self.articles_dir.exists():
            return articles

        # Walk through year/month/day/slug directories
        for metadata_file in self.articles_dir.rglob("metadata.json"):
            try:
                with open(metadata_file) as f:
                    articles.append(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load {metadata_file}: {e}")

        # Sort by date descending
        articles.sort(key=lambda x: x.get('date', ''), reverse=True)
        return articles

    def generate_articles_index(self, design: Optional[Dict] = None) -> str:
        """Generate an index page listing all articles."""
        articles = self.get_all_articles()

        if not articles:
            return ""

        # Get design colors
        primary_color = design.get('primary_color', '#667eea') if design else '#667eea'
        accent_color = design.get('accent_color', '#4facfe') if design else '#4facfe'
        bg_color = design.get('background_color', '#0f0f23') if design else '#0f0f23'

        # Build article cards
        article_cards = []
        for article in articles[:50]:  # Limit to 50 most recent
            date_formatted = datetime.strptime(article['date'], "%Y-%m-%d").strftime("%B %d, %Y")
            article_cards.append(f'''
            <article class="article-card">
                <time datetime="{article['date']}">{date_formatted}</time>
                <h2><a href="{article['url']}">{article['title']}</a></h2>
                <p>{article.get('summary', '')}</p>
                <div class="article-meta">
                    <span class="mood-badge">{article.get('mood', 'informative')}</span>
                    <span>{article.get('word_count', 0)} words</span>
                </div>
            </article>
            ''')

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Editorial Articles | DailyTrending.info</title>
    <meta name="description" content="Daily editorial articles analyzing trending news and technology stories.">
    <link rel="canonical" href="https://dailytrending.info/articles/">

    <meta property="og:title" content="Editorial Articles | DailyTrending.info">
    <meta property="og:description" content="Daily editorial articles analyzing trending news and technology stories.">
    <meta property="og:type" content="website">

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">

    <style>
        :root {{
            --primary: {primary_color};
            --accent: {accent_color};
            --bg: {bg_color};
            --text: #ffffff;
            --text-muted: rgba(255,255,255,0.7);
            --border: rgba(255,255,255,0.1);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}

        .page-header {{
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
        }}

        .page-header h1 {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: clamp(2rem, 5vw, 3rem);
            margin-bottom: 0.5rem;
        }}

        .page-header p {{
            color: var(--text-muted);
        }}

        .articles-grid {{
            display: grid;
            gap: 2rem;
        }}

        .article-card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            transition: transform 0.2s, border-color 0.2s;
        }}

        .article-card:hover {{
            transform: translateY(-2px);
            border-color: var(--primary);
        }}

        .article-card time {{
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .article-card h2 {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 1.5rem;
            margin: 0.5rem 0;
        }}

        .article-card h2 a {{
            color: var(--text);
            text-decoration: none;
        }}

        .article-card h2 a:hover {{
            color: var(--accent);
        }}

        .article-card p {{
            color: var(--text-muted);
            margin-bottom: 1rem;
        }}

        .article-meta {{
            display: flex;
            gap: 1rem;
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .mood-badge {{
            background: var(--primary);
            color: white;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 500;
            text-transform: uppercase;
        }}

        .back-link {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--accent);
            text-decoration: none;
            margin-bottom: 2rem;
        }}

        .back-link:hover {{
            opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back to Today's Trends
        </a>

        <header class="page-header">
            <h1>Editorial Articles</h1>
            <p>Daily analysis and insights from DailyTrending.info</p>
        </header>

        <div class="articles-grid">
            {''.join(article_cards)}
        </div>
    </div>
</body>
</html>'''

        # Save index
        self.articles_dir.mkdir(parents=True, exist_ok=True)
        (self.articles_dir / "index.html").write_text(html, encoding='utf-8')

        return html
