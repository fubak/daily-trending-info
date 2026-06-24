#!/usr/bin/env python3
"""Tests for the fixed deterministic design system."""

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_build_fixed_design_emits_deterministic_profile_regardless_of_input():
    """The determinism contract: build_fixed_design must always emit the fixed
    Signal Desk seed/layout/hero, no matter the trends/keywords. Asserting on
    the BUILDER OUTPUT (not the FIXED_DESIGN_BASE constant) catches a builder
    that fails to carry the fixed profile through — a constant-equals-itself
    check would not."""
    from fixed_design import build_fixed_design

    for trends, keywords in (([], []), ([{"title": "Anything"}], ["ai", "x"])):
        design = build_fixed_design(trends, keywords)
        assert design["design_seed"] == "fixed-v1"
        assert design["layout_style"] == "newspaper"
        assert design["hero_style"] == "glassmorphism"


def test_build_fixed_design_carries_typography_and_dark_mode_into_output():
    """Typography/mode must survive into the built design (the deepcopy+merge),
    not just exist on the base constant."""
    from fixed_design import build_fixed_design

    design = build_fixed_design([{"title": "Lead"}], ["ai"])
    assert design["font_primary"] == "Newsreader"
    assert design["font_secondary"] == "Inter"
    assert design["is_dark_mode"] is True


def test_build_fixed_design_sets_dynamic_headline_and_subheadline():
    """Headline/subheadline should update from content while tokens stay fixed."""
    from fixed_design import build_fixed_design

    trends = [{"title": "Custom Lead Story"}]
    keywords = ["ai", "security", "infrastructure"]
    design = build_fixed_design(trends, keywords)

    assert design["headline"] == "Custom Lead Story"
    assert design["subheadline"] == "Tracking developments in ai, security, infrastructure."
    assert design["layout_style"] == "newspaper"
    assert design["hero_style"] == "glassmorphism"


def test_build_fixed_design_falls_back_when_no_trends_or_keywords():
    """Fallback copy should be predictable when content is sparse."""
    from fixed_design import build_fixed_design

    design = build_fixed_design([], [])

    assert "Daily Briefing" in design["headline"]
    assert "modern" in design["subheadline"].lower()
    assert design["design_seed"] == "fixed-v1"


def test_data_design_matches_fixed_profile():
    """Persisted design file should align with fixed profile values.

    data/ is gitignored, so design.json only exists after a pipeline run.
    Skip when it's absent (e.g. a clean CI checkout) rather than fail — the
    determinism contract itself is covered by the build_fixed_design output
    tests above, which run everywhere.
    """
    design_path = ROOT / "data" / "design.json"
    if not design_path.exists():
        pytest.skip("data/design.json not present (no pipeline run in this env)")
    data_design = json.loads(design_path.read_text())

    assert data_design["design_seed"] == "fixed-v1"
    assert data_design["layout_style"] == "newspaper"
    assert data_design["hero_style"] == "glassmorphism"
    assert data_design["font_primary"] == "Newsreader"
    assert data_design["font_secondary"] == "Inter"


def test_builder_falls_back_to_fixed_profile_when_design_omits_style():
    """Behavioural replacement for a test that used to grep build_website.py
    source text. A builder handed a design with no layout/hero must fall back
    to the fixed newspaper/glassmorphism profile — exercising the real default
    logic so a regression (e.g. a random-style fallback) actually fails."""
    from build_website import (
        WebsiteBuilder,
        BuildContext,
        DEFAULT_LAYOUT,
        DEFAULT_HERO_STYLE,
    )

    ctx = BuildContext(trends=[], images=[], design={}, keywords=[])
    builder = WebsiteBuilder(ctx)

    assert builder.layout == DEFAULT_LAYOUT == "newspaper"
    assert builder.hero_style == DEFAULT_HERO_STYLE == "glassmorphism"


def test_theme_css_contains_light_and_dark_modes():
    """Theme styles should explicitly support both modes."""
    base_css = (ROOT / "templates" / "css" / "base.css").read_text()
    nav_css = (ROOT / "templates" / "components" / "nav.css").read_text()
    hero_css = (ROOT / "templates" / "css" / "hero.css").read_text()

    assert "body.light-mode" in base_css
    assert "body.dark-mode" in base_css
    assert "body.light-mode .nav" in nav_css
    assert "body.light-mode .hero" in hero_css
