#!/usr/bin/env python3
"""Offline tests for the CMMC LinkedIn fetcher (no Apify calls)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import fetch_linkedin_posts as linkedin

PROFILE_URL = "https://www.linkedin.com/in/example-author/"

# Rows shaped like the johnvc/linkedin-posts-api dataset schema. Synthetic
# values, not real profile data.
POST_ROW = {
    "result_type": "post",
    "postId": "7380000000000000001",
    "postUrl": "https://www.linkedin.com/posts/example-author_activity-7380000000000000001",
    "postType": "post",
    "datePosted": "2026-10-20T14:30:00.000Z",
    "text": "CMMC Phase 2 assessments are filling up. Is your C3PAO booked? #CMMC #NIST",
    "hashtags": ["CMMC", "NIST"],
    "authorName": "Example Author",
    "authorHeadline": "CMMC Registered Practitioner",
    "authorUrl": "https://www.linkedin.com/in/example-author",
    "authorType": "Person",
    "numLikes": 120,
    "numComments": 14,
    "numShares": 3,
    "fromCache": False,
    "fetched_at": "2026-10-21T11:00:00.000Z",
}

ERROR_ROW = {
    "result_type": "error",
    "sourceUrl": "https://www.linkedin.com/in/example-author",
    "error_type": "CollectionError",
    "error_message": "The data source returned no posts for this profile.",
}


class _DummyDataset:
    def __init__(self, items):
        self._items = items

    def iterate_items(self):
        return iter(self._items)


class _DummyActor:
    def __init__(self, client, actor_id):
        self._client = client
        self._actor_id = actor_id

    def call(self, run_input=None, timeout_secs=None):
        self._client.calls.append((self._actor_id, run_input))
        return {"defaultDatasetId": "dataset-1"}


class _DummyApifyClient:
    def __init__(self, items):
        self._items = items
        self.calls = []

    def actor(self, actor_id):
        return _DummyActor(self, actor_id)

    def dataset(self, dataset_id):
        return _DummyDataset(self._items)


@pytest.fixture
def dummy_client(monkeypatch):
    client = _DummyApifyClient([ERROR_ROW, POST_ROW])
    monkeypatch.setattr(linkedin, "get_apify_client", lambda: client)
    monkeypatch.setattr(linkedin.time, "sleep", lambda _seconds: None)
    return client


def test_empty_actor_secret_falls_back_to_default(monkeypatch, dummy_client):
    """An unset GitHub secret is passed as "" and must not become the actor ID."""
    monkeypatch.setenv("APIFY_ACTOR_ID", "")

    linkedin.fetch_linkedin_posts([PROFILE_URL])

    actor_id, _ = dummy_client.calls[0]
    assert actor_id == "johnvc/linkedin-posts-api"


def test_actor_id_env_override_still_wins(monkeypatch, dummy_client):
    monkeypatch.setenv("APIFY_ACTOR_ID", "someone/other-linkedin-actor")

    linkedin.fetch_linkedin_posts([PROFILE_URL])

    actor_id, _ = dummy_client.calls[0]
    assert actor_id == "someone/other-linkedin-actor"


def test_run_input_uses_actor_input_names(monkeypatch, dummy_client):
    monkeypatch.delenv("APIFY_ACTOR_ID", raising=False)

    linkedin.fetch_linkedin_posts([PROFILE_URL], max_posts_per_profile=5)

    _, run_input = dummy_client.calls[0]
    assert run_input == {"profileUrls": [PROFILE_URL], "maxPostsPerProfile": 5}


def test_error_rows_are_skipped(monkeypatch, dummy_client):
    monkeypatch.delenv("APIFY_ACTOR_ID", raising=False)

    posts = linkedin.fetch_linkedin_posts([PROFILE_URL])

    assert len(posts) == 1
    assert posts[0].post_url == POST_ROW["postUrl"]


def test_actor_row_maps_to_linkedin_post():
    post = linkedin._parse_linkedin_item(POST_ROW)

    assert post is not None
    assert post.content == POST_ROW["text"]
    assert post.author_name == "Example Author"
    assert post.author_title == "CMMC Registered Practitioner"
    assert post.author_url == "https://www.linkedin.com/in/example-author"
    assert post.likes == 120
    assert post.comments == 14
    assert post.shares == 3

    expected = (
        datetime(2026, 10, 20, 14, 30, tzinfo=timezone.utc)
        .astimezone()
        .replace(tzinfo=None)
    )
    assert post.timestamp == expected
    assert post.timestamp.tzinfo is None


def test_actor_rows_convert_to_trends():
    """datePosted ends in "Z"; scoring must not mix aware and naive datetimes."""
    post = linkedin._parse_linkedin_item(POST_ROW)
    assert post is not None

    trends = linkedin.linkedin_posts_to_trends([post])

    assert len(trends) == 1
    trend = trends[0]
    assert trend["source"] == "cmmc_linkedin"
    assert trend["url"] == POST_ROW["postUrl"]
    assert trend["title"].startswith("Example Author: CMMC Phase 2")
    assert trend["score"] >= 1.5
    assert {"cmmc", "c3pao", "nist"} <= set(trend["keywords"])
