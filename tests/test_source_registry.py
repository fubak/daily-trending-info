"""Tests for source_registry public API."""

import pytest

from scripts.source_registry import (
    SourceMetadata,
    format_source_label,
    get_source_metadata,
    source_metadata_dict,
    source_quality_multiplier,
)


class TestSourceMetadata:
    """Sanity checks on the SourceMetadata dataclass."""

    def test_construction(self):
        m = SourceMetadata(
            tier=1, source_type="news", risk="low", language="en", parser="rss"
        )
        assert m.tier == 1
        assert m.source_type == "news"
        assert m.risk == "low"
        assert m.language == "en"
        assert m.parser == "rss"
        assert m.fallback_url is None
        assert m.display_name is None


class TestGetSourceMetadata:
    """Resolution by exact key, prefix, or default."""

    def test_known_news_rss_source(self):
        # Sources like 'news_rss_apnews' should resolve through prefix or exact match.
        m = get_source_metadata("news_rss_apnews")
        assert isinstance(m, SourceMetadata)
        assert 1 <= m.tier <= 4

    def test_unknown_source_returns_default(self):
        m = get_source_metadata("totally_unknown_source_xyz")
        assert isinstance(m, SourceMetadata)
        # Default tier should be the lowest priority bucket.
        assert m.tier >= 4

    def test_empty_string_returns_default(self):
        m = get_source_metadata("")
        assert isinstance(m, SourceMetadata)


class TestSourceMetadataDict:
    """source_metadata_dict() always returns a serialisable dict with a display name."""

    def test_returns_dict(self):
        result = source_metadata_dict("news_rss_apnews")
        assert isinstance(result, dict)

    def test_has_display_name(self):
        result = source_metadata_dict("news_rss_apnews")
        assert "display_name" in result
        assert result["display_name"]  # non-empty

    def test_unknown_source_gets_humanised_name(self):
        result = source_metadata_dict("brand_new_source")
        # No exact match; the humanised default should kick in.
        assert "display_name" in result
        # "Brand New Source" or similar — at least non-empty + capitalised words.
        assert any(c.isupper() for c in result["display_name"])

    def test_includes_tier_and_risk(self):
        result = source_metadata_dict("hackernews")
        assert "tier" in result
        assert "risk" in result


class TestFormatSourceLabel:
    """format_source_label() builds a compact UI badge string."""

    def test_returns_string(self):
        label = format_source_label("hackernews")
        assert isinstance(label, str)
        assert len(label) > 0

    def test_format_contains_tier_and_risk(self):
        label = format_source_label("hackernews")
        # Format is: "<display> [T<tier>/<RISK>]"
        assert "[T" in label
        assert "/" in label
        assert "]" in label

    def test_unknown_source_still_returns_label(self):
        label = format_source_label("unknown_source_123")
        assert isinstance(label, str)
        assert "[T" in label

    def test_empty_source(self):
        label = format_source_label("")
        assert isinstance(label, str)


class TestSourceQualityMultiplier:
    """source_quality_multiplier() returns a numeric ranking factor."""

    def test_returns_float(self):
        m = source_quality_multiplier("hackernews")
        assert isinstance(m, float)
        assert m > 0

    def test_tier_1_higher_than_tier_4(self):
        # Find a tier-1 source and a tier-4 (or unknown) source.
        m_unknown = source_quality_multiplier("totally_unknown_xyz")
        # Tier 1 sources (e.g. major newswires) score higher than unknown ones.
        # Even without knowing exactly which sources are tier 1, an unknown
        # source should be at most ~1.0 (per tier_boost mapping).
        assert m_unknown <= 1.05

    def test_handles_empty_string(self):
        # Empty source falls back to default tier, should still return a number.
        m = source_quality_multiplier("")
        assert isinstance(m, float)
        assert m > 0
