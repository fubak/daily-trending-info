"""Tests for trend_deduplicator.deduplicate_trends()."""

from datetime import datetime, timezone
from typing import Optional

import pytest

from scripts.trend_deduplicator import deduplicate_trends


class FakeTrend:
    """Minimal trend stand-in matching the attributes deduplicate_trends needs."""

    def __init__(
        self,
        title: str,
        score: float = 50.0,
        source: str = "news_rss",
        source_diversity: int = 1,
        timestamp: Optional[datetime] = None,
    ):
        self.title = title
        self.score = score
        self.source = source
        self.source_diversity = source_diversity
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.corroborations = []

    def register_corroboration(self, other: "FakeTrend") -> None:
        self.corroborations.append(other)


class TestDeduplicateTrends:
    """Unit tests for the dedup clustering."""

    def test_empty_input(self):
        assert deduplicate_trends([]) == []

    def test_single_trend_returned_unchanged(self):
        trend = FakeTrend("Apple announces new iPhone")
        result = deduplicate_trends([trend])
        assert len(result) == 1
        assert result[0] is trend

    def test_distinct_trends_all_kept(self):
        a = FakeTrend("Apple announces new iPhone")
        b = FakeTrend("Climate report shows record temperatures")
        c = FakeTrend("Mars rover discovers water ice")
        result = deduplicate_trends([a, b, c])
        assert len(result) == 3

    def test_near_duplicate_titles_merged(self):
        """Titles that share most distinctive tokens should cluster."""
        a = FakeTrend(
            "OpenAI launches GPT-5 with reasoning capabilities", score=80.0
        )
        b = FakeTrend(
            "OpenAI launches GPT-5 reasoning capabilities", score=60.0
        )
        result = deduplicate_trends([a, b])
        assert len(result) == 1
        # Higher-score trend is kept as canonical.
        assert result[0] is a
        # The duplicate is recorded as a corroboration.
        assert b in a.corroborations

    def test_canonical_picked_by_score(self):
        """When titles match closely, higher score wins."""
        low = FakeTrend("Apple unveils new iPhone 17 with titanium frame", score=10.0)
        high = FakeTrend("Apple unveils new iPhone 17 titanium frame", score=90.0)
        result = deduplicate_trends([low, high])
        assert len(result) == 1
        assert result[0] is high

    def test_returns_new_list_not_input(self):
        a = FakeTrend("Test trend one")
        b = FakeTrend("Test trend two")
        original = [a, b]
        result = deduplicate_trends(original)
        # Same items, but result is a freshly built list.
        assert result is not original

    def test_duplicates_in_long_list(self):
        trends = [
            FakeTrend("Federal Reserve raises interest rates", score=80.0),
            FakeTrend("Federal Reserve hikes interest rates", score=70.0),
            FakeTrend("Stock market closes higher on jobs report", score=60.0),
            FakeTrend("Stock market rallies on strong jobs report", score=50.0),
            FakeTrend("Hurricane forms off east coast", score=55.0),
        ]
        result = deduplicate_trends(trends)
        # Should collapse the two Fed entries and the two stock entries.
        assert len(result) <= 4
        assert len(result) >= 3

    def test_empty_title_handled(self):
        a = FakeTrend("")
        b = FakeTrend("Some real headline")
        result = deduplicate_trends([a, b])
        # No crash; both kept since tokens differ.
        assert len(result) == 2

    def test_completely_unrelated_titles_not_merged(self):
        """Token overlap below threshold should leave trends separate."""
        a = FakeTrend("Brazil elects new president")
        b = FakeTrend("Tokyo hosts Olympics opening ceremony")
        result = deduplicate_trends([a, b])
        assert len(result) == 2
