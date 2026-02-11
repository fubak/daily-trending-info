#!/usr/bin/env python3
"""Tests for the fixed deterministic design system."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_fixed_design_has_single_seed_and_layout():
    """Fixed design contract should remain deterministic."""
    from fixed_design import FIXED_DESIGN_BASE

    assert FIXED_DESIGN_BASE["design_seed"] == "fixed-v1"
    assert FIXED_DESIGN_BASE["layout_style"] == "newspaper"
    assert FIXED_DESIGN_BASE["hero_style"] == "glassmorphism"


def test_fixed_design_uses_expected_typography_and_mode():
    """Typography and base mode should stay stable."""
    from fixed_design import FIXED_DESIGN_BASE

    assert FIXED_DESIGN_BASE["font_primary"] == "Newsreader"
    assert FIXED_DESIGN_BASE["font_secondary"] == "Inter"
    assert FIXED_DESIGN_BASE["is_dark_mode"] is True


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
    """Persisted design file should align with fixed profile values."""
    data_design = json.loads((ROOT / "data" / "design.json").read_text())

    assert data_design["design_seed"] == "fixed-v1"
    assert data_design["layout_style"] == "newspaper"
    assert data_design["hero_style"] == "glassmorphism"
    assert data_design["font_primary"] == "Newsreader"
    assert data_design["font_secondary"] == "Inter"


def test_builder_defaults_are_deterministic():
    """Builder defaults should not include random style fallback."""
    build_source = (SCRIPTS_DIR / "build_website.py").read_text()

    assert "DEFAULT_LAYOUT = \"newspaper\"" in build_source
    assert "DEFAULT_HERO_STYLE = \"glassmorphism\"" in build_source
    assert "self.layout = layout_style or DEFAULT_LAYOUT" in build_source
    assert "self.hero_style = hero_style or DEFAULT_HERO_STYLE" in build_source


def test_theme_css_contains_light_and_dark_modes():
    """Theme styles should explicitly support both modes."""
    base_css = (ROOT / "templates" / "css" / "base.css").read_text()
    nav_css = (ROOT / "templates" / "components" / "nav.css").read_text()
    hero_css = (ROOT / "templates" / "css" / "hero.css").read_text()

    assert "body.light-mode" in base_css
    assert "body.dark-mode" in base_css
    assert "body.light-mode .nav" in nav_css
    assert "body.light-mode .hero" in hero_css
