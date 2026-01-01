#!/usr/bin/env python3
"""
Pytest configuration and fixtures for DailyTrending.info tests.
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_trends():
    """Sample trend data for testing."""
    return [
        {
            "title": "Breaking: Major Tech Announcement",
            "source": "hackernews",
            "url": "https://example.com/tech-announcement",
            "description": "A major technology company made a significant announcement today.",
            "score": 150,
            "keywords": ["tech", "announcement", "major"],
            "timestamp": datetime.now().isoformat()
        },
        {
            "title": "New AI Model Released",
            "source": "reddit",
            "url": "https://example.com/ai-model",
            "description": "Researchers unveiled a new AI model with impressive capabilities.",
            "score": 120,
            "keywords": ["ai", "model", "research"],
            "timestamp": datetime.now().isoformat()
        },
        {
            "title": "Climate Report: Global Temperatures Rising",
            "source": "news_rss",
            "url": "https://example.com/climate-report",
            "description": "New report shows global temperatures continue to rise.",
            "score": 100,
            "keywords": ["climate", "temperature", "global"],
            "timestamp": datetime.now().isoformat()
        },
        {
            "title": "Sports Team Wins Championship",
            "source": "reddit",
            "url": "https://example.com/sports-win",
            "description": "Local sports team claims championship victory.",
            "score": 80,
            "keywords": ["sports", "championship", "team"],
            "timestamp": (datetime.now() - timedelta(hours=12)).isoformat()
        },
        {
            "title": "New Movie Breaks Box Office Records",
            "source": "news_rss",
            "url": "https://example.com/movie-records",
            "description": "The latest blockbuster has broken multiple box office records.",
            "score": 90,
            "keywords": ["movie", "box office", "records"],
            "timestamp": (datetime.now() - timedelta(hours=6)).isoformat()
        }
    ]


@pytest.fixture
def sample_images():
    """Sample image data for testing."""
    return [
        {
            "id": "pexels_12345",
            "url_small": "https://images.pexels.com/small/12345.jpg",
            "url_medium": "https://images.pexels.com/medium/12345.jpg",
            "url_large": "https://images.pexels.com/large/12345.jpg",
            "url_original": "https://images.pexels.com/original/12345.jpg",
            "photographer": "John Doe",
            "photographer_url": "https://pexels.com/johndoe",
            "source": "pexels",
            "alt_text": "Technology abstract",
            "color": "#4a90d9",
            "width": 1920,
            "height": 1080
        },
        {
            "id": "unsplash_67890",
            "url_small": "https://images.unsplash.com/small/67890.jpg",
            "url_medium": "https://images.unsplash.com/medium/67890.jpg",
            "url_large": "https://images.unsplash.com/large/67890.jpg",
            "url_original": "https://images.unsplash.com/original/67890.jpg",
            "photographer": "Jane Smith",
            "photographer_url": "https://unsplash.com/janesmith",
            "source": "unsplash",
            "alt_text": "Nature landscape",
            "color": "#2d9653",
            "width": 2560,
            "height": 1440
        }
    ]


@pytest.fixture
def sample_design():
    """Sample design specification for testing."""
    return {
        "theme_name": "Tech",
        "mood": "innovative",
        "headline": "Today's Top Trends",
        "subheadline": "Stay informed with the latest",
        "personality": "tech",
        "layout": "dashboard",
        "color_scheme": "midnight_indigo",
        "primary_color": "#667eea",
        "secondary_color": "#764ba2",
        "accent_color": "#4facfe",
        "background_color": "#0f0f23",
        "text_color": "#ffffff",
        "font_heading": "Space Grotesk",
        "font_body": "Inter",
        "animation_level": "moderate",
        "hero_style": "particles"
    }


@pytest.fixture
def mock_requests():
    """Mock requests for API tests."""
    with patch('requests.Session') as mock_session:
        mock_instance = MagicMock()
        mock_session.return_value = mock_instance
        yield mock_instance
