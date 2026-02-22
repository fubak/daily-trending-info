#!/usr/bin/env python3
"""Tests for source health check behaviors."""

from __future__ import annotations

import requests


def _mock_response(url: str, status: int, content: bytes, content_type: str):
    response = requests.Response()
    response.status_code = status
    response._content = content
    response.url = url
    response.headers = requests.structures.CaseInsensitiveDict(
        {"content-type": content_type}
    )
    return response


class _DummySession:
    def __init__(self, responses):
        self._responses = iter(responses)

    def get(self, url, timeout=None, headers=None):
        item = next(self._responses)
        if isinstance(item, Exception):
            raise item
        return item


def test_health_check_marks_source_flaky_after_retry_success():
    """A failure followed by success should be marked as flaky/intermittent."""
    from source_catalog import get_source_by_key
    from source_health_check import check_source

    source = get_source_by_key("news_npr")
    assert source is not None

    session = _DummySession(
        [
            requests.exceptions.ReadTimeout("transient timeout"),
            _mock_response(
                source.url,
                200,
                b"<rss><channel><item><title>ok</title></item></channel></rss>",
                "application/rss+xml",
            ),
        ]
    )

    result = check_source(session, source, timeout=2.0, attempts=2)
    assert result["status"] == "flaky"
    assert result["successful_attempts"] == 1
    assert result["failed_attempts"] == 1


def test_health_sources_include_all_active_reddit_feeds():
    """Catalog-backed health checks should include expanded Reddit coverage."""
    from source_catalog import get_health_sources

    keys = {source.key for source in get_health_sources()}
    assert "reddit_nba" in keys
    assert "reddit_soccer" in keys
    assert "reddit_todayilearned" in keys
    assert "cmmc_reddit_cmmc" in keys
