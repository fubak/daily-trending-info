"""Unified HTTP client for OpenAI chat-completions-compatible LLM providers.

All four of Groq, OpenRouter, OpenCode, and Mistral speak the same wire format:
POST {"model": ..., "messages": [...], "max_tokens": ..., "temperature": ...}
→ {"choices": [{"message": {"content": ...}}]}

This module encodes each provider as a ProviderSpec and provides a single
call_openai_compatible() function that handles rate-limit checks, retry-after
headers, proactive throttling, and response parsing uniformly.

Google AI and HuggingFace use different wire formats and stay in editorial_generator.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

logger = logging.getLogger("llm_client")


@dataclass
class ProviderSpec:
    """Descriptor for one OpenAI-compatible LLM provider."""

    name: str
    endpoint: str
    models: List[str]
    extra_headers: Dict[str, str] = field(default_factory=dict)
    use_min_call_interval: bool = False


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

GROQ_SPEC = ProviderSpec(
    name="groq",
    endpoint="https://api.groq.com/openai/v1/chat/completions",
    models=["llama-3.3-70b-versatile"],
    use_min_call_interval=True,
)

OPENROUTER_SPEC = ProviderSpec(
    name="openrouter",
    endpoint="https://openrouter.ai/api/v1/chat/completions",
    models=[
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1-0528:free",
        "google/gemma-3-27b-it:free",
    ],
    extra_headers={
        "HTTP-Referer": "https://dailytrending.info",
        "X-Title": "DailyTrending.info",
    },
)

OPENCODE_SPEC = ProviderSpec(
    name="opencode",
    endpoint="https://opencode.ai/zen/v1/chat/completions",
    models=["glm-4.7-free", "minimax-m2.1-free"],
    use_min_call_interval=True,
)

MISTRAL_SPEC = ProviderSpec(
    name="mistral",
    endpoint="https://api.mistral.ai/v1/chat/completions",
    models=["mistral-small-latest", "open-mistral-7b"],
    use_min_call_interval=True,
)


# ---------------------------------------------------------------------------
# Shared call function
# ---------------------------------------------------------------------------

def call_openai_compatible(
    spec: ProviderSpec,
    api_key: Optional[str],
    prompt: str,
    max_tokens: int,
    max_retries: int,
    session: requests.Session,
    max_retry_wait: float,
    min_call_interval: float = 0.0,
    last_call_ref: Optional[List[float]] = None,
) -> Optional[str]:
    """Call a provider that speaks the OpenAI chat-completions wire format.

    Args:
        spec:              Provider descriptor.
        api_key:           Secret key for this provider (None → skip).
        prompt:            User prompt string.
        max_tokens:        Response length cap.
        max_retries:       Attempts per model before moving to the next.
        session:           Shared requests.Session.
        max_retry_wait:    Cap (seconds) on Retry-After waits.
        min_call_interval: Proactive gap between successive calls (seconds).
                           Only enforced when spec.use_min_call_interval is True.
        last_call_ref:     One-element list holding a float timestamp.
                           Updated in-place after each call attempt so the
                           caller can persist the value across provider methods.

    Returns:
        Text content string on success, None on all failures.
    """
    if not api_key:
        logger.info(f"No API key for {spec.name}, skipping")
        return None

    # Consult the shared rate-limiter if available.
    try:
        from rate_limiter import get_rate_limiter, check_before_call
        rate_limiter = get_rate_limiter()
        status = check_before_call(spec.name)
        if not status.is_available:
            logger.warning(f"{spec.name} not available: {status.error}")
            return None
        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for {spec.name} rate limit...")
            time.sleep(status.wait_seconds)
    except ImportError:
        rate_limiter = None

    for model in spec.models:
        for attempt in range(max_retries):
            # Proactive throttle: enforce a minimum gap between any two LLM calls.
            if spec.use_min_call_interval and last_call_ref is not None and min_call_interval > 0:
                elapsed = time.time() - last_call_ref[0]
                if elapsed < min_call_interval:
                    time.sleep(min_call_interval - elapsed)

            try:
                if last_call_ref is not None:
                    last_call_ref[0] = time.time()

                logger.info(f"Trying {spec.name}/{model} (attempt {attempt + 1}/{max_retries})")
                response = session.post(
                    spec.endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        **spec.extra_headers,
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

                if rate_limiter is not None:
                    rate_limiter.update_from_response_headers(spec.name, dict(response.headers))
                    rate_limiter._last_call_time[spec.name] = time.time()

                result = (
                    response.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )
                if result:
                    logger.info(f"{spec.name} success with {model}")
                    return result

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "10")
                    try:
                        wait_time = min(float(retry_after), max_retry_wait)
                    except ValueError:
                        wait_time = max_retry_wait
                    logger.warning(
                        f"{spec.name}/{model} rate limited, waiting {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                logger.warning(f"{spec.name}/{model} failed: {e}")
                break  # Try next model
            except (requests.RequestException, ValueError, KeyError, IndexError, AttributeError) as e:
                logger.warning(f"{spec.name}/{model} failed: {e}")
                break  # Try next model

    logger.warning(f"All {spec.name} models exhausted")
    return None
