"""Tests for llm_client.call_openai_compatible()."""

import pytest
import requests
from unittest.mock import MagicMock, patch

from scripts.llm_client import (
    GROQ_SPEC,
    OPENROUTER_SPEC,
    ProviderSpec,
    call_openai_compatible,
)


@pytest.fixture(autouse=True)
def bypass_rate_limiter():
    """Stub out the shared rate-limiter so tests focus on call_openai_compatible.

    The real rate_limiter consults env vars and per-provider quota state,
    which would gate all of these unit tests on an external configuration.
    """
    fake_status = MagicMock(is_available=True, wait_seconds=0.0, error=None)
    # llm_client imports from `rate_limiter` (no scripts. prefix) at call time.
    with patch("rate_limiter.check_before_call", return_value=fake_status):
        with patch("rate_limiter.get_rate_limiter") as mock_get:
            mock_get.return_value = MagicMock(_last_call_time={})
            yield


@pytest.fixture
def mock_session():
    """A mock requests.Session whose .post() returns a configurable response."""
    session = MagicMock(spec=requests.Session)
    return session


def _make_response(status: int = 200, json_body: dict = None, headers: dict = None):
    """Build a fake requests.Response-like object."""
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.json.return_value = json_body or {}
    if status >= 400:
        # raise_for_status should raise for 4xx/5xx
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestProviderSpec:
    """ProviderSpec dataclass behaviour."""

    def test_default_extra_headers_is_empty_dict(self):
        spec = ProviderSpec(name="x", endpoint="https://x", models=["m"])
        assert spec.extra_headers == {}

    def test_default_min_call_interval_false(self):
        spec = ProviderSpec(name="x", endpoint="https://x", models=["m"])
        assert spec.use_min_call_interval is False

    def test_groq_spec_uses_min_call_interval(self):
        assert GROQ_SPEC.use_min_call_interval is True

    def test_openrouter_has_referer_header(self):
        assert "HTTP-Referer" in OPENROUTER_SPEC.extra_headers


class TestCallOpenAICompatibleBasics:
    """Smoke tests around the happy path and quick-exit branches."""

    def test_no_api_key_returns_none(self, mock_session):
        result = call_openai_compatible(
            GROQ_SPEC, None, "prompt", 100, 1, mock_session, 10.0
        )
        assert result is None
        mock_session.post.assert_not_called()

    def test_empty_api_key_returns_none(self, mock_session):
        result = call_openai_compatible(
            GROQ_SPEC, "", "prompt", 100, 1, mock_session, 10.0
        )
        assert result is None

    def test_successful_response_returned(self, mock_session):
        mock_session.post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "Hello, world!"}}]}
        )
        result = call_openai_compatible(
            OPENROUTER_SPEC, "test-key", "prompt", 100, 1, mock_session, 10.0
        )
        assert result == "Hello, world!"

    def test_endpoint_url_used(self, mock_session):
        mock_session.post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "ok"}}]}
        )
        call_openai_compatible(
            OPENROUTER_SPEC, "test-key", "prompt", 100, 1, mock_session, 10.0
        )
        args, kwargs = mock_session.post.call_args
        assert args[0] == OPENROUTER_SPEC.endpoint

    def test_authorization_header_sent(self, mock_session):
        mock_session.post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "ok"}}]}
        )
        call_openai_compatible(
            GROQ_SPEC, "secret-key", "prompt", 100, 1, mock_session, 10.0
        )
        args, kwargs = mock_session.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer secret-key"

    def test_extra_headers_merged(self, mock_session):
        mock_session.post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "ok"}}]}
        )
        call_openai_compatible(
            OPENROUTER_SPEC, "k", "prompt", 100, 1, mock_session, 10.0
        )
        args, kwargs = mock_session.post.call_args
        assert kwargs["headers"]["HTTP-Referer"] == "https://dailytrending.info"

    def test_prompt_passed_in_body(self, mock_session):
        mock_session.post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "ok"}}]}
        )
        call_openai_compatible(
            GROQ_SPEC, "k", "my prompt text", 100, 1, mock_session, 10.0
        )
        args, kwargs = mock_session.post.call_args
        assert kwargs["json"]["messages"] == [
            {"role": "user", "content": "my prompt text"}
        ]
        assert kwargs["json"]["max_tokens"] == 100


class TestCallOpenAICompatibleErrorHandling:
    """Error-path behaviour: missing content, retries, exception types."""

    def test_empty_choices_returns_none(self, mock_session):
        mock_session.post.return_value = _make_response(200, {"choices": []})
        result = call_openai_compatible(
            GROQ_SPEC, "k", "prompt", 100, 1, mock_session, 10.0
        )
        assert result is None

    def test_missing_content_returns_none(self, mock_session):
        mock_session.post.return_value = _make_response(
            200, {"choices": [{"message": {}}]}
        )
        result = call_openai_compatible(
            GROQ_SPEC, "k", "prompt", 100, 1, mock_session, 10.0
        )
        assert result is None

    def test_request_exception_returns_none(self, mock_session):
        mock_session.post.side_effect = requests.exceptions.ConnectionError("network down")
        result = call_openai_compatible(
            GROQ_SPEC, "k", "prompt", 100, 1, mock_session, 10.0
        )
        assert result is None

    def test_500_error_breaks_to_next_model(self, mock_session):
        # OPENROUTER_SPEC has 3 models. A 500 on the first should make
        # call_openai_compatible try the second.
        responses = [
            _make_response(500),
            _make_response(200, {"choices": [{"message": {"content": "fallback"}}]}),
            _make_response(200, {"choices": [{"message": {"content": "third"}}]}),
        ]
        mock_session.post.side_effect = responses
        result = call_openai_compatible(
            OPENROUTER_SPEC, "k", "prompt", 100, 1, mock_session, 10.0
        )
        assert result == "fallback"


class TestRateLimitHandling:
    """429 response handling and Retry-After header parsing."""

    @patch("scripts.llm_client.time.sleep")
    def test_429_with_retry_after_waits_and_retries(self, mock_sleep, mock_session):
        # First call: 429 with Retry-After: 2; second call: success.
        responses = [
            _make_response(429, headers={"Retry-After": "2"}),
            _make_response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
        mock_session.post.side_effect = responses

        result = call_openai_compatible(
            GROQ_SPEC, "k", "prompt", 100, 2, mock_session, 10.0
        )
        assert result == "ok"
        # Sleep called with 2.0 seconds.
        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        assert 2.0 in sleeps

    @patch("scripts.llm_client.time.sleep")
    def test_429_retry_after_capped_at_max_retry_wait(self, mock_sleep, mock_session):
        responses = [
            _make_response(429, headers={"Retry-After": "9999"}),
            _make_response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
        mock_session.post.side_effect = responses

        call_openai_compatible(
            GROQ_SPEC, "k", "prompt", 100, 2, mock_session, max_retry_wait=5.0
        )
        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        assert 5.0 in sleeps  # Capped at max_retry_wait
        assert 9999.0 not in sleeps

    @patch("scripts.llm_client.time.sleep")
    def test_429_invalid_retry_after_uses_max(self, mock_sleep, mock_session):
        responses = [
            _make_response(429, headers={"Retry-After": "not-a-number"}),
            _make_response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
        mock_session.post.side_effect = responses
        call_openai_compatible(
            GROQ_SPEC, "k", "prompt", 100, 2, mock_session, max_retry_wait=7.0
        )
        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        assert 7.0 in sleeps


class TestMinCallInterval:
    """Proactive throttling for providers with use_min_call_interval=True."""

    @patch("scripts.llm_client.time.sleep")
    @patch("scripts.llm_client.time.time")
    def test_throttle_when_called_too_soon(self, mock_time, mock_sleep, mock_session):
        # First time.time() call sets the initial clock. Subsequent calls
        # advance it so the elapsed-since-last-call is < min_call_interval.
        mock_time.return_value = 100.0
        mock_session.post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "ok"}}]}
        )

        last_ref = [99.5]  # 0.5s ago
        call_openai_compatible(
            GROQ_SPEC, "k", "prompt", 100, 1, mock_session, 10.0,
            min_call_interval=3.0, last_call_ref=last_ref,
        )

        # Should have slept ~2.5s to reach the 3.0s gap.
        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        assert any(abs(s - 2.5) < 0.01 for s in sleeps)

    @patch("scripts.llm_client.time.sleep")
    @patch("scripts.llm_client.time.time")
    def test_no_throttle_when_enough_time_elapsed(
        self, mock_time, mock_sleep, mock_session
    ):
        mock_time.return_value = 200.0
        mock_session.post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "ok"}}]}
        )

        last_ref = [100.0]  # 100s ago — well past min_call_interval
        call_openai_compatible(
            GROQ_SPEC, "k", "prompt", 100, 1, mock_session, 10.0,
            min_call_interval=3.0, last_call_ref=last_ref,
        )
        # No proactive throttling sleep call (0 or close to it).
        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        # All sleeps should be <= 0 (no throttling needed).
        assert all(s <= 0.5 for s in sleeps if s > 0) or len(sleeps) == 0

    def test_last_call_ref_updated_in_place(self, mock_session):
        mock_session.post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "ok"}}]}
        )
        last_ref = [0.0]
        call_openai_compatible(
            GROQ_SPEC, "k", "prompt", 100, 1, mock_session, 10.0,
            min_call_interval=3.0, last_call_ref=last_ref,
        )
        # last_ref[0] should have been updated to ~now.
        assert last_ref[0] > 0


class TestModelRotation:
    """Provider iterates through its model list when each previous one fails."""

    def test_all_models_exhausted_returns_none(self, mock_session):
        # All three OpenRouter models return 500 → final result is None.
        mock_session.post.return_value = _make_response(500)
        result = call_openai_compatible(
            OPENROUTER_SPEC, "k", "prompt", 100, 1, mock_session, 10.0
        )
        assert result is None
        # POST called exactly once per model (max_retries=1, break on 500).
        assert mock_session.post.call_count == len(OPENROUTER_SPEC.models)
