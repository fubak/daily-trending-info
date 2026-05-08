#!/usr/bin/env python3
"""
Tests for cmmc_page_generator.py — pure/deterministic functions only.

Covers:
- filter_cmmc_trends()
- categorize_trend()
- sort_trends_by_priority()
- build_cmmc_page()  (smoke test)
"""

import sys
from pathlib import Path

import pytest

# Ensure the scripts package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from cmmc_page_generator import (
    filter_cmmc_trends,
    categorize_trend,
    sort_trends_by_priority,
    build_cmmc_page,
    CMMC_CORE_KEYWORDS,
    NIST_KEYWORDS,
    DIB_KEYWORDS,
)


# ---------------------------------------------------------------------------
# Shared minimal fixtures (defined locally — no conftest dependency)
# ---------------------------------------------------------------------------

def _make_trend(
    title="Generic title",
    source="cmmc_fedscoop",
    description="",
    summary="",
    score=50,
    url="https://example.com",
    source_label=None,
    timestamp=None,
):
    """Return a minimal trend dict with caller-supplied overrides."""
    t = {
        "title": title,
        "source": source,
        "description": description,
        "summary": summary,
        "score": score,
        "url": url,
    }
    if source_label is not None:
        t["source_label"] = source_label
    if timestamp is not None:
        t["timestamp"] = timestamp
    return t


MINIMAL_DESIGN = {
    "color_bg": "#0a0a0a",
    "color_text": "#ffffff",
    "color_muted": "#a1a1aa",
    "color_border": "#27272a",
    "color_card_bg": "#18181b",
    "color_accent": "#3b82f6",
    "color_accent_secondary": "#60a5fa",
    "font_primary": "Space Grotesk",
    "font_secondary": "Inter",
}


# ===========================================================================
# TestFilterCmmcTrends
# ===========================================================================

class TestFilterCmmcTrends:
    """Tests for filter_cmmc_trends()."""

    def test_returns_only_cmmc_sourced_trends(self):
        """Only trends whose source starts with 'cmmc_' should be returned."""
        trends = [
            _make_trend(source="cmmc_fedscoop"),
            _make_trend(source="hackernews"),
            _make_trend(source="cmmc_reddit"),
            _make_trend(source="news_rss"),
        ]
        result = filter_cmmc_trends(trends)
        assert len(result) == 2
        assert all(t["source"].startswith("cmmc_") for t in result)

    def test_empty_list_returns_empty(self):
        """An empty input list should yield an empty output list."""
        result = filter_cmmc_trends([])
        assert result == []

    def test_no_cmmc_sources_returns_empty(self):
        """A list with no 'cmmc_' sources should return empty."""
        trends = [
            _make_trend(source="hackernews"),
            _make_trend(source="reddit"),
        ]
        result = filter_cmmc_trends(trends)
        assert result == []

    def test_all_cmmc_sources_returns_all(self):
        """When every trend has a 'cmmc_' source, all should be returned."""
        trends = [
            _make_trend(source="cmmc_fedscoop"),
            _make_trend(source="cmmc_defensescoop"),
            _make_trend(source="cmmc_govcon"),
        ]
        result = filter_cmmc_trends(trends)
        assert len(result) == 3

    def test_source_prefix_must_be_exact(self):
        """Sources like 'not_cmmc_source' should not match (prefix check)."""
        trends = [
            _make_trend(source="not_cmmc_source"),
            _make_trend(source="xcmmc_feed"),
        ]
        result = filter_cmmc_trends(trends)
        assert result == []

    def test_missing_source_key_is_excluded(self):
        """Trends without a 'source' key should be silently excluded."""
        trends = [{"title": "No source trend"}]
        result = filter_cmmc_trends(trends)
        assert result == []

    def test_preserves_trend_data(self):
        """Filtered trends should retain all original fields."""
        t = _make_trend(
            title="CMMC Policy Update",
            source="cmmc_cyberscoop",
            score=99,
            url="https://example.com/cmmc",
        )
        result = filter_cmmc_trends([t])
        assert len(result) == 1
        assert result[0]["title"] == "CMMC Policy Update"
        assert result[0]["score"] == 99

    def test_non_dict_without_source_attr_excluded(self):
        """Non-dict objects with no 'source' attribute should be skipped."""
        # A plain string has no 'source' attribute and is not a dict
        result = filter_cmmc_trends(["not_a_trend"])
        assert result == []


# ===========================================================================
# TestCategorizeTrend
# ===========================================================================

class TestCategorizeTrend:
    """Tests for categorize_trend()."""

    # --- CMMC core keyword matching ---

    def test_cmmc_keyword_in_title_returns_cmmc(self):
        """A trend with 'cmmc' in the title should be categorized as 'cmmc'."""
        trend = _make_trend(title="New CMMC 2.0 Assessment Guidelines Released")
        assert categorize_trend(trend) == "cmmc"

    def test_c3pao_keyword_returns_cmmc(self):
        """'c3pao' is a top-priority keyword; the category should be 'cmmc'."""
        trend = _make_trend(title="C3PAO audit requirements explained")
        assert categorize_trend(trend) == "cmmc"

    def test_cyber_ab_keyword_returns_cmmc(self):
        """'cyber-ab' in the title should map to category 'cmmc'."""
        trend = _make_trend(title="Cyber-AB releases new guidance for assessors")
        assert categorize_trend(trend) == "cmmc"

    def test_cmmc_in_description_returns_cmmc(self):
        """'cmmc certification' appearing in the description should still categorize as 'cmmc'."""
        trend = _make_trend(
            title="Federal contractor news",
            description="Firms are racing to achieve cmmc certification before deadline.",
        )
        assert categorize_trend(trend) == "cmmc"

    def test_cmmc_case_insensitive_uppercase(self):
        """CMMC keyword matching should be case-insensitive (ALL-CAPS input)."""
        trend = _make_trend(title="CMMC COMPLIANCE REQUIREMENTS FOR DOD VENDORS")
        assert categorize_trend(trend) == "cmmc"

    def test_cmmc_case_insensitive_mixed(self):
        """CMMC keyword matching should be case-insensitive (mixed-case input)."""
        trend = _make_trend(title="Understanding Cmmc Level 2 Requirements")
        assert categorize_trend(trend) == "cmmc"

    # --- NIST keyword matching ---

    def test_nist_800_171_returns_nist(self):
        """'nist 800-171' in the title should map to category 'nist'."""
        trend = _make_trend(title="NIST 800-171 revision 3 final published")
        assert categorize_trend(trend) == "nist"

    def test_dfars_keyword_returns_nist(self):
        """'dfars' in title should categorize as 'nist' (second priority)."""
        trend = _make_trend(title="DFARS 7012 compliance enforcement update")
        assert categorize_trend(trend) == "nist"

    def test_fedramp_keyword_returns_nist(self):
        """'fedramp' in the title should map to category 'nist'."""
        trend = _make_trend(title="FedRAMP authorization process streamlined")
        assert categorize_trend(trend) == "nist"

    def test_fisma_keyword_returns_nist(self):
        """'fisma' in the summary should map to category 'nist'."""
        trend = _make_trend(title="Agency report", summary="FISMA compliance scores improve across agencies")
        assert categorize_trend(trend) == "nist"

    def test_cui_keyword_returns_nist(self):
        """'cui' in the title should categorize as 'nist'."""
        trend = _make_trend(title="CUI handling requirements updated for contractors")
        assert categorize_trend(trend) == "nist"

    def test_nist_case_insensitive(self):
        """NIST keyword matching should be case-insensitive."""
        trend = _make_trend(title="Understanding FISMA Reporting Obligations")
        assert categorize_trend(trend) == "nist"

    # --- DIB keyword matching ---

    def test_defense_industrial_base_returns_dib(self):
        """'defense industrial base' should map to category 'dib'."""
        trend = _make_trend(title="Defense Industrial Base cybersecurity strategy released")
        assert categorize_trend(trend) == "dib"

    def test_pentagon_keyword_returns_dib(self):
        """'pentagon' in the title should map to category 'dib'."""
        trend = _make_trend(title="Pentagon releases new cybersecurity guidelines")
        assert categorize_trend(trend) == "dib"

    def test_defense_contractor_keyword_returns_dib(self):
        """'defense contractor' should be recognized as category 'dib'."""
        trend = _make_trend(title="Major defense contractor fails cybersecurity audit")
        assert categorize_trend(trend) == "dib"

    def test_dib_in_description_returns_dib(self):
        """'dib' in the description should still yield category 'dib'."""
        trend = _make_trend(
            title="Contractor cybersecurity news",
            description="The DIB supply chain faces increasing threats.",
        )
        assert categorize_trend(trend) == "dib"

    def test_dib_case_insensitive(self):
        """DIB keyword matching should be case-insensitive."""
        trend = _make_trend(title="DoD Contractor Requirements for 2025")
        assert categorize_trend(trend) == "dib"

    # --- Priority ordering: cmmc beats nist beats dib ---

    def test_cmmc_takes_priority_over_nist(self):
        """When both CMMC and NIST keywords appear, 'cmmc' must win."""
        trend = _make_trend(
            title="CMMC alignment with NIST 800-171 rev3"
        )
        assert categorize_trend(trend) == "cmmc"

    def test_cmmc_takes_priority_over_dib(self):
        """When both CMMC and DIB keywords appear, 'cmmc' must win."""
        trend = _make_trend(
            title="Pentagon adopts CMMC for defense contractor compliance"
        )
        assert categorize_trend(trend) == "cmmc"

    def test_nist_takes_priority_over_dib(self):
        """When both NIST and DIB keywords appear, 'nist' must win."""
        trend = _make_trend(
            title="Defense contractor implements NIST 800-171 controls"
        )
        assert categorize_trend(trend) == "nist"

    # --- Fallback ---

    def test_unrelated_content_returns_general(self):
        """Content with none of the watched keywords should return 'general'."""
        trend = _make_trend(title="Sports team wins championship", description="A great victory.")
        assert categorize_trend(trend) == "general"

    def test_empty_trend_returns_general(self):
        """A trend with empty title and no description should fall back to 'general'."""
        trend = {"title": "", "description": ""}
        assert categorize_trend(trend) == "general"

    def test_missing_title_key_returns_general(self):
        """A trend dict with no 'title' key at all should return 'general'."""
        trend = {}
        assert categorize_trend(trend) == "general"

    def test_summary_field_used_when_description_absent(self):
        """categorize_trend should check the 'summary' field when 'description' is absent."""
        trend = {
            "title": "Compliance news",
            "summary": "FedRAMP modernization act signed into law",
        }
        assert categorize_trend(trend) == "nist"


# ===========================================================================
# TestSortTrendsByPriority
# ===========================================================================

class TestSortTrendsByPriority:
    """Tests for sort_trends_by_priority()."""

    def test_cmmc_before_nist_before_dib_before_general(self):
        """Output order should be: cmmc → nist → dib → general."""
        trends = [
            _make_trend(title="Pentagon news roundup", score=80),          # dib
            _make_trend(title="FedRAMP authorization update", score=70),   # nist
            _make_trend(title="Random tech story", score=60),              # general
            _make_trend(title="CMMC 2.0 assessment phase begins", score=50),  # cmmc
        ]
        result = sort_trends_by_priority(trends)
        categories = [categorize_trend(t) for t in result]
        assert categories[0] == "cmmc"
        assert categories[1] == "nist"
        assert categories[2] == "dib"
        assert categories[3] == "general"

    def test_empty_input_returns_empty(self):
        """Sorting an empty list should return an empty list."""
        assert sort_trends_by_priority([]) == []

    def test_single_trend_returned_unchanged(self):
        """A single-element list should come back as a single-element list."""
        trends = [_make_trend(title="CMMC certification news", score=100)]
        result = sort_trends_by_priority(trends)
        assert len(result) == 1
        assert result[0]["title"] == "CMMC certification news"

    def test_same_category_trends_all_present(self):
        """All trends of the same category should appear in the output."""
        trends = [
            _make_trend(title="CMMC Level 1 basics", score=30),
            _make_trend(title="CMMC Level 2 requirements", score=90),
            _make_trend(title="CMMC 2.0 changes", score=60),
        ]
        result = sort_trends_by_priority(trends)
        assert len(result) == 3
        assert all(categorize_trend(t) == "cmmc" for t in result)

    def test_general_trends_sorted_to_end(self):
        """General (uncategorized) trends should all appear after specific categories."""
        trends = [
            _make_trend(title="Movie review", score=100),          # general
            _make_trend(title="CMMC policy update", score=10),     # cmmc
            _make_trend(title="Sports championship", score=80),    # general
        ]
        result = sort_trends_by_priority(trends)
        # cmmc should be first
        assert categorize_trend(result[0]) == "cmmc"
        # remaining two should both be general
        assert all(categorize_trend(t) == "general" for t in result[1:])

    def test_does_not_mutate_input_list(self):
        """The original list should not be modified by sorting."""
        trends = [
            _make_trend(title="General story", score=50),
            _make_trend(title="CMMC certification audit", score=30),
        ]
        original_order = [t["title"] for t in trends]
        sort_trends_by_priority(trends)
        assert [t["title"] for t in trends] == original_order

    def test_nist_before_dib(self):
        """NIST-categorized trends should appear before DIB-categorized ones."""
        trends = [
            _make_trend(title="Defense Industrial Base security report", score=90),  # dib
            _make_trend(title="DFARS rule published in Federal Register", score=20), # nist
        ]
        result = sort_trends_by_priority(trends)
        assert categorize_trend(result[0]) == "nist"
        assert categorize_trend(result[1]) == "dib"


# ===========================================================================
# TestBuildCmmcPage
# ===========================================================================

class TestBuildCmmcPage:
    """Smoke tests for build_cmmc_page()."""

    def _make_cmmc_trends(self, count=3):
        """Return a list of minimal CMMC-sourced trend dicts."""
        return [
            _make_trend(
                title=f"CMMC Compliance Story {i}",
                source="cmmc_fedscoop",
                description=f"Story {i} about CMMC certification requirements.",
                score=80 - i * 5,
                url=f"https://example.com/cmmc-story-{i}",
            )
            for i in range(count)
        ]

    def test_returns_non_empty_string(self):
        """build_cmmc_page should return a non-empty string."""
        result = build_cmmc_page(self._make_cmmc_trends(), [], MINIMAL_DESIGN)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_doctype(self):
        """The returned HTML should start with a DOCTYPE declaration."""
        result = build_cmmc_page(self._make_cmmc_trends(), [], MINIMAL_DESIGN)
        assert "<!DOCTYPE html>" in result

    def test_contains_cmmc_watch_title(self):
        """The page title should reference 'CMMC Watch'."""
        result = build_cmmc_page(self._make_cmmc_trends(), [], MINIMAL_DESIGN)
        assert "CMMC Watch" in result

    def test_contains_cmmc_branding_strings(self):
        """Key CMMC branding strings should appear in the generated HTML."""
        result = build_cmmc_page(self._make_cmmc_trends(), [], MINIMAL_DESIGN)
        assert "CMMC" in result
        assert "cmmc" in result.lower()

    def test_contains_html_and_body_tags(self):
        """The output should include opening <html> and <body> tags."""
        result = build_cmmc_page(self._make_cmmc_trends(), [], MINIMAL_DESIGN)
        assert "<html" in result
        assert "<body" in result

    def test_empty_trends_still_returns_html(self):
        """build_cmmc_page with an empty trends list should return valid HTML."""
        result = build_cmmc_page([], [], MINIMAL_DESIGN)
        assert "<!DOCTYPE html>" in result
        assert "CMMC Watch" in result

    def test_non_cmmc_source_trends_are_excluded(self):
        """Trends from non-cmmc_ sources should not appear as story cards."""
        non_cmmc_trends = [
            _make_trend(title="Hackernews story", source="hackernews"),
            _make_trend(title="Reddit story", source="reddit"),
        ]
        result = build_cmmc_page(non_cmmc_trends, [], MINIMAL_DESIGN)
        # Page should render but contain no story titles from non-cmmc sources
        assert "Hackernews story" not in result
        assert "Reddit story" not in result

    def test_cmmc_trend_title_appears_in_output(self):
        """A CMMC trend's title should be visible in the generated HTML."""
        trends = [_make_trend(
            title="CMMC Level 2 Assessment Deadline Extended",
            source="cmmc_fedscoop",
        )]
        result = build_cmmc_page(trends, [], MINIMAL_DESIGN)
        assert "CMMC Level 2 Assessment Deadline Extended" in result

    def test_design_colors_used_in_styles(self):
        """Custom accent color from design dict should appear in the CSS block."""
        design = dict(MINIMAL_DESIGN)
        design["color_accent"] = "#abcdef"
        result = build_cmmc_page(self._make_cmmc_trends(), [], design)
        assert "#abcdef" in result

    def test_contains_rss_feed_link(self):
        """The page should include a link to the CMMC RSS feed."""
        result = build_cmmc_page(self._make_cmmc_trends(), [], MINIMAL_DESIGN)
        assert "feed.xml" in result

    def test_contains_footer(self):
        """The generated page should include a footer element."""
        result = build_cmmc_page(self._make_cmmc_trends(), [], MINIMAL_DESIGN)
        assert "cmmc-footer" in result

    def test_contains_header(self):
        """The generated page should include a header element."""
        result = build_cmmc_page(self._make_cmmc_trends(), [], MINIMAL_DESIGN)
        assert "cmmc-header" in result

    def test_story_count_shown_in_hero(self):
        """The hero section should report how many stories are available today."""
        trends = self._make_cmmc_trends(count=5)
        result = build_cmmc_page(trends, [], MINIMAL_DESIGN)
        assert "5 stories today" in result

    def test_default_font_used_when_not_in_design(self):
        """When font keys are absent from design, defaults ('Space Grotesk', 'Inter') apply."""
        result = build_cmmc_page(self._make_cmmc_trends(), [], {})
        assert "Space Grotesk" in result
        assert "Inter" in result

    def test_html_escaping_in_title(self):
        """Titles containing HTML special characters should be escaped in output."""
        trends = [_make_trend(
            title='CMMC & <script>alert("xss")</script> threat',
            source="cmmc_fedscoop",
        )]
        result = build_cmmc_page(trends, [], MINIMAL_DESIGN)
        assert "<script>alert" not in result
        assert "&amp;" in result or "&lt;" in result

    def test_story_url_in_output(self):
        """A trend's URL should appear as a hyperlink in the generated page."""
        trends = [_make_trend(
            title="CMMC Policy Update",
            source="cmmc_govcon",
            url="https://example.com/cmmc-policy-2025",
        )]
        result = build_cmmc_page(trends, [], MINIMAL_DESIGN)
        assert "https://example.com/cmmc-policy-2025" in result
