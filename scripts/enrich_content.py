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

try:
    from rate_limiter import get_rate_limiter, check_before_call, mark_provider_exhausted, is_provider_exhausted
except ImportError:
    from scripts.rate_limiter import get_rate_limiter, check_before_call, mark_provider_exhausted, is_provider_exhausted

logger = logging.getLogger("pipeline")

# Grokipedia API endpoint (unofficial API wrapper)
GROKIPEDIA_API_URL = "https://grokipedia-api.com/page"

# JSON Schemas for Gemini structured outputs (guarantees valid JSON)
WORD_OF_DAY_SCHEMA = {
    "type": "object",
    "properties": {
        "word": {"type": "string", "description": "The selected word"},
        "part_of_speech": {"type": "string", "description": "Part of speech (noun/verb/adjective/adverb/etc)"},
        "definition": {"type": "string", "description": "Clear, concise definition in 1-2 sentences"},
        "example_usage": {"type": "string", "description": "Example sentence using the word"},
        "origin": {"type": "string", "description": "Brief etymology or origin (1 sentence)"},
        "why_chosen": {"type": "string", "description": "1 sentence explaining why this word is interesting today"},
        "related_trend": {"type": "string", "description": "The headline this word relates to"}
    },
    "required": ["word", "part_of_speech", "definition", "example_usage"]
}

GROKIPEDIA_TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "Article Title in Title Case"},
        "slug": {"type": "string", "description": "article_title_with_underscores"},
        "reason": {"type": "string", "description": "1 sentence explaining why this topic is relevant today"},
        "related_trend": {"type": "string", "description": "The headline this relates to"}
    },
    "required": ["topic", "slug"]
}

STORY_SUMMARIES_SCHEMA = {
    "type": "object",
    "properties": {
        "summaries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Original title"},
                    "summary": {"type": "string", "description": "15-25 word summary"},
                    "source": {"type": "string", "description": "Source name"}
                },
                "required": ["title", "summary"]
            }
        }
    },
    "required": ["summaries"]
}


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

    # Rate limiting: minimum seconds between API calls to stay under 30 req/min
    MIN_CALL_INTERVAL = 3.0
    MAX_RETRY_WAIT = 10  # Cap retry waits to prevent long delays

    def __init__(self, groq_key: Optional[str] = None, openrouter_key: Optional[str] = None, google_key: Optional[str] = None):
        self.groq_key = groq_key or os.getenv('GROQ_API_KEY')
        self.openrouter_key = openrouter_key or os.getenv('OPENROUTER_API_KEY')
        self.google_key = google_key or os.getenv('GOOGLE_AI_API_KEY')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DailyTrending.info/1.0 (Content Enrichment)'
        })
        self._last_call_time = 0.0  # Track last API call for rate limiting

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

    def _call_groq(self, prompt: str, max_tokens: int = 500, max_retries: int = 1, task_complexity: str = 'simple') -> Optional[str]:
        """
        Call LLM API with smart provider routing based on task complexity.

        For simple tasks: OpenCode (free) > Mistral (free) > Hugging Face (free) > Groq > OpenRouter > Google AI
        For complex tasks: Mistral > Google AI > OpenRouter > OpenCode > Hugging Face > Groq
        """
        if task_complexity == 'simple':
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

    def _call_google_ai(self, prompt: str, max_tokens: int = 500, max_retries: int = 1) -> Optional[str]:
        """Call Google AI (Gemini) API - primary provider with generous free tier."""
        if not self.google_key:
            logger.info("No Google AI API key available, skipping to next provider")
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('google')

        if not status.is_available:
            logger.warning(f"Google AI not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for Google AI rate limit...")
            time.sleep(status.wait_seconds)

        # Use Gemini 2.5 Flash Lite - highest RPM (10) among free models
        model = "gemini-2.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for attempt in range(max_retries):
            try:
                logger.info(f"Trying Google AI {model} (attempt {attempt + 1}/{max_retries})")
                response = self.session.post(
                    url,
                    headers={
                        "x-goog-api-key": self.google_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": max_tokens,
                            "temperature": 0.7
                        }
                    },
                    timeout=60
                )
                response.raise_for_status()

                # Update rate limiter tracking
                rate_limiter._last_call_time['google'] = time.time()

                # Parse response
                data = response.json()
                candidates = data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        text = parts[0].get('text', '')
                        if text:
                            logger.info(f"Google AI success with {model}")
                            return text

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # Check if this is a quota exhaustion (daily limit) vs temporary rate limit
                    try:
                        error_data = response.json()
                        error_msg = str(error_data).lower()
                        if 'quota' in error_msg or 'exhausted' in error_msg or 'daily' in error_msg:
                            # This is a quota exhaustion - mark provider as exhausted
                            mark_provider_exhausted('google', 'daily quota exceeded')
                            return None
                    except Exception:
                        pass

                    # Temporary rate limit - wait and retry
                    retry_after = response.headers.get('Retry-After', '10')
                    try:
                        wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                    except ValueError:
                        wait_time = self.MAX_RETRY_WAIT
                    logger.warning(f"Google AI rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                logger.warning(f"Google AI failed: {e}")
                return None
            except Exception as e:
                logger.warning(f"Google AI failed: {e}")
                return None

        logger.warning("Google AI: Max retries exceeded")
        return None

    def _call_google_ai_structured(
        self,
        prompt: str,
        schema: Dict,
        max_tokens: int = 500,
        max_retries: int = 1
    ) -> Optional[Dict]:
        """
        Call Google AI with structured output (guaranteed valid JSON).

        Uses Gemini's response_schema parameter to ensure the response
        conforms to the provided JSON schema.
        """
        if not self.google_key:
            logger.info("No Google AI API key available for structured output")
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('google')

        if not status.is_available:
            logger.warning(f"Google AI not available for structured output: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for Google AI rate limit...")
            time.sleep(status.wait_seconds)

        model = "gemini-2.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for attempt in range(max_retries):
            try:
                logger.info(f"Trying Google AI structured output (attempt {attempt + 1}/{max_retries})")
                response = self.session.post(
                    url,
                    headers={
                        "x-goog-api-key": self.google_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": max_tokens,
                            "temperature": 0.7,
                            "responseMimeType": "application/json",
                            "responseSchema": schema
                        }
                    },
                    timeout=60
                )
                response.raise_for_status()

                # Update rate limiter tracking
                rate_limiter._last_call_time['google'] = time.time()

                # Parse response
                data = response.json()
                candidates = data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        text = parts[0].get('text', '')
                        if text:
                            # Parse the JSON - should be valid due to structured output
                            try:
                                result = json.loads(text)
                                logger.info("Google AI structured output success")
                                return result
                            except json.JSONDecodeError as je:
                                logger.warning(f"Google AI structured output JSON parse error: {je}")
                                # Retry with higher token limit if this was a truncation issue
                                if attempt < max_retries - 1:
                                    logger.info("Retrying with more tokens...")
                                    continue
                                return None

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # Check if this is a quota exhaustion (daily limit) vs temporary rate limit
                    try:
                        error_data = response.json()
                        error_msg = str(error_data).lower()
                        if 'quota' in error_msg or 'exhausted' in error_msg or 'daily' in error_msg:
                            # This is a quota exhaustion - mark provider as exhausted
                            mark_provider_exhausted('google', 'daily quota exceeded')
                            return None
                    except Exception:
                        pass

                    # Temporary rate limit - wait and retry
                    retry_after = response.headers.get('Retry-After', '10')
                    try:
                        wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                    except ValueError:
                        wait_time = self.MAX_RETRY_WAIT
                    logger.warning(f"Google AI rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                logger.warning(f"Google AI structured output failed: {e}")
                return None
            except Exception as e:
                logger.warning(f"Google AI structured output failed: {e}")
                return None

        logger.warning("Google AI structured output: Max retries exceeded")
        return None

    def _call_openrouter(self, prompt: str, max_tokens: int = 500, max_retries: int = 1) -> Optional[str]:
        """Call OpenRouter API with free models (primary)."""
        if not self.openrouter_key:
            logger.warning("No OpenRouter API key available")
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('openrouter')

        if not status.is_available:
            logger.warning(f"OpenRouter not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for OpenRouter rate limit...")
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
                    logger.info(f"Trying OpenRouter {model} (attempt {attempt + 1}/{max_retries})")
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

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers('openrouter', dict(response.headers))

                    result = response.json().get('choices', [{}])[0].get('message', {}).get('content')
                    if result:
                        logger.info(f"OpenRouter success with {model}")
                        return result
                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        # Parse retry-after header if available
                        retry_after = response.headers.get('Retry-After', '10')
                        try:
                            wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                        except ValueError:
                            wait_time = self.MAX_RETRY_WAIT
                        logger.warning(f"OpenRouter {model} rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    logger.warning(f"OpenRouter {model} failed: {e}")
                    break  # Try next model
                except Exception as e:
                    logger.warning(f"OpenRouter {model} failed: {e}")
                    break  # Try next model

        logger.warning("All OpenRouter models failed")
        return None

    def _call_groq_direct(self, prompt: str, max_tokens: int = 500, max_retries: int = 1) -> Optional[str]:
        """Call Groq API directly (fallback)."""
        if not self.groq_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('groq')

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

                # Update rate limiter from response headers
                rate_limiter.update_from_response_headers('groq', dict(response.headers))

                return response.json().get('choices', [{}])[0].get('message', {}).get('content')
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # Parse retry-after header if available
                    retry_after = response.headers.get('Retry-After', '10')
                    try:
                        wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                    except ValueError:
                        wait_time = self.MAX_RETRY_WAIT
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

    def _call_opencode(self, prompt: str, max_tokens: int = 500, max_retries: int = 1) -> Optional[str]:
        """Call OpenCode API with free models (glm-4.7-free, minimax-m2.1-free)."""
        opencode_key = os.getenv('OPENCODE_API_KEY')
        if not opencode_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('opencode')

        if not status.is_available:
            logger.warning(f"OpenCode not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for OpenCode rate limit...")
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
                    logger.info(f"Trying OpenCode {model} (attempt {attempt + 1}/{max_retries})")
                    response = self.session.post(
                        "https://opencode.ai/zen/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {opencode_key}",
                            "Content-Type": "application/json"
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

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers('opencode', dict(response.headers))
                    rate_limiter._last_call_time['opencode'] = time.time()

                    result = response.json().get('choices', [{}])[0].get('message', {}).get('content')
                    if result:
                        logger.info(f"OpenCode success with {model}")
                        return result

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        retry_after = response.headers.get('Retry-After', '10')
                        try:
                            wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                        except ValueError:
                            wait_time = self.MAX_RETRY_WAIT
                        logger.warning(f"OpenCode rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    logger.warning(f"OpenCode API error with {model}: {e}")
                    break  # Try next model
                except Exception as e:
                    logger.warning(f"OpenCode API error with {model}: {e}")
                    break  # Try next model

        logger.warning("All OpenCode models failed")
        return None

    def _call_huggingface(self, prompt: str, max_tokens: int = 500, max_retries: int = 1) -> Optional[str]:
        """Call Hugging Face Inference API with free models."""
        huggingface_key = os.getenv('HUGGINGFACE_API_KEY')
        if not huggingface_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('huggingface')

        if not status.is_available:
            logger.warning(f"Hugging Face not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for Hugging Face rate limit...")
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
                    logger.info(f"Trying Hugging Face {model} (attempt {attempt + 1}/{max_retries})")
                    response = self.session.post(
                        f"https://api-inference.huggingface.co/models/{model}",
                        headers={
                            "Authorization": f"Bearer {huggingface_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "inputs": prompt,
                            "parameters": {
                                "max_new_tokens": max_tokens,
                                "temperature": 0.7,
                                "return_full_text": False
                            }
                        },
                        timeout=60
                    )
                    response.raise_for_status()

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers('huggingface', dict(response.headers))
                    rate_limiter._last_call_time['huggingface'] = time.time()

                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        text = result[0].get('generated_text', '')
                        if text:
                            logger.info(f"Hugging Face success with {model}")
                            return text

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        retry_after = response.headers.get('Retry-After', '10')
                        try:
                            wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                        except ValueError:
                            wait_time = self.MAX_RETRY_WAIT
                        logger.warning(f"Hugging Face rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    elif response.status_code == 503:
                        # Model is loading, wait and retry
                        logger.warning(f"Hugging Face model {model} is loading, waiting {self.MAX_RETRY_WAIT}s...")
                        time.sleep(self.MAX_RETRY_WAIT)
                        continue
                    logger.warning(f"Hugging Face API error with {model}: {e}")
                    break  # Try next model
                except Exception as e:
                    logger.warning(f"Hugging Face API error with {model}: {e}")
                    break  # Try next model

        logger.warning("All Hugging Face models failed")
        return None

    def _call_mistral(self, prompt: str, max_tokens: int = 500, max_retries: int = 1) -> Optional[str]:
        """Call Mistral AI API - high quality free tier models."""
        mistral_key = os.getenv('MISTRAL_API_KEY')
        if not mistral_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('mistral')

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
                    logger.info(f"Trying Mistral {model} (attempt {attempt + 1}/{max_retries})")
                    response = self.session.post(
                        "https://api.mistral.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {mistral_key}",
                            "Content-Type": "application/json"
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

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers('mistral', dict(response.headers))
                    rate_limiter._last_call_time['mistral'] = time.time()

                    result = response.json().get('choices', [{}])[0].get('message', {}).get('content')
                    if result:
                        logger.info(f"Mistral success with {model}")
                        return result

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        retry_after = response.headers.get('Retry-After', '10')
                        try:
                            wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                        except ValueError:
                            wait_time = self.MAX_RETRY_WAIT
                        logger.warning(f"Mistral rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
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
        json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
        json_str = re.sub(r'}\s*\n\s*{', '},\n{', json_str)
        json_str = re.sub(r']\s*\n\s*\[', '],\n[', json_str)
        json_str = re.sub(r'"\s*\n\s*{', '",\n{', json_str)
        json_str = re.sub(r'}\s*\n\s*"', '},\n"', json_str)
        json_str = re.sub(r'"\s*\n\s*\[', '",\n[', json_str)
        json_str = re.sub(r']\s*\n\s*"', '],\n"', json_str)

        # Fix missing comma after value before next key
        json_str = re.sub(r'"\s+("[\w]+"\s*:)', r'", \1', json_str)

        # Fix trailing commas before closing brackets
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)

        return json_str

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
                json_str = json_match.group()
                # Try parsing as-is first
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
                def escape_string_contents(match):
                    s = match.group(0)
                    inner = s[1:-1]  # Remove quotes
                    # Only escape raw control characters
                    inner = inner.replace('\n', '\\n')
                    inner = inner.replace('\r', '\\r')
                    inner = inner.replace('\t', '\\t')
                    inner = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', lambda m: f'\\u{ord(m.group()):04x}', inner)
                    return f'"{inner}"'

                try:
                    sanitized = re.sub(r'"(?:[^"\\]|\\.)*"', escape_string_contents, json_str)
                    return json.loads(sanitized)
                except (json.JSONDecodeError, Exception):
                    pass

                # Try repair + escape combination
                try:
                    repaired = self._repair_json(json_str)
                    sanitized = re.sub(r'"(?:[^"\\]|\\.)*"', escape_string_contents, repaired)
                    return json.loads(sanitized)
                except (json.JSONDecodeError, Exception):
                    pass

                # Last resort: strip all control chars except structural whitespace
                try:
                    stripped = re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f]', ' ', json_str)
                    repaired = self._repair_json(stripped)
                    return json.loads(repaired)
                except (json.JSONDecodeError, Exception):
                    pass

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

Return a JSON object with word, part_of_speech, definition, example_usage, origin, why_chosen, and related_trend."""

        # Try structured output first (guaranteed valid JSON)
        data = self._call_google_ai_structured(prompt, WORD_OF_DAY_SCHEMA, max_tokens=400)

        # Fallback to regular LLM call with JSON parsing
        if not data:
            prompt_with_json = prompt + """

Respond with ONLY a valid JSON object:
{
  "word": "selected word",
  "part_of_speech": "noun/verb/adjective/adverb/etc",
  "definition": "Clear, concise definition in 1-2 sentences",
  "example_usage": "Example sentence using the word, ideally relating to today's news",
  "origin": "Brief etymology or origin (1 sentence, optional)",
  "why_chosen": "1 sentence explaining why this word is interesting today",
  "related_trend": "The headline this word relates to"
}"""
            response = self._call_groq(prompt_with_json, max_tokens=400)
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

Return a JSON object with topic, slug, reason, and related_trend."""

        # Try structured output first (guaranteed valid JSON)
        data = self._call_google_ai_structured(prompt, GROKIPEDIA_TOPIC_SCHEMA, max_tokens=200)

        # Fallback to regular LLM call with JSON parsing
        if not data:
            prompt_with_json = prompt + """

Respond with ONLY a valid JSON object:
{
  "topic": "Article Title in Title Case",
  "slug": "article_title_with_underscores",
  "reason": "1 sentence explaining why this topic is relevant today",
  "related_trend": "The headline this relates to"
}"""
            response = self._call_groq(prompt_with_json, max_tokens=200)
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

Return a JSON object with a summaries array containing objects with title, summary, and source fields."""

        # Try structured output first (guaranteed valid JSON)
        data = self._call_google_ai_structured(prompt, STORY_SUMMARIES_SCHEMA, max_tokens=1200, max_retries=2)

        # Fallback to regular LLM call with JSON parsing
        if not data:
            prompt_with_json = prompt + """

Respond with ONLY a valid JSON object:
{
  "summaries": [
    {"title": "Original title", "summary": "Your 15-25 word summary", "source": "Source Name"},
    ...
  ]
}"""
            response = self._call_groq(prompt_with_json, max_tokens=800)
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
