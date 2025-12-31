#!/usr/bin/env python3
"""
Design Generator - Uses AI to generate unique website designs based on trends.
Supports Groq, OpenRouter, and Google AI with preset fallbacks.
"""

import os
import json
import random
import re
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime

import requests


@dataclass
class DesignSpec:
    """Specification for a generated design."""
    # Typography
    font_primary: str = "Space Grotesk"
    font_secondary: str = "Inter"
    font_size_base: str = "16px"
    font_size_hero: str = "clamp(2.5rem, 8vw, 6rem)"
    font_size_h2: str = "clamp(1.5rem, 4vw, 2.5rem)"
    font_size_body: str = "clamp(1rem, 2vw, 1.125rem)"

    # Colors
    color_bg: str = "#0a0a0a"
    color_text: str = "#ffffff"
    color_accent: str = "#6366f1"
    color_accent_secondary: str = "#8b5cf6"
    color_muted: str = "#a1a1aa"
    color_card_bg: str = "#18181b"
    color_border: str = "#27272a"

    # Layout
    layout_type: str = "bento"  # bento, masonry, grid
    card_radius: str = "1.5rem"
    card_padding: str = "1.5rem"
    section_gap: str = "1.5rem"
    max_width: str = "1400px"

    # Effects
    shadow_card: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    backdrop_blur: str = "12px"
    transition_speed: str = "0.3s"

    # Hero
    hero_overlay_opacity: str = "0.85"
    hero_gradient: str = ""

    # Mood/Theme
    mood: str = "modern"
    theme_name: str = "Default Dark"

    # Meta
    headline: str = "Today's Trends"
    subheadline: str = "What the world is talking about"
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()
        if not self.hero_gradient:
            self.hero_gradient = f"linear-gradient(135deg, {self.color_accent}, {self.color_accent_secondary})"


class DesignGenerator:
    """Generates design specifications using AI or presets."""

    # Curated font pairings
    FONT_PAIRINGS = [
        ("Space Grotesk", "Inter"),
        ("Outfit", "Source Sans 3"),
        ("DM Sans", "IBM Plex Sans"),
        ("Sora", "Nunito Sans"),
        ("Manrope", "Open Sans"),
        ("Plus Jakarta Sans", "Work Sans"),
        ("Rubik", "Karla"),
        ("Urbanist", "Lato"),
        ("Poppins", "Roboto"),
        ("Montserrat", "Hind"),
        ("Archivo", "Inter"),
        ("Barlow", "Source Sans 3"),
    ]

    # Curated color schemes
    COLOR_SCHEMES = [
        {
            "name": "Midnight Indigo",
            "bg": "#0a0a0a",
            "text": "#ffffff",
            "accent": "#6366f1",
            "accent_secondary": "#8b5cf6",
            "muted": "#a1a1aa",
            "card_bg": "#18181b",
            "border": "#27272a",
            "mood": "professional"
        },
        {
            "name": "Cyberpunk Neon",
            "bg": "#0d0d0d",
            "text": "#f0f0f0",
            "accent": "#00ff88",
            "accent_secondary": "#00ccff",
            "muted": "#888888",
            "card_bg": "#1a1a1a",
            "border": "#333333",
            "mood": "futuristic"
        },
        {
            "name": "Warm Sunset",
            "bg": "#1a1410",
            "text": "#fef3c7",
            "accent": "#f59e0b",
            "accent_secondary": "#ef4444",
            "muted": "#d4a574",
            "card_bg": "#292017",
            "border": "#3d2d1f",
            "mood": "warm"
        },
        {
            "name": "Ocean Deep",
            "bg": "#0a1628",
            "text": "#e2e8f0",
            "accent": "#0ea5e9",
            "accent_secondary": "#06b6d4",
            "muted": "#64748b",
            "card_bg": "#0f2847",
            "border": "#1e3a5f",
            "mood": "calm"
        },
        {
            "name": "Forest Night",
            "bg": "#0a120a",
            "text": "#ecfdf5",
            "accent": "#10b981",
            "accent_secondary": "#34d399",
            "muted": "#6b7c6b",
            "card_bg": "#152015",
            "border": "#1f3520",
            "mood": "natural"
        },
        {
            "name": "Royal Purple",
            "bg": "#0f0a1a",
            "text": "#f5f3ff",
            "accent": "#a855f7",
            "accent_secondary": "#c084fc",
            "muted": "#9c8fac",
            "card_bg": "#1a1025",
            "border": "#2e1f4a",
            "mood": "elegant"
        },
        {
            "name": "Crimson Dark",
            "bg": "#0f0a0a",
            "text": "#fef2f2",
            "accent": "#ef4444",
            "accent_secondary": "#f87171",
            "muted": "#a89090",
            "card_bg": "#1a1010",
            "border": "#3f1f1f",
            "mood": "bold"
        },
        {
            "name": "Minimal Light",
            "bg": "#fafafa",
            "text": "#18181b",
            "accent": "#18181b",
            "accent_secondary": "#3f3f46",
            "muted": "#71717a",
            "card_bg": "#ffffff",
            "border": "#e4e4e7",
            "mood": "clean"
        },
        {
            "name": "Soft Rose",
            "bg": "#1a0f14",
            "text": "#fdf2f8",
            "accent": "#ec4899",
            "accent_secondary": "#f472b6",
            "muted": "#a88899",
            "card_bg": "#251520",
            "border": "#3d1f30",
            "mood": "playful"
        },
        {
            "name": "Arctic Blue",
            "bg": "#0f1419",
            "text": "#f0f9ff",
            "accent": "#38bdf8",
            "accent_secondary": "#7dd3fc",
            "muted": "#7899a8",
            "card_bg": "#1a2633",
            "border": "#243544",
            "mood": "cool"
        },
    ]

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

    def generate(self, trends: List[Dict], keywords: List[str]) -> DesignSpec:
        """Generate a design based on trends and keywords."""
        print("Generating design specification...")

        # Try AI generation first
        ai_spec = self._try_ai_generation(trends, keywords)
        if ai_spec:
            print("  AI-generated design created")
            return ai_spec

        # Fall back to curated presets
        print("  Using curated preset design")
        return self._generate_preset(trends, keywords)

    def _try_ai_generation(self, trends: List[Dict], keywords: List[str]) -> Optional[DesignSpec]:
        """Attempt to generate design using AI."""

        # Prepare context
        trend_titles = [t.get('title', '') for t in trends[:10]]
        keyword_str = ', '.join(keywords[:15])

        prompt = self._build_prompt(trend_titles, keyword_str)

        # Try each AI provider in order
        providers = [
            ("Groq", self._call_groq),
            ("OpenRouter", self._call_openrouter),
            ("Google AI", self._call_google),
        ]

        for name, caller in providers:
            if self._has_key_for(name):
                try:
                    print(f"  Trying {name}...")
                    response = caller(prompt)
                    if response:
                        spec = self._parse_ai_response(response, trends)
                        if spec:
                            return spec
                except Exception as e:
                    print(f"    {name} error: {e}")
                    continue

        return None

    def _has_key_for(self, provider: str) -> bool:
        """Check if we have an API key for the provider."""
        if provider == "Groq":
            return bool(self.groq_key)
        elif provider == "OpenRouter":
            return bool(self.openrouter_key)
        elif provider == "Google AI":
            return bool(self.google_key)
        return False

    def _build_prompt(self, trends: List[str], keywords: str) -> str:
        """Build the prompt for AI design generation."""
        return f"""You are a creative web designer. Based on today's trending topics, create a unique website design specification.

Today's trending topics:
{chr(10).join(f'- {t}' for t in trends[:8])}

Key themes: {keywords}

Generate a design spec as JSON with these exact fields:
{{
  "theme_name": "creative name for this design",
  "mood": "one word mood (e.g., energetic, calm, bold, elegant)",
  "font_primary": "Google Font name for headings",
  "font_secondary": "Google Font name for body text",
  "color_bg": "hex background color (prefer dark, e.g., #0a0a0a)",
  "color_text": "hex text color",
  "color_accent": "hex primary accent color",
  "color_accent_secondary": "hex secondary accent color",
  "color_muted": "hex muted text color",
  "color_card_bg": "hex card background color",
  "headline": "creative headline (max 5 words) reflecting today's mood",
  "subheadline": "short tagline (max 10 words)"
}}

Requirements:
- Use modern, readable Google Fonts (e.g., Inter, Space Grotesk, Outfit, DM Sans)
- Dark mode preferred (dark background, light text)
- Accent colors should feel relevant to the trending topics
- Headline should be catchy and relevant to current events

Respond with ONLY the JSON object, no explanation."""

    def _call_groq(self, prompt: str) -> Optional[str]:
        """Call Groq API."""
        if not self.groq_key:
            return None

        response = self.session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.7
            },
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data.get('choices', [{}])[0].get('message', {}).get('content')

    def _call_openrouter(self, prompt: str) -> Optional[str]:
        """Call OpenRouter API."""
        if not self.openrouter_key:
            return None

        response = self.session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.7
            },
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data.get('choices', [{}])[0].get('message', {}).get('content')

    def _call_google(self, prompt: str) -> Optional[str]:
        """Call Google AI API."""
        if not self.google_key:
            return None

        response = self.session.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.google_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 500
                }
            },
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        candidates = data.get('candidates', [])
        if candidates:
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if parts:
                return parts[0].get('text')

        return None

    def _parse_ai_response(self, response: str, trends: List[Dict]) -> Optional[DesignSpec]:
        """Parse AI response into a DesignSpec."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if not json_match:
                return None

            data = json.loads(json_match.group())

            # Get top trend for headline if AI didn't provide one
            top_trend = trends[0].get('title', 'Trending Now') if trends else 'Trending Now'

            spec = DesignSpec(
                theme_name=data.get('theme_name', 'AI Generated'),
                mood=data.get('mood', 'modern'),
                font_primary=data.get('font_primary', 'Space Grotesk'),
                font_secondary=data.get('font_secondary', 'Inter'),
                color_bg=data.get('color_bg', '#0a0a0a'),
                color_text=data.get('color_text', '#ffffff'),
                color_accent=data.get('color_accent', '#6366f1'),
                color_accent_secondary=data.get('color_accent_secondary', '#8b5cf6'),
                color_muted=data.get('color_muted', '#a1a1aa'),
                color_card_bg=data.get('color_card_bg', '#18181b'),
                headline=data.get('headline', top_trend[:50]),
                subheadline=data.get('subheadline', 'What the world is talking about')
            )

            return spec

        except (json.JSONDecodeError, KeyError) as e:
            print(f"    Failed to parse AI response: {e}")
            return None

    def _generate_preset(self, trends: List[Dict], keywords: List[str]) -> DesignSpec:
        """Generate a design from curated presets."""
        # Select a random color scheme
        scheme = random.choice(self.COLOR_SCHEMES)

        # Select a random font pairing
        fonts = random.choice(self.FONT_PAIRINGS)

        # Generate headline from top trend
        top_trend = trends[0].get('title', 'Trending Today') if trends else 'Trending Today'
        headline = self._create_headline(top_trend)

        spec = DesignSpec(
            theme_name=scheme['name'],
            mood=scheme['mood'],
            font_primary=fonts[0],
            font_secondary=fonts[1],
            color_bg=scheme['bg'],
            color_text=scheme['text'],
            color_accent=scheme['accent'],
            color_accent_secondary=scheme['accent_secondary'],
            color_muted=scheme['muted'],
            color_card_bg=scheme['card_bg'],
            color_border=scheme['border'],
            headline=headline,
            subheadline=self._create_subheadline(keywords)
        )

        return spec

    def _create_headline(self, trend: str) -> str:
        """Create a catchy headline from a trend."""
        # Truncate if too long
        if len(trend) > 40:
            words = trend.split()[:5]
            trend = ' '.join(words)
            if len(trend) > 40:
                trend = trend[:37] + '...'

        return trend

    def _create_subheadline(self, keywords: List[str]) -> str:
        """Create a subheadline from keywords."""
        templates = [
            "Today's pulse: {kw1}, {kw2}, and more",
            "The world is talking about {kw1}",
            "From {kw1} to {kw2}",
            "Exploring {kw1}, {kw2}, {kw3}",
            "What's trending in {kw1}",
        ]

        if len(keywords) >= 3:
            template = random.choice(templates)
            return template.format(
                kw1=keywords[0],
                kw2=keywords[1],
                kw3=keywords[2]
            )

        return "What the world is talking about"

    def save(self, spec: DesignSpec, filepath: str):
        """Save design spec to a JSON file."""
        with open(filepath, 'w') as f:
            json.dump(asdict(spec), f, indent=2)
        print(f"Saved design spec to {filepath}")


def main():
    """Main entry point for testing design generation."""
    from dotenv import load_dotenv
    load_dotenv()

    generator = DesignGenerator()

    # Sample trends for testing
    sample_trends = [
        {"title": "AI Breakthrough in Medicine", "keywords": ["ai", "medicine", "health"]},
        {"title": "Climate Summit 2024", "keywords": ["climate", "environment", "summit"]},
        {"title": "Space X Launch Success", "keywords": ["space", "spacex", "launch"]},
        {"title": "New iPhone Announcement", "keywords": ["apple", "iphone", "tech"]},
        {"title": "Global Economy Update", "keywords": ["economy", "markets", "finance"]},
    ]

    sample_keywords = ["ai", "climate", "space", "tech", "economy", "health"]

    spec = generator.generate(sample_trends, sample_keywords)

    print("\nGenerated Design Spec:")
    print("-" * 60)
    print(f"Theme: {spec.theme_name}")
    print(f"Mood: {spec.mood}")
    print(f"Fonts: {spec.font_primary} / {spec.font_secondary}")
    print(f"Colors:")
    print(f"  Background: {spec.color_bg}")
    print(f"  Text: {spec.color_text}")
    print(f"  Accent: {spec.color_accent}")
    print(f"Headline: {spec.headline}")
    print(f"Subheadline: {spec.subheadline}")

    # Save
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, '..', 'data', 'design.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    generator.save(spec, output_path)


if __name__ == "__main__":
    main()
