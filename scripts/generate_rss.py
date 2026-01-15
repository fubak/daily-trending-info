#!/usr/bin/env python3
"""
RSS Feed Generator - Generates an RSS feed from collected trends.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional
from xml.etree import ElementTree as ET
from xml.dom import minidom

from config import (
    setup_logging,
    RSS_FEED_TITLE,
    RSS_FEED_DESCRIPTION,
    RSS_FEED_LINK,
    RSS_FEED_MAX_ITEMS,
    DATA_DIR,
    PUBLIC_DIR,
)

# Setup logging
logger = setup_logging("rss")


def _build_content_html(
    title: str, description: str, source: str, url: str, why_matters: str = ""
) -> str:
    """
    Build rich HTML content for RSS content:encoded element.

    Args:
        title: Story title
        description: Story description
        source: Source name
        url: Story URL
        why_matters: Optional 'Why This Matters' context

    Returns:
        HTML string wrapped in CDATA
    """
    source_formatted = source.replace("_", " ").title() if source else "Unknown"

    html_parts = [f"<h3>{title}</h3>"]

    if description:
        html_parts.append(f"<p>{description}</p>")

    if why_matters:
        html_parts.append(
            f"<blockquote><strong>Why This Matters:</strong> {why_matters}</blockquote>"
        )

    html_parts.append(f"<p><small>Source: {source_formatted}</small></p>")

    if url and url.startswith("http"):
        html_parts.append(f'<p><a href="{url}">Read full story →</a></p>')

    return "".join(html_parts)


def generate_rss_feed(
    trends: List[Dict],
    output_path: Optional[Path] = None,
    title: str = RSS_FEED_TITLE,
    description: str = RSS_FEED_DESCRIPTION,
    link: str = RSS_FEED_LINK,
    max_items: int = RSS_FEED_MAX_ITEMS,
) -> str:
    """
    Generate an RSS 2.0 feed from a list of trends.

    Args:
        trends: List of trend dictionaries with title, url, description, source, timestamp
        output_path: Optional path to save the feed
        title: Feed title
        description: Feed description
        link: Feed website link
        max_items: Maximum number of items to include

    Returns:
        The RSS XML as a string
    """
    # Create root element with content namespace for full text
    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:atom": "http://www.w3.org/2005/Atom",
            "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
            "xmlns:dc": "http://purl.org/dc/elements/1.1/",
        },
    )

    # Create channel
    channel = ET.SubElement(rss, "channel")

    # Channel metadata
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "link").text = link
    ET.SubElement(channel, "language").text = "en-us"

    # Build date
    now = datetime.now(timezone.utc)
    build_date = now.strftime("%a, %d %b %Y %H:%M:%S %z")
    ET.SubElement(channel, "lastBuildDate").text = build_date
    ET.SubElement(channel, "pubDate").text = build_date

    # Generator
    ET.SubElement(channel, "generator").text = "DailyTrending.info Pipeline"

    # Atom self-link for feed validation
    atom_link = ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    atom_link.set("href", f"{link}/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    # Add items (limited)
    items_added = 0
    seen_urls = set()

    for trend in trends[: max_items * 2]:  # Process extra in case of duplicates
        if items_added >= max_items:
            break

        url = trend.get("url")
        title_text = trend.get("title", "").strip()

        # Skip items without title or URL
        if not title_text:
            continue

        # Use a generated URL if none provided
        if not url:
            url = f"{link}#trend-{items_added}"

        # Skip duplicate URLs
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Create item
        item = ET.SubElement(channel, "item")

        # Title
        ET.SubElement(item, "title").text = title_text

        # Link
        ET.SubElement(item, "link").text = url

        # Description
        desc = trend.get("description") or trend.get("title", "")
        # Truncate long descriptions
        if len(desc) > 500:
            desc = desc[:497] + "..."
        ET.SubElement(item, "description").text = desc

        # Source/Category
        source = trend.get("source", "Unknown")
        ET.SubElement(item, "category").text = source

        # GUID (use URL or generate one)
        guid = ET.SubElement(item, "guid")
        guid.text = url
        guid.set("isPermaLink", "true" if url.startswith("http") else "false")

        # Publication date
        timestamp = trend.get("timestamp")
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                else:
                    dt = timestamp
                pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S %z")
                if (
                    not pub_date.endswith("+0000")
                    and "+" not in pub_date
                    and "-" not in pub_date[-5:]
                ):
                    pub_date += " +0000"
                ET.SubElement(item, "pubDate").text = pub_date
            except (ValueError, AttributeError):
                ET.SubElement(item, "pubDate").text = build_date
        else:
            ET.SubElement(item, "pubDate").text = build_date

        # Dublin Core creator
        ET.SubElement(item, "{http://purl.org/dc/elements/1.1/}creator").text = (
            "DailyTrending.info"
        )

        # Full content (content:encoded) with rich HTML
        full_desc = trend.get("description") or trend.get("title", "")
        why_matters = trend.get("why_this_matters", "")
        content_html = _build_content_html(
            title_text, full_desc, source, url, why_matters
        )
        content_encoded = ET.SubElement(
            item, "{http://purl.org/rss/1.0/modules/content/}encoded"
        )
        content_encoded.text = content_html

        items_added += 1

    # Convert to pretty XML string
    xml_string = ET.tostring(rss, encoding="unicode")

    # Parse and prettify
    try:
        dom = minidom.parseString(xml_string)
        pretty_xml = dom.toprettyxml(indent="  ", encoding=None)
        # Remove extra blank lines and fix declaration
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        pretty_xml = "\n".join(lines)
    except Exception:
        pretty_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_string}'

    logger.info(f"Generated RSS feed with {items_added} items")

    # Save if output path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(pretty_xml)
        logger.info(f"RSS feed saved to {output_path}")

    return pretty_xml


def generate_cmmc_rss_feed(
    trends: List[Dict],
    output_path: Optional[Path] = None,
    max_items: int = RSS_FEED_MAX_ITEMS,
) -> str:
    """
    Generate an RSS 2.0 feed for CMMC Watch from CMMC-related trends.

    Filters trends to only include those with 'cmmc_' source prefix.

    Args:
        trends: List of all trend dictionaries
        output_path: Optional path to save the feed (defaults to public/cmmc/feed.xml)
        max_items: Maximum number of items to include

    Returns:
        The RSS XML as a string
    """
    # Filter trends to only CMMC-related (source starts with 'cmmc_')
    cmmc_trends = [t for t in trends if t.get("source", "").startswith("cmmc_")]

    if not cmmc_trends:
        logger.info("No CMMC trends found for RSS feed")
        return ""

    # Use CMMC Watch branding
    return generate_rss_feed(
        trends=cmmc_trends,
        output_path=output_path,
        title="CMMC Watch - DailyTrending.info",
        description="CMMC compliance, certification, and Defense Industrial Base news aggregated daily",
        link=f"{RSS_FEED_LINK}/cmmc",
        max_items=max_items,
    )


def generate_cmmc_from_data_file(
    trends_file: Path = None, output_path: Path = None
) -> str:
    """
    Generate CMMC RSS feed from the saved trends.json data file.

    Args:
        trends_file: Path to trends.json (defaults to data/trends.json)
        output_path: Path to save feed.xml (defaults to public/cmmc/feed.xml)

    Returns:
        The RSS XML string
    """
    trends_file = trends_file or DATA_DIR / "trends.json"
    output_path = output_path or PUBLIC_DIR / "cmmc" / "feed.xml"

    if not trends_file.exists():
        logger.warning(f"Trends file not found: {trends_file}")
        return ""

    try:
        with open(trends_file) as f:
            trends = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load trends: {e}")
        return ""

    return generate_cmmc_rss_feed(trends, output_path)


def generate_from_data_file(trends_file: Path = None, output_path: Path = None) -> str:
    """
    Generate RSS feed from the saved trends.json data file.

    Args:
        trends_file: Path to trends.json (defaults to data/trends.json)
        output_path: Path to save feed.xml (defaults to public/feed.xml)

    Returns:
        The RSS XML string
    """
    trends_file = trends_file or DATA_DIR / "trends.json"
    output_path = output_path or PUBLIC_DIR / "feed.xml"

    if not trends_file.exists():
        logger.warning(f"Trends file not found: {trends_file}")
        return ""

    try:
        with open(trends_file) as f:
            trends = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load trends: {e}")
        return ""

    return generate_rss_feed(trends, output_path)


if __name__ == "__main__":
    # Generate feed from existing data
    xml = generate_from_data_file()
    if xml:
        print("RSS feed generated successfully!")
    else:
        print("Failed to generate RSS feed")
