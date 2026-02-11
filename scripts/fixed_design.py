#!/usr/bin/env python3
"""
Fixed design system for DailyTrending.info.

This module intentionally removes day-to-day style variability so the site
always renders with one consistent visual identity.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Dict, List


FIXED_DESIGN_BASE: Dict = {
    "theme_name": "Signal Desk",
    "personality": "editorial",
    "mood": "professional",
    "font_primary": "Newsreader",
    "font_secondary": "Inter",
    "font_style": "modern",
    "text_transform_headings": "none",
    "color_bg": "#0b1220",
    "color_text": "#e6edf7",
    "color_accent": "#3b82f6",
    "color_accent_secondary": "#22d3ee",
    "color_muted": "#94a3b8",
    "color_card_bg": "#121a2a",
    "color_border": "#243047",
    "is_dark_mode": True,
    "layout_style": "newspaper",
    "spacing": "comfortable",
    "max_width": "1400px",
    "card_style": "bordered",
    "card_radius": "0.75rem",
    "card_padding": "1.25rem",
    "animation_level": "subtle",
    "use_gradients": True,
    "use_blur": False,
    "hover_effect": "lift",
    "hero_style": "glassmorphism",
    "hero_overlay_opacity": 0.82,
    "background_pattern": "none",
    "accent_style": "none",
    "special_mode": "standard",
    "transition_speed": "200ms",
    "hover_transform": "translateY(-2px)",
    "use_pulse_animation": False,
    "use_float_animation": False,
    "image_treatment": "none",
    "typography_scale": {
        "scale_ratio": 1.25,
        "base_size": "1.05rem",
        "headline_xl": "clamp(2.5rem, 8vw, 5rem)",
        "headline_lg": "clamp(1.75rem, 4.5vw, 3rem)",
        "headline_md": "clamp(1.25rem, 2.5vw, 1.75rem)",
        "letter_spacing_headings": "-0.01em",
    },
    "section_divider": "line",
    "card_aspect_ratio": "classic",
    "content_sentiment": "neutral",
    "contrast_validated": True,
    "story_capsules": [],
    "cta_options": ["Read Story", "Explore Topics", "View Archive"],
    "cta_primary": "Read Story",
    "design_seed": "fixed-v1",
}


def build_fixed_design(trends: List[Dict], keywords: List[str]) -> Dict:
    """Build deterministic design data with dynamic content text only."""
    design = deepcopy(FIXED_DESIGN_BASE)

    headline = "Daily Briefing: Top Stories Across Technology, Science, and World News"
    if trends:
        first_title = (trends[0].get("title") or "").strip()
        if first_title:
            headline = first_title

    keyword_slice = [kw for kw in keywords[:3] if isinstance(kw, str) and kw.strip()]
    if keyword_slice:
        subheadline = "Tracking developments in " + ", ".join(keyword_slice) + "."
    else:
        subheadline = "A modern, continuously updated snapshot of what matters today."

    design["headline"] = headline
    design["subheadline"] = subheadline
    design["generated_at"] = datetime.now().isoformat()
    return design

