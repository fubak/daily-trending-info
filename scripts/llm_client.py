"""Unified HTTP client for OpenAI chat-completions-compatible LLM providers.

All four of Groq, OpenRouter, OpenCode, and Mistral speak the same wire format:
POST {"model": ..., "messages": [...], "max_tokens": ..., "temperature": ...}
→ {"choices": [{"message": {"content": ...}}]}

This module encodes each provider as a ProviderSpec and provides a single
call_openai_compatible() function that handles rate-limit checks, retry-after
headers, proactive throttling, and response parsing uniformly.

Google AI and HuggingFace use different wire formats and stay in editorial_generator.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

from config import LLM_MIN_CALL_INTERVAL, LLM_MAX_RETRY_WAIT
from json_utils import escape_control_chars_in_strings

try:
    from rate_limiter import (
        get_rate_limiter,
        check_before_call,
        mark_provider_exhausted,
    )
except ImportError:  # pragma: no cover - import path fallback
    from scripts.rate_limiter import (
        get_rate_limiter,
        check_before_call,
        mark_provider_exhausted,
    )

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


# ---------------------------------------------------------------------------
# Shared base class for LLM-backed generators
# ---------------------------------------------------------------------------
#
# EditorialGenerator and ContentEnricher both drive the same LLM providers with
# identical routing, Google AI / HuggingFace wire formats, and JSON
# parsing/repair logic. That logic lived duplicated (~500 lines) in both
# modules; it now lives here once. Subclasses set the instance attributes
# session / groq_key / openrouter_key / google_key / _last_call_time in their
# __init__ and may override the DEFAULT_* class attributes below.


class LLMClientBase:
    """Mixin: provider routing + JSON parsing shared by LLM generators."""

    MIN_CALL_INTERVAL = LLM_MIN_CALL_INTERVAL
    MAX_RETRY_WAIT = LLM_MAX_RETRY_WAIT

    # Routing defaults used when a caller omits the argument. Editorial favours
    # high-quality "complex" routing; enrichment favours cheap "simple" routing.
    DEFAULT_MAX_TOKENS = 500
    DEFAULT_TASK_COMPLEXITY = "simple"

    def _call_groq(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        max_retries: int = 1,
        task_complexity: Optional[str] = None,
    ) -> Optional[str]:
        """
        Call LLM API with smart provider routing based on task complexity.

        For simple tasks: OpenCode (free) > Mistral (free) > Hugging Face (free) > Groq > OpenRouter > Google AI
        For complex tasks: Mistral > Google AI > OpenRouter > OpenCode > Hugging Face > Groq
        """
        if max_tokens is None:
            max_tokens = self.DEFAULT_MAX_TOKENS
        if task_complexity is None:
            task_complexity = self.DEFAULT_TASK_COMPLEXITY
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

    def _call_openrouter(
        self, prompt: str, max_tokens: int = 500, max_retries: int = 1
    ) -> Optional[str]:
        return call_openai_compatible(
            OPENROUTER_SPEC,
            self.openrouter_key,
            prompt,
            max_tokens,
            max_retries,
            self.session,
            self.MAX_RETRY_WAIT,
        )

    def _call_groq_direct(
        self, prompt: str, max_tokens: int = 500, max_retries: int = 1
    ) -> Optional[str]:
        timing = [self._last_call_time]
        result = call_openai_compatible(
            GROQ_SPEC,
            self.groq_key,
            prompt,
            max_tokens,
            max_retries,
            self.session,
            self.MAX_RETRY_WAIT,
            self.MIN_CALL_INTERVAL,
            timing,
        )
        self._last_call_time = timing[0]
        return result

    def _call_opencode(
        self, prompt: str, max_tokens: int = 500, max_retries: int = 1
    ) -> Optional[str]:
        opencode_key = os.getenv("OPENCODE_API_KEY")
        timing = [self._last_call_time]
        result = call_openai_compatible(
            OPENCODE_SPEC,
            opencode_key,
            prompt,
            max_tokens,
            max_retries,
            self.session,
            self.MAX_RETRY_WAIT,
            self.MIN_CALL_INTERVAL,
            timing,
        )
        self._last_call_time = timing[0]
        return result

    def _call_mistral(
        self, prompt: str, max_tokens: int = 500, max_retries: int = 1
    ) -> Optional[str]:
        mistral_key = os.getenv("MISTRAL_API_KEY")
        timing = [self._last_call_time]
        result = call_openai_compatible(
            MISTRAL_SPEC,
            mistral_key,
            prompt,
            max_tokens,
            max_retries,
            self.session,
            self.MAX_RETRY_WAIT,
            self.MIN_CALL_INTERVAL,
            timing,
        )
        self._last_call_time = timing[0]
        return result

    def _call_google_ai(
        self, prompt: str, max_tokens: int = 500, max_retries: int = 1
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
                        logger.debug(
                            f"Could not parse 429 body for quota check: {parse_err}"
                        )

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
                logger.warning(f"Google AI failed: {e}")
                return None
            except (
                requests.RequestException,
                json.JSONDecodeError,
                KeyError,
                ValueError,
                AttributeError,
            ) as e:
                logger.warning(f"Google AI failed: {e}")
                return None

        logger.warning("Google AI: Max retries exceeded")
        return None

    def _call_google_ai_structured(
        self, prompt: str, schema: Dict, max_tokens: int = 500, max_retries: int = 1
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
        status = check_before_call("google")

        if not status.is_available:
            logger.warning(
                f"Google AI not available for structured output: {status.error}"
            )
            return None

        if status.wait_seconds > 0:
            logger.info(
                f"Waiting {status.wait_seconds:.1f}s for Google AI rate limit..."
            )
            time.sleep(status.wait_seconds)

        model = "gemini-2.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Trying Google AI structured output (attempt {attempt + 1}/{max_retries})"
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
                            "responseMimeType": "application/json",
                            "responseSchema": schema,
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
                            # Parse the JSON - should be valid due to structured output
                            try:
                                result = json.loads(text)
                                logger.info("Google AI structured output success")
                                return result
                            except json.JSONDecodeError as je:
                                logger.warning(
                                    f"Google AI structured output JSON parse error: {je}"
                                )
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
                        if (
                            "quota" in error_msg
                            or "exhausted" in error_msg
                            or "daily" in error_msg
                        ):
                            # This is a quota exhaustion - mark provider as exhausted
                            mark_provider_exhausted("google", "daily quota exceeded")
                            return None
                    except (ValueError, KeyError) as parse_err:
                        logger.debug(
                            f"Could not parse 429 body for quota check: {parse_err}"
                        )

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
                logger.warning(f"Google AI structured output failed: {e}")
                return None
            except (
                requests.RequestException,
                json.JSONDecodeError,
                KeyError,
                ValueError,
                AttributeError,
            ) as e:
                logger.warning(f"Google AI structured output failed: {e}")
                return None

        logger.warning("Google AI structured output: Max retries exceeded")
        return None

    def _call_huggingface(
        self, prompt: str, max_tokens: int = 500, max_retries: int = 1
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
                except (
                    requests.RequestException,
                    json.JSONDecodeError,
                    KeyError,
                    ValueError,
                    AttributeError,
                ) as e:
                    logger.warning(f"Hugging Face API error with {model}: {e}")
                    break  # Try next model

        logger.warning("All Hugging Face models failed")
        return None

    def _repair_json(self, json_str: str) -> str:
        """Attempt to repair common JSON formatting issues from LLM output."""
        # Fix missing commas between elements (common LLM error)
        json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
        json_str = re.sub(r"}\s*\n\s*{", "},\n{", json_str)
        json_str = re.sub(r"]\s*\n\s*\[", "],\n[", json_str)
        json_str = re.sub(r'"\s*\n\s*{', '",\n{', json_str)
        json_str = re.sub(r'}\s*\n\s*"', '},\n"', json_str)
        json_str = re.sub(r'"\s*\n\s*\[', '",\n[', json_str)
        json_str = re.sub(r']\s*\n\s*"', '],\n"', json_str)

        # Fix missing comma after value before next key
        json_str = re.sub(r'"\s+("[\w]+"\s*:)', r'", \1', json_str)

        # Fix trailing commas before closing brackets
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)

        return json_str

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if not response:
            return None

        try:
            # Remove markdown code blocks if present
            clean = re.sub(r"^```(?:json)?\s*", "", response.strip())
            clean = re.sub(r"\s*```$", "", clean)

            # Find JSON object
            json_match = re.search(r"\{.*\}", clean, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                # Try parsing as-is first
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.debug("JSON parse as-is failed: %s", e)

                # Try repairing common JSON issues (missing commas, etc.)
                try:
                    repaired = self._repair_json(json_str)
                    return json.loads(repaired)
                except json.JSONDecodeError as e:
                    logger.debug("JSON parse after repair failed: %s", e)

                # Escape raw control characters that appear inside quoted
                # strings (a common defect in LLM JSON output).
                try:
                    sanitized = escape_control_chars_in_strings(json_str)
                    return json.loads(sanitized)
                except json.JSONDecodeError as e:
                    logger.debug("JSON parse after control-char escape failed: %s", e)

                # Try repair + escape combination
                try:
                    repaired = self._repair_json(json_str)
                    sanitized = escape_control_chars_in_strings(repaired)
                    return json.loads(sanitized)
                except json.JSONDecodeError as e:
                    logger.debug("JSON parse after repair+escape failed: %s", e)

                # Last resort: strip all control chars except structural whitespace
                try:
                    stripped = re.sub(r"[\x00-\x09\x0b\x0c\x0e-\x1f]", " ", json_str)
                    repaired = self._repair_json(stripped)
                    return json.loads(repaired)
                except json.JSONDecodeError as e:
                    logger.debug("JSON parse last-resort failed: %s", e)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON parse error: {e}")

        return None
