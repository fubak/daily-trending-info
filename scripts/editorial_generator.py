#!/usr/bin/env python3
"""
Editorial Article Generator for DailyTrending.info

Generates AI-written editorial articles that synthesize top stories into
cohesive narratives. Articles are permanently retained (not archived).

URL Structure: /articles/YYYY/MM/DD/slug/index.html
"""

import html
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

from config import LLM_MIN_CALL_INTERVAL, LLM_MAX_RETRY_WAIT
from json_utils import escape_control_chars_in_strings
from llm_client import (
    call_openai_compatible,
    GROQ_SPEC,
    OPENROUTER_SPEC,
    OPENCODE_SPEC,
    MISTRAL_SPEC,
)
from editorial_renderer import generate_article_html, generate_amp_html
from articles_index_renderer import generate_articles_index_html

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

    # Rate limiting (sourced from config so editorial_generator and
    # enrich_content stay in sync).
    MIN_CALL_INTERVAL = LLM_MIN_CALL_INTERVAL
    MAX_RETRY_WAIT = LLM_MAX_RETRY_WAIT

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
        categories: Dict[str, int] = {}
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
        keyword_freq: Dict[str, int] = {}
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
        return generate_article_html(article, tokens, related_articles)

    def _generate_amp_html(
        self,
        article: EditorialArticle,
        tokens: Dict,
    ) -> str:
        return generate_amp_html(article, tokens)

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
                    except (ValueError, KeyError) as parse_err:
                        logger.debug(f"Could not parse 429 body for quota check: {parse_err}")

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
                    except (ValueError, KeyError) as parse_err:
                        logger.debug(f"Could not parse 429 body for quota check: {parse_err}")

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
        result = call_openai_compatible(
            OPENROUTER_SPEC, self.openrouter_key, prompt, max_tokens, max_retries,
            self.session, self.MAX_RETRY_WAIT,
        )
        return result

    def _call_groq_direct(
        self, prompt: str, max_tokens: int = 800, max_retries: int = 1
    ) -> Optional[str]:
        """Call Groq API directly (fallback)."""
        timing = [self._last_call_time]
        result = call_openai_compatible(
            GROQ_SPEC, self.groq_key, prompt, max_tokens, max_retries,
            self.session, self.MAX_RETRY_WAIT, self.MIN_CALL_INTERVAL, timing,
        )
        self._last_call_time = timing[0]
        return result

    def _call_opencode(
        self, prompt: str, max_tokens: int = 800, max_retries: int = 1
    ) -> Optional[str]:
        """Call OpenCode API with free models (glm-4.7-free, minimax-m2.1-free)."""
        opencode_key = os.getenv("OPENCODE_API_KEY")
        timing = [self._last_call_time]
        result = call_openai_compatible(
            OPENCODE_SPEC, opencode_key, prompt, max_tokens, max_retries,
            self.session, self.MAX_RETRY_WAIT, self.MIN_CALL_INTERVAL, timing,
        )
        self._last_call_time = timing[0]
        return result

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
        timing = [self._last_call_time]
        result = call_openai_compatible(
            MISTRAL_SPEC, mistral_key, prompt, max_tokens, max_retries,
            self.session, self.MAX_RETRY_WAIT, self.MIN_CALL_INTERVAL, timing,
        )
        self._last_call_time = timing[0]
        return result

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

                # Escape raw control characters that appear inside quoted
                # strings (a common defect in LLM JSON output).
                try:
                    sanitized = escape_control_chars_in_strings(json_str)
                    return json.loads(sanitized)
                except (json.JSONDecodeError, Exception):
                    pass

                # Try repair + escape combination
                try:
                    repaired = self._repair_json(json_str)
                    sanitized = escape_control_chars_in_strings(repaired)
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
        articles: List[Dict] = []

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
        """Generate the /articles/ index page and save it."""
        articles = self.get_all_articles()
        tokens = self._get_design_tokens(design)
        html = generate_articles_index_html(articles, tokens)

        self.articles_dir.mkdir(parents=True, exist_ok=True)
        (self.articles_dir / "index.html").write_text(html, encoding="utf-8")

        logger.info(f"Generated enhanced articles index with {len(articles)} articles")
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
