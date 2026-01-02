#!/usr/bin/env python3
"""
Rate Limiter Module - Manages API rate limits for Google AI, OpenRouter, and Groq.

Checks rate limits before making API calls and implements backoff strategies.
"""

import os
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Tuple
import requests

logger = logging.getLogger(__name__)


@dataclass
class RateLimitStatus:
    """Rate limit status for an API."""
    requests_remaining: Optional[int] = None
    requests_limit: Optional[int] = None
    tokens_remaining: Optional[int] = None
    tokens_limit: Optional[int] = None
    reset_time: Optional[datetime] = None
    is_available: bool = True
    wait_seconds: float = 0.0
    error: Optional[str] = None


class RateLimiter:
    """Manages rate limits for Google AI, OpenRouter, Groq, OpenCode, Hugging Face, Mistral, and Anthropic APIs."""

    # Minimum wait between API calls (seconds)
    MIN_CALL_INTERVAL = 2.0  # Reduced for Google AI's generous limits

    # Thresholds for rate limit warnings
    REQUEST_THRESHOLD_PERCENT = 10  # Warn when less than 10% requests remaining
    TOKEN_THRESHOLD_PERCENT = 10    # Warn when less than 10% tokens remaining

    def __init__(
        self,
        google_key: Optional[str] = None,
        openrouter_key: Optional[str] = None,
        groq_key: Optional[str] = None,
        opencode_key: Optional[str] = None,
        huggingface_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        mistral_key: Optional[str] = None
    ):
        self.google_key = google_key or os.getenv('GOOGLE_AI_API_KEY')
        self.openrouter_key = openrouter_key or os.getenv('OPENROUTER_API_KEY')
        self.groq_key = groq_key or os.getenv('GROQ_API_KEY')
        self.opencode_key = opencode_key or os.getenv('OPENCODE_API_KEY')
        self.huggingface_key = huggingface_key or os.getenv('HUGGINGFACE_API_KEY')
        self.anthropic_key = anthropic_key or os.getenv('ANTHROPIC_API_KEY')
        self.mistral_key = mistral_key or os.getenv('MISTRAL_API_KEY')
        self.session = requests.Session()

        # Track last call times per provider
        self._last_call_time: Dict[str, float] = {
            'google': 0.0,
            'openrouter': 0.0,
            'groq': 0.0,
            'opencode': 0.0,
            'huggingface': 0.0,
            'anthropic': 0.0,
            'mistral': 0.0
        }

        # Cache rate limit status
        self._rate_limit_cache: Dict[str, Tuple[RateLimitStatus, float]] = {}
        self._cache_ttl = 30  # Cache for 30 seconds

    def check_google_limits(self, force_refresh: bool = False) -> RateLimitStatus:
        """
        Check Google AI rate limits before making a call.

        Google AI has very generous limits (1M tokens/min, 1500 req/day for free tier).
        We mainly track call timing to avoid bursts.

        Returns:
            RateLimitStatus with availability info
        """
        if not self.google_key:
            return RateLimitStatus(
                is_available=False,
                error="No Google AI API key configured"
            )

        # Check cache
        cache_key = 'google'
        if not force_refresh and cache_key in self._rate_limit_cache:
            cached_status, cached_time = self._rate_limit_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_status

        # Google AI doesn't have a rate limit check endpoint
        # We track timing and rely on response headers/errors
        elapsed = time.time() - self._last_call_time.get('google', 0)

        status = RateLimitStatus(is_available=True)

        # Ensure minimum interval between calls
        if elapsed < self.MIN_CALL_INTERVAL:
            status.wait_seconds = self.MIN_CALL_INTERVAL - elapsed

        self._rate_limit_cache[cache_key] = (status, time.time())
        return status

    def check_openrouter_limits(self, force_refresh: bool = False) -> RateLimitStatus:
        """
        Check OpenRouter rate limits before making a call.

        Returns:
            RateLimitStatus with availability and wait time info
        """
        if not self.openrouter_key:
            return RateLimitStatus(
                is_available=False,
                error="No OpenRouter API key configured"
            )

        # Check cache
        cache_key = 'openrouter'
        if not force_refresh and cache_key in self._rate_limit_cache:
            cached_status, cached_time = self._rate_limit_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_status

        try:
            # Check OpenRouter API key limits endpoint
            # Docs: https://openrouter.ai/docs/api/reference/limits
            response = self.session.get(
                "https://openrouter.ai/api/v1/key",
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json().get('data', {})

                # Extract rate limit info
                rate_limit = data.get('rate_limit', {})
                requests_remaining = rate_limit.get('requests')
                interval = rate_limit.get('interval', 'minute')

                # Check usage
                usage = data.get('usage', 0)
                limit = data.get('limit', None)

                status = RateLimitStatus(
                    requests_remaining=requests_remaining,
                    is_available=True
                )

                # Check if we're running low on requests
                if requests_remaining is not None and requests_remaining < 5:
                    status.wait_seconds = 60  # Wait a minute if low on requests
                    logger.warning(f"OpenRouter: Only {requests_remaining} requests remaining")

                # Check if usage is approaching limit
                if limit is not None and usage is not None:
                    usage_percent = (usage / limit) * 100 if limit > 0 else 0
                    if usage_percent > 90:
                        logger.warning(f"OpenRouter: {usage_percent:.1f}% of credit limit used")
                        status.is_available = False
                        status.error = f"Usage at {usage_percent:.1f}% of limit"

                # Cache the result
                self._rate_limit_cache[cache_key] = (status, time.time())
                return status

            elif response.status_code == 429:
                # Already rate limited
                retry_after = response.headers.get('Retry-After', '10')
                try:
                    wait_seconds = float(retry_after)
                except ValueError:
                    wait_seconds = 10.0

                status = RateLimitStatus(
                    is_available=False,
                    wait_seconds=wait_seconds,
                    error="Rate limited"
                )
                self._rate_limit_cache[cache_key] = (status, time.time())
                return status

            else:
                logger.warning(f"OpenRouter rate limit check failed: {response.status_code}")
                # Assume available but unknown status
                return RateLimitStatus(is_available=True)

        except Exception as e:
            logger.warning(f"Failed to check OpenRouter rate limits: {e}")
            # Assume available on error
            return RateLimitStatus(is_available=True)

    def check_groq_limits(self, force_refresh: bool = False) -> RateLimitStatus:
        """
        Check Groq rate limits.

        Groq doesn't have a dedicated rate limit endpoint, so we track from response headers.

        Returns:
            RateLimitStatus with availability info
        """
        if not self.groq_key:
            return RateLimitStatus(
                is_available=False,
                error="No Groq API key configured"
            )

        # Check cache
        cache_key = 'groq'
        if not force_refresh and cache_key in self._rate_limit_cache:
            cached_status, cached_time = self._rate_limit_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_status

        # Groq rate limits are typically:
        # - Free tier: 30 requests/minute, 6000 tokens/minute
        # We track this from response headers after each call

        # For now, check if we should wait based on last call time
        elapsed = time.time() - self._last_call_time.get('groq', 0)

        if elapsed < self.MIN_CALL_INTERVAL:
            wait_seconds = self.MIN_CALL_INTERVAL - elapsed
            return RateLimitStatus(
                is_available=True,
                wait_seconds=wait_seconds
            )

        return RateLimitStatus(is_available=True)

    def check_opencode_limits(self, force_refresh: bool = False) -> RateLimitStatus:
        """
        Check OpenCode rate limits.

        OpenCode offers free models with generous limits.
        We track timing to avoid bursts.

        Returns:
            RateLimitStatus with availability info
        """
        if not self.opencode_key:
            return RateLimitStatus(
                is_available=False,
                error="No OpenCode API key configured"
            )

        # Check cache
        cache_key = 'opencode'
        if not force_refresh and cache_key in self._rate_limit_cache:
            cached_status, cached_time = self._rate_limit_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_status

        # For now, check if we should wait based on last call time
        elapsed = time.time() - self._last_call_time.get('opencode', 0)

        if elapsed < self.MIN_CALL_INTERVAL:
            wait_seconds = self.MIN_CALL_INTERVAL - elapsed
            return RateLimitStatus(
                is_available=True,
                wait_seconds=wait_seconds
            )

        return RateLimitStatus(is_available=True)

    def check_huggingface_limits(self, force_refresh: bool = False) -> RateLimitStatus:
        """
        Check Hugging Face rate limits.

        Hugging Face Inference API has generous free tier (~few hundred requests/hour).
        We track timing to avoid bursts.

        Returns:
            RateLimitStatus with availability info
        """
        if not self.huggingface_key:
            return RateLimitStatus(
                is_available=False,
                error="No Hugging Face API key configured"
            )

        # Check cache
        cache_key = 'huggingface'
        if not force_refresh and cache_key in self._rate_limit_cache:
            cached_status, cached_time = self._rate_limit_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_status

        # For now, check if we should wait based on last call time
        elapsed = time.time() - self._last_call_time.get('huggingface', 0)

        if elapsed < self.MIN_CALL_INTERVAL:
            wait_seconds = self.MIN_CALL_INTERVAL - elapsed
            return RateLimitStatus(
                is_available=True,
                wait_seconds=wait_seconds
            )

        return RateLimitStatus(is_available=True)

    def check_anthropic_limits(self, force_refresh: bool = False) -> RateLimitStatus:
        """
        Check Anthropic rate limits.

        Anthropic has rate limits based on tier (free tier: 5 RPM, 10K TPM).
        We track timing to avoid bursts.

        Returns:
            RateLimitStatus with availability info
        """
        if not self.anthropic_key:
            return RateLimitStatus(
                is_available=False,
                error="No Anthropic API key configured"
            )

        # Check cache
        cache_key = 'anthropic'
        if not force_refresh and cache_key in self._rate_limit_cache:
            cached_status, cached_time = self._rate_limit_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_status

        # For now, check if we should wait based on last call time
        # Anthropic free tier is 5 RPM, so we need 12 seconds between calls
        elapsed = time.time() - self._last_call_time.get('anthropic', 0)
        min_interval = 12.0  # 5 RPM = 12 seconds between calls

        if elapsed < min_interval:
            wait_seconds = min_interval - elapsed
            return RateLimitStatus(
                is_available=True,
                wait_seconds=wait_seconds
            )

        return RateLimitStatus(is_available=True)

    def check_mistral_limits(self, force_refresh: bool = False) -> RateLimitStatus:
        """
        Check Mistral AI rate limits.

        Mistral has generous free tier limits.
        We track timing to avoid bursts.

        Returns:
            RateLimitStatus with availability info
        """
        if not self.mistral_key:
            return RateLimitStatus(
                is_available=False,
                error="No Mistral API key configured"
            )

        # Check cache
        cache_key = 'mistral'
        if not force_refresh and cache_key in self._rate_limit_cache:
            cached_status, cached_time = self._rate_limit_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_status

        # For now, check if we should wait based on last call time
        elapsed = time.time() - self._last_call_time.get('mistral', 0)

        if elapsed < self.MIN_CALL_INTERVAL:
            wait_seconds = self.MIN_CALL_INTERVAL - elapsed
            return RateLimitStatus(
                is_available=True,
                wait_seconds=wait_seconds
            )

        return RateLimitStatus(is_available=True)

    def update_from_response_headers(
        self,
        provider: str,
        headers: Dict[str, str]
    ) -> None:
        """
        Update rate limit status from API response headers.

        Args:
            provider: 'openrouter', 'groq', 'opencode', 'huggingface', or 'mistral'
            headers: Response headers from API call
        """
        status = RateLimitStatus(is_available=True)

        # Common rate limit headers
        remaining_requests = headers.get('x-ratelimit-remaining-requests')
        limit_requests = headers.get('x-ratelimit-limit-requests')
        remaining_tokens = headers.get('x-ratelimit-remaining-tokens')
        limit_tokens = headers.get('x-ratelimit-limit-tokens')
        reset_time = headers.get('x-ratelimit-reset-requests')

        if remaining_requests is not None:
            try:
                status.requests_remaining = int(remaining_requests)
            except ValueError:
                pass

        if limit_requests is not None:
            try:
                status.requests_limit = int(limit_requests)
            except ValueError:
                pass

        if remaining_tokens is not None:
            try:
                status.tokens_remaining = int(remaining_tokens)
            except ValueError:
                pass

        if limit_tokens is not None:
            try:
                status.tokens_limit = int(limit_tokens)
            except ValueError:
                pass

        # Check if we're running low
        if status.requests_remaining is not None and status.requests_limit is not None:
            if status.requests_limit > 0:
                remaining_percent = (status.requests_remaining / status.requests_limit) * 100
                if remaining_percent < self.REQUEST_THRESHOLD_PERCENT:
                    logger.warning(
                        f"{provider}: Only {status.requests_remaining}/{status.requests_limit} "
                        f"requests remaining ({remaining_percent:.1f}%)"
                    )
                    status.wait_seconds = 60  # Wait a minute

        if status.tokens_remaining is not None and status.tokens_limit is not None:
            if status.tokens_limit > 0:
                remaining_percent = (status.tokens_remaining / status.tokens_limit) * 100
                if remaining_percent < self.TOKEN_THRESHOLD_PERCENT:
                    logger.warning(
                        f"{provider}: Only {status.tokens_remaining}/{status.tokens_limit} "
                        f"tokens remaining ({remaining_percent:.1f}%)"
                    )

        # Update last call time
        self._last_call_time[provider] = time.time()

        # Cache the status
        self._rate_limit_cache[provider] = (status, time.time())

    def wait_if_needed(self, provider: str) -> None:
        """
        Wait if necessary based on rate limits.

        Args:
            provider: 'google', 'openrouter', 'groq', 'opencode', 'huggingface', 'mistral', or 'anthropic'
        """
        if provider == 'google':
            status = self.check_google_limits()
        elif provider == 'openrouter':
            status = self.check_openrouter_limits()
        elif provider == 'opencode':
            status = self.check_opencode_limits()
        elif provider == 'huggingface':
            status = self.check_huggingface_limits()
        elif provider == 'mistral':
            status = self.check_mistral_limits()
        elif provider == 'anthropic':
            status = self.check_anthropic_limits()
        else:
            status = self.check_groq_limits()

        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for {provider} rate limit...")
            time.sleep(status.wait_seconds)

    def get_best_provider(self, task_complexity: str = 'simple') -> Optional[str]:
        """
        Get the best available provider based on rate limits and task complexity.

        For simple tasks: OpenCode (free) > Mistral (free) > Hugging Face (free) > Groq > OpenRouter > Google AI
        For complex tasks: Mistral > Google AI > OpenRouter > OpenCode > Hugging Face > Groq

        Note: Anthropic is disabled (no free tier) but tracking code is preserved.

        Args:
            task_complexity: 'simple' or 'complex'

        Returns:
            Provider name or None if none available
        """
        google_status = self.check_google_limits()
        openrouter_status = self.check_openrouter_limits()
        groq_status = self.check_groq_limits()
        opencode_status = self.check_opencode_limits()
        huggingface_status = self.check_huggingface_limits()
        mistral_status = self.check_mistral_limits()

        # Define priority order based on task complexity
        # Note: Anthropic excluded from routing (no free tier)
        if task_complexity == 'simple':
            # For simple tasks, prefer free models to save quota
            priority = [
                ('opencode', opencode_status),
                ('mistral', mistral_status),
                ('huggingface', huggingface_status),
                ('groq', groq_status),
                ('openrouter', openrouter_status),
                ('google', google_status),
            ]
        else:
            # For complex tasks, prefer higher quality models (Mistral is high quality)
            priority = [
                ('mistral', mistral_status),
                ('google', google_status),
                ('openrouter', openrouter_status),
                ('opencode', opencode_status),
                ('huggingface', huggingface_status),
                ('groq', groq_status),
            ]

        # Find first available with no wait
        for name, status in priority:
            if status.is_available and status.wait_seconds == 0:
                return name

        # If all need waiting, choose the one with shortest wait
        available = [(name, s) for name, s in priority if s.is_available]
        if available:
            available.sort(key=lambda x: x[1].wait_seconds)
            return available[0][0]

        return None

    def log_status(self) -> None:
        """Log current rate limit status for all providers."""
        google_status = self.check_google_limits()
        openrouter_status = self.check_openrouter_limits()
        groq_status = self.check_groq_limits()
        opencode_status = self.check_opencode_limits()
        huggingface_status = self.check_huggingface_limits()
        mistral_status = self.check_mistral_limits()
        anthropic_status = self.check_anthropic_limits()

        logger.info("=== Rate Limit Status ===")

        if self.google_key:
            logger.info(f"Google AI: available={google_status.is_available}, "
                       f"wait={google_status.wait_seconds:.1f}s")
        else:
            logger.info("Google AI: not configured")

        if self.openrouter_key:
            logger.info(f"OpenRouter: available={openrouter_status.is_available}, "
                       f"wait={openrouter_status.wait_seconds:.1f}s, "
                       f"requests_remaining={openrouter_status.requests_remaining}")
        else:
            logger.info("OpenRouter: not configured")

        if self.groq_key:
            logger.info(f"Groq: available={groq_status.is_available}, "
                       f"wait={groq_status.wait_seconds:.1f}s")
        else:
            logger.info("Groq: not configured")

        if self.opencode_key:
            logger.info(f"OpenCode: available={opencode_status.is_available}, "
                       f"wait={opencode_status.wait_seconds:.1f}s")
        else:
            logger.info("OpenCode: not configured")

        if self.huggingface_key:
            logger.info(f"Hugging Face: available={huggingface_status.is_available}, "
                       f"wait={huggingface_status.wait_seconds:.1f}s")
        else:
            logger.info("Hugging Face: not configured")

        if self.mistral_key:
            logger.info(f"Mistral: available={mistral_status.is_available}, "
                       f"wait={mistral_status.wait_seconds:.1f}s")
        else:
            logger.info("Mistral: not configured")

        if self.anthropic_key:
            logger.info(f"Anthropic: available={anthropic_status.is_available}, "
                       f"wait={anthropic_status.wait_seconds:.1f}s")
        else:
            logger.info("Anthropic: not configured")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def check_before_call(provider: str) -> RateLimitStatus:
    """
    Check rate limits before making an API call.

    Args:
        provider: 'google', 'openrouter', 'groq', 'opencode', 'huggingface', 'mistral', or 'anthropic'

    Returns:
        RateLimitStatus indicating if call is safe to make
    """
    limiter = get_rate_limiter()

    if provider == 'google':
        return limiter.check_google_limits()
    elif provider == 'openrouter':
        return limiter.check_openrouter_limits()
    elif provider == 'groq':
        return limiter.check_groq_limits()
    elif provider == 'opencode':
        return limiter.check_opencode_limits()
    elif provider == 'huggingface':
        return limiter.check_huggingface_limits()
    elif provider == 'mistral':
        return limiter.check_mistral_limits()
    elif provider == 'anthropic':
        return limiter.check_anthropic_limits()
    else:
        return RateLimitStatus(is_available=True)
