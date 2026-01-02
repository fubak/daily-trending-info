#!/usr/bin/env python3
"""
Design Generator - Creates unique website designs with multiple style dimensions.

Design Dimensions:
- Personality: brutalist, editorial, minimal, corporate, playful, tech, news, magazine
- Color Scheme: 20+ curated palettes
- Typography: 25+ font pairings with style variants
- Card Style: bordered, shadow, glass, minimal, accent, outline
- Spacing: compact, comfortable, spacious
- Border Radius: sharp, rounded, pill
- Animation: none, subtle, moderate, playful
- Layout Pattern: from build_website.py
"""

import os
import json
import random
import re
import hashlib
import time
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path

import requests

try:
    from rate_limiter import get_rate_limiter, check_before_call
except ImportError:
    from scripts.rate_limiter import get_rate_limiter, check_before_call


@dataclass
class DesignSpec:
    """Complete specification for a generated design."""
    # Identity
    theme_name: str = "Default"
    personality: str = "modern"
    mood: str = "professional"

    # Typography
    font_primary: str = "Space Grotesk"
    font_secondary: str = "Inter"
    font_style: str = "geometric"  # geometric, humanist, neo-grotesque, slab, display
    text_transform_headings: str = "none"  # none, uppercase, capitalize

    # Colors
    color_bg: str = "#0a0a0a"
    color_text: str = "#ffffff"
    color_accent: str = "#6366f1"
    color_accent_secondary: str = "#8b5cf6"
    color_muted: str = "#a1a1aa"
    color_card_bg: str = "#18181b"
    color_border: str = "#27272a"
    is_dark_mode: bool = True

    # Layout & Spacing
    layout_style: str = "newspaper"
    spacing: str = "comfortable"  # compact, comfortable, spacious
    max_width: str = "1400px"

    # Cards
    card_style: str = "bordered"  # bordered, shadow, glass, minimal, accent, outline
    card_radius: str = "1rem"  # 0, 0.5rem, 1rem, 1.5rem, 2rem, 9999px
    card_padding: str = "1.5rem"

    # Effects
    animation_level: str = "subtle"  # none, subtle, moderate, playful
    use_gradients: bool = True
    use_blur: bool = True
    hover_effect: str = "lift"  # none, lift, glow, scale, border

    # Hero
    hero_style: str = "full"
    hero_overlay_opacity: float = 0.85

    # Creative flourishes
    background_pattern: str = "none"
    accent_style: str = "none"
    special_mode: str = "standard"
    transition_speed: str = "200ms"
    hover_transform: str = "translateY(-2px)"
    use_pulse_animation: bool = False
    use_float_animation: bool = False

    # New design dimensions
    image_treatment: str = "none"  # none, grayscale, sepia, saturate, contrast, vignette
    typography_scale: Dict[str, str] = field(default_factory=dict)  # headline sizes per personality
    section_divider: str = "none"  # none, line, thick_line, gradient_line, dots, fade, wave
    card_aspect_ratio: str = "auto"  # auto, landscape, portrait, square, wide, classic
    content_sentiment: str = "neutral"  # breaking, positive, negative, entertainment, neutral
    contrast_validated: bool = True  # Whether colors pass WCAG AA

    # Content
    headline: str = "Today's Trends"
    subheadline: str = "What the world is talking about"
    story_capsules: List[str] = field(default_factory=list)
    cta_options: List[str] = field(default_factory=list)
    cta_primary: str = ""

    # Meta
    generated_at: str = ""
    design_seed: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()
        if not self.design_seed:
            self.design_seed = datetime.now().strftime("%Y-%m-%d")
        if not self.cta_primary and self.cta_options:
            self.cta_primary = self.cta_options[0]


# ============================================================================
# DESIGN PERSONALITIES - Each defines a complete aesthetic
# ============================================================================

PERSONALITIES = {
    "brutalist": {
        "description": "Raw, bold, unconventional",
        "font_styles": ["display", "slab", "mono"],
        "card_styles": ["minimal", "outline", "bordered"],
        "border_radius": ["0", "0"],
        "spacing": ["compact", "comfortable"],
        "animations": ["none", "subtle"],
        "use_gradients": False,
        "hover_effects": ["none", "border"],
        "text_transform": ["uppercase", "none"],
    },
    "editorial": {
        "description": "Magazine-style, sophisticated",
        "font_styles": ["serif", "humanist"],
        "card_styles": ["minimal", "bordered"],
        "border_radius": ["0", "0.25rem"],
        "spacing": ["spacious", "comfortable"],
        "animations": ["subtle"],
        "use_gradients": False,
        "hover_effects": ["none", "lift"],
        "text_transform": ["none", "capitalize"],
    },
    "minimal": {
        "description": "Clean, lots of whitespace",
        "font_styles": ["neo-grotesque", "geometric"],
        "card_styles": ["minimal", "bordered"],
        "border_radius": ["0.5rem", "1rem"],
        "spacing": ["spacious"],
        "animations": ["subtle"],
        "use_gradients": False,
        "hover_effects": ["lift", "none"],
        "text_transform": ["none"],
    },
    "corporate": {
        "description": "Professional, trustworthy",
        "font_styles": ["neo-grotesque", "humanist"],
        "card_styles": ["shadow", "bordered"],
        "border_radius": ["0.5rem", "0.75rem"],
        "spacing": ["comfortable"],
        "animations": ["subtle"],
        "use_gradients": True,
        "hover_effects": ["lift", "glow"],
        "text_transform": ["none"],
    },
    "playful": {
        "description": "Fun, energetic, colorful",
        "font_styles": ["geometric", "display"],
        "card_styles": ["shadow", "accent", "glass"],
        "border_radius": ["1rem", "1.5rem", "2rem"],
        "spacing": ["comfortable", "spacious"],
        "animations": ["moderate", "playful"],
        "use_gradients": True,
        "hover_effects": ["scale", "glow", "lift"],
        "text_transform": ["none"],
    },
    "tech": {
        "description": "Modern, sleek, innovative",
        "font_styles": ["geometric", "mono"],
        "card_styles": ["glass", "bordered", "accent"],
        "border_radius": ["0.75rem", "1rem"],
        "spacing": ["comfortable"],
        "animations": ["subtle", "moderate"],
        "use_gradients": True,
        "hover_effects": ["glow", "lift"],
        "text_transform": ["none", "uppercase"],
    },
    "news": {
        "description": "Information-dense, authoritative",
        "font_styles": ["neo-grotesque", "humanist"],
        "card_styles": ["bordered", "minimal"],
        "border_radius": ["0.25rem", "0.5rem"],
        "spacing": ["compact", "comfortable"],
        "animations": ["none", "subtle"],
        "use_gradients": False,
        "hover_effects": ["border", "lift"],
        "text_transform": ["none", "uppercase"],
    },
    "magazine": {
        "description": "Visual, immersive, story-driven",
        "font_styles": ["serif", "display", "humanist"],
        "card_styles": ["minimal", "shadow"],
        "border_radius": ["0", "0.5rem"],
        "spacing": ["spacious"],
        "animations": ["subtle", "moderate"],
        "use_gradients": True,
        "hover_effects": ["scale", "lift"],
        "text_transform": ["capitalize", "none"],
    },
    "dashboard": {
        "description": "Data-focused, organized, efficient",
        "font_styles": ["mono", "neo-grotesque"],
        "card_styles": ["bordered", "glass"],
        "border_radius": ["0.5rem", "0.75rem"],
        "spacing": ["compact"],
        "animations": ["subtle"],
        "use_gradients": True,
        "hover_effects": ["glow", "border"],
        "text_transform": ["uppercase", "none"],
    },
}

# ============================================================================
# FONT PAIRINGS - Organized by style
# ============================================================================

FONT_PAIRINGS = {
    "geometric": [
        ("Space Grotesk", "Inter"),
        ("Outfit", "Inter"),
        ("Plus Jakarta Sans", "Inter"),
        ("Urbanist", "Inter"),
        ("Sora", "Inter"),
        ("Montserrat", "Hind"),
        ("Poppins", "Open Sans"),
        ("Nunito", "Open Sans"),
    ],
    "neo-grotesque": [
        ("Inter", "Inter"),
        ("DM Sans", "DM Sans"),
        ("Manrope", "Inter"),
        ("Rubik", "Open Sans"),
        ("Work Sans", "Work Sans"),
        ("IBM Plex Sans", "IBM Plex Sans"),
        ("Barlow", "Barlow"),
    ],
    "humanist": [
        ("Source Sans 3", "Source Sans 3"),
        ("Lato", "Lato"),
        ("Open Sans", "Open Sans"),
        ("Nunito Sans", "Nunito Sans"),
        ("Karla", "Karla"),
        ("Cabin", "Cabin"),
    ],
    "display": [
        ("Bebas Neue", "Inter"),
        ("Oswald", "Open Sans"),
        ("Anton", "Roboto"),
        ("Archivo Black", "Inter"),
        ("Righteous", "Nunito"),
        ("Bowlby One SC", "Work Sans"),
    ],
    "serif": [
        ("Playfair Display", "Source Sans 3"),
        ("Merriweather", "Open Sans"),
        ("Lora", "Inter"),
        ("Crimson Pro", "Inter"),
        ("Libre Baskerville", "Source Sans 3"),
        ("DM Serif Display", "DM Sans"),
        ("Fraunces", "Inter"),
    ],
    "slab": [
        ("Roboto Slab", "Roboto"),
        ("Arvo", "Open Sans"),
        ("Zilla Slab", "Inter"),
        ("Crete Round", "Open Sans"),
        ("Rockwell", "Arial"),
    ],
    "mono": [
        ("JetBrains Mono", "Inter"),
        ("Fira Code", "Inter"),
        ("IBM Plex Mono", "IBM Plex Sans"),
        ("Source Code Pro", "Source Sans 3"),
        ("Space Mono", "Space Grotesk"),
    ],
}

# ============================================================================
# COLOR SCHEMES - Expanded palette
# ============================================================================

COLOR_SCHEMES = [
    # Dark themes
    {
        "name": "Midnight Indigo",
        "bg": "#0a0a0a", "text": "#ffffff", "accent": "#6366f1",
        "accent_secondary": "#8b5cf6", "muted": "#a1a1aa",
        "card_bg": "#18181b", "border": "#27272a", "dark": True,
        "mood": "professional", "personalities": ["corporate", "tech", "minimal"]
    },
    {
        "name": "Cyberpunk Neon",
        "bg": "#0d0d0d", "text": "#f0f0f0", "accent": "#00ff88",
        "accent_secondary": "#00ccff", "muted": "#888888",
        "card_bg": "#1a1a1a", "border": "#333333", "dark": True,
        "mood": "futuristic", "personalities": ["tech", "playful", "dashboard"]
    },
    {
        "name": "Warm Ember",
        "bg": "#1a1410", "text": "#fef3c7", "accent": "#f59e0b",
        "accent_secondary": "#ef4444", "muted": "#d4a574",
        "card_bg": "#292017", "border": "#3d2d1f", "dark": True,
        "mood": "warm", "personalities": ["editorial", "magazine"]
    },
    {
        "name": "Ocean Depths",
        "bg": "#0a1628", "text": "#e2e8f0", "accent": "#0ea5e9",
        "accent_secondary": "#06b6d4", "muted": "#64748b",
        "card_bg": "#0f2847", "border": "#1e3a5f", "dark": True,
        "mood": "calm", "personalities": ["corporate", "news"]
    },
    {
        "name": "Forest Night",
        "bg": "#0a120a", "text": "#ecfdf5", "accent": "#10b981",
        "accent_secondary": "#34d399", "muted": "#6b7c6b",
        "card_bg": "#152015", "border": "#1f3520", "dark": True,
        "mood": "natural", "personalities": ["minimal", "editorial"]
    },
    {
        "name": "Royal Purple",
        "bg": "#0f0a1a", "text": "#f5f3ff", "accent": "#a855f7",
        "accent_secondary": "#c084fc", "muted": "#9c8fac",
        "card_bg": "#1a1025", "border": "#2e1f4a", "dark": True,
        "mood": "elegant", "personalities": ["magazine", "playful"]
    },
    {
        "name": "Crimson Dark",
        "bg": "#0f0a0a", "text": "#fef2f2", "accent": "#ef4444",
        "accent_secondary": "#f87171", "muted": "#a89090",
        "card_bg": "#1a1010", "border": "#3f1f1f", "dark": True,
        "mood": "bold", "personalities": ["news", "brutalist"]
    },
    {
        "name": "Soft Rose",
        "bg": "#1a0f14", "text": "#fdf2f8", "accent": "#ec4899",
        "accent_secondary": "#f472b6", "muted": "#a88899",
        "card_bg": "#251520", "border": "#3d1f30", "dark": True,
        "mood": "playful", "personalities": ["playful", "magazine"]
    },
    {
        "name": "Arctic Night",
        "bg": "#0f1419", "text": "#f0f9ff", "accent": "#38bdf8",
        "accent_secondary": "#7dd3fc", "muted": "#7899a8",
        "card_bg": "#1a2633", "border": "#243544", "dark": True,
        "mood": "cool", "personalities": ["tech", "dashboard"]
    },
    {
        "name": "Slate Dark",
        "bg": "#0f172a", "text": "#f8fafc", "accent": "#f97316",
        "accent_secondary": "#fb923c", "muted": "#94a3b8",
        "card_bg": "#1e293b", "border": "#334155", "dark": True,
        "mood": "modern", "personalities": ["corporate", "news"]
    },
    {
        "name": "Noir",
        "bg": "#000000", "text": "#ffffff", "accent": "#ffffff",
        "accent_secondary": "#a3a3a3", "muted": "#737373",
        "card_bg": "#171717", "border": "#262626", "dark": True,
        "mood": "dramatic", "personalities": ["brutalist", "editorial", "minimal"]
    },
    {
        "name": "Matrix",
        "bg": "#0a0a0a", "text": "#00ff00", "accent": "#00ff00",
        "accent_secondary": "#00cc00", "muted": "#008800",
        "card_bg": "#0d1a0d", "border": "#1a2f1a", "dark": True,
        "mood": "retro", "personalities": ["tech", "brutalist"]
    },
    # Light themes
    {
        "name": "Clean White",
        "bg": "#ffffff", "text": "#18181b", "accent": "#6366f1",
        "accent_secondary": "#8b5cf6", "muted": "#71717a",
        "card_bg": "#f4f4f5", "border": "#e4e4e7", "dark": False,
        "mood": "clean", "personalities": ["minimal", "corporate"]
    },
    {
        "name": "Warm Paper",
        "bg": "#faf9f6", "text": "#1c1917", "accent": "#ea580c",
        "accent_secondary": "#f97316", "muted": "#78716c",
        "card_bg": "#f5f4f0", "border": "#e7e5e4", "dark": False,
        "mood": "warm", "personalities": ["editorial", "magazine"]
    },
    {
        "name": "Cool Gray",
        "bg": "#f8fafc", "text": "#0f172a", "accent": "#3b82f6",
        "accent_secondary": "#60a5fa", "muted": "#64748b",
        "card_bg": "#f1f5f9", "border": "#e2e8f0", "dark": False,
        "mood": "professional", "personalities": ["corporate", "news", "dashboard"]
    },
    {
        "name": "Mint Fresh",
        "bg": "#f0fdf4", "text": "#14532d", "accent": "#16a34a",
        "accent_secondary": "#22c55e", "muted": "#4ade80",
        "card_bg": "#dcfce7", "border": "#bbf7d0", "dark": False,
        "mood": "fresh", "personalities": ["playful", "minimal"]
    },
    {
        "name": "Lavender Mist",
        "bg": "#faf5ff", "text": "#3b0764", "accent": "#9333ea",
        "accent_secondary": "#a855f7", "muted": "#c084fc",
        "card_bg": "#f3e8ff", "border": "#e9d5ff", "dark": False,
        "mood": "creative", "personalities": ["playful", "magazine"]
    },
    {
        "name": "Newspaper",
        "bg": "#f5f5dc", "text": "#1a1a1a", "accent": "#b91c1c",
        "accent_secondary": "#dc2626", "muted": "#525252",
        "card_bg": "#fafad2", "border": "#d4d4a8", "dark": False,
        "mood": "classic", "personalities": ["news", "editorial"]
    },
    {
        "name": "Terminal",
        "bg": "#1e1e1e", "text": "#d4d4d4", "accent": "#569cd6",
        "accent_secondary": "#4ec9b0", "muted": "#808080",
        "card_bg": "#252526", "border": "#3c3c3c", "dark": True,
        "mood": "technical", "personalities": ["tech", "dashboard", "brutalist"]
    },
    {
        "name": "Sunset Gradient",
        "bg": "#1a1a2e", "text": "#eaeaea", "accent": "#e94560",
        "accent_secondary": "#ff6b6b", "muted": "#a0a0a0",
        "card_bg": "#16213e", "border": "#0f3460", "dark": True,
        "mood": "vibrant", "personalities": ["playful", "tech"]
    },
]

# ============================================================================
# LAYOUT PATTERNS - Matched with build_website.py
# ============================================================================

LAYOUT_PATTERNS = [
    "newspaper",   # Classic columns
    "magazine",    # Large featured images
    "dashboard",   # Data-dense grid
    "minimal",     # Clean, centered
    "bold",        # Large typography
    "mosaic",      # Asymmetric grid
]

HERO_PATTERNS = [
    "full",        # Full viewport
    "split",       # Split screen
    "minimal",     # Compact
    "gradient",    # Animated gradient
    "ticker",      # Breaking news style
    "cinematic",   # Wide letterbox with blur
    "stack",       # Vertically stacked headline
    "marquee",     # Scrolling ticker bar
]

# ============================================================================
# VISUAL FLOURISHES - Additional creative elements
# ============================================================================

BACKGROUND_PATTERNS = {
    "none": "",
    "dots": "radial-gradient(circle, var(--color-border) 1px, transparent 1px)",
    "grid": "linear-gradient(var(--color-border) 1px, transparent 1px), linear-gradient(90deg, var(--color-border) 1px, transparent 1px)",
    "diagonal": "repeating-linear-gradient(45deg, var(--color-border), var(--color-border) 1px, transparent 1px, transparent 10px)",
    "noise": "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.7' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E\")",
    "gradient_radial": "radial-gradient(ellipse at top, var(--color-accent) 0%, transparent 50%)",
    "gradient_sweep": "conic-gradient(from 180deg at 50% 50%, var(--color-accent) 0deg, transparent 60deg, transparent 300deg, var(--color-accent) 360deg)",
}

# Decorative accents that can be added to sections
ACCENT_STYLES = {
    "none": {},
    "glow": {"box-shadow": "0 0 60px -20px var(--color-accent)"},
    "neon_border": {"border": "2px solid var(--color-accent)", "box-shadow": "0 0 20px var(--color-accent), inset 0 0 20px rgba(255,255,255,0.05)"},
    "gradient_border": {"border-image": "linear-gradient(135deg, var(--color-accent), var(--color-accent-secondary)) 1"},
    "underline": {"border-bottom": "3px solid var(--color-accent)"},
    "corner_accent": {"border-top": "4px solid var(--color-accent)", "border-left": "4px solid var(--color-accent)"},
    "pill_badge": {"border-radius": "9999px", "padding": "0.5rem 1.5rem"},
}

# Animation presets for different energy levels
ANIMATION_PRESETS = {
    "none": {
        "transition_speed": "0ms",
        "hover_transform": "none",
        "pulse": False,
        "float": False,
    },
    "subtle": {
        "transition_speed": "200ms",
        "hover_transform": "translateY(-2px)",
        "pulse": False,
        "float": False,
    },
    "moderate": {
        "transition_speed": "300ms",
        "hover_transform": "translateY(-4px) scale(1.01)",
        "pulse": False,
        "float": False,
    },
    "playful": {
        "transition_speed": "400ms",
        "hover_transform": "translateY(-6px) scale(1.02) rotate(0.5deg)",
        "pulse": True,
        "float": True,
    },
    "energetic": {
        "transition_speed": "250ms",
        "hover_transform": "translateY(-8px) scale(1.03)",
        "pulse": True,
        "float": True,
    },
}

# Special visual modes for dramatic variation
SPECIAL_MODES = [
    "standard",      # Normal look
    "high_contrast", # Maximum readability
    "duotone",       # Two-color aesthetic
    "monochrome",    # Single accent color
    "vibrant",       # Saturated colors
    "muted",         # Desaturated, subtle
    "retro",         # Vintage feel
    "glassmorphism", # Frosted glass everywhere
]

# ============================================================================
# PERSONALITY-HERO STYLE ALIGNMENT
# Each personality has compatible hero styles for visual consistency
# ============================================================================

# Valid hero styles that have CSS implementations in build_website.py
HERO_STYLES_WITH_CSS = [
    "cinematic", "glassmorphism", "neon", "duotone", "particles",
    "waves", "geometric", "spotlight", "glitch", "aurora", "mesh", "retro"
]

PERSONALITY_HERO_ALIGNMENT = {
    "brutalist": ["cinematic", "glitch", "geometric", "spotlight"],
    "editorial": ["cinematic", "duotone", "spotlight"],
    "minimal": ["mesh", "aurora", "glassmorphism"],
    "corporate": ["mesh", "cinematic", "spotlight"],
    "playful": ["particles", "waves", "aurora", "geometric", "neon", "retro"],
    "tech": ["neon", "glitch", "particles", "mesh", "geometric"],
    "news": ["cinematic", "spotlight"],
    "magazine": ["cinematic", "duotone", "glassmorphism", "spotlight"],
    "dashboard": ["mesh", "glassmorphism", "geometric"],
}

# ============================================================================
# IMAGE TREATMENTS - Filters applied to card images
# ============================================================================

IMAGE_TREATMENTS = {
    "none": {},
    "grayscale": {"filter": "grayscale(100%)"},
    "sepia": {"filter": "sepia(30%)"},
    "saturate": {"filter": "saturate(1.3)"},
    "contrast": {"filter": "contrast(1.1)"},
    "vignette": {"box-shadow": "inset 0 0 100px rgba(0,0,0,0.5)"},
    "blur_edges": {"mask-image": "radial-gradient(ellipse, black 50%, transparent 100%)"},
    "duotone_warm": {"filter": "sepia(20%) saturate(1.2) hue-rotate(-10deg)"},
    "duotone_cool": {"filter": "saturate(0.8) hue-rotate(20deg)"},
}

PERSONALITY_IMAGE_TREATMENTS = {
    "brutalist": ["none", "grayscale", "contrast"],
    "editorial": ["none", "sepia", "grayscale"],
    "minimal": ["none", "grayscale"],
    "corporate": ["none", "saturate"],
    "playful": ["saturate", "duotone_warm", "none"],
    "tech": ["none", "contrast", "duotone_cool"],
    "news": ["none", "contrast"],
    "magazine": ["none", "saturate", "sepia", "vignette"],
    "dashboard": ["none", "grayscale"],
}

# ============================================================================
# TYPOGRAPHY SCALES - Different heading size ratios per personality
# ============================================================================

TYPOGRAPHY_SCALES = {
    "brutalist": {
        "scale_ratio": 1.5,        # Dramatic jumps
        "base_size": "1rem",
        "headline_xl": "clamp(3rem, 10vw, 6rem)",
        "headline_lg": "clamp(2rem, 5vw, 3.5rem)",
        "headline_md": "clamp(1.5rem, 3vw, 2rem)",
        "letter_spacing_headings": "0.05em",
    },
    "editorial": {
        "scale_ratio": 1.25,       # Classic proportions
        "base_size": "1.1rem",
        "headline_xl": "clamp(2.5rem, 7vw, 4.5rem)",
        "headline_lg": "clamp(1.75rem, 4vw, 2.75rem)",
        "headline_md": "clamp(1.25rem, 2.5vw, 1.75rem)",
        "letter_spacing_headings": "0",
    },
    "minimal": {
        "scale_ratio": 1.2,        # Subtle differences
        "base_size": "1rem",
        "headline_xl": "clamp(2rem, 6vw, 4rem)",
        "headline_lg": "clamp(1.5rem, 3.5vw, 2.5rem)",
        "headline_md": "clamp(1.2rem, 2vw, 1.5rem)",
        "letter_spacing_headings": "-0.01em",
    },
    "corporate": {
        "scale_ratio": 1.25,
        "base_size": "1rem",
        "headline_xl": "clamp(2.5rem, 7vw, 4.5rem)",
        "headline_lg": "clamp(1.75rem, 4vw, 2.75rem)",
        "headline_md": "clamp(1.25rem, 2.5vw, 1.75rem)",
        "letter_spacing_headings": "0",
    },
    "playful": {
        "scale_ratio": 1.4,        # Fun, bouncy
        "base_size": "1rem",
        "headline_xl": "clamp(2.75rem, 9vw, 5.5rem)",
        "headline_lg": "clamp(1.75rem, 4.5vw, 3rem)",
        "headline_md": "clamp(1.25rem, 2.5vw, 1.75rem)",
        "letter_spacing_headings": "0",
    },
    "tech": {
        "scale_ratio": 1.3,
        "base_size": "0.95rem",
        "headline_xl": "clamp(2.5rem, 8vw, 5rem)",
        "headline_lg": "clamp(1.75rem, 4vw, 3rem)",
        "headline_md": "clamp(1.25rem, 2.5vw, 1.75rem)",
        "letter_spacing_headings": "0.02em",
    },
    "news": {
        "scale_ratio": 1.35,       # Authority
        "base_size": "1rem",
        "headline_xl": "clamp(2.5rem, 8vw, 5rem)",
        "headline_lg": "clamp(1.75rem, 4vw, 3rem)",
        "headline_md": "clamp(1.25rem, 2.5vw, 1.75rem)",
        "letter_spacing_headings": "0",
    },
    "magazine": {
        "scale_ratio": 1.3,
        "base_size": "1.05rem",
        "headline_xl": "clamp(2.5rem, 8vw, 5rem)",
        "headline_lg": "clamp(1.75rem, 4.5vw, 3rem)",
        "headline_md": "clamp(1.25rem, 2.5vw, 1.75rem)",
        "letter_spacing_headings": "-0.01em",
    },
    "dashboard": {
        "scale_ratio": 1.15,       # Compact, data-dense
        "base_size": "0.9rem",
        "headline_xl": "clamp(2rem, 6vw, 3.5rem)",
        "headline_lg": "clamp(1.5rem, 3.5vw, 2.25rem)",
        "headline_md": "clamp(1.1rem, 2vw, 1.5rem)",
        "letter_spacing_headings": "0.02em",
    },
}

# ============================================================================
# SECTION DIVIDERS - Visual separators between content sections
# ============================================================================

SECTION_DIVIDERS = {
    "none": "",
    "line": "border-top: 1px solid var(--color-border);",
    "thick_line": "border-top: 3px solid var(--color-accent);",
    "gradient_line": "background: linear-gradient(90deg, transparent, var(--color-accent), transparent); height: 2px;",
    "dots": "background: radial-gradient(circle, var(--color-accent) 2px, transparent 2px); background-size: 20px 20px; height: 10px;",
    "fade": "background: linear-gradient(180deg, var(--color-bg), var(--color-card-bg)); height: 40px;",
    "wave": "mask-image: url(\"data:image/svg+xml,%3Csvg viewBox='0 0 1200 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 20 Q300 0 600 20 T1200 20 V40 H0 Z' fill='black'/%3E%3C/svg%3E\"); background: var(--color-accent); height: 40px; opacity: 0.3;",
}

PERSONALITY_SECTION_DIVIDERS = {
    "brutalist": ["thick_line", "none"],
    "editorial": ["line", "none"],
    "minimal": ["none", "fade"],
    "corporate": ["line", "gradient_line"],
    "playful": ["dots", "wave", "gradient_line"],
    "tech": ["gradient_line", "line"],
    "news": ["thick_line", "line"],
    "magazine": ["fade", "line", "none"],
    "dashboard": ["line", "none"],
}

# ============================================================================
# CARD ASPECT RATIOS - Variation in card proportions
# ============================================================================

CARD_ASPECT_RATIOS = {
    "auto": "auto",           # Natural content flow
    "landscape": "16/9",      # Wide cards
    "portrait": "3/4",        # Tall cards
    "square": "1/1",          # Equal dimensions
    "wide": "21/9",           # Ultra-wide
    "classic": "4/3",         # Traditional
}

PERSONALITY_CARD_RATIOS = {
    "brutalist": ["auto", "square"],
    "editorial": ["auto", "classic", "landscape"],
    "minimal": ["auto"],
    "corporate": ["auto", "landscape"],
    "playful": ["square", "auto", "landscape"],
    "tech": ["landscape", "auto", "wide"],
    "news": ["auto", "landscape"],
    "magazine": ["landscape", "portrait", "auto"],
    "dashboard": ["auto", "square"],
}


# ============================================================================
# WCAG CONTRAST RATIO VALIDATION
# Ensures text is readable against backgrounds (WCAG AA requires 4.5:1 for normal text)
# ============================================================================

def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def get_relative_luminance(rgb: tuple) -> float:
    """Calculate relative luminance per WCAG 2.1 specification."""
    def channel_luminance(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel_luminance(r) + 0.7152 * channel_luminance(g) + 0.0722 * channel_luminance(b)


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors."""
    try:
        lum1 = get_relative_luminance(hex_to_rgb(color1))
        lum2 = get_relative_luminance(hex_to_rgb(color2))
        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)
        return (lighter + 0.05) / (darker + 0.05)
    except (ValueError, TypeError):
        return 1.0  # Return lowest ratio if calculation fails


def validate_color_contrast(text_color: str, bg_color: str, min_ratio: float = 4.5) -> bool:
    """Check if text color has sufficient contrast against background (WCAG AA)."""
    ratio = calculate_contrast_ratio(text_color, bg_color)
    return ratio >= min_ratio


def adjust_color_for_contrast(text_color: str, bg_color: str, min_ratio: float = 4.5) -> str:
    """Adjust text color to meet minimum contrast ratio if needed."""
    if validate_color_contrast(text_color, bg_color, min_ratio):
        return text_color

    # Determine if background is light or dark
    bg_lum = get_relative_luminance(hex_to_rgb(bg_color))

    # Use white or black based on background luminance
    if bg_lum > 0.5:
        return "#1a1a1a"  # Dark text for light backgrounds
    else:
        return "#ffffff"  # Light text for dark backgrounds


# ============================================================================
# CONTENT-AWARE ANIMATION INTENSITY
# Adjusts animation level based on news sentiment and urgency
# ============================================================================

SENTIMENT_ANIMATION_MAP = {
    "breaking": "moderate",    # Breaking news: moderate activity
    "urgent": "moderate",      # Urgent news: attention-grabbing
    "positive": "playful",     # Good news: celebratory
    "negative": "subtle",      # Serious news: restrained
    "neutral": "subtle",       # Normal: balanced
    "tech": "moderate",        # Tech news: modern feel
    "entertainment": "playful", # Entertainment: fun
}

def analyze_content_sentiment(trends: list, keywords: list) -> str:
    """Analyze content to determine appropriate animation intensity."""
    # Keywords that suggest different sentiments
    breaking_words = ["breaking", "just in", "urgent", "developing", "alert"]
    positive_words = ["success", "breakthrough", "wins", "celebrates", "achieves", "record"]
    negative_words = ["crisis", "disaster", "death", "crash", "fails", "warning", "threat"]
    entertainment_words = ["movie", "music", "celebrity", "game", "sports", "entertainment"]

    # Count occurrences - handle None values safely
    text_parts = []
    for t in trends:
        title = t.get("title") or ""
        description = t.get("description") or ""
        text_parts.append(f"{title} {description}")
    text = " ".join(text_parts).lower()
    text += " " + " ".join(k for k in keywords if k).lower()

    breaking_count = sum(1 for w in breaking_words if w in text)
    positive_count = sum(1 for w in positive_words if w in text)
    negative_count = sum(1 for w in negative_words if w in text)
    entertainment_count = sum(1 for w in entertainment_words if w in text)

    # Determine dominant sentiment
    if breaking_count >= 2:
        return "breaking"
    if entertainment_count >= 3:
        return "entertainment"
    if positive_count > negative_count and positive_count >= 2:
        return "positive"
    if negative_count > positive_count and negative_count >= 2:
        return "negative"

    return "neutral"


def get_content_aware_animation(trends: list, keywords: list, base_animation: str) -> str:
    """Get animation level adjusted for content sentiment."""
    sentiment = analyze_content_sentiment(trends, keywords)
    suggested = SENTIMENT_ANIMATION_MAP.get(sentiment, "subtle")

    # Balance between personality preference and content sentiment
    animation_levels = ["none", "subtle", "moderate", "playful", "energetic"]
    base_idx = animation_levels.index(base_animation) if base_animation in animation_levels else 1
    suggested_idx = animation_levels.index(suggested) if suggested in animation_levels else 1

    # Average the two, rounding toward the suggested
    final_idx = (base_idx + suggested_idx + 1) // 2
    return animation_levels[min(final_idx, len(animation_levels) - 1)]


class DesignGenerator:
    """Generates unique design specifications using combinatorial approach."""

    # Rate limiting: minimum seconds between API calls to stay under 30 req/min
    MIN_CALL_INTERVAL = 3.0

    def __init__(
        self,
        groq_key: Optional[str] = None,
        openrouter_key: Optional[str] = None,
        google_key: Optional[str] = None
    ):
        self.groq_key = groq_key or os.getenv('GROQ_API_KEY')
        self.openrouter_key = openrouter_key or os.getenv('OPENROUTER_API_KEY')
        self.google_key = google_key or os.getenv('GOOGLE_AI_API_KEY')
        self.session = requests.Session()
        self.history_path = Path(__file__).parent.parent / "data" / "design_history.json"
        self._last_call_time = 0.0  # Track last API call for rate limiting

    def generate(self, trends: List[Dict], keywords: List[str]) -> DesignSpec:
        """Generate a unique design based on trends and timestamp."""
        print("Generating design specification...")

        # Use timestamp as seed for unique designs on each generation
        # This ensures each run produces a different design
        timestamp_seed = datetime.now().isoformat()
        rng = random.Random(timestamp_seed)

        # Try AI generation for colors/theme
        ai_enhancements = self._try_ai_generation(trends, keywords)

        # Generate the combinatorial design
        spec = self._generate_combinatorial(rng, trends, keywords, ai_enhancements)

        print(f"  Personality: {spec.personality}")
        print(f"  Theme: {spec.theme_name}")
        print(f"  Layout: {spec.layout_style} / Hero: {spec.hero_style}")
        print(f"  Card style: {spec.card_style} / Radius: {spec.card_radius}")

        return spec

    def _generate_combinatorial(
        self,
        rng: random.Random,
        trends: List[Dict],
        keywords: List[str],
        ai_data: Optional[Dict] = None
    ) -> DesignSpec:
        """Generate design by combining multiple style dimensions."""

        # Prepare history for repeat-avoidance
        recent_themes = self._load_recent_themes(days=7)

        # 1. Select personality
        personality_name = rng.choice(list(PERSONALITIES.keys()))
        personality = PERSONALITIES[personality_name]

        # 2. Select color scheme that matches personality
        matching_schemes = [
            s for s in COLOR_SCHEMES
            if personality_name in s.get("personalities", [])
        ]
        if not matching_schemes:
            matching_schemes = COLOR_SCHEMES

        scheme = rng.choice(matching_schemes)

        # 3. Select font pairing based on personality's font styles
        font_style = rng.choice(personality["font_styles"])
        if font_style in FONT_PAIRINGS:
            fonts = rng.choice(FONT_PAIRINGS[font_style])
        else:
            fonts = rng.choice(FONT_PAIRINGS["geometric"])

        # 4. Select other style attributes from personality
        card_style = rng.choice(personality["card_styles"])
        border_radius = rng.choice(personality["border_radius"])
        spacing = rng.choice(personality["spacing"])
        animation = rng.choice(personality["animations"])
        hover_effect = rng.choice(personality["hover_effects"])
        text_transform = rng.choice(personality["text_transform"])

        # 5. Select layout and hero patterns (personality-aligned)
        layout_style = rng.choice(LAYOUT_PATTERNS)

        # Select hero style aligned with personality for visual consistency
        # Use only hero styles that have CSS implementations
        personality_heroes = PERSONALITY_HERO_ALIGNMENT.get(personality_name, HERO_STYLES_WITH_CSS)
        # Filter to only include valid hero styles with CSS
        valid_heroes = [h for h in personality_heroes if h in HERO_STYLES_WITH_CSS]
        hero_style = rng.choice(valid_heroes) if valid_heroes else rng.choice(HERO_STYLES_WITH_CSS)

        # 5b. Select creative flourishes based on personality
        bg_pattern = self._select_background_pattern(personality_name, rng)
        accent_style = self._select_accent_style(personality_name, rng)
        special_mode = self._select_special_mode(personality_name, scheme, rng)
        animation_preset = ANIMATION_PRESETS.get(animation, ANIMATION_PRESETS["subtle"])

        # 5c. Select new design dimensions
        # Image treatment based on personality
        image_treatments = PERSONALITY_IMAGE_TREATMENTS.get(personality_name, ["none"])
        image_treatment = rng.choice(image_treatments)

        # Typography scale based on personality
        typography_scale = TYPOGRAPHY_SCALES.get(personality_name, TYPOGRAPHY_SCALES["editorial"])

        # Section divider based on personality
        section_dividers = PERSONALITY_SECTION_DIVIDERS.get(personality_name, ["line"])
        section_divider = rng.choice(section_dividers)

        # Card aspect ratio based on personality
        card_ratios = PERSONALITY_CARD_RATIOS.get(personality_name, ["auto"])
        card_aspect_ratio = rng.choice(card_ratios)

        # 5d. Content-aware animation adjustment
        content_sentiment = analyze_content_sentiment(trends, keywords)
        animation = get_content_aware_animation(trends, keywords, animation)

        # 5e. WCAG contrast validation
        contrast_validated = validate_color_contrast(scheme["text"], scheme["bg"])
        # Adjust text color if contrast is insufficient
        if not contrast_validated:
            scheme = {**scheme}  # Make a copy
            scheme["text"] = adjust_color_for_contrast(scheme["text"], scheme["bg"])
            contrast_validated = True

        # 6. Select AI variant if available (multi-variant support)
        selected_variant = None
        story_capsules: List[str] = []
        cta_options: List[str] = []

        if ai_data:
            variants = ai_data.get('variants') or []
            if variants:
                selected_variant = self._select_ai_variant(variants, keywords, recent_themes)
            story_capsules = ai_data.get('story_capsules') or []
            cta_options = ai_data.get('ctas') or []

        # 7. Generate headline and subheadline
        if selected_variant:
            headline = selected_variant.get('headline') or self._create_headline(trends, rng)
            subheadline = selected_variant.get('subheadline') or self._create_subheadline(keywords, rng)
            # Override scheme with AI colors/theme
            if selected_variant.get('color_accent'):
                scheme = {**scheme}
                scheme['accent'] = selected_variant['color_accent']
            if selected_variant.get('color_accent_secondary'):
                scheme['accent_secondary'] = selected_variant['color_accent_secondary']
            if selected_variant.get('theme_name'):
                scheme['name'] = selected_variant['theme_name']
        else:
            headline = self._create_headline(trends, rng)
            subheadline = self._create_subheadline(keywords, rng)

        # Map spacing to padding values
        padding_map = {
            "compact": "1rem",
            "comfortable": "1.5rem",
            "spacious": "2rem"
        }

        # Map border radius
        radius_map = {
            "0": "0",
            "0.25rem": "0.25rem",
            "0.5rem": "0.5rem",
            "0.75rem": "0.75rem",
            "1rem": "1rem",
            "1.5rem": "1.5rem",
            "2rem": "2rem",
            "9999px": "9999px",
        }

        return DesignSpec(
            # Identity
            theme_name=scheme["name"],
            personality=personality_name,
            mood=scheme.get("mood", "modern"),

            # Typography
            font_primary=fonts[0],
            font_secondary=fonts[1],
            font_style=font_style,
            text_transform_headings=text_transform,

            # Colors
            color_bg=scheme["bg"],
            color_text=scheme["text"],
            color_accent=scheme["accent"],
            color_accent_secondary=scheme["accent_secondary"],
            color_muted=scheme["muted"],
            color_card_bg=scheme["card_bg"],
            color_border=scheme["border"],
            is_dark_mode=scheme.get("dark", True),

            # Layout
            layout_style=layout_style,
            spacing=spacing,

            # Cards
            card_style=card_style,
            card_radius=radius_map.get(border_radius, "1rem"),
            card_padding=padding_map.get(spacing, "1.5rem"),

            # Effects
            animation_level=animation,
            use_gradients=personality.get("use_gradients", True),
            use_blur=card_style == "glass",
            hover_effect=hover_effect,

            # Hero
            hero_style=hero_style,

            # Creative flourishes
            background_pattern=bg_pattern,
            accent_style=accent_style,
            special_mode=special_mode,
            transition_speed=animation_preset.get("transition_speed", "200ms"),
            hover_transform=animation_preset.get("hover_transform", "translateY(-2px)"),
            use_pulse_animation=animation_preset.get("pulse", False),
            use_float_animation=animation_preset.get("float", False),

            # New design dimensions
            image_treatment=image_treatment,
            typography_scale=typography_scale,
            section_divider=section_divider,
            card_aspect_ratio=card_aspect_ratio,
            content_sentiment=content_sentiment,
            contrast_validated=contrast_validated,

            # Content
            headline=headline,
            subheadline=subheadline,
            story_capsules=story_capsules[:8],
            cta_options=cta_options[:3],
            cta_primary=(cta_options[0] if cta_options else ""),

            # Meta
            design_seed=datetime.now().strftime("%Y-%m-%d"),
        )

    def _select_background_pattern(self, personality: str, rng: random.Random) -> str:
        """Select a background pattern based on personality."""
        pattern_weights = {
            "brutalist": ["none", "grid", "diagonal"],
            "editorial": ["none", "none", "dots"],
            "minimal": ["none", "none", "none"],
            "corporate": ["none", "dots", "gradient_radial"],
            "playful": ["dots", "gradient_radial", "gradient_sweep", "noise"],
            "tech": ["grid", "dots", "noise", "gradient_radial"],
            "news": ["none", "none", "grid"],
            "magazine": ["none", "gradient_radial", "noise"],
            "dashboard": ["grid", "dots", "none"],
        }
        options = pattern_weights.get(personality, ["none"])
        return rng.choice(options)

    def _select_accent_style(self, personality: str, rng: random.Random) -> str:
        """Select decorative accent style based on personality."""
        accent_weights = {
            "brutalist": ["none", "underline", "corner_accent"],
            "editorial": ["none", "underline"],
            "minimal": ["none", "none"],
            "corporate": ["none", "glow"],
            "playful": ["glow", "neon_border", "pill_badge", "gradient_border"],
            "tech": ["glow", "neon_border", "gradient_border"],
            "news": ["none", "underline"],
            "magazine": ["none", "glow"],
            "dashboard": ["none", "glow", "neon_border"],
        }
        options = accent_weights.get(personality, ["none"])
        return rng.choice(options)

    def _select_special_mode(self, personality: str, scheme: Dict, rng: random.Random) -> str:
        """Select a special visual mode for dramatic variation."""
        mode_weights = {
            "brutalist": ["standard", "high_contrast", "monochrome", "duotone"],
            "editorial": ["standard", "standard", "muted"],
            "minimal": ["standard", "standard", "muted", "monochrome"],
            "corporate": ["standard", "standard"],
            "playful": ["standard", "vibrant", "glassmorphism"],
            "tech": ["standard", "glassmorphism", "duotone", "vibrant"],
            "news": ["standard", "high_contrast"],
            "magazine": ["standard", "vibrant", "muted"],
            "dashboard": ["standard", "glassmorphism", "high_contrast"],
        }
        options = mode_weights.get(personality, ["standard"])
        return rng.choice(options)

    def _select_ai_variant(self, variants: List[Dict], keywords: List[str], recent_themes: List[str]) -> Optional[Dict]:
        """Choose an AI variant deterministically while avoiding recent repeats."""
        if not variants:
            return None

        # Deterministic index based on date + top keyword
        seed_basis = datetime.now().strftime("%Y-%m-%d") + (keywords[0] if keywords else "")
        idx = int(hashlib.sha256(seed_basis.encode()).hexdigest(), 16) % len(variants)

        # Try to avoid recent theme reuse
        for offset in range(len(variants)):
            candidate = variants[(idx + offset) % len(variants)]
            theme_name = (candidate.get('theme_name') or "").lower()
            if theme_name and theme_name not in recent_themes:
                self._store_theme(theme_name)
                return candidate

        # Fallback to deterministic choice
        chosen = variants[idx]
        theme_name = (chosen.get('theme_name') or "").lower()
        if theme_name:
            self._store_theme(theme_name)
        return chosen

    def _build_rich_context(self, trends: List[Dict], keywords: List[str]) -> str:
        """
        Build rich context for AI design generation.

        Expands from basic titles to include descriptions, source distribution,
        and categorical analysis for better mood detection.
        """
        # Expand to 30 trends with descriptions for richer understanding
        trend_lines = []
        for i, t in enumerate(trends[:30]):
            source = t.get('source', 'unknown').replace('_', ' ').title()
            title = t.get('title', '')[:80]
            desc = (t.get('description', '') or '')[:120]

            # Format: [Source] Title
            trend_lines.append(f"{i+1}. [{source}] {title}")
            if desc and len(desc) > 20:
                # Add truncated description for context
                trend_lines.append(f"   → {desc}...")

        # Calculate source distribution for category awareness
        sources = {}
        for t in trends:
            src = t.get('source', 'other')
            # Normalize source names
            if 'rss' in src.lower():
                category = 'News' if 'news' in src.lower() else 'Tech'
            elif src in ['hackernews', 'lobsters', 'github_trending']:
                category = 'Tech'
            elif src == 'reddit':
                category = 'Social'
            else:
                category = src.replace('_', ' ').title()
            sources[category] = sources.get(category, 0) + 1

        # Sort by count descending
        distribution = ", ".join(
            f"{count} {cat}"
            for cat, count in sorted(sources.items(), key=lambda x: -x[1])[:5]
        )

        # Detect breaking news / urgency signals
        urgency_keywords = ['breaking', 'urgent', 'just in', 'developing', 'alert']
        breaking_count = sum(
            1 for t in trends
            if any(kw in t.get('title', '').lower() for kw in urgency_keywords)
        )
        urgency_note = f"BREAKING NEWS DETECTED: {breaking_count} urgent stories" if breaking_count > 0 else ""

        context = f"""TODAY'S TRENDING STORIES ({len(trends)} total):
{chr(10).join(trend_lines)}

SOURCE DISTRIBUTION: {distribution}
TOP KEYWORDS: {', '.join(keywords[:25])}"""

        if urgency_note:
            context += f"\n{urgency_note}"

        return context

    def _try_ai_generation(self, trends: List[Dict], keywords: List[str]) -> Optional[Dict]:
        """Try to get AI-generated design elements with rich context."""
        # Build rich context with expanded trend information
        rich_context = self._build_rich_context(trends, keywords)

        prompt = f"""You are a creative director designing a daily news aggregation website.

Analyze today's trending topics and create a cohesive design system that reflects the mood and themes of the day.

{rich_context}

Create multiple design variants that capture the essence of today's news cycle. Consider:
- Is the news mood serious, hopeful, chaotic, or transformative?
- What visual metaphors would resonate with these stories?
- What colors evoke the right emotional response?

Respond with ONLY a valid JSON object:
{{
  "mood_analysis": "1-2 sentence analysis of today's news mood",
  "variants": [
    {{
      "theme_name": "Evocative 2-3 word theme name",
      "headline": "Attention-grabbing 3-6 word headline",
      "subheadline": "Contextual subheadline, max 12 words",
      "color_accent": "#RRGGBB (mood-appropriate primary color)",
      "color_accent_secondary": "#RRGGBB (complementary secondary)",
      "cta": "Action-oriented CTA label"
    }},
    {{
      "theme_name": "Alternative theme",
      "headline": "Different angle headline",
      "subheadline": "Alternative subheadline",
      "color_accent": "#RRGGBB",
      "color_accent_secondary": "#RRGGBB",
      "cta": "Alternative CTA"
    }}
  ],
  "story_capsules": [
    "50-80 char engaging summary of top story 1",
    "50-80 char engaging summary of top story 2",
    "50-80 char engaging summary of top story 3"
  ],
  "ctas": ["Primary CTA", "Secondary CTA", "Tertiary CTA"]
}}"""

        providers = [
            ("Google AI", self._call_google_ai),
            ("OpenRouter", self._call_openrouter),
            ("Groq", self._call_groq_direct),
        ]

        for name, caller in providers:
            if self._has_key_for(name):
                try:
                    print(f"  Trying {name} for creative elements...")
                    response = caller(prompt)
                    if response:
                        return self._parse_ai_response(response)
                except Exception as e:
                    print(f"    {name} error: {e}")
                    continue

        return None

    def _has_key_for(self, provider: str) -> bool:
        if provider == "Google AI":
            return bool(self.google_key)
        elif provider == "Groq":
            return bool(self.groq_key)
        elif provider == "OpenRouter":
            return bool(self.openrouter_key)
        return False

    def _call_groq(self, prompt: str, max_tokens: int = 1000, max_retries: int = 1, task_complexity: str = 'simple') -> Optional[str]:
        """
        Call LLM API with smart provider routing based on task complexity.

        For simple tasks: OpenCode (free) > Mistral (free) > Hugging Face (free) > Groq > OpenRouter > Google AI
        For complex tasks: Mistral > Google AI > OpenRouter > OpenCode > Hugging Face > Groq

        Note: Design generation is 'simple' by default as it's a structured output task.
        """
        if task_complexity == 'simple':
            # For simple tasks, prioritize free models to save quota
            result = self._call_opencode(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_mistral(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_huggingface(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_groq_direct(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_openrouter(prompt, max_tokens, max_retries)
            if result:
                return result

            return self._call_google_ai(prompt, max_tokens, max_retries)
        else:
            # For complex tasks, prioritize higher quality models
            result = self._call_mistral(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_google_ai(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_openrouter(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_opencode(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_huggingface(prompt, max_tokens, max_retries)
            if result:
                return result

            return self._call_groq_direct(prompt, max_tokens, max_retries)

    def _call_google_ai(self, prompt: str, max_tokens: int = 1000, max_retries: int = 1) -> Optional[str]:
        """Call Google AI (Gemini) API - primary provider with generous free tier."""
        if not self.google_key:
            print("    No Google AI API key available")
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('google')

        if not status.is_available:
            print(f"    Google AI not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            print(f"    Waiting {status.wait_seconds:.1f}s for Google AI rate limit...")
            time.sleep(status.wait_seconds)

        # Use Gemini 2.5 Flash Lite - highest RPM (10) among free models
        model = "gemini-2.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for attempt in range(max_retries):
            try:
                print(f"    Trying Google AI {model} (attempt {attempt + 1}/{max_retries})")
                response = self.session.post(
                    url,
                    headers={
                        "x-goog-api-key": self.google_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": max_tokens,
                            "temperature": 0.7
                        }
                    },
                    timeout=60
                )
                response.raise_for_status()

                # Update rate limiter tracking
                rate_limiter._last_call_time['google'] = time.time()

                # Parse response
                data = response.json()
                candidates = data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        text = parts[0].get('text', '')
                        if text:
                            print(f"    Google AI success with {model}")
                            return text

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', '10')
                    try:
                        wait_time = float(retry_after)
                    except ValueError:
                        wait_time = 10.0
                    print(f"    Google AI rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                print(f"    Google AI failed: {e}")
                return None
            except Exception as e:
                print(f"    Google AI failed: {e}")
                return None

        print("    Google AI: Max retries exceeded")
        return None

    def _call_openrouter(self, prompt: str, max_tokens: int = 1000, max_retries: int = 1) -> Optional[str]:
        """Call OpenRouter API with free models (primary)."""
        if not self.openrouter_key:
            print("    No OpenRouter API key available")
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('openrouter')

        if not status.is_available:
            print(f"    OpenRouter not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            print(f"    Waiting {status.wait_seconds:.1f}s for OpenRouter rate limit...")
            time.sleep(status.wait_seconds)

        # Free models to try in order of preference
        free_models = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-r1-0528:free",
            "google/gemma-3-27b-it:free",
        ]

        for model in free_models:
            for attempt in range(max_retries):
                try:
                    print(f"    Trying OpenRouter {model} (attempt {attempt + 1}/{max_retries})")
                    response = self.session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openrouter_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://dailytrending.info",
                            "X-Title": "DailyTrending.info"
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": 0.7
                        },
                        timeout=60
                    )
                    response.raise_for_status()

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers('openrouter', dict(response.headers))

                    result = response.json().get('choices', [{}])[0].get('message', {}).get('content')
                    if result:
                        print(f"    OpenRouter success with {model}")
                        return result
                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        # Parse retry-after header if available
                        retry_after = response.headers.get('Retry-After', '10')
                        try:
                            wait_time = float(retry_after)
                        except ValueError:
                            wait_time = 10.0
                        print(f"    OpenRouter {model} rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    print(f"    OpenRouter {model} failed: {e}")
                    break  # Try next model
                except Exception as e:
                    print(f"    OpenRouter {model} failed: {e}")
                    break  # Try next model

        print("    All OpenRouter models failed")
        return None

    def _call_groq_direct(self, prompt: str, max_tokens: int = 1000, max_retries: int = 1) -> Optional[str]:
        """Call Groq API directly (fallback)."""
        if not self.groq_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('groq')

        if not status.is_available:
            print(f"    Groq not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            print(f"    Waiting {status.wait_seconds:.1f}s for Groq rate limit...")
            time.sleep(status.wait_seconds)

        # Proactive rate limiting
        elapsed = time.time() - self._last_call_time
        if elapsed < self.MIN_CALL_INTERVAL:
            time.sleep(self.MIN_CALL_INTERVAL - elapsed)

        for attempt in range(max_retries):
            try:
                self._last_call_time = time.time()
                response = self.session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.7
                    },
                    timeout=45
                )
                response.raise_for_status()

                # Update rate limiter from response headers
                rate_limiter.update_from_response_headers('groq', dict(response.headers))

                return response.json().get('choices', [{}])[0].get('message', {}).get('content')
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # Parse retry-after header if available
                    retry_after = response.headers.get('Retry-After', '10')
                    try:
                        wait_time = float(retry_after)
                    except ValueError:
                        wait_time = 10.0
                    print(f"    Groq rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                print(f"    Groq API error: {e}")
                return None
            except Exception as e:
                print(f"    Groq API error: {e}")
                return None

        print("    Groq API: Max retries exceeded")
        return None

    def _call_opencode(self, prompt: str, max_tokens: int = 1000, max_retries: int = 1) -> Optional[str]:
        """Call OpenCode API with free models (glm-4.7-free, minimax-m2.1-free)."""
        opencode_key = os.getenv('OPENCODE_API_KEY')
        if not opencode_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('opencode')

        if not status.is_available:
            print(f"    OpenCode not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            print(f"    Waiting {status.wait_seconds:.1f}s for OpenCode rate limit...")
            time.sleep(status.wait_seconds)

        # Proactive rate limiting
        elapsed = time.time() - self._last_call_time
        if elapsed < self.MIN_CALL_INTERVAL:
            time.sleep(self.MIN_CALL_INTERVAL - elapsed)

        # Free models to try in order
        free_models = ["glm-4.7-free", "minimax-m2.1-free"]

        for model in free_models:
            for attempt in range(max_retries):
                try:
                    self._last_call_time = time.time()
                    print(f"    Trying OpenCode {model} (attempt {attempt + 1}/{max_retries})")
                    response = self.session.post(
                        "https://opencode.ai/zen/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {opencode_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": 0.7
                        },
                        timeout=60
                    )
                    response.raise_for_status()

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers('opencode', dict(response.headers))
                    rate_limiter._last_call_time['opencode'] = time.time()

                    result = response.json().get('choices', [{}])[0].get('message', {}).get('content')
                    if result:
                        print(f"    OpenCode success with {model}")
                        return result

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        retry_after = response.headers.get('Retry-After', '10')
                        try:
                            wait_time = float(retry_after)
                        except ValueError:
                            wait_time = 10.0
                        print(f"    OpenCode rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    print(f"    OpenCode API error with {model}: {e}")
                    break  # Try next model
                except Exception as e:
                    print(f"    OpenCode API error with {model}: {e}")
                    break  # Try next model

        print("    All OpenCode models failed")
        return None

    def _call_huggingface(self, prompt: str, max_tokens: int = 1000, max_retries: int = 1) -> Optional[str]:
        """Call Hugging Face Inference API with free models."""
        huggingface_key = os.getenv('HUGGINGFACE_API_KEY')
        if not huggingface_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('huggingface')

        if not status.is_available:
            print(f"    Hugging Face not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            print(f"    Waiting {status.wait_seconds:.1f}s for Hugging Face rate limit...")
            time.sleep(status.wait_seconds)

        # Proactive rate limiting
        elapsed = time.time() - self._last_call_time
        if elapsed < self.MIN_CALL_INTERVAL:
            time.sleep(self.MIN_CALL_INTERVAL - elapsed)

        # Free models to try in order (7B models work well on free tier)
        free_models = [
            "mistralai/Mistral-7B-Instruct-v0.3",
            "Qwen/Qwen2.5-7B-Instruct",
            "microsoft/Phi-3-mini-4k-instruct",
        ]

        for model in free_models:
            for attempt in range(max_retries):
                try:
                    self._last_call_time = time.time()
                    print(f"    Trying Hugging Face {model} (attempt {attempt + 1}/{max_retries})")
                    response = self.session.post(
                        f"https://api-inference.huggingface.co/models/{model}",
                        headers={
                            "Authorization": f"Bearer {huggingface_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "inputs": prompt,
                            "parameters": {
                                "max_new_tokens": max_tokens,
                                "temperature": 0.7,
                                "return_full_text": False
                            }
                        },
                        timeout=60
                    )
                    response.raise_for_status()

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers('huggingface', dict(response.headers))
                    rate_limiter._last_call_time['huggingface'] = time.time()

                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        text = result[0].get('generated_text', '')
                        if text:
                            print(f"    Hugging Face success with {model}")
                            return text

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        retry_after = response.headers.get('Retry-After', '10')
                        try:
                            wait_time = float(retry_after)
                        except ValueError:
                            wait_time = 10.0
                        print(f"    Hugging Face rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    elif response.status_code == 503:
                        # Model is loading, wait and retry
                        print(f"    Hugging Face model {model} is loading, waiting...")
                        time.sleep(20)
                        continue
                    print(f"    Hugging Face API error with {model}: {e}")
                    break  # Try next model
                except Exception as e:
                    print(f"    Hugging Face API error with {model}: {e}")
                    break  # Try next model

        print("    All Hugging Face models failed")
        return None

    def _call_mistral(self, prompt: str, max_tokens: int = 1000, max_retries: int = 1) -> Optional[str]:
        """Call Mistral AI API - high quality free tier models."""
        mistral_key = os.getenv('MISTRAL_API_KEY')
        if not mistral_key:
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call('mistral')

        if not status.is_available:
            print(f"    Mistral not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            print(f"    Waiting {status.wait_seconds:.1f}s for Mistral rate limit...")
            time.sleep(status.wait_seconds)

        # Proactive rate limiting
        elapsed = time.time() - self._last_call_time
        if elapsed < self.MIN_CALL_INTERVAL:
            time.sleep(self.MIN_CALL_INTERVAL - elapsed)

        # Free tier models to try in order of preference
        # mistral-small-latest is the best free model, open-mistral-7b as fallback
        free_models = ["mistral-small-latest", "open-mistral-7b"]

        for model in free_models:
            for attempt in range(max_retries):
                try:
                    self._last_call_time = time.time()
                    print(f"    Trying Mistral {model} (attempt {attempt + 1}/{max_retries})")
                    response = self.session.post(
                        "https://api.mistral.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {mistral_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": 0.7
                        },
                        timeout=60
                    )
                    response.raise_for_status()

                    # Update rate limiter from response headers
                    rate_limiter.update_from_response_headers('mistral', dict(response.headers))
                    rate_limiter._last_call_time['mistral'] = time.time()

                    result = response.json().get('choices', [{}])[0].get('message', {}).get('content')
                    if result:
                        print(f"    Mistral success with {model}")
                        return result

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        retry_after = response.headers.get('Retry-After', '10')
                        try:
                            wait_time = float(retry_after)
                        except ValueError:
                            wait_time = 10.0
                        print(f"    Mistral rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    print(f"    Mistral API error with {model}: {e}")
                    break  # Try next model
                except Exception as e:
                    print(f"    Mistral API error with {model}: {e}")
                    break  # Try next model

        print("    All Mistral models failed")
        return None

    def _parse_ai_response(self, response: str) -> Optional[Dict]:
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            payload = json_match.group() if json_match else response

            # Try parsing as-is first
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                # Escape control characters only INSIDE quoted strings
                def escape_string_contents(match):
                    s = match.group(0)
                    inner = s[1:-1]  # Remove quotes
                    # Only escape raw control characters
                    inner = inner.replace('\n', '\\n')
                    inner = inner.replace('\r', '\\r')
                    inner = inner.replace('\t', '\\t')
                    inner = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', lambda m: f'\\u{ord(m.group()):04x}', inner)
                    return f'"{inner}"'

                try:
                    sanitized = re.sub(r'"(?:[^"\\]|\\.)*"', escape_string_contents, payload)
                    data = json.loads(sanitized)
                except (json.JSONDecodeError, Exception):
                    # Last resort: strip all control chars except structural whitespace
                    stripped = re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f]', ' ', payload)
                    data = json.loads(stripped)

            # Normalize single-variant responses
            if data and 'variants' not in data:
                data = {
                    "variants": [
                        {
                            "theme_name": data.get("theme_name"),
                            "headline": data.get("headline"),
                            "subheadline": data.get("subheadline"),
                            "color_accent": data.get("color_accent"),
                            "color_accent_secondary": data.get("color_accent_secondary"),
                            "cta": data.get("cta") or data.get("cta_primary"),
                        }
                    ]
                }
            return data
        except (json.JSONDecodeError, Exception) as e:
            print(f"    Parse error: {e}")
        return None

    def _create_headline(self, trends: List[Dict], rng: random.Random) -> str:
        """Create a headline from trends."""
        if not trends:
            return "What's Trending"

        # Get top trend title - display full text, CSS handles wrapping
        top = trends[0].get('title', 'Trending Now')

        return top

    def _create_subheadline(self, keywords: List[str], rng: random.Random) -> str:
        """Create a subheadline."""
        templates = [
            "The stories shaping today",
            "What the world is talking about",
            "Today's pulse: {kw1}, {kw2}, and more",
            "From {kw1} to {kw2}—today's top trends",
            "Breaking: {kw1} headlines dominate",
            "Exploring {kw1}, {kw2}, {kw3}",
            "{kw1} trends worldwide",
            "Top stories in {kw1} and beyond",
        ]

        template = rng.choice(templates)

        if '{kw' in template and len(keywords) >= 3:
            return template.format(
                kw1=keywords[0].title(),
                kw2=keywords[1].title(),
                kw3=keywords[2].title()
            )

        return template

    def save(self, spec: DesignSpec, filepath: str):
        """Save design spec to JSON."""
        with open(filepath, 'w') as f:
            json.dump(asdict(spec), f, indent=2)
        print(f"Saved design spec to {filepath}")

    def _load_recent_themes(self, days: int = 7) -> List[str]:
        """Load theme history and return recent theme names."""
        if not self.history_path.exists():
            return []
        try:
            with open(self.history_path) as f:
                data = json.load(f)
            cutoff = datetime.now() - timedelta(days=days)
            recent = [
                entry.get('theme', '').lower()
                for entry in data
                if entry.get('timestamp') and datetime.fromisoformat(entry['timestamp']) > cutoff
            ]
            return [r for r in recent if r]
        except Exception:
            return []

    def _store_theme(self, theme: str):
        """Persist the chosen theme to avoid repeats."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            history = []
            if self.history_path.exists():
                with open(self.history_path) as f:
                    history = json.load(f)
            history.append({"theme": theme, "timestamp": datetime.now().isoformat()})
            history = history[-30:]  # keep compact
            with open(self.history_path, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass


def calculate_combinations():
    """Calculate total possible design combinations."""
    personalities = len(PERSONALITIES)
    avg_schemes_per_personality = 4
    avg_fonts_per_style = 6
    card_styles = 4  # average per personality
    radii = 2
    spacings = 2
    animations = 2
    hovers = 2
    layouts = len(LAYOUT_PATTERNS)
    heroes = len(HERO_PATTERNS)

    total = (
        personalities *
        avg_schemes_per_personality *
        avg_fonts_per_style *
        card_styles *
        radii *
        spacings *
        animations *
        hovers *
        layouts *
        heroes
    )
    return total


def main():
    """Test design generation."""
    from dotenv import load_dotenv
    load_dotenv()

    print(f"Total possible combinations: ~{calculate_combinations():,}")
    print()

    generator = DesignGenerator()

    sample_trends = [
        {"title": "AI Breakthrough in Medicine", "keywords": ["ai", "medicine"]},
        {"title": "Climate Summit 2024", "keywords": ["climate", "environment"]},
        {"title": "SpaceX Launch", "keywords": ["space", "rocket"]},
    ]
    sample_keywords = ["ai", "climate", "space", "tech", "economy"]

    spec = generator.generate(sample_trends, sample_keywords)

    print("\nGenerated Design:")
    print("-" * 60)
    print(f"Personality: {spec.personality}")
    print(f"Theme: {spec.theme_name}")
    print(f"Mood: {spec.mood}")
    print(f"Fonts: {spec.font_primary} / {spec.font_secondary} ({spec.font_style})")
    print(f"Colors: bg={spec.color_bg}, accent={spec.color_accent}")
    print(f"Layout: {spec.layout_style} / Hero: {spec.hero_style}")
    print(f"Cards: {spec.card_style}, radius={spec.card_radius}")
    print(f"Effects: animation={spec.animation_level}, hover={spec.hover_effect}")
    print(f"Headline: {spec.headline}")


if __name__ == "__main__":
    main()
