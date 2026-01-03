#!/usr/bin/env python3
"""
Media of the Day Fetcher - Fetches daily curated image and video content.

Sources:
- NASA Astronomy Picture of the Day (APOD) - Public domain space imagery
- Vimeo Staff Picks - High-quality curated short films
- Bing Image of the Day - Beautiful landscape/nature photography (backup)
"""

import os
import re
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
import requests
import feedparser

from config import setup_logging, TIMEOUTS

logger = setup_logging("media_of_day")


@dataclass
class ImageOfTheDay:
    """Represents the daily featured image."""
    title: str
    url: str
    url_hd: Optional[str]
    explanation: str
    date: str
    copyright: Optional[str]
    source: str  # 'nasa_apod' or 'bing'
    source_url: str  # Link to original source


@dataclass
class VideoOfTheDay:
    """Represents the daily featured video."""
    title: str
    description: str
    thumbnail_url: str
    video_url: str  # Vimeo/YouTube page URL
    embed_url: str  # Embeddable URL
    duration: Optional[str]
    author: str
    author_url: str
    date: str
    source: str  # 'vimeo_staff_picks'


class MediaOfDayFetcher:
    """Fetches daily curated media content."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DailyTrending.info/1.0 (https://dailytrending.info)'
        })
        self.image_of_day: Optional[ImageOfTheDay] = None
        self.video_of_day: Optional[VideoOfTheDay] = None

    def fetch_all(self) -> Dict:
        """Fetch both image and video of the day."""
        logger.info("Fetching Media of the Day...")

        # Fetch image of the day (try NASA APOD first, then Bing)
        self.image_of_day = self._fetch_nasa_apod()
        if not self.image_of_day:
            logger.info("NASA APOD unavailable, trying Bing Image of the Day...")
            self.image_of_day = self._fetch_bing_image()

        # Fetch video of the day
        self.video_of_day = self._fetch_vimeo_staff_pick()

        # Log results
        if self.image_of_day:
            logger.info(f"  Image of the Day: {self.image_of_day.title}")
        else:
            logger.warning("  No Image of the Day available")

        if self.video_of_day:
            logger.info(f"  Video of the Day: {self.video_of_day.title}")
        else:
            logger.warning("  No Video of the Day available")

        return self.to_dict()

    def _fetch_nasa_apod(self) -> Optional[ImageOfTheDay]:
        """Fetch NASA Astronomy Picture of the Day.

        API: https://api.nasa.gov/planetary/apod
        Free tier: 1000 requests/hour with demo key, more with registered key
        """
        try:
            # Use demo key or environment variable
            api_key = os.getenv('NASA_API_KEY', 'DEMO_KEY')
            url = f"https://api.nasa.gov/planetary/apod?api_key={api_key}"

            response = self.session.get(url, timeout=TIMEOUTS.get('default', 15))
            response.raise_for_status()

            data = response.json()

            # APOD sometimes returns videos instead of images
            media_type = data.get('media_type', 'image')
            if media_type != 'image':
                logger.info(f"NASA APOD is a {media_type} today, skipping for image section")
                return None

            return ImageOfTheDay(
                title=data.get('title', 'Astronomy Picture of the Day'),
                url=data.get('url', ''),
                url_hd=data.get('hdurl'),
                explanation=data.get('explanation', ''),
                date=data.get('date', datetime.now().strftime('%Y-%m-%d')),
                copyright=data.get('copyright'),
                source='nasa_apod',
                source_url='https://apod.nasa.gov/apod/astropix.html'
            )

        except Exception as e:
            logger.warning(f"NASA APOD fetch error: {e}")
            return None

    def _fetch_bing_image(self) -> Optional[ImageOfTheDay]:
        """Fetch Bing Image of the Day as backup.

        API: https://www.bing.com/HPImageArchive.aspx
        No API key required.
        """
        try:
            url = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=en-US"
            response = self.session.get(url, timeout=TIMEOUTS.get('default', 15))
            response.raise_for_status()

            data = response.json()
            images = data.get('images', [])

            if not images:
                return None

            img = images[0]
            base_url = "https://www.bing.com"

            # Extract title and copyright from the combined string
            title = img.get('title', 'Bing Image of the Day')
            copyright_text = img.get('copyright', '')

            # Bing provides various resolutions
            url_path = img.get('url', '')
            # Get higher resolution version
            hd_url = url_path.replace('1920x1080', 'UHD') if url_path else None

            return ImageOfTheDay(
                title=title,
                url=f"{base_url}{url_path}" if url_path else '',
                url_hd=f"{base_url}{hd_url}" if hd_url else None,
                explanation=copyright_text,  # Bing doesn't have explanations
                date=img.get('startdate', datetime.now().strftime('%Y%m%d')),
                copyright=copyright_text,
                source='bing',
                source_url=img.get('copyrightlink', 'https://www.bing.com')
            )

        except Exception as e:
            logger.warning(f"Bing Image fetch error: {e}")
            return None

    def _fetch_vimeo_staff_pick(self) -> Optional[VideoOfTheDay]:
        """Fetch latest Vimeo Staff Pick.

        RSS Feed: https://vimeo.com/channels/staffpicks/videos/rss
        High-quality curated short films.
        """
        try:
            url = "https://vimeo.com/channels/staffpicks/videos/rss"
            response = self.session.get(url, timeout=TIMEOUTS.get('default', 15))
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            if not feed.entries:
                logger.warning("No Vimeo Staff Picks found in feed")
                return None

            # Get the most recent entry
            entry = feed.entries[0]

            # Extract video ID from link for embed URL
            video_url = entry.get('link', '')
            video_id = self._extract_vimeo_id(video_url)
            embed_url = f"https://player.vimeo.com/video/{video_id}" if video_id else ''

            # Extract thumbnail from media:content or description
            thumbnail_url = ''
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                thumbnail_url = entry.media_thumbnail[0].get('url', '')
            elif hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if 'image' in media.get('type', '') or media.get('medium') == 'image':
                        thumbnail_url = media.get('url', '')
                        break

            # If still no thumbnail, try to extract from description
            if not thumbnail_url:
                desc = entry.get('description', '')
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
                if img_match:
                    thumbnail_url = img_match.group(1)

            # Extract author info
            author = entry.get('author', '')
            if hasattr(entry, 'media_credit'):
                author = entry.media_credit
            author_url = ''

            # Parse duration if available
            duration = None
            if hasattr(entry, 'itunes_duration'):
                duration = entry.itunes_duration

            # Clean description (remove HTML)
            description = entry.get('description', '')
            description = re.sub(r'<[^>]+>', '', description)
            description = re.sub(r'\s+', ' ', description).strip()
            # Truncate if too long
            if len(description) > 500:
                description = description[:497] + '...'

            return VideoOfTheDay(
                title=entry.get('title', 'Vimeo Staff Pick'),
                description=description,
                thumbnail_url=thumbnail_url,
                video_url=video_url,
                embed_url=embed_url,
                duration=duration,
                author=author,
                author_url=author_url,
                date=entry.get('published', datetime.now().strftime('%Y-%m-%d')),
                source='vimeo_staff_picks'
            )

        except Exception as e:
            logger.warning(f"Vimeo Staff Picks fetch error: {e}")
            return None

    def _extract_vimeo_id(self, url: str) -> Optional[str]:
        """Extract Vimeo video ID from URL."""
        if not url:
            return None
        # Match patterns like vimeo.com/123456 or vimeo.com/channels/xxx/123456
        match = re.search(r'vimeo\.com/(?:channels/[^/]+/)?(\d+)', url)
        return match.group(1) if match else None

    def to_dict(self) -> Dict:
        """Convert media data to dictionary format."""
        return {
            'image_of_day': asdict(self.image_of_day) if self.image_of_day else None,
            'video_of_day': asdict(self.video_of_day) if self.video_of_day else None,
            'fetched_at': datetime.now().isoformat()
        }


def main():
    """Test the media fetcher."""
    fetcher = MediaOfDayFetcher()
    data = fetcher.fetch_all()

    print("\n=== Media of the Day ===\n")

    if data['image_of_day']:
        img = data['image_of_day']
        print(f"IMAGE: {img['title']}")
        print(f"  Source: {img['source']}")
        print(f"  URL: {img['url'][:80]}...")
        print(f"  Explanation: {img['explanation'][:100]}...")
        print()

    if data['video_of_day']:
        vid = data['video_of_day']
        print(f"VIDEO: {vid['title']}")
        print(f"  Author: {vid['author']}")
        print(f"  URL: {vid['video_url']}")
        print(f"  Embed: {vid['embed_url']}")
        print(f"  Description: {vid['description'][:100]}...")


if __name__ == "__main__":
    main()
