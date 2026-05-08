"""Tests for rate_limiter (RateLimiter class + module helpers)."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from scripts.rate_limiter import (
    OpenRouterCredits,
    RateLimitStatus,
    RateLimiter,
    check_before_call,
    is_provider_exhausted,
    mark_provider_exhausted,
)


@pytest.fixture
def limiter():
    """A fresh RateLimiter with no API keys (so calls don't hit the network)."""
    return RateLimiter()


@pytest.fixture(autouse=True)
def reset_global_limiter():
    """Reset the module-level singleton between tests."""
    import scripts.rate_limiter as rl
    rl._rate_limiter = None
    yield
    rl._rate_limiter = None


# ---------------------------------------------------------------------------
# Dataclass sanity
# ---------------------------------------------------------------------------

class TestRateLimitStatusDefaults:

    def test_defaults_to_available(self):
        status = RateLimitStatus()
        assert status.is_available is True
        assert status.wait_seconds == 0.0
        assert status.error is None


class TestOpenRouterCreditsDefaults:

    def test_defaults_to_zero_usage(self):
        credits = OpenRouterCredits()
        assert credits.usage == 0.0
        assert credits.is_low is False


# ---------------------------------------------------------------------------
# Provider-exhaustion lifecycle (the critical mutex around 429 quota errors)
# ---------------------------------------------------------------------------

class TestProviderExhaustion:

    def test_initially_not_exhausted(self, limiter):
        assert limiter.is_provider_exhausted("google") is False
        assert limiter.is_provider_exhausted("openrouter") is False

    def test_mark_exhausted_persists(self, limiter):
        limiter.mark_provider_exhausted("google", "daily quota")
        assert limiter.is_provider_exhausted("google") is True

    def test_exhaustion_isolated_per_provider(self, limiter):
        limiter.mark_provider_exhausted("google", "daily quota")
        assert limiter.is_provider_exhausted("groq") is False
        assert limiter.is_provider_exhausted("openrouter") is False

    def test_get_exhausted_providers(self, limiter):
        limiter.mark_provider_exhausted("google")
        limiter.mark_provider_exhausted("groq")
        exhausted = limiter.get_exhausted_providers()
        assert "google" in exhausted
        assert "groq" in exhausted

    def test_reset_exhausted_providers(self, limiter):
        limiter.mark_provider_exhausted("google")
        limiter.reset_exhausted_providers()
        assert limiter.is_provider_exhausted("google") is False
        assert limiter.get_exhausted_providers() == set()

    def test_mark_exhausted_idempotent(self, limiter):
        # Marking twice should be a no-op the second time.
        limiter.mark_provider_exhausted("google", "first")
        limiter.mark_provider_exhausted("google", "second")
        assert limiter.is_provider_exhausted("google") is True


# ---------------------------------------------------------------------------
# Module-level helpers (the API used by editorial_generator/enrich_content).
# ---------------------------------------------------------------------------

class TestModuleHelpers:

    def test_check_before_call_returns_status(self):
        # Without any API keys configured, check_before_call should still
        # return a RateLimitStatus rather than raising.
        status = check_before_call("groq")
        assert isinstance(status, RateLimitStatus)

    def test_check_before_call_unknown_provider_is_available(self):
        status = check_before_call("nonexistent-provider")
        assert status.is_available is True

    def test_mark_then_is_exhausted(self):
        mark_provider_exhausted("openrouter", "test")
        assert is_provider_exhausted("openrouter") is True

    def test_check_before_call_blocks_exhausted_provider(self):
        mark_provider_exhausted("groq", "daily limit hit")
        status = check_before_call("groq")
        assert status.is_available is False
        assert "exhausted" in (status.error or "").lower()


# ---------------------------------------------------------------------------
# Header parsing (update_from_response_headers).
# ---------------------------------------------------------------------------

class TestUpdateFromResponseHeaders:

    def test_handles_groq_request_remaining(self, limiter):
        # Groq returns x-ratelimit-remaining-requests in response headers.
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-ratelimit-limit-requests": "1000",
        }
        # Should not raise.
        limiter.update_from_response_headers("groq", headers)

    def test_handles_openrouter_credits_headers(self, limiter):
        headers = {
            "x-ratelimit-remaining": "50",
            "x-ratelimit-limit": "200",
        }
        limiter.update_from_response_headers("openrouter", headers)

    def test_handles_unknown_provider(self, limiter):
        # An unknown provider shouldn't raise.
        limiter.update_from_response_headers("unknown", {"x-foo": "bar"})

    def test_handles_empty_headers(self, limiter):
        limiter.update_from_response_headers("groq", {})


# ---------------------------------------------------------------------------
# check_*_limits without an API key should return is_available=False/error.
# ---------------------------------------------------------------------------

class TestCheckLimitsWithoutKeys:

    def test_check_google_no_key(self, limiter):
        status = limiter.check_google_limits()
        assert isinstance(status, RateLimitStatus)
        # No key means we can't make a useful availability check; the
        # implementation should report the missing key rather than crash.
        assert status.is_available is False or status.error is not None

    def test_check_openrouter_no_key(self, limiter):
        status = limiter.check_openrouter_limits()
        assert isinstance(status, RateLimitStatus)

    def test_check_groq_no_key(self, limiter):
        status = limiter.check_groq_limits()
        assert isinstance(status, RateLimitStatus)

    def test_check_mistral_no_key(self, limiter):
        status = limiter.check_mistral_limits()
        assert isinstance(status, RateLimitStatus)

    def test_check_opencode_no_key(self, limiter):
        status = limiter.check_opencode_limits()
        assert isinstance(status, RateLimitStatus)


# ---------------------------------------------------------------------------
# RateLimiter.__init__ accepts keys as constructor args.
# ---------------------------------------------------------------------------

class TestRateLimiterInit:

    def test_constructor_accepts_keys(self):
        limiter = RateLimiter(
            google_key="g", openrouter_key="o", groq_key="grq",
            mistral_key="m", opencode_key="oc",
        )
        # Check that the keys are stored (sanity, not all attribute names guaranteed).
        # At minimum the limiter should not raise on creation.
        assert limiter is not None

    def test_init_keys_default_to_env_or_none(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
        limiter = RateLimiter()
        # Should construct fine with no env vars.
        assert limiter is not None
