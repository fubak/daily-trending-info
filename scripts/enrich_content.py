"""
Content Enrichment Module for DailyTrending.info

Provides AI-powered content enhancement features:
- Word of the Day selection and definition
- Grokipedia Article of the Day
- Story summaries generation
"""

import json
import logging
import os
import re
import time
import requests
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

logger = logging.getLogger("pipeline")

# Grokipedia API endpoint (unofficial API wrapper)
GROKIPEDIA_API_URL = "https://grokipedia-api.com/page"


@dataclass
class WordOfTheDay:
    """Represents the Word of the Day with definition and context."""
    word: str
    part_of_speech: str
    definition: str
    example_usage: str
    origin: Optional[str] = None
    why_chosen: Optional[str] = None
    related_trend: Optional[str] = None


@dataclass
class GrokipediaArticle:
    """Represents a Grokipedia article summary."""
    title: str
    slug: str
    url: str
    summary: str
    word_count: int = 0
    related_trend: Optional[str] = None


@dataclass
class StorySummary:
    """Represents an AI-generated story summary."""
    title: str
    summary: str
    source: str


@dataclass
class EnrichedContent:
    """Container for all enriched content."""
    word_of_the_day: Optional[WordOfTheDay] = None
    grokipedia_article: Optional[GrokipediaArticle] = None
    story_summaries: List[StorySummary] = field(default_factory=list)


class ContentEnricher:
    """
    Enriches trending content with AI-generated features.

    Uses Groq API for LLM-powered content generation and
    Grokipedia API for encyclopedia article fetching.
    """

    def __init__(self, groq_key: Optional[str] = None):
        self.groq_key = groq_key or os.getenv('GROQ_API_KEY')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DailyTrending.info/1.0 (Content Enrichment)'
        })

    def enrich(self, trends: List[Dict], keywords: List[str]) -> EnrichedContent:
        """
        Generate all enriched content for today's trends.

        Args:
            trends: List of trend dictionaries with 'title', 'source', etc.
            keywords: List of extracted keywords from trends

        Returns:
            EnrichedContent with word of day, article, and summaries
        """
        enriched = EnrichedContent()

        # Phase 2: Word of the Day
        logger.info("Generating Word of the Day...")
        enriched.word_of_the_day = self._get_word_of_the_day(keywords, trends)
        if enriched.word_of_the_day:
            logger.info(f"  Word: {enriched.word_of_the_day.word}")

        # Phase 3: Grokipedia Article
        logger.info("Fetching Grokipedia Article of the Day...")
        enriched.grokipedia_article = self._get_grokipedia_article(trends, keywords)
        if enriched.grokipedia_article:
            logger.info(f"  Article: {enriched.grokipedia_article.title}")

        # Phase 4: Story Summaries
        logger.info("Generating story summaries...")
        enriched.story_summaries = self._generate_story_summaries(trends[:10])
        logger.info(f"  Generated {len(enriched.story_summaries)} summaries")

        return enriched

    def _call_groq(self, prompt: str, max_tokens: int = 500, max_retries: int = 5) -> Optional[str]:
        """Call Groq API with the given prompt and retry logic."""
        if not self.groq_key:
            logger.warning("No Groq API key available")
            return None

        for attempt in range(max_retries):
            try:
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
                    timeout=45
                )
                response.raise_for_status()
                return response.json().get('choices', [{}])[0].get('message', {}).get('content')
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 5
                    logger.warning(f"Groq rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                logger.warning(f"Groq API error: {e}")
                return None
            except Exception as e:
                logger.warning(f"Groq API error: {e}")
                return None

        logger.warning("Groq API: Max retries exceeded")
        return None

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if not response:
            return None

        try:
            # Remove markdown code blocks if present
            clean = re.sub(r'^```(?:json)?\s*', '', response.strip())
            clean = re.sub(r'\s*```$', '', clean)

            # Find JSON object
            json_match = re.search(r'\{.*\}', clean, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"JSON parse error: {e}")

        return None

    # =========================================================================
    # PHASE 2: Word of the Day
    # =========================================================================

    def _build_rich_context(self, trends: List[Dict], keywords: List[str], max_trends: int = 20) -> str:
        """
        Build rich context for AI content generation.

        Provides expanded trend information with descriptions and source context.
        """
        trend_lines = []
        for i, t in enumerate(trends[:max_trends]):
            source = t.get('source', 'unknown').replace('_', ' ').title()
            title = t.get('title', '')[:100]
            desc = (t.get('description', '') or '')[:150]

            trend_lines.append(f"{i+1}. [{source}] {title}")
            if desc and len(desc) > 30:
                trend_lines.append(f"   Context: {desc}")

        # Calculate theme categories
        categories = {}
        category_map = {
            'hackernews': 'Technology', 'lobsters': 'Technology',
            'github_trending': 'Technology', 'tech_rss': 'Technology',
            'news_rss': 'World News', 'reddit': 'Social/Viral',
            'product_hunt': 'Startups', 'devto': 'Development',
            'wikipedia': 'Current Events', 'google_trends': 'Popular Search'
        }
        for t in trends:
            src = t.get('source', 'other')
            cat = category_map.get(src, 'General')
            categories[cat] = categories.get(cat, 0) + 1

        category_summary = ", ".join(
            f"{count} {cat}" for cat, count in
            sorted(categories.items(), key=lambda x: -x[1])[:4]
        )

        return f"""TODAY'S STORIES ({len(trends)} total, {category_summary}):
{chr(10).join(trend_lines)}

TOP KEYWORDS: {', '.join(keywords[:40])}"""

    def _get_word_of_the_day(
        self,
        keywords: List[str],
        trends: List[Dict]
    ) -> Optional[WordOfTheDay]:
        """
        Select and define a Word of the Day from trending keywords.

        Uses LLM to pick an interesting, educational word and generate
        a definition with example usage in context.
        """
        if not keywords:
            return None

        # Build rich context with expanded trend information
        rich_context = self._build_rich_context(trends, keywords, max_trends=15)

        prompt = f"""You are a lexicographer selecting an educational "Word of the Day" for a news website.

{rich_context}

Select ONE word from the keywords that would be most educational and interesting as Word of the Day.

SELECTION CRITERIA:
- Prefer words that are unusual, have interesting etymology, or are newly relevant
- Avoid overly common words (the, and, new, etc.)
- Avoid proper nouns and abbreviations
- Choose words that readers might want to learn more about
- The word should connect to today's news in some way

Respond with ONLY a valid JSON object:
{{
  "word": "selected word",
  "part_of_speech": "noun/verb/adjective/adverb/etc",
  "definition": "Clear, concise definition in 1-2 sentences",
  "example_usage": "Example sentence using the word, ideally relating to today's news",
  "origin": "Brief etymology or origin (1 sentence, optional)",
  "why_chosen": "1 sentence explaining why this word is interesting today",
  "related_trend": "The headline this word relates to"
}}"""

        response = self._call_groq(prompt, max_tokens=400)
        data = self._parse_json_response(response)

        if data and data.get('word'):
            return WordOfTheDay(
                word=data.get('word', ''),
                part_of_speech=data.get('part_of_speech', ''),
                definition=data.get('definition', ''),
                example_usage=data.get('example_usage', ''),
                origin=data.get('origin'),
                why_chosen=data.get('why_chosen'),
                related_trend=data.get('related_trend')
            )

        return None

    # =========================================================================
    # PHASE 3: Grokipedia Article of the Day
    # =========================================================================

    def _get_grokipedia_article(
        self,
        trends: List[Dict],
        keywords: List[str]
    ) -> Optional[GrokipediaArticle]:
        """
        Fetch a relevant Grokipedia article based on trending topics.

        Uses LLM to select the best topic, then fetches the article
        from the Grokipedia API.
        """
        # First, use LLM to select the best topic for lookup
        topic = self._select_grokipedia_topic(trends, keywords)

        if not topic:
            # Fallback: try the first trend's main keyword
            if keywords:
                topic = keywords[0].title()

        if not topic:
            return None

        # Try to fetch the article
        article = self._fetch_grokipedia_article(topic)

        if not article:
            # Try alternate topics
            alternate_topics = self._get_alternate_topics(trends, keywords, topic)
            for alt_topic in alternate_topics[:3]:
                article = self._fetch_grokipedia_article(alt_topic)
                if article:
                    break

        return article

    def _select_grokipedia_topic(
        self,
        trends: List[Dict],
        keywords: List[str]
    ) -> Optional[str]:
        """Use LLM to select the best topic for Grokipedia lookup."""
        # Build rich context for better topic selection
        rich_context = self._build_rich_context(trends, keywords, max_trends=12)

        prompt = f"""You are selecting an encyclopedia article topic that relates to today's news.

{rich_context}

Select ONE topic that would make an interesting encyclopedia article to feature alongside today's news.

SELECTION CRITERIA:
- Choose a broad, educational topic (not a specific news event)
- Topics like technologies, scientific concepts, historical events, notable people, places, or phenomena
- The topic should provide background context for understanding today's news
- Use Wikipedia-style article titles (e.g., "Artificial intelligence", "Climate change", "European Union")

Respond with ONLY a valid JSON object:
{{
  "topic": "Article Title in Title Case",
  "slug": "article_title_with_underscores",
  "reason": "1 sentence explaining why this topic is relevant today",
  "related_trend": "The headline this relates to"
}}"""

        response = self._call_groq(prompt, max_tokens=200)
        data = self._parse_json_response(response)

        if data and data.get('topic'):
            return data.get('topic')

        return None

    def _get_alternate_topics(
        self,
        trends: List[Dict],
        keywords: List[str],
        failed_topic: str
    ) -> List[str]:
        """Get alternate topics if the first one fails."""
        # Simple fallback: use top keywords as topics
        alternates = []
        for kw in keywords[:5]:
            topic = kw.title()
            if topic.lower() != failed_topic.lower():
                alternates.append(topic)
        return alternates

    def _fetch_grokipedia_article(self, topic: str) -> Optional[GrokipediaArticle]:
        """
        Fetch article from Grokipedia API.

        Uses the unofficial API at grokipedia-api.com
        """
        # Convert topic to slug format
        slug = topic.replace(' ', '_')
        url = f"{GROKIPEDIA_API_URL}/{slug}"

        try:
            response = self.session.get(url, timeout=15)

            if response.status_code == 404:
                logger.debug(f"Grokipedia article not found: {topic}")
                return None

            response.raise_for_status()
            data = response.json()

            # Extract content
            content = data.get('content_text', '')

            # Create summary from first ~500 chars, ending at sentence
            summary = self._create_summary(content, max_chars=500)

            if not summary:
                return None

            return GrokipediaArticle(
                title=data.get('title', topic),
                slug=data.get('slug', slug),
                url=data.get('url', f"https://grokipedia.com/page/{slug}"),
                summary=summary,
                word_count=data.get('word_count', 0),
                related_trend=topic
            )

        except requests.exceptions.RequestException as e:
            logger.warning(f"Grokipedia API error for '{topic}': {e}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Grokipedia response parse error: {e}")
            return None

    def _create_summary(self, content: str, max_chars: int = 500) -> str:
        """Create a clean summary from article content."""
        if not content:
            return ""

        # Clean up the content
        content = content.strip()

        # Take first portion
        if len(content) <= max_chars:
            summary = content
        else:
            # Try to end at a sentence boundary
            summary = content[:max_chars]

            # Find last sentence ending
            last_period = summary.rfind('. ')
            last_question = summary.rfind('? ')
            last_exclaim = summary.rfind('! ')

            last_sentence = max(last_period, last_question, last_exclaim)

            if last_sentence > max_chars * 0.5:  # At least half the content
                summary = summary[:last_sentence + 1]
            else:
                # Just add ellipsis
                summary = summary.rsplit(' ', 1)[0] + '...'

        return summary

    # =========================================================================
    # PHASE 4: Story Summaries
    # =========================================================================

    def _generate_story_summaries(
        self,
        trends: List[Dict]
    ) -> List[StorySummary]:
        """
        Generate concise summaries for top trending stories.

        Uses LLM to create engaging 15-25 word summaries.
        """
        if not trends:
            return []

        # Prepare story data
        stories = []
        for t in trends[:10]:
            title = t.get('title', '')
            source = t.get('source', '').replace('_', ' ').title()
            desc = t.get('description', '')[:200] if t.get('description') else ''
            stories.append({
                'title': title,
                'source': source,
                'description': desc
            })

        prompt = f"""You are a news editor writing brief, engaging summaries for trending stories.

STORIES TO SUMMARIZE:
{json.dumps(stories, indent=2)}

For each story, write a concise 15-25 word summary that:
- Captures the key information
- Is engaging and informative
- Works as a standalone description
- Uses active voice

Respond with ONLY a valid JSON object:
{{
  "summaries": [
    {{"title": "Original title", "summary": "Your 15-25 word summary", "source": "Source Name"}},
    ...
  ]
}}"""

        response = self._call_groq(prompt, max_tokens=800)
        data = self._parse_json_response(response)

        summaries = []
        if data and data.get('summaries'):
            for item in data['summaries']:
                if item.get('title') and item.get('summary'):
                    summaries.append(StorySummary(
                        title=item.get('title', ''),
                        summary=item.get('summary', ''),
                        source=item.get('source', '')
                    ))

        return summaries


def enrich_content(
    trends: List[Dict],
    keywords: List[str],
    groq_key: Optional[str] = None
) -> EnrichedContent:
    """
    Convenience function to enrich content.

    Args:
        trends: List of trend dictionaries
        keywords: List of extracted keywords
        groq_key: Optional Groq API key (defaults to env var)

    Returns:
        EnrichedContent with all enriched features
    """
    enricher = ContentEnricher(groq_key=groq_key)
    return enricher.enrich(trends, keywords)
