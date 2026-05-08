"""Shared TypedDict schemas for the dictionaries that flow through the pipeline.

These mirror the dataclass fields in `collect_trends.Trend`, `fetch_images.Image`,
and the design-token shape produced by `fixed_design.build_fixed_design`. We
keep them as TypedDicts (not the dataclasses themselves) because most pipeline
stages serialise data via `asdict()` and pass plain `dict`s thereafter.

Use `total=False` so missing keys don't trigger type errors — the pipeline
defensively `.get()`s most fields anyway.
"""

from __future__ import annotations

from typing import List, Optional, TypedDict


class TrendDict(TypedDict, total=False):
    """Serialised form of `collect_trends.Trend` (after `asdict`)."""

    title: str
    source: str
    url: Optional[str]
    description: Optional[str]
    category: Optional[str]
    score: float
    keywords: List[str]
    timestamp: str  # ISO-8601 after asdict()
    image_url: Optional[str]
    source_metadata: dict
    source_label: Optional[str]
    corroborating_sources: List[str]
    corroborating_urls: List[str]
    source_diversity: int


class ImageDict(TypedDict, total=False):
    """Serialised form of `fetch_images.Image` (after `asdict`)."""

    id: str
    url_small: str
    url_medium: str
    url_large: str
    url_original: str
    photographer: str
    photographer_url: str
    source: str  # "pexels" | "unsplash" | "pixabay" | "lorem_picsum"
    alt_text: str
    color: Optional[str]
    width: int
    height: int


class DesignTokens(TypedDict, total=False):
    """Design-token dict consumed by renderers.

    Matches the keys validated by `design_tokens.validate_design_tokens()`.
    """

    primary_color: str
    accent_color: str
    bg_color: str
    text_color: str
    muted_color: str
    border_color: str
    card_bg: str
    font_primary: str
    font_secondary: str
    base_mode: str  # "dark-mode" | "light-mode"


class MediaItemDict(TypedDict, total=False):
    """Single media item (image or video) inside MediaData."""

    title: str
    description: str
    url: str
    url_hd: str
    embed_url: str
    video_url: str
    thumbnail: str
    explanation: str
    source: str
    source_url: str
    copyright: str
    creator: str
    author: str
    date: str


class MediaData(TypedDict, total=False):
    """Top-level media-of-the-day payload consumed by media_page_generator."""

    image_of_day: MediaItemDict
    video_of_day: MediaItemDict
