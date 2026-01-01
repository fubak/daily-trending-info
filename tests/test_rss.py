#!/usr/bin/env python3
"""Tests for RSS feed generation."""

import pytest
from pathlib import Path
from xml.etree import ElementTree as ET


class TestRSSGeneration:
    """Tests for RSS feed generator."""

    def test_generate_rss_feed_basic(self, sample_trends, temp_dir):
        """Test basic RSS feed generation."""
        from generate_rss import generate_rss_feed

        output_path = temp_dir / "feed.xml"
        xml = generate_rss_feed(sample_trends, output_path)

        assert xml
        assert output_path.exists()

        # Parse and validate
        root = ET.fromstring(xml)
        assert root.tag == "rss"
        assert root.get("version") == "2.0"

    def test_rss_contains_channel(self, sample_trends, temp_dir):
        """Test RSS feed has proper channel structure."""
        from generate_rss import generate_rss_feed

        xml = generate_rss_feed(sample_trends, temp_dir / "feed.xml")
        root = ET.fromstring(xml)

        channel = root.find("channel")
        assert channel is not None

        # Check required elements
        assert channel.find("title") is not None
        assert channel.find("link") is not None
        assert channel.find("description") is not None

    def test_rss_contains_items(self, sample_trends, temp_dir):
        """Test RSS feed contains trend items."""
        from generate_rss import generate_rss_feed

        xml = generate_rss_feed(sample_trends, temp_dir / "feed.xml")
        root = ET.fromstring(xml)

        channel = root.find("channel")
        items = channel.findall("item")

        assert len(items) > 0
        assert len(items) <= len(sample_trends)

        # Check item structure
        item = items[0]
        assert item.find("title") is not None
        assert item.find("link") is not None

    def test_rss_max_items_limit(self, sample_trends, temp_dir):
        """Test RSS feed respects max items limit."""
        from generate_rss import generate_rss_feed

        xml = generate_rss_feed(sample_trends, temp_dir / "feed.xml", max_items=2)
        root = ET.fromstring(xml)

        channel = root.find("channel")
        items = channel.findall("item")

        assert len(items) <= 2

    def test_rss_empty_trends(self, temp_dir):
        """Test RSS feed handles empty trends list."""
        from generate_rss import generate_rss_feed

        xml = generate_rss_feed([], temp_dir / "feed.xml")
        root = ET.fromstring(xml)

        channel = root.find("channel")
        items = channel.findall("item")

        assert len(items) == 0

    def test_rss_custom_metadata(self, sample_trends, temp_dir):
        """Test RSS feed with custom metadata."""
        from generate_rss import generate_rss_feed

        xml = generate_rss_feed(
            sample_trends,
            temp_dir / "feed.xml",
            title="Custom Title",
            description="Custom Description",
            link="https://custom.example.com"
        )
        root = ET.fromstring(xml)

        channel = root.find("channel")
        assert channel.find("title").text == "Custom Title"
        assert channel.find("description").text == "Custom Description"
        assert channel.find("link").text == "https://custom.example.com"
