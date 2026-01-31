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

try:
    from rate_limiter import (
        get_rate_limiter,
        check_before_call,
        mark_provider_exhausted,
        is_provider_exhausted,
    )
    from shared_components import (
        build_header,
        build_footer,
        get_header_styles,
        get_footer_styles,
        get_theme_script,
    )
except ImportError:
    from scripts.rate_limiter import (
        get_rate_limiter,
        check_before_call,
        mark_provider_exhausted,
        is_provider_exhausted,
    )
    from scripts.shared_components import (
        build_header,
        build_footer,
        get_header_styles,
        get_footer_styles,
        get_theme_script,
    )

logger = logging.getLogger("pipeline")

# JSON Schemas for Gemini Structured Outputs
EDITORIAL_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Compelling headline (6-12 words)"},
        "slug": {"type": "string", "description": "URL-friendly slug with dashes"},
        "summary": {
            "type": "string",
            "description": "1-2 sentence meta description for SEO",
        },
        "mood": {
            "type": "string",
            "description": "One word describing tone (hopeful, concerned, transformative, etc.)",
        },
        "content": {
            "type": "string",
            "description": "Full article content with HTML formatting",
        },
        "key_themes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 key themes",
        },
        "predictions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-3 specific predictions",
        },
    },
    "required": ["title", "slug", "summary", "mood", "content", "key_themes"],
}

STORY_SUMMARIES_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": "2-3 sentence explanation of why this matters",
                    },
                    "impact_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Areas of impact",
                    },
                },
                "required": ["explanation"],
            },
        }
    },
    "required": ["stories"],
}


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
    MAX_RETRY_WAIT = 10  # Cap retry waits to prevent long delays

    def __init__(
        self,
        groq_key: Optional[str] = None,
        openrouter_key: Optional[str] = None,
        google_key: Optional[str] = None,
        public_dir: Optional[Path] = None,
    ):
        self.groq_key = groq_key or os.getenv("GROQ_API_KEY")
        self.openrouter_key = openrouter_key or os.getenv("OPENROUTER_API_KEY")
        self.google_key = google_key or os.getenv("GOOGLE_AI_API_KEY")
        self.public_dir = public_dir or Path(__file__).parent.parent / "public"
        self.articles_dir = self.public_dir / "articles"
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "CMMCWatch/1.0 (Editorial Generator)"}
        )
        self._last_call_time = 0.0  # Track last API call for rate limiting

    def _get_design_tokens(self, design: Optional[Dict]) -> Dict:
        """Normalize design tokens for editorial templates."""
        tokens = {
            "primary_color": "#667eea",
            "accent_color": "#4facfe",
            "bg_color": "#0f0f23",
            "text_color": "#ffffff",
            "muted_color": "#a1a1aa",
            "border_color": "#27272a",
            "card_bg": "rgba(255,255,255,0.03)",
            "font_primary": "Playfair Display",
            "font_secondary": "Inter",
            "radius": "1rem",
            "transition": "200ms",
            "base_mode": "dark-mode",
        }

        if not design:
            return tokens

        tokens.update(
            {
                "primary_color": design.get("color_accent", tokens["primary_color"]),
                "accent_color": design.get(
                    "color_accent_secondary", tokens["accent_color"]
                ),
                "bg_color": design.get("color_bg", tokens["bg_color"]),
                "text_color": design.get("color_text", tokens["text_color"]),
                "muted_color": design.get("color_muted", tokens["muted_color"]),
                "border_color": design.get("color_border", tokens["border_color"]),
                "card_bg": design.get("color_card_bg", tokens["card_bg"]),
                "font_primary": design.get("font_primary", tokens["font_primary"]),
                "font_secondary": design.get(
                    "font_secondary", tokens["font_secondary"]
                ),
                "radius": design.get("card_radius", tokens["radius"]),
                "transition": design.get("transition_speed", tokens["transition"]),
                "base_mode": (
                    "dark-mode" if design.get("is_dark_mode", True) else "light-mode"
                ),
            }
        )

        return tokens

    def generate_editorial(
        self, trends: List[Dict], keywords: List[str], design: Optional[Dict] = None
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

        # Check if an article for today already exists (prevent duplicates)
        today = datetime.now().strftime("%Y-%m-%d")
        today_parts = today.split("-")
        today_dir = self.articles_dir / today_parts[0] / today_parts[1] / today_parts[2]
        if today_dir.exists() and any(today_dir.iterdir()):
            existing_articles = list(today_dir.glob("*/metadata.json"))
            if existing_articles:
                # Load and return the existing article instead of regenerating
                try:
                    metadata_path = existing_articles[0]
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                    logger.info(
                        f"Loading existing editorial for {today}: {metadata.get('title', 'Unknown')}"
                    )
                    return EditorialArticle(
                        title=metadata.get("title", ""),
                        slug=metadata.get("slug", ""),
                        date=metadata.get("date", today),
                        summary=metadata.get("summary", ""),
                        content="",  # Content not needed for display card
                        word_count=metadata.get("word_count", 0),
                        top_stories=metadata.get("top_stories", []),
                        keywords=metadata.get("keywords", []),
                        mood=metadata.get("mood", "informative"),
                        url=metadata.get("url", ""),
                    )
                except Exception as e:
                    logger.warning(f"Failed to load existing article: {e}")
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
            # Try structured output first (guaranteed valid JSON from Gemini)
            # Use 4000 tokens to accommodate 600-900 word article + HTML + JSON wrapper
            data = self._call_google_ai_structured(
                prompt, EDITORIAL_SCHEMA, max_tokens=4000
            )

            # Fall back to regular LLM call + JSON parsing if structured output fails
            if not data:
                logger.info(
                    "Structured output unavailable, falling back to regular LLM call"
                )
                response = self._call_groq(prompt, max_tokens=4000)
                data = self._parse_json_response(response)

            if not data or not data.get("content"):
                logger.warning("Failed to parse editorial response")
                return None

            content = data.get("content", "")

            # Validate article completeness - warn if sections are missing
            is_complete, missing_sections = self._validate_article_completeness(content)
            if not is_complete:
                logger.warning(
                    f"Article may be truncated - missing sections: {', '.join(missing_sections)}"
                )
                # Check if conclusion is missing (strong indicator of cutoff)
                if "conclusion" in missing_sections:
                    logger.error(
                        "Article is likely cut off (missing conclusion). "
                        "Consider increasing max_tokens or reducing prompt complexity."
                    )

            # Build article object
            today = datetime.now().strftime("%Y-%m-%d")
            slug = self._sanitize_slug(data.get("slug", "daily-editorial"))

            article = EditorialArticle(
                title=data.get("title", "Today's Analysis"),
                slug=slug,
                date=today,
                summary=data.get("summary", ""),
                content=content,
                word_count=len(content.split()),
                top_stories=[t.get("title", "") for t in top_stories[:5]],
                keywords=data.get("key_themes", keywords[:5]),
                mood=data.get("mood", "informative"),
                url=f"/articles/{today.replace('-', '/')}/{slug}/",
            )

            # Save the article
            self._save_article(article, design)

            logger.info(
                f"Generated editorial: {article.title} ({article.word_count} words)"
            )
            return article

        except Exception as e:
            logger.error(f"Editorial generation failed: {e}")
            return None

    def generate_why_this_matters(
        self, trends: List[Dict], count: int = 3
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
            title = story.get("title", "") or ""
            desc = (story.get("description") or "")[:200]
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
            # Try structured output first (guaranteed valid JSON from Gemini)
            data = self._call_google_ai_structured(
                prompt, STORY_SUMMARIES_SCHEMA, max_tokens=600
            )

            # Fall back to regular LLM call + JSON parsing if structured output fails
            if not data:
                logger.info(
                    "Structured output unavailable for story summaries, falling back"
                )
                response = self._call_groq(prompt, max_tokens=600)
                data = self._parse_json_response(response)

            results = []
            if data and data.get("stories"):
                for i, item in enumerate(data["stories"]):
                    if i < len(top_stories) and item.get("explanation"):
                        story = top_stories[i]
                        results.append(
                            WhyThisMatters(
                                story_title=story.get("title", "") or "",
                                story_url=story.get("url", "") or "",
                                explanation=item.get("explanation", ""),
                                impact_areas=item.get("impact_areas", []),
                            )
                        )
            return results
        except Exception as e:
            logger.warning(f"Why This Matters batch generation failed: {e}")
            return []

    def _build_editorial_context(self, stories: List[Dict], keywords: List[str]) -> str:
        """Build rich context for editorial generation."""
        story_lines = []
        for i, s in enumerate(stories):
            title = s.get("title") or ""
            source = (s.get("source") or "unknown").replace("_", " ").title()
            desc = (s.get("description") or "")[:200]
            story_lines.append(f"{i+1}. [{source}] {title}")
            if desc:
                story_lines.append(f"   Summary: {desc}")

        # Categorize stories
        categories = {}
        for s in stories:
            src = s.get("source", "other")
            if src in ["hackernews", "lobsters", "tech_rss", "github_trending"]:
                cat = "Technology"
            elif src in ["news_rss", "wikipedia"]:
                cat = "World News"
            elif src == "reddit":
                cat = "Social/Viral"
            else:
                cat = "General"
            categories[cat] = categories.get(cat, 0) + 1

        cat_summary = ", ".join(f"{v} {k}" for k, v in categories.items())

        return f"""TODAY'S TOP STORIES ({len(stories)} stories, {cat_summary}):
{chr(10).join(story_lines)}

TRENDING KEYWORDS: {', '.join(keywords[:20])}
DATE: {datetime.now().strftime('%B %d, %Y')}"""

    def _identify_central_themes(
        self, stories: List[Dict], keywords: List[str]
    ) -> Dict:
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
            source = (story.get("source") or "").lower()
            title = (story.get("title") or "").lower()

            if source in ["hackernews", "lobsters", "github_trending"] or any(
                kw in title
                for kw in [
                    "ai",
                    "tech",
                    "software",
                    "code",
                    "app",
                    "google",
                    "apple",
                    "microsoft",
                ]
            ):
                tech_count += 1
            if source == "reddit" or "viral" in title or "trend" in title:
                social_count += 1
            if any(
                kw in title
                for kw in [
                    "market",
                    "stock",
                    "company",
                    "ceo",
                    "billion",
                    "deal",
                    "startup",
                ]
            ):
                business_count += 1
            if any(
                kw in title
                for kw in ["study", "research", "science", "space", "health", "climate"]
            ):
                science_count += 1

        # Detect recurring keywords
        keyword_freq = {}
        for kw in keywords[:30]:
            kw_lower = kw.lower()
            for story in stories:
                if (
                    kw_lower in (story.get("title") or "").lower()
                    or kw_lower in (story.get("description") or "").lower()
                ):
                    keyword_freq[kw] = keyword_freq.get(kw, 0) + 1

        # Find most connected keywords (appear in multiple stories)
        connected_keywords = sorted(
            [(k, v) for k, v in keyword_freq.items() if v >= 2],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        # Generate central question based on dominant theme
        if tech_count >= 4:
            if any("ai" in kw.lower() for kw, _ in connected_keywords):
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
            question = (
                "What common thread connects today's seemingly disparate top stories?"
            )

        return {
            "question": question,
            "dominant_category": max(
                [
                    ("technology", tech_count),
                    ("business", business_count),
                    ("science", science_count),
                    ("social", social_count),
                ],
                key=lambda x: x[1],
            )[0],
            "connected_keywords": [kw for kw, _ in connected_keywords],
        }

    def _save_article(self, article: EditorialArticle, design: Optional[Dict] = None):
        """Save editorial article to permanent storage."""
        # Create directory structure: /articles/YYYY/MM/DD/slug/
        date_parts = article.date.split("-")
        article_dir = (
            self.articles_dir
            / date_parts[0]
            / date_parts[1]
            / date_parts[2]
            / article.slug
        )
        article_dir.mkdir(parents=True, exist_ok=True)

        tokens = self._get_design_tokens(design)

        # Get related articles for internal linking
        related_articles = self._get_related_articles(
            article.date, article.slug, limit=3
        )

        # Generate HTML
        html = self._generate_article_html(article, tokens, related_articles)

        # Save index.html
        (article_dir / "index.html").write_text(html, encoding="utf-8")

        # Generate and save AMP version
        amp_dir = (
            self.public_dir
            / "amp"
            / "articles"
            / date_parts[0]
            / date_parts[1]
            / date_parts[2]
            / article.slug
        )
        amp_dir.mkdir(parents=True, exist_ok=True)
        amp_html = self._generate_amp_html(article, tokens)
        (amp_dir / "index.html").write_text(amp_html, encoding="utf-8")
        logger.info(f"Saved AMP version to {amp_dir}")

        # Save metadata JSON for sitemap/index generation
        metadata = asdict(article)
        (article_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        logger.info(f"Saved article to {article_dir}")

    def _generate_article_html(
        self,
        article: EditorialArticle,
        tokens: Dict,
        related_articles: Optional[List[Dict]] = None,
    ) -> str:
        """Generate full HTML page for an editorial article."""
        date_formatted = datetime.strptime(article.date, "%Y-%m-%d").strftime(
            "%B %d, %Y"
        )

        # Escape for HTML attributes
        title_escaped = article.title.replace('"', "&quot;")
        summary_escaped = article.summary.replace('"', "&quot;")

        # Build related articles HTML
        related_html = ""
        if related_articles:
            related_cards = []
            for rel in related_articles:
                rel_date = datetime.strptime(rel["date"], "%Y-%m-%d").strftime(
                    "%B %d, %Y"
                )
                rel_title = (
                    rel.get("title", "").replace("<", "&lt;").replace(">", "&gt;")
                )
                rel_summary = (rel.get("summary", "") or "")[:100]
                if len(rel.get("summary", "")) > 100:
                    rel_summary += "..."
                related_cards.append(
                    f"""
                <a href="{rel.get('url', '')}" class="related-card">
                    <time datetime="{rel['date']}">{rel_date}</time>
                    <h4>{rel_title}</h4>
                    <p>{rel_summary}</p>
                </a>"""
                )
            related_html = f"""
            <div class="related-articles">
                <h3>More Analysis</h3>
                <div class="related-grid">
                    {''.join(related_cards)}
                </div>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article.title} | DailyTrending.info</title>
    <meta name="description" content="{summary_escaped}">
    <meta name="keywords" content="{', '.join(article.keywords)}">
    <link rel="canonical" href="https://dailytrending.info{article.url}">
    <link rel="amphtml" href="https://dailytrending.info/amp{article.url}">

    <!-- Open Graph -->
    <meta property="og:title" content="{title_escaped}">
    <meta property="og:description" content="{summary_escaped}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://dailytrending.info{article.url}">
    <meta property="og:site_name" content="DailyTrending.info">
    <meta property="og:image" content="https://dailytrending.info/og-image.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="article:published_time" content="{article.date}T06:00:00Z">
    <meta property="article:author" content="https://twitter.com/bradshannon">
    <meta property="article:section" content="Analysis">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@bradshannon">
    <meta name="twitter:creator" content="@bradshannon">
    <meta name="twitter:title" content="{title_escaped}">
    <meta name="twitter:description" content="{summary_escaped}">
    <meta name="twitter:image" content="https://dailytrending.info/og-image.png">

    <!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2196222970720414"
         crossorigin="anonymous"></script>

    <!-- JSON-LD Structured Data -->
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@graph": [
            {{
                "@type": "NewsArticle",
                "@id": "https://dailytrending.info{article.url}#article",
                "headline": "{title_escaped}",
                "description": "{summary_escaped}",
                "datePublished": "{article.date}T06:00:00Z",
                "dateModified": "{article.date}T06:00:00Z",
                "author": {{
                    "@type": "Person",
                    "name": "Brad Shannon",
                    "url": "https://twitter.com/bradshannon",
                    "sameAs": ["https://twitter.com/bradshannon"]
                }},
                "publisher": {{
                    "@type": "Organization",
                    "name": "DailyTrending.info",
                    "url": "https://dailytrending.info",
                    "logo": {{
                        "@type": "ImageObject",
                        "url": "https://dailytrending.info/icons/icon-512.png"
                    }}
                }},
                "mainEntityOfPage": {{
                    "@type": "WebPage",
                    "@id": "https://dailytrending.info{article.url}"
                }},
                "wordCount": {article.word_count},
                "keywords": {json.dumps(article.keywords)},
                "articleSection": "Analysis",
                "inLanguage": "en-US"
            }},
            {{
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://dailytrending.info/"}},
                    {{"@type": "ListItem", "position": 2, "name": "Articles", "item": "https://dailytrending.info/articles/"}},
                    {{"@type": "ListItem", "position": 3, "name": "{title_escaped}"}}
                ]
            }}
        ]
    }}
    </script>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family={tokens['font_secondary'].replace(' ', '+')}:wght@400;500;600;700&family={tokens['font_primary'].replace(' ', '+')}:wght@600;700&display=swap" rel="stylesheet">

    <style>
        :root {{
            --primary: {tokens['primary_color']};
            --accent: {tokens['accent_color']};
            --bg: {tokens['bg_color']};
            --text: {tokens['text_color']};
            --text-muted: {tokens['muted_color']};
            --border: {tokens['border_color']};
            --card-bg: {tokens['card_bg']};
            --font-primary: '{tokens['font_primary']}', system-ui, sans-serif;
            --font-secondary: '{tokens['font_secondary']}', system-ui, sans-serif;
            /* Shared component color mappings */
            --color-text: var(--text);
            --color-muted: var(--text-muted);
            --color-bg: var(--bg);
            --color-accent: var(--accent);
            --color-border: var(--border);
            --color-card-bg: var(--card-bg);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: var(--font-secondary);
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            min-height: 100vh;
        }}

        body.light-mode {{
            --bg: #ffffff;
            --text: #1a1a2e;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --card-bg: #f8fafc;
            --color-text: var(--text);
            --color-muted: var(--text-muted);
            --color-bg: var(--bg);
            --color-border: var(--border);
            --color-card-bg: var(--card-bg);
        }}

        body.dark-mode {{
            --bg: #0a0a0a;
            --text: #ffffff;
            --text-muted: #a1a1aa;
            --border: #27272a;
            --card-bg: #18181b;
            --color-text: var(--text);
            --color-muted: var(--text-muted);
            --color-bg: var(--bg);
            --color-border: var(--border);
            --color-card-bg: var(--card-bg);
        }}

        /* Density settings */
        body.density-compact {{
            --section-gap: 1.5rem;
            --card-gap: 0.75rem;
            --card-padding: 0.75rem;
        }}
        body.density-comfortable {{
            --section-gap: 2.5rem;
            --card-gap: 1.25rem;
            --card-padding: 1.25rem;
        }}
        body.density-spacious {{
            --section-gap: 4rem;
            --card-gap: 2rem;
            --card-padding: 1.75rem;
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
            font-family: var(--font-primary);
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
            font-family: var(--font-primary);
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

        /* Related Articles */
        .related-articles {{
            margin-top: 2.5rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
        }}

        .related-articles h3 {{
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 1.5rem;
        }}

        .related-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}

        .related-card {{
            display: block;
            padding: 1rem;
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            text-decoration: none;
            transition: all 0.2s ease;
        }}

        .related-card:hover {{
            border-color: var(--primary);
            transform: translateY(-2px);
        }}

        .related-card time {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .related-card h4 {{
            font-size: 0.95rem;
            margin: 0.5rem 0;
            color: var(--text);
            line-height: 1.4;
        }}

        .related-card p {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin: 0;
            line-height: 1.5;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}

            h1 {{
                font-size: clamp(1.75rem, 5vw, 2.5rem);
            }}

            .article-summary {{
                font-size: 1rem;
            }}

            .article-content {{
                font-size: 1rem;
            }}

            .article-content h2 {{
                font-size: 1.25rem;
            }}

            .article-content blockquote {{
                padding-left: 1rem;
                margin: 1.5rem 0;
            }}

            .sources-section {{
                padding: 1rem;
            }}

            .related-articles {{
                grid-template-columns: 1fr;
            }}

            .breadcrumb {{
                font-size: 0.8rem;
            }}

            .article-meta {{
                flex-wrap: wrap;
            }}
        }}

        @media (max-width: 480px) {{
            .container {{
                padding: 0.75rem;
            }}

            h1 {{
                font-size: 1.5rem;
            }}

            .article-meta {{
                font-size: 0.75rem;
                gap: 0.5rem;
            }}

            .keywords {{
                gap: 0.375rem;
            }}

            .keyword {{
                font-size: 0.7rem;
                padding: 0.2rem 0.5rem;
            }}
        }}

        body.light-mode h1 {{
            background: linear-gradient(135deg, var(--text), var(--primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        {get_header_styles()}
        {get_footer_styles()}
    </style>
</head>
<body class="{tokens['base_mode']} editorial-mode">
    {build_header('articles', date_formatted)}

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

            {related_html}

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

    {build_footer(date_formatted)}

    {get_theme_script()}
</body>
</html>"""

    def _generate_amp_html(
        self,
        article: EditorialArticle,
        tokens: Dict,
    ) -> str:
        """Generate AMP HTML page for an editorial article."""
        date_formatted = datetime.strptime(article.date, "%Y-%m-%d").strftime(
            "%B %d, %Y"
        )

        # Escape for HTML attributes
        title_escaped = article.title.replace('"', "&quot;")
        summary_escaped = article.summary.replace('"', "&quot;")

        # AMP requires inline styles under 75KB and no external stylesheets except fonts
        amp_styles = f"""
        body {{
            font-family: 'Inter', system-ui, sans-serif;
            background: {tokens['bg_color']};
            color: {tokens['text_color']};
            margin: 0;
            padding: 0;
            line-height: 1.7;
        }}
        .container {{
            max-width: 720px;
            margin: 0 auto;
            padding: 1rem 1.5rem 3rem;
        }}
        header {{
            text-align: center;
            padding: 2rem 0;
            border-bottom: 1px solid {tokens['border_color']};
            margin-bottom: 2rem;
        }}
        .logo {{
            font-size: 1.25rem;
            font-weight: 700;
            color: {tokens['accent_color']};
            text-decoration: none;
        }}
        .article-meta {{
            display: flex;
            gap: 1rem;
            justify-content: center;
            font-size: 0.875rem;
            color: {tokens['muted_color']};
            margin-bottom: 1rem;
        }}
        h1 {{
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 1rem;
            color: {tokens['text_color']};
        }}
        .summary {{
            font-size: 1.125rem;
            color: {tokens['muted_color']};
        }}
        .content {{
            font-size: 1.0625rem;
        }}
        .content p {{
            margin-bottom: 1.5rem;
        }}
        .content h2 {{
            font-size: 1.375rem;
            margin: 2rem 0 1rem;
            color: {tokens['accent_color']};
        }}
        .content blockquote {{
            border-left: 4px solid {tokens['primary_color']};
            padding-left: 1rem;
            margin: 1.5rem 0;
            font-style: italic;
            color: {tokens['muted_color']};
        }}
        .content strong {{
            color: {tokens['accent_color']};
        }}
        .sources {{
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            padding: 1rem;
            margin: 2rem 0;
        }}
        .sources h3 {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: {tokens['muted_color']};
            margin-bottom: 0.75rem;
        }}
        .sources ul {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .sources li {{
            padding: 0.5rem 0;
            font-size: 0.875rem;
            color: {tokens['muted_color']};
            border-bottom: 1px solid {tokens['border_color']};
        }}
        .sources li:last-child {{
            border-bottom: none;
        }}
        .keywords {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 1.5rem 0;
        }}
        .keyword {{
            background: rgba(255,255,255,0.05);
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            font-size: 0.75rem;
            color: {tokens['muted_color']};
        }}
        footer {{
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid {tokens['border_color']};
            text-align: center;
        }}
        .back-link {{
            color: {tokens['accent_color']};
            text-decoration: none;
        }}
        """

        return f"""<!doctype html>
<html amp lang="en">
<head>
    <meta charset="utf-8">
    <script async src="https://cdn.ampproject.org/v0.js"></script>
    <title>{article.title} | DailyTrending.info</title>
    <link rel="canonical" href="https://dailytrending.info{article.url}">
    <meta name="viewport" content="width=device-width,minimum-scale=1,initial-scale=1">
    <meta name="description" content="{summary_escaped}">

    <!-- AMP Boilerplate -->
    <style amp-boilerplate>body{{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}}@-webkit-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-moz-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-ms-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-o-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}</style><noscript><style amp-boilerplate>body{{-webkit-animation:none;-moz-animation:none;-ms-animation:none;animation:none}}</style></noscript>

    <!-- AMP Analytics -->
    <script async custom-element="amp-analytics" src="https://cdn.ampproject.org/v0/amp-analytics-0.1.js"></script>

    <!-- JSON-LD -->
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "{title_escaped}",
        "description": "{summary_escaped}",
        "datePublished": "{article.date}T06:00:00Z",
        "dateModified": "{article.date}T06:00:00Z",
        "author": {{
            "@type": "Person",
            "name": "Brad Shannon"
        }},
        "publisher": {{
            "@type": "Organization",
            "name": "DailyTrending.info",
            "logo": {{
                "@type": "ImageObject",
                "url": "https://dailytrending.info/icons/icon-512.png"
            }}
        }},
        "mainEntityOfPage": "https://dailytrending.info{article.url}"
    }}
    </script>

    <style amp-custom>
        {amp_styles}
    </style>
</head>
<body>
    <amp-analytics type="gtag" data-credentials="include">
        <script type="application/json">
        {{
            "vars": {{
                "gtag_id": "G-XZNXRW8S7L",
                "config": {{
                    "G-XZNXRW8S7L": {{"groups": "default"}}
                }}
            }}
        }}
        </script>
    </amp-analytics>

    <header>
        <a href="/" class="logo">DailyTrending.info</a>
    </header>

    <article class="container">
        <div class="article-meta">
            <time datetime="{article.date}">{date_formatted}</time>
            <span>{article.word_count} words</span>
        </div>

        <h1>{article.title}</h1>
        <p class="summary">{article.summary}</p>

        <div class="content">
            {article.content}
        </div>

        <div class="sources">
            <h3>Stories Referenced</h3>
            <ul>
                {''.join(f'<li>{story}</li>' for story in article.top_stories[:5])}
            </ul>
        </div>

        <div class="keywords">
            {''.join(f'<span class="keyword">{kw}</span>' for kw in article.keywords[:8])}
        </div>

        <footer>
            <a href="/" class="back-link">Back to Today's Trends</a>
            <p style="margin-top: 1rem; font-size: 0.875rem; color: {tokens['muted_color']};">
                <a href="https://dailytrending.info{article.url}" style="color: {tokens['accent_color']};">View full version</a>
            </p>
        </footer>
    </article>
</body>
</html>"""

    def _call_groq(
        self,
        prompt: str,
        max_tokens: int = 800,
        max_retries: int = 1,
        task_complexity: str = "complex",
    ) -> Optional[str]:
        """
        Call LLM API with smart provider routing based on task complexity.

        For simple tasks: OpenCode (free) > Mistral (free) > Hugging Face (free) > Groq > OpenRouter > Google AI
        For complex tasks: Mistral > Google AI > OpenRouter > OpenCode > Hugging Face > Groq

        Note: Editorial defaults to 'complex' as it requires high-quality writing.
        """
        if task_complexity == "simple":
            # For simple tasks, prioritize free models to save quota
            result = self._call_opencode(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_mistral(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_huggingface(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_groq_direct(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_openrouter(prompt, max_tokens, max_retries)
            if result:
                return result

            return self._call_google_ai(prompt, max_tokens, max_retries)
        else:
            # For complex tasks, prioritize higher quality models (Mistral is high quality)
            result = self._call_mistral(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_google_ai(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_openrouter(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_opencode(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_huggingface(prompt, max_tokens, max_retries)
            if result:
                return result

            return self._call_groq_direct(prompt, max_tokens, max_retries)

    def _call_google_ai(
        self, prompt: str, max_tokens: int = 800, max_retries: int = 1
    ) -> Optional[str]:
        """Call Google AI (Gemini) API - primary provider with generous free tier."""
        if not self.google_key:
            logger.info("No Google AI API key available, skipping to next provider")
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call("google")

        if not status.is_available:
            logger.warning(f"Google AI not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(
                f"Waiting {status.wait_seconds:.1f}s for Google AI rate limit..."
            )
            time.sleep(status.wait_seconds)

        # Use Gemini 2.5 Flash Lite - highest RPM (10) among free models
        model = "gemini-2.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Trying Google AI {model} (attempt {attempt + 1}/{max_retries})"
                )
                response = self.session.post(
                    url,
                    headers={
                        "x-goog-api-key": self.google_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": max_tokens,
                            "temperature": 0.7,
                        },
                    },
                    timeout=60,
                )
                response.raise_for_status()

                # Update rate limiter tracking
                rate_limiter._last_call_time["google"] = time.time()

                # Parse response
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
                        if text:
                            logger.info(f"Google AI success with {model}")
                            return text

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # Check if this is a quota exhaustion (daily limit) vs temporary rate limit
                    try:
                        error_data = response.json()
                        error_msg = str(error_data).lower()
                        if (
                            "quota" in error_msg
                            or "exhausted" in error_msg
                            or "daily" in error_msg
                        ):
                            # This is a quota exhaustion - mark provider as exhausted
                            mark_provider_exhausted("google", "daily quota exceeded")
                            return None
                    except Exception:
                        pass

                    # Temporary rate limit - wait and retry
                    retry_after = response.headers.get("Retry-After", "10")
                    try:
                        wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                    except ValueError:
                        wait_time = self.MAX_RETRY_WAIT
                    logger.warning(
                        f"Google AI rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                logger.error(f"Google AI failed: {e}")
                return None
            except Exception as e:
                logger.error(f"Google AI failed: {e}")
                return None

        logger.warning("Google AI: Max retries exceeded")
        return None

    def _call_google_ai_structured(
        self, prompt: str, schema: dict, max_tokens: int = 2000, max_retries: int = 1
    ) -> Optional[Dict]:
        """
        Call Google AI with structured output (guaranteed valid JSON).

        Uses Gemini's response_mime_type and response_schema to ensure
        the response matches the provided JSON schema.
        """
        if not self.google_key:
            logger.info("No Google AI API key available, skipping structured output")
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call("google")

        if not status.is_available:
            logger.warning(f"Google AI not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(
                f"Waiting {status.wait_seconds:.1f}s for Google AI rate limit..."
            )
            time.sleep(status.wait_seconds)

        # Use Gemini 2.5 Flash Lite with structured output
        model = "gemini-2.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Trying Google AI {model} with structured output (attempt {attempt + 1}/{max_retries})"
                )
                response = self.session.post(
                    url,
                    headers={
                        "x-goog-api-key": self.google_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": max_tokens,
                            "temperature": 0.7,
                            "response_mime_type": "application/json",
                            "response_schema": schema,
                        },
                    },
                    timeout=90,  # Longer timeout for structured output
                )
                response.raise_for_status()

                # Update rate limiter tracking
                rate_limiter._last_call_time["google"] = time.time()

                # Parse response - should be valid JSON
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
                        if text:
                            try:
                                result = json.loads(text)
                                logger.info(
                                    f"Google AI structured output success with {model}"
                                )
                                return result
                            except json.JSONDecodeError as e:
                                # Shouldn't happen with structured output, but fallback to repair
                                logger.warning(
                                    f"Structured output JSON parse error (unexpected): {e}"
                                )
                                repaired = self._repair_json(text)
                                return json.loads(repaired)

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # Check if this is a quota exhaustion (daily limit) vs temporary rate limit
                    try:
                        error_data = response.json()
                        error_msg = str(error_data).lower()
                        if (
                            "quota" in error_msg
                            or "exhausted" in error_msg
                            or "daily" in error_msg
                        ):
                            # This is a quota exhaustion - mark provider as exhausted
                            mark_provider_exhausted("google", "daily quota exceeded")
                            return None
                    except Exception:
                        pass

                    # Temporary rate limit - wait and retry
                    retry_after = response.headers.get("Retry-After", "10")
                    try:
                        wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                    except ValueError:
                        wait_time = self.MAX_RETRY_WAIT
                    logger.warning(
                        f"Google AI rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                logger.error(f"Google AI structured output failed: {e}")
                return None
            except Exception as e:
                logger.error(f"Google AI structured output failed: {e}")
                return None

        logger.warning("Google AI structured output: Max retries exceeded")
        return None

    def _call_openrouter(
        self, prompt: str, max_tokens: int = 800, max_retries: int = 1
    ) -> Optional[str]:
        """Call OpenRouter API with free models (primary)."""
        if not self.openrouter_key:
            logger.warning("No OpenRouter API key available")
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call("openrouter")

        if not status.is_available:
            logger.warning(f"OpenRouter not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(
                f"Waiting {status.wait_seconds:.1f}s for OpenRouter rate limit..."
            )
            time.sleep(status.wait_seconds)

        # Free models to try in order of preference
        free_models = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-r1-0528:free",
            "google/gemma-3-27b-it:free",
        ]

        for model in free_models:
            for attempt in range(max_retries):
                try:
                    logger.info(
                        f"Trying OpenRouter {model} (attempt {attempt + 1}/{max_retries})"
                    )
                    response = self.session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openrouter_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://dailytrending.info",
                            "X-Title": "DailyTrending.info",
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": 0.7,
                        },
                        timeout=60,
                    )
                    response.raise_for_status()

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers(
                        "openrouter", dict(response.headers)
                    )

                    result = (
                        response.json()
                        .get("choices", [{}])[0]
                        .get("message", {})
                        .get("content")
                    )
                    if result:
                        logger.info(f"OpenRouter success with {model}")
                        return result
                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        # Parse retry-after header if available
                        retry_after = response.headers.get("Retry-After", "10")
                        try:
                            wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                        except ValueError:
                            wait_time = self.MAX_RETRY_WAIT
                        logger.warning(
                            f"OpenRouter {model} rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    logger.warning(f"OpenRouter {model} failed: {e}")
                    break  # Try next model
                except Exception as e:
                    logger.warning(f"OpenRouter {model} failed: {e}")
                    break  # Try next model

        logger.warning("All OpenRouter models failed")
        return None

    def _call_groq_direct(
        self, prompt: str, max_tokens: int = 800, max_retries: int = 1
    ) -> Optional[str]:
        """Call Groq API directly (fallback)."""
        if not self.groq_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call("groq")

        if not status.is_available:
            logger.warning(f"Groq not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for Groq rate limit...")
            time.sleep(status.wait_seconds)

        # Proactive rate limiting
        elapsed = time.time() - self._last_call_time
        if elapsed < self.MIN_CALL_INTERVAL:
            time.sleep(self.MIN_CALL_INTERVAL - elapsed)

        for attempt in range(max_retries):
            try:
                self._last_call_time = time.time()
                response = self.session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.7,
                    },
                    timeout=60,
                )
                response.raise_for_status()

                # Update rate limiter from response headers
                rate_limiter.update_from_response_headers(
                    "groq", dict(response.headers)
                )

                return (
                    response.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # Parse retry-after header if available
                    retry_after = response.headers.get("Retry-After", "10")
                    try:
                        wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                    except ValueError:
                        wait_time = self.MAX_RETRY_WAIT
                    logger.warning(
                        f"Groq rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                logger.error(f"Groq API error: {e}")
                return None
            except Exception as e:
                logger.error(f"Groq API error: {e}")
                return None

        logger.warning("Groq API: Max retries exceeded")
        return None

    def _call_opencode(
        self, prompt: str, max_tokens: int = 800, max_retries: int = 1
    ) -> Optional[str]:
        """Call OpenCode API with free models (glm-4.7-free, minimax-m2.1-free)."""
        opencode_key = os.getenv("OPENCODE_API_KEY")
        if not opencode_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call("opencode")

        if not status.is_available:
            logger.warning(f"OpenCode not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(
                f"Waiting {status.wait_seconds:.1f}s for OpenCode rate limit..."
            )
            time.sleep(status.wait_seconds)

        # Proactive rate limiting
        elapsed = time.time() - self._last_call_time
        if elapsed < self.MIN_CALL_INTERVAL:
            time.sleep(self.MIN_CALL_INTERVAL - elapsed)

        # Free models to try in order
        free_models = ["glm-4.7-free", "minimax-m2.1-free"]

        for model in free_models:
            for attempt in range(max_retries):
                try:
                    self._last_call_time = time.time()
                    logger.info(
                        f"Trying OpenCode {model} (attempt {attempt + 1}/{max_retries})"
                    )
                    response = self.session.post(
                        "https://opencode.ai/zen/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {opencode_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": 0.7,
                        },
                        timeout=60,
                    )
                    response.raise_for_status()

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers(
                        "opencode", dict(response.headers)
                    )
                    rate_limiter._last_call_time["opencode"] = time.time()

                    result = (
                        response.json()
                        .get("choices", [{}])[0]
                        .get("message", {})
                        .get("content")
                    )
                    if result:
                        logger.info(f"OpenCode success with {model}")
                        return result

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", "10")
                        try:
                            wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                        except ValueError:
                            wait_time = self.MAX_RETRY_WAIT
                        logger.warning(
                            f"OpenCode rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    logger.warning(f"OpenCode API error with {model}: {e}")
                    break  # Try next model
                except Exception as e:
                    logger.warning(f"OpenCode API error with {model}: {e}")
                    break  # Try next model

        logger.warning("All OpenCode models failed")
        return None

    def _call_huggingface(
        self, prompt: str, max_tokens: int = 800, max_retries: int = 1
    ) -> Optional[str]:
        """Call Hugging Face Inference API with free models."""
        huggingface_key = os.getenv("HUGGINGFACE_API_KEY")
        if not huggingface_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call("huggingface")

        if not status.is_available:
            logger.warning(f"Hugging Face not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(
                f"Waiting {status.wait_seconds:.1f}s for Hugging Face rate limit..."
            )
            time.sleep(status.wait_seconds)

        # Proactive rate limiting
        elapsed = time.time() - self._last_call_time
        if elapsed < self.MIN_CALL_INTERVAL:
            time.sleep(self.MIN_CALL_INTERVAL - elapsed)

        # Free models to try in order (7B models work well on free tier)
        free_models = [
            "mistralai/Mistral-7B-Instruct-v0.3",
            "Qwen/Qwen2.5-7B-Instruct",
            "microsoft/Phi-3-mini-4k-instruct",
        ]

        for model in free_models:
            for attempt in range(max_retries):
                try:
                    self._last_call_time = time.time()
                    logger.info(
                        f"Trying Hugging Face {model} (attempt {attempt + 1}/{max_retries})"
                    )
                    response = self.session.post(
                        f"https://api-inference.huggingface.co/models/{model}",
                        headers={
                            "Authorization": f"Bearer {huggingface_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "inputs": prompt,
                            "parameters": {
                                "max_new_tokens": max_tokens,
                                "temperature": 0.7,
                                "return_full_text": False,
                            },
                        },
                        timeout=60,
                    )
                    response.raise_for_status()

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers(
                        "huggingface", dict(response.headers)
                    )
                    rate_limiter._last_call_time["huggingface"] = time.time()

                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        text = result[0].get("generated_text", "")
                        if text:
                            logger.info(f"Hugging Face success with {model}")
                            return text

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", "10")
                        try:
                            wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                        except ValueError:
                            wait_time = self.MAX_RETRY_WAIT
                        logger.warning(
                            f"Hugging Face rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    elif response.status_code == 503:
                        # Model is loading, wait and retry
                        logger.warning(
                            f"Hugging Face model {model} is loading, waiting {self.MAX_RETRY_WAIT}s..."
                        )
                        time.sleep(self.MAX_RETRY_WAIT)
                        continue
                    logger.warning(f"Hugging Face API error with {model}: {e}")
                    break  # Try next model
                except Exception as e:
                    logger.warning(f"Hugging Face API error with {model}: {e}")
                    break  # Try next model

        logger.warning("All Hugging Face models failed")
        return None

    def _call_mistral(
        self, prompt: str, max_tokens: int = 800, max_retries: int = 1
    ) -> Optional[str]:
        """Call Mistral AI API - high quality free tier models."""
        mistral_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call("mistral")

        if not status.is_available:
            logger.warning(f"Mistral not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for Mistral rate limit...")
            time.sleep(status.wait_seconds)

        # Proactive rate limiting
        elapsed = time.time() - self._last_call_time
        if elapsed < self.MIN_CALL_INTERVAL:
            time.sleep(self.MIN_CALL_INTERVAL - elapsed)

        # Mistral free tier models
        models = [
            "mistral-small-latest",
            "open-mistral-7b",
        ]

        for model in models:
            for attempt in range(max_retries):
                try:
                    self._last_call_time = time.time()
                    logger.info(
                        f"Trying Mistral {model} (attempt {attempt + 1}/{max_retries})"
                    )
                    response = self.session.post(
                        "https://api.mistral.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {mistral_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": 0.7,
                        },
                        timeout=60,
                    )
                    response.raise_for_status()

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers(
                        "mistral", dict(response.headers)
                    )
                    rate_limiter._last_call_time["mistral"] = time.time()

                    result = (
                        response.json()
                        .get("choices", [{}])[0]
                        .get("message", {})
                        .get("content")
                    )
                    if result:
                        logger.info(f"Mistral success with {model}")
                        return result

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", "10")
                        try:
                            wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                        except ValueError:
                            wait_time = self.MAX_RETRY_WAIT
                        logger.warning(
                            f"Mistral rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    logger.warning(f"Mistral API error with {model}: {e}")
                    break  # Try next model
                except Exception as e:
                    logger.warning(f"Mistral API error with {model}: {e}")
                    break  # Try next model

        logger.warning("All Mistral models failed")
        return None

    def _repair_json(self, json_str: str) -> str:
        """Attempt to repair common JSON formatting issues from LLM output."""
        # Fix missing commas between elements (common LLM error)
        # Pattern: }" followed by whitespace and then "{ or "[
        json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
        json_str = re.sub(r"}\s*\n\s*{", "},\n{", json_str)
        json_str = re.sub(r"]\s*\n\s*\[", "],\n[", json_str)
        json_str = re.sub(r'"\s*\n\s*{', '",\n{', json_str)
        json_str = re.sub(r'}\s*\n\s*"', '},\n"', json_str)
        json_str = re.sub(r'"\s*\n\s*\[', '",\n[', json_str)
        json_str = re.sub(r']\s*\n\s*"', '],\n"', json_str)

        # Fix missing comma after value before next key
        # Pattern: "value" (whitespace) "key":
        json_str = re.sub(r'"\s+("[\w]+"\s*:)', r'", \1', json_str)

        # Fix trailing commas before closing brackets
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)

        return json_str

    def _parse_json_response(self, response: Optional[str]) -> Optional[Dict]:
        """Parse JSON from LLM response."""
        if not response:
            return None

        try:
            # Try to find JSON in response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                # First, try parsing as-is
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

                # Try repairing common JSON issues (missing commas, etc.)
                try:
                    repaired = self._repair_json(json_str)
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass

                # Escape control characters only INSIDE quoted strings
                # This preserves structural JSON formatting
                def escape_string_contents(match):
                    s = match.group(0)
                    inner = s[1:-1]  # Remove quotes
                    # Only escape raw control characters, not already-escaped sequences
                    inner = inner.replace("\n", "\\n")
                    inner = inner.replace("\r", "\\r")
                    inner = inner.replace("\t", "\\t")
                    # Escape other control characters (except those already handled)
                    inner = re.sub(
                        r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
                        lambda m: f"\\u{ord(m.group()):04x}",
                        inner,
                    )
                    return f'"{inner}"'

                # Match quoted strings (handles escaped quotes inside)
                try:
                    sanitized = re.sub(
                        r'"(?:[^"\\]|\\.)*"', escape_string_contents, json_str
                    )
                    return json.loads(sanitized)
                except (json.JSONDecodeError, Exception):
                    pass

                # Try repair + escape combination
                try:
                    repaired = self._repair_json(json_str)
                    sanitized = re.sub(
                        r'"(?:[^"\\]|\\.)*"', escape_string_contents, repaired
                    )
                    return json.loads(sanitized)
                except (json.JSONDecodeError, Exception):
                    pass

                # Last resort: strip all control chars except structural whitespace
                try:
                    stripped = re.sub(r"[\x00-\x09\x0b\x0c\x0e-\x1f]", " ", json_str)
                    repaired = self._repair_json(stripped)
                    return json.loads(repaired)
                except (json.JSONDecodeError, Exception):
                    pass

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"JSON parse error: {e}")

        return None

    def _sanitize_slug(self, slug: str) -> str:
        """Sanitize slug for URL usage."""
        # Convert to lowercase, replace spaces with dashes
        slug = slug.lower().strip()
        slug = re.sub(r"[^a-z0-9\-]", "-", slug)
        slug = re.sub(r"-+", "-", slug)  # Remove duplicate dashes
        slug = slug.strip("-")
        return slug[:60] or "daily-editorial"  # Max 60 chars

    def _validate_article_completeness(self, content: str) -> tuple[bool, List[str]]:
        """
        Validate that the article contains all 8 required sections.

        Returns:
            Tuple of (is_complete, missing_sections)
        """
        # Required section headers (case-insensitive matching)
        required_sections = [
            "the lead",
            "what people think",
            "what's actually happening",
            "the hidden tradeoffs",
            "the best counterarguments",
            "what this means next",
            "practical framework",
            "conclusion",
        ]

        # Alternative section names that are acceptable
        section_aliases = {
            "what's actually happening": [
                "what is actually happening",
                "what's happening",
                "what is happening",
            ],
            "the hidden tradeoffs": ["hidden tradeoffs", "the tradeoffs", "tradeoffs"],
            "the best counterarguments": [
                "best counterarguments",
                "counterarguments",
                "the counterarguments",
            ],
            "what this means next": ["what comes next", "what's next", "next steps"],
            "practical framework": [
                "framework",
                "the framework",
                "a practical framework",
            ],
        }

        content_lower = content.lower()
        missing_sections = []

        for section in required_sections:
            # Check for the main section name
            found = section in content_lower

            # Check aliases if not found
            if not found and section in section_aliases:
                for alias in section_aliases[section]:
                    if alias in content_lower:
                        found = True
                        break

            if not found:
                missing_sections.append(section)

        is_complete = len(missing_sections) == 0
        return is_complete, missing_sections

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
        articles.sort(key=lambda x: x.get("date", ""), reverse=True)
        return articles

    def regenerate_all_article_pages(self, design: Optional[Dict] = None) -> int:
        """
        Regenerate HTML pages for all existing articles from their metadata.

        This updates the HTML (header, footer, styling) without regenerating
        the AI-written content.

        Args:
            design: Optional design spec for colors

        Returns:
            Number of articles regenerated
        """
        if not self.articles_dir.exists():
            logger.info("No articles directory found")
            return 0

        tokens = self._get_design_tokens(design)

        count = 0
        for metadata_file in self.articles_dir.rglob("metadata.json"):
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)

                # Reconstruct EditorialArticle from metadata
                article = EditorialArticle(
                    title=metadata.get("title", ""),
                    slug=metadata.get("slug", ""),
                    date=metadata.get("date", ""),
                    summary=metadata.get("summary", ""),
                    content=metadata.get("content", ""),
                    word_count=metadata.get("word_count", 0),
                    top_stories=metadata.get("top_stories", []),
                    keywords=metadata.get("keywords", []),
                    mood=metadata.get("mood", "informative"),
                    url=metadata.get("url", ""),
                )

                # Get related articles for internal linking
                related_articles = self._get_related_articles(
                    article.date, article.slug, limit=3
                )

                # Generate new HTML
                html = self._generate_article_html(article, tokens, related_articles)

                # Save to index.html in same directory as metadata.json
                article_dir = metadata_file.parent
                (article_dir / "index.html").write_text(html, encoding="utf-8")

                logger.info(f"Regenerated: {article.title}")
                count += 1

            except Exception as e:
                logger.warning(f"Failed to regenerate {metadata_file}: {e}")

        logger.info(f"Regenerated {count} article pages")
        return count

    def _get_related_articles(
        self, current_date: str, current_slug: str, limit: int = 3
    ) -> List[Dict]:
        """Get related articles for internal linking (excludes current article)."""
        all_articles = self.get_all_articles()
        related = []

        for article in all_articles:
            # Skip current article
            if (
                article.get("date") == current_date
                and article.get("slug") == current_slug
            ):
                continue
            related.append(article)
            if len(related) >= limit:
                break

        return related

    def generate_articles_index(self, design: Optional[Dict] = None) -> str:
        """
        Generate an enhanced index page with search, filter, sort, and pagination.

        Features:
        - Full-text search across title, summary, keywords
        - Filter by date range, mood, word count
        - Sort by date, length, or alphabetically
        - Pagination (20 per page)
        - Month grouping with dividers
        - View toggle (list/compact)
        - Stats bar
        - Keyboard navigation
        - URL state persistence
        """
        articles = self.get_all_articles()

        tokens = self._get_design_tokens(design)

        # Calculate stats
        total_articles = len(articles)
        total_words = sum(a.get("word_count", 0) for a in articles)
        reading_hours = round(total_words / 200 / 60, 1)  # 200 wpm

        # Get unique moods for filter
        moods = sorted(set(a.get("mood", "informative") for a in articles))

        # Escape article data for JSON embedding
        # The data comes from our own metadata files (trusted), but we still escape for HTML safety
        articles_json = json.dumps(
            [
                {
                    "title": a.get("title", "")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"),
                    "date": a.get("date", ""),
                    "url": a.get("url", ""),
                    "summary": (a.get("summary", "") or "")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"),
                    "mood": a.get("mood", "informative"),
                    "word_count": a.get("word_count", 0),
                    "keywords": a.get("keywords", []),
                }
                for a in articles
            ]
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Editorial Articles | DailyTrending.info</title>
    <meta name="description" content="Browse {total_articles} daily editorial articles analyzing CMMC and compliance news stories. Search, filter by mood, and explore our archive.">
    <link rel="canonical" href="https://dailytrending.info/articles/">

    <meta property="og:title" content="Editorial Articles | DailyTrending.info">
    <meta property="og:description" content="Browse {total_articles} daily editorial articles analyzing trending news and technology stories.">
    <meta property="og:type" content="website">

    <!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2196222970720414"
         crossorigin="anonymous"></script>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family={tokens['font_secondary'].replace(' ', '+')}:wght@400;500;600;700&family={tokens['font_primary'].replace(' ', '+')}:wght@600;700&display=swap" rel="stylesheet">

    <style>
        :root {{
            --primary: {tokens['primary_color']};
            --accent: {tokens['accent_color']};
            --bg: {tokens['bg_color']};
            --text: {tokens['text_color']};
            --text-muted: {tokens['muted_color']};
            --border: {tokens['border_color']};
            --card-bg: {tokens['card_bg']};
            --font-primary: '{tokens['font_primary']}', system-ui, sans-serif;
            --font-secondary: '{tokens['font_secondary']}', system-ui, sans-serif;
            /* Shared component color mappings */
            --color-text: var(--text);
            --color-muted: var(--text-muted);
            --color-bg: var(--bg);
            --color-accent: var(--accent);
            --color-border: var(--border);
            --color-card-bg: var(--card-bg);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: var(--font-secondary);
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        body.light-mode {{
            --bg: #ffffff;
            --text: #1a1a2e;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --card-bg: #f8fafc;
            --color-text: var(--text);
            --color-muted: var(--text-muted);
            --color-bg: var(--bg);
            --color-border: var(--border);
            --color-card-bg: var(--card-bg);
        }}

        body.dark-mode {{
            --bg: #0a0a0a;
            --text: #ffffff;
            --text-muted: #a1a1aa;
            --border: #27272a;
            --card-bg: #18181b;
            --color-text: var(--text);
            --color-muted: var(--text-muted);
            --color-bg: var(--bg);
            --color-border: var(--border);
            --color-card-bg: var(--card-bg);
        }}

        /* Density settings */
        body.density-compact {{
            --section-gap: 1.5rem;
            --card-gap: 0.75rem;
            --card-padding: 0.75rem;
        }}
        body.density-comfortable {{
            --section-gap: 2.5rem;
            --card-gap: 1.25rem;
            --card-padding: 1.25rem;
        }}
        body.density-spacious {{
            --section-gap: 4rem;
            --card-gap: 2rem;
            --card-padding: 1.75rem;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}

        .back-link {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--accent);
            text-decoration: none;
            margin-bottom: 2rem;
            font-weight: 500;
        }}

        .back-link:hover {{ opacity: 0.8; }}

        .page-header {{
            text-align: center;
            margin-bottom: 2rem;
        }}

        .page-header h1 {{
            font-family: var(--font-primary);
            font-size: clamp(2rem, 5vw, 3rem);
            margin-bottom: 0.5rem;
        }}

        .page-header p {{
            color: var(--text-muted);
        }}

        /* Stats bar */
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            padding: 1rem;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }}

        .stat {{
            text-align: center;
        }}

        .stat-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--accent);
        }}

        .stat-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        /* Search box */
        .search-box {{
            position: relative;
            margin-bottom: 1.5rem;
        }}

        .search-box input {{
            width: 100%;
            padding: 1rem 1rem 1rem 3rem;
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        .search-box input:focus {{
            border-color: var(--primary);
        }}

        .search-box input::placeholder {{
            color: var(--text-muted);
        }}

        .search-icon {{
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
        }}

        .search-hint {{
            position: absolute;
            right: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            font-size: 0.75rem;
            background: rgba(255,255,255,0.1);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
        }}

        /* Controls bar */
        .controls-bar {{
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
            align-items: center;
        }}

        .filter-group {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .filter-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        select {{
            padding: 0.5rem 2rem 0.5rem 0.75rem;
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            font-size: 0.875rem;
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='white' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10l-5 5z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 0.75rem center;
        }}

        select:focus {{
            outline: none;
            border-color: var(--primary);
        }}

        .view-toggle {{
            display: flex;
            margin-left: auto;
            background: rgba(255,255,255,0.05);
            border-radius: 6px;
            overflow: hidden;
        }}

        .view-btn {{
            padding: 0.5rem 0.75rem;
            background: transparent;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s;
        }}

        .view-btn.active {{
            background: var(--primary);
            color: white;
        }}

        .view-btn:hover:not(.active) {{
            background: rgba(255,255,255,0.1);
        }}

        /* Results info */
        .results-info {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .clear-filters {{
            background: none;
            border: none;
            color: var(--accent);
            cursor: pointer;
            font-size: 0.875rem;
        }}

        .clear-filters:hover {{
            text-decoration: underline;
        }}

        /* Month dividers */
        .month-divider {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin: 2rem 0 1rem;
            color: var(--text-muted);
            font-size: 0.875rem;
            font-weight: 600;
        }}

        .month-divider::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: var(--border);
        }}

        .month-divider span {{
            background: var(--bg);
            padding-right: 1rem;
        }}

        /* Articles grid */
        .articles-grid {{
            display: grid;
            gap: 1.5rem;
        }}

        .articles-grid.compact {{
            gap: 0.5rem;
        }}

        /* Article card */
        .article-card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }}

        .article-card:hover {{
            transform: translateY(-2px);
            border-color: var(--primary);
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }}

        .article-card.focused {{
            border-color: var(--accent);
            box-shadow: 0 0 0 2px var(--accent);
        }}

        .article-card time {{
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .article-card h2 {{
            font-family: var(--font-primary);
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
            line-height: 1.5;
        }}

        .article-meta {{
            display: flex;
            gap: 1rem;
            font-size: 0.875rem;
            color: var(--text-muted);
            align-items: center;
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

        /* Compact view */
        .articles-grid.compact .article-card {{
            padding: 1rem;
            border-radius: 8px;
        }}

        .articles-grid.compact .article-card h2 {{
            font-size: 1.1rem;
            margin: 0.25rem 0;
        }}

        .articles-grid.compact .article-card p {{
            display: none;
        }}

        .articles-grid.compact .article-meta {{
            margin-top: 0.5rem;
        }}

        /* Pagination */
        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.5rem;
            margin-top: 2rem;
            flex-wrap: wrap;
        }}

        .page-btn {{
            padding: 0.5rem 1rem;
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.875rem;
        }}

        .page-btn:hover:not(:disabled) {{
            background: var(--primary);
            border-color: var(--primary);
        }}

        .page-btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}

        .page-btn.active {{
            background: var(--primary);
            border-color: var(--primary);
        }}

        .page-info {{
            font-size: 0.875rem;
            color: var(--text-muted);
            margin: 0 1rem;
        }}

        /* No results */
        .no-results {{
            text-align: center;
            padding: 3rem;
            color: var(--text-muted);
        }}

        .no-results h3 {{
            margin-bottom: 0.5rem;
            color: var(--text);
        }}

        /* Highlight */
        mark {{
            background: var(--accent);
            color: var(--bg);
            padding: 0 0.2rem;
            border-radius: 2px;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .controls-bar {{
                flex-direction: column;
                align-items: stretch;
            }}

            .filter-group {{
                width: 100%;
            }}

            select {{
                flex: 1;
            }}

            .view-toggle {{
                margin-left: 0;
                justify-content: center;
            }}

            .stats-bar {{
                gap: 1rem;
            }}

            .stat-value {{
                font-size: 1.25rem;
            }}

            .search-hint {{
                display: none;
            }}
        }}

        @media (max-width: 480px) {{
            .container {{
                padding: 1rem;
            }}

            .article-card {{
                padding: 1rem;
            }}

            .article-card h2 {{
                font-size: 1.25rem;
            }}

            .pagination {{
                gap: 0.25rem;
            }}

            .page-btn {{
                padding: 0.4rem 0.6rem;
                font-size: 0.8rem;
            }}
        }}

        /* Keyboard focus visible */
        :focus-visible {{
            outline: 2px solid var(--accent);
            outline-offset: 2px;
        }}

        /* Screen reader only */
        .sr-only {{
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0,0,0,0);
            border: 0;
        }}

        {get_header_styles()}
        {get_footer_styles()}
    </style>
</head>
<body class="{tokens['base_mode']} editorial-mode">
    {build_header('articles', datetime.now().strftime('%B %d, %Y'))}

    <div class="container">
        <header class="page-header">
            <h1>Editorial Articles</h1>
            <p>Daily analysis and insights from DailyTrending.info</p>
        </header>

        <div class="stats-bar" aria-label="Article statistics">
            <div class="stat">
                <div class="stat-value" id="stat-articles">{total_articles}</div>
                <div class="stat-label">Articles</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_words:,}</div>
                <div class="stat-label">Total Words</div>
            </div>
            <div class="stat">
                <div class="stat-value">{reading_hours}h</div>
                <div class="stat-label">Reading Time</div>
            </div>
        </div>

        <div class="search-box">
            <svg class="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <path d="M21 21l-4.35-4.35"/>
            </svg>
            <input type="search" id="search-input" placeholder="Search articles..." aria-label="Search articles">
            <span class="search-hint">Press /</span>
        </div>

        <div class="controls-bar">
            <div class="filter-group">
                <label class="filter-label" for="date-filter">Date:</label>
                <select id="date-filter">
                    <option value="all">All Time</option>
                    <option value="week">This Week</option>
                    <option value="month">This Month</option>
                    <option value="3months">Last 3 Months</option>
                    <option value="year">This Year</option>
                </select>
            </div>

            <div class="filter-group">
                <label class="filter-label" for="mood-filter">Mood:</label>
                <select id="mood-filter">
                    <option value="all">All Moods</option>
                    {chr(10).join(f'<option value="{m.lower()}">{m.title()}</option>' for m in moods)}
                </select>
            </div>

            <div class="filter-group">
                <label class="filter-label" for="length-filter">Length:</label>
                <select id="length-filter">
                    <option value="all">Any Length</option>
                    <option value="short">Quick (&lt;800)</option>
                    <option value="medium">Standard (800-1000)</option>
                    <option value="long">Deep Dive (&gt;1000)</option>
                </select>
            </div>

            <div class="filter-group">
                <label class="filter-label" for="sort-select">Sort:</label>
                <select id="sort-select">
                    <option value="newest">Newest First</option>
                    <option value="oldest">Oldest First</option>
                    <option value="longest">Longest First</option>
                    <option value="shortest">Shortest First</option>
                    <option value="az">A-Z</option>
                </select>
            </div>

            <div class="view-toggle" role="group" aria-label="View mode">
                <button class="view-btn active" data-view="list" aria-pressed="true" title="List view">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="6" rx="1"/>
                        <rect x="3" y="15" width="18" height="6" rx="1"/>
                    </svg>
                </button>
                <button class="view-btn" data-view="compact" aria-pressed="false" title="Compact view">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="3" y1="6" x2="21" y2="6"/>
                        <line x1="3" y1="12" x2="21" y2="12"/>
                        <line x1="3" y1="18" x2="21" y2="18"/>
                    </svg>
                </button>
            </div>
        </div>

        <div class="results-info">
            <span id="results-count">Showing {total_articles} articles</span>
            <button class="clear-filters" id="clear-filters" style="display:none;">Clear filters</button>
        </div>

        <div class="articles-grid" id="articles-grid" role="list" aria-label="Articles">
            <!-- Articles rendered by JavaScript -->
        </div>

        <nav class="pagination" id="pagination" aria-label="Pagination">
            <!-- Pagination rendered by JavaScript -->
        </nav>

        <div id="no-results" class="no-results" style="display:none;">
            <h3>No articles found</h3>
            <p>Try adjusting your search or filters</p>
        </div>
    </div>

    <script>
    (function() {{
        'use strict';

        // Article data (server-rendered, escaped)
        const ARTICLES = {articles_json};

        // State
        let state = {{
            search: '',
            dateFilter: 'all',
            moodFilter: 'all',
            lengthFilter: 'all',
            sort: 'newest',
            page: 1,
            perPage: 20,
            view: 'list',
            focusedIndex: -1
        }};

        // DOM elements
        const searchInput = document.getElementById('search-input');
        const dateFilter = document.getElementById('date-filter');
        const moodFilter = document.getElementById('mood-filter');
        const lengthFilter = document.getElementById('length-filter');
        const sortSelect = document.getElementById('sort-select');
        const articlesGrid = document.getElementById('articles-grid');
        const pagination = document.getElementById('pagination');
        const resultsCount = document.getElementById('results-count');
        const clearBtn = document.getElementById('clear-filters');
        const noResults = document.getElementById('no-results');
        const viewBtns = document.querySelectorAll('.view-btn');

        // Initialize from URL
        function initFromURL() {{
            const params = new URLSearchParams(window.location.search);
            if (params.get('q')) state.search = params.get('q');
            if (params.get('date')) state.dateFilter = params.get('date');
            if (params.get('mood')) state.moodFilter = params.get('mood');
            if (params.get('length')) state.lengthFilter = params.get('length');
            if (params.get('sort')) state.sort = params.get('sort');
            if (params.get('page')) state.page = parseInt(params.get('page')) || 1;
            if (params.get('view')) state.view = params.get('view');

            // Sync UI
            searchInput.value = state.search;
            dateFilter.value = state.dateFilter;
            moodFilter.value = state.moodFilter;
            lengthFilter.value = state.lengthFilter;
            sortSelect.value = state.sort;

            viewBtns.forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.view === state.view);
                btn.setAttribute('aria-pressed', btn.dataset.view === state.view);
            }});

            if (state.view === 'compact') {{
                articlesGrid.classList.add('compact');
            }}
        }}

        // Update URL
        function updateURL() {{
            const params = new URLSearchParams();
            if (state.search) params.set('q', state.search);
            if (state.dateFilter !== 'all') params.set('date', state.dateFilter);
            if (state.moodFilter !== 'all') params.set('mood', state.moodFilter);
            if (state.lengthFilter !== 'all') params.set('length', state.lengthFilter);
            if (state.sort !== 'newest') params.set('sort', state.sort);
            if (state.page > 1) params.set('page', state.page);
            if (state.view !== 'list') params.set('view', state.view);

            const url = params.toString() ? '?' + params.toString() : window.location.pathname;
            history.replaceState(null, '', url);
        }}

        // Filter articles
        function filterArticles() {{
            let filtered = [...ARTICLES];
            const now = new Date();

            // Search
            if (state.search) {{
                const q = state.search.toLowerCase();
                filtered = filtered.filter(a =>
                    a.title.toLowerCase().includes(q) ||
                    a.summary.toLowerCase().includes(q) ||
                    a.keywords.some(k => k.toLowerCase().includes(q))
                );
            }}

            // Date filter
            if (state.dateFilter !== 'all') {{
                const cutoff = new Date();
                switch (state.dateFilter) {{
                    case 'week': cutoff.setDate(now.getDate() - 7); break;
                    case 'month': cutoff.setMonth(now.getMonth() - 1); break;
                    case '3months': cutoff.setMonth(now.getMonth() - 3); break;
                    case 'year': cutoff.setFullYear(now.getFullYear() - 1); break;
                }}
                filtered = filtered.filter(a => new Date(a.date) >= cutoff);
            }}

            // Mood filter
            if (state.moodFilter !== 'all') {{
                filtered = filtered.filter(a => a.mood.toLowerCase() === state.moodFilter);
            }}

            // Length filter
            if (state.lengthFilter !== 'all') {{
                switch (state.lengthFilter) {{
                    case 'short': filtered = filtered.filter(a => a.word_count < 800); break;
                    case 'medium': filtered = filtered.filter(a => a.word_count >= 800 && a.word_count <= 1000); break;
                    case 'long': filtered = filtered.filter(a => a.word_count > 1000); break;
                }}
            }}

            // Sort
            switch (state.sort) {{
                case 'newest': filtered.sort((a, b) => b.date.localeCompare(a.date)); break;
                case 'oldest': filtered.sort((a, b) => a.date.localeCompare(b.date)); break;
                case 'longest': filtered.sort((a, b) => b.word_count - a.word_count); break;
                case 'shortest': filtered.sort((a, b) => a.word_count - b.word_count); break;
                case 'az': filtered.sort((a, b) => a.title.localeCompare(b.title)); break;
            }}

            return filtered;
        }}

        // Highlight search term
        function highlight(text, query) {{
            if (!query) return text;
            const regex = new RegExp('(' + query.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
            return text.replace(regex, '<mark>$1</mark>');
        }}

        // Format date
        function formatDate(dateStr) {{
            const date = new Date(dateStr + 'T00:00:00');
            return date.toLocaleDateString('en-US', {{ year: 'numeric', month: 'long', day: 'numeric' }});
        }}

        // Get month key
        function getMonthKey(dateStr) {{
            const date = new Date(dateStr + 'T00:00:00');
            return date.toLocaleDateString('en-US', {{ year: 'numeric', month: 'long' }});
        }}

        // Render articles
        function render() {{
            const filtered = filterArticles();
            const totalPages = Math.ceil(filtered.length / state.perPage);
            state.page = Math.max(1, Math.min(state.page, totalPages || 1));

            const start = (state.page - 1) * state.perPage;
            const pageArticles = filtered.slice(start, start + state.perPage);

            // Update results count
            const hasFilters = state.search || state.dateFilter !== 'all' || state.moodFilter !== 'all' || state.lengthFilter !== 'all';
            if (filtered.length === 0) {{
                resultsCount.textContent = 'No articles found';
            }} else if (hasFilters) {{
                resultsCount.textContent = 'Showing ' + filtered.length + ' of ' + ARTICLES.length + ' articles';
            }} else {{
                resultsCount.textContent = 'Showing ' + ARTICLES.length + ' articles';
            }}
            clearBtn.style.display = hasFilters ? 'inline' : 'none';

            // Show/hide no results
            noResults.style.display = filtered.length === 0 ? 'block' : 'none';
            articlesGrid.style.display = filtered.length === 0 ? 'none' : 'grid';
            pagination.style.display = totalPages <= 1 ? 'none' : 'flex';

            // Render articles with month dividers
            let html = '';
            let currentMonth = '';

            pageArticles.forEach((article, index) => {{
                const monthKey = getMonthKey(article.date);

                // Add month divider if new month
                if (monthKey !== currentMonth && state.sort === 'newest') {{
                    currentMonth = monthKey;
                    html += '<div class="month-divider" aria-hidden="true"><span>' + monthKey + '</span></div>';
                }}

                const title = highlight(article.title, state.search);
                const summary = highlight(article.summary, state.search);

                html += '<article class="article-card" role="listitem" data-index="' + index + '" tabindex="0">' +
                    '<time datetime="' + article.date + '">' + formatDate(article.date) + '</time>' +
                    '<h2><a href="' + article.url + '">' + title + '</a></h2>' +
                    '<p>' + summary + '</p>' +
                    '<div class="article-meta">' +
                        '<span class="mood-badge">' + article.mood + '</span>' +
                        '<span>' + article.word_count + ' words</span>' +
                    '</div>' +
                '</article>';
            }});

            articlesGrid.innerHTML = html;

            // Render pagination
            if (totalPages > 1) {{
                let paginationHtml = '<button class="page-btn" data-page="prev" ' + (state.page === 1 ? 'disabled' : '') + '>Previous</button>';

                // Page numbers
                const maxVisible = 5;
                let startPage = Math.max(1, state.page - Math.floor(maxVisible / 2));
                let endPage = Math.min(totalPages, startPage + maxVisible - 1);
                if (endPage - startPage < maxVisible - 1) {{
                    startPage = Math.max(1, endPage - maxVisible + 1);
                }}

                if (startPage > 1) {{
                    paginationHtml += '<button class="page-btn" data-page="1">1</button>';
                    if (startPage > 2) paginationHtml += '<span class="page-info">...</span>';
                }}

                for (let i = startPage; i <= endPage; i++) {{
                    paginationHtml += '<button class="page-btn' + (i === state.page ? ' active' : '') + '" data-page="' + i + '">' + i + '</button>';
                }}

                if (endPage < totalPages) {{
                    if (endPage < totalPages - 1) paginationHtml += '<span class="page-info">...</span>';
                    paginationHtml += '<button class="page-btn" data-page="' + totalPages + '">' + totalPages + '</button>';
                }}

                paginationHtml += '<button class="page-btn" data-page="next" ' + (state.page === totalPages ? 'disabled' : '') + '>Next</button>';

                pagination.innerHTML = paginationHtml;
            }}

            updateURL();
        }}

        // Debounce helper
        function debounce(fn, delay) {{
            let timer;
            return function(...args) {{
                clearTimeout(timer);
                timer = setTimeout(() => fn.apply(this, args), delay);
            }};
        }}

        // Event handlers
        searchInput.addEventListener('input', debounce(function() {{
            state.search = this.value.trim();
            state.page = 1;
            render();
        }}, 200));

        dateFilter.addEventListener('change', function() {{
            state.dateFilter = this.value;
            state.page = 1;
            render();
        }});

        moodFilter.addEventListener('change', function() {{
            state.moodFilter = this.value;
            state.page = 1;
            render();
        }});

        lengthFilter.addEventListener('change', function() {{
            state.lengthFilter = this.value;
            state.page = 1;
            render();
        }});

        sortSelect.addEventListener('change', function() {{
            state.sort = this.value;
            state.page = 1;
            render();
        }});

        clearBtn.addEventListener('click', function() {{
            state.search = '';
            state.dateFilter = 'all';
            state.moodFilter = 'all';
            state.lengthFilter = 'all';
            state.page = 1;
            searchInput.value = '';
            dateFilter.value = 'all';
            moodFilter.value = 'all';
            lengthFilter.value = 'all';
            render();
        }});

        // View toggle
        viewBtns.forEach(btn => {{
            btn.addEventListener('click', function() {{
                state.view = this.dataset.view;
                viewBtns.forEach(b => {{
                    b.classList.toggle('active', b === this);
                    b.setAttribute('aria-pressed', b === this);
                }});
                articlesGrid.classList.toggle('compact', state.view === 'compact');
                updateURL();
            }});
        }});

        // Pagination
        pagination.addEventListener('click', function(e) {{
            const btn = e.target.closest('.page-btn');
            if (!btn || btn.disabled) return;

            const page = btn.dataset.page;
            if (page === 'prev') {{
                state.page--;
            }} else if (page === 'next') {{
                state.page++;
            }} else {{
                state.page = parseInt(page);
            }}
            render();
            window.scrollTo({{ top: articlesGrid.offsetTop - 100, behavior: 'smooth' }});
        }});

        // Keyboard navigation
        document.addEventListener('keydown', function(e) {{
            // Focus search with /
            if (e.key === '/' && document.activeElement !== searchInput) {{
                e.preventDefault();
                searchInput.focus();
                return;
            }}

            // Escape clears focus
            if (e.key === 'Escape') {{
                searchInput.blur();
                document.activeElement.blur();
                state.focusedIndex = -1;
                document.querySelectorAll('.article-card.focused').forEach(el => el.classList.remove('focused'));
                return;
            }}

            // Arrow navigation
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {{
                const cards = document.querySelectorAll('.article-card');
                if (cards.length === 0) return;

                e.preventDefault();

                // Remove current focus
                cards.forEach(c => c.classList.remove('focused'));

                if (e.key === 'ArrowDown') {{
                    state.focusedIndex = Math.min(state.focusedIndex + 1, cards.length - 1);
                }} else {{
                    state.focusedIndex = Math.max(state.focusedIndex - 1, 0);
                }}

                const card = cards[state.focusedIndex];
                card.classList.add('focused');
                card.focus();
                card.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
            }}

            // Enter to open
            if (e.key === 'Enter' && document.activeElement.classList.contains('article-card')) {{
                const link = document.activeElement.querySelector('a');
                if (link) window.location.href = link.href;
            }}
        }});

        // Click card to navigate
        articlesGrid.addEventListener('click', function(e) {{
            const card = e.target.closest('.article-card');
            if (card && !e.target.closest('a')) {{
                const link = card.querySelector('a');
                if (link) window.location.href = link.href;
            }}
        }});

        // Initialize
        initFromURL();
        render();

        // Mobile menu toggle
        const menuToggle = document.getElementById('mobile-menu-toggle');
        const navLinksEl = document.getElementById('nav-links');
        if (menuToggle && navLinksEl) {{
            menuToggle.addEventListener('click', () => {{
                navLinksEl.classList.toggle('active');
            }});
        }}
    }})();
    </script>

    {build_footer(datetime.now().strftime('%B %d, %Y'))}

    {get_theme_script()}
</body>
</html>"""

        # Save index
        self.articles_dir.mkdir(parents=True, exist_ok=True)
        (self.articles_dir / "index.html").write_text(html, encoding="utf-8")

        logger.info(f"Generated enhanced articles index with {total_articles} articles")
        return html


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Editorial Generator CLI")
    parser.add_argument(
        "--regenerate-html",
        action="store_true",
        help="Regenerate HTML for all existing articles (updates header/footer without re-running AI)",
    )
    parser.add_argument(
        "--regenerate-index",
        action="store_true",
        help="Regenerate the articles index page",
    )

    args = parser.parse_args()

    gen = EditorialGenerator()

    if args.regenerate_html:
        count = gen.regenerate_all_article_pages()
        print(f"Regenerated {count} article pages")
    elif args.regenerate_index:
        gen.generate_articles_index()
        print("Regenerated articles index")
    else:
        parser.print_help()
