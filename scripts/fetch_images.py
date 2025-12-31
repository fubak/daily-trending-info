#!/usr/bin/env python3
"""
Image Fetcher - Fetches images from Pexels and Unsplash based on trending keywords.
Provides fallback mechanisms and proper attribution.
"""

import os
import json
import time
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus

import requests


@dataclass
class Image:
    """Represents a fetched image with metadata."""
    id: str
    url_small: str  # ~400px
    url_medium: str  # ~800px
    url_large: str  # ~1200px
    url_original: str
    photographer: str
    photographer_url: str
    source: str  # 'pexels' or 'unsplash'
    alt_text: str
    color: Optional[str] = None  # Dominant color
    width: int = 0
    height: int = 0


class ImageFetcher:
    """Fetches and manages images from multiple sources."""

    def __init__(self, pexels_key: Optional[str] = None, unsplash_key: Optional[str] = None):
        self.pexels_key = pexels_key or os.getenv('PEXELS_API_KEY')
        self.unsplash_key = unsplash_key or os.getenv('UNSPLASH_ACCESS_KEY')

        self.session = requests.Session()
        self.images: List[Image] = []
        self.used_ids: set = set()

        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.5  # seconds

    def _rate_limit(self):
        """Ensure we don't exceed API rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def search_pexels(self, query: str, per_page: int = 5) -> List[Image]:
        """Search for images on Pexels."""
        if not self.pexels_key:
            print("  Pexels API key not configured")
            return []

        images = []

        try:
            self._rate_limit()

            headers = {'Authorization': self.pexels_key}
            params = {
                'query': query,
                'per_page': per_page,
                'orientation': 'landscape'
            }

            response = self.session.get(
                'https://api.pexels.com/v1/search',
                headers=headers,
                params=params,
                timeout=15
            )
            response.raise_for_status()

            data = response.json()

            for photo in data.get('photos', []):
                src = photo.get('src', {})

                image = Image(
                    id=f"pexels_{photo['id']}",
                    url_small=src.get('small', src.get('medium', '')),
                    url_medium=src.get('medium', src.get('large', '')),
                    url_large=src.get('large', src.get('large2x', '')),
                    url_original=src.get('original', src.get('large2x', '')),
                    photographer=photo.get('photographer', 'Unknown'),
                    photographer_url=photo.get('photographer_url', 'https://pexels.com'),
                    source='pexels',
                    alt_text=photo.get('alt', query),
                    color=photo.get('avg_color'),
                    width=photo.get('width', 0),
                    height=photo.get('height', 0)
                )
                images.append(image)

        except requests.exceptions.HTTPError as e:
            print(f"  Pexels API error: {e}")
        except Exception as e:
            print(f"  Pexels error: {e}")

        return images

    def search_unsplash(self, query: str, per_page: int = 5) -> List[Image]:
        """Search for images on Unsplash."""
        if not self.unsplash_key:
            print("  Unsplash API key not configured")
            return []

        images = []

        try:
            self._rate_limit()

            headers = {'Authorization': f'Client-ID {self.unsplash_key}'}
            params = {
                'query': query,
                'per_page': per_page,
                'orientation': 'landscape'
            }

            response = self.session.get(
                'https://api.unsplash.com/search/photos',
                headers=headers,
                params=params,
                timeout=15
            )
            response.raise_for_status()

            data = response.json()

            for photo in data.get('results', []):
                urls = photo.get('urls', {})
                user = photo.get('user', {})

                image = Image(
                    id=f"unsplash_{photo['id']}",
                    url_small=urls.get('small', urls.get('regular', '')),
                    url_medium=urls.get('regular', urls.get('full', '')),
                    url_large=urls.get('full', urls.get('raw', '')),
                    url_original=urls.get('raw', urls.get('full', '')),
                    photographer=user.get('name', 'Unknown'),
                    photographer_url=user.get('links', {}).get('html', 'https://unsplash.com'),
                    source='unsplash',
                    alt_text=photo.get('alt_description') or photo.get('description') or query,
                    color=photo.get('color'),
                    width=photo.get('width', 0),
                    height=photo.get('height', 0)
                )
                images.append(image)

        except requests.exceptions.HTTPError as e:
            print(f"  Unsplash API error: {e}")
        except Exception as e:
            print(f"  Unsplash error: {e}")

        return images

    def search(self, query: str, per_page: int = 5) -> List[Image]:
        """Search for images, trying Pexels first then Unsplash as fallback."""
        print(f"  Searching for: '{query}'")

        # Try Pexels first
        images = self.search_pexels(query, per_page)

        # If no results, try Unsplash
        if not images:
            images = self.search_unsplash(query, per_page)

        # Filter out already used images
        images = [img for img in images if img.id not in self.used_ids]

        print(f"    Found {len(images)} images")
        return images

    def fetch_for_keywords(self, keywords: List[str], images_per_keyword: int = 3) -> List[Image]:
        """Fetch images for a list of keywords."""
        print("Fetching images for keywords...")

        all_images = []

        for keyword in keywords:
            images = self.search(keyword, images_per_keyword)
            all_images.extend(images)

            # Mark as used
            for img in images:
                self.used_ids.add(img.id)

            time.sleep(0.3)  # Be nice to APIs

        self.images = all_images
        print(f"Total images fetched: {len(all_images)}")

        return all_images

    def get_hero_image(self) -> Optional[Image]:
        """Get a high-quality image suitable for hero section."""
        # Prefer larger images
        candidates = [
            img for img in self.images
            if img.width >= 1200 or 'large' in img.url_large
        ]

        if candidates:
            return random.choice(candidates)
        elif self.images:
            return random.choice(self.images)

        return None

    def get_card_images(self, count: int = 6) -> List[Image]:
        """Get images suitable for card backgrounds."""
        available = [img for img in self.images if img.id not in self.used_ids]

        if len(available) < count:
            # Reset used IDs if we need more
            available = self.images.copy()

        random.shuffle(available)
        selected = available[:count]

        # Mark as used
        for img in selected:
            self.used_ids.add(img.id)

        return selected

    def get_attributions(self) -> List[Dict]:
        """Get attribution info for all used images."""
        attributions = []
        seen = set()

        for img in self.images:
            if img.id in self.used_ids and img.photographer not in seen:
                seen.add(img.photographer)
                attributions.append({
                    'photographer': img.photographer,
                    'url': img.photographer_url,
                    'source': img.source.title()
                })

        return attributions

    def to_json(self) -> str:
        """Export images as JSON."""
        return json.dumps([asdict(img) for img in self.images], indent=2)

    def save(self, filepath: str):
        """Save images to a JSON file."""
        with open(filepath, 'w') as f:
            f.write(self.to_json())
        print(f"Saved {len(self.images)} images to {filepath}")


class FallbackImageGenerator:
    """
    Generates fallback gradient/pattern data when no images are available.
    Uses CSS gradients and patterns instead of external images.
    """

    # Curated gradient pairs
    GRADIENTS = [
        ('135deg', '#667eea', '#764ba2'),  # Purple blue
        ('135deg', '#f093fb', '#f5576c'),  # Pink
        ('135deg', '#4facfe', '#00f2fe'),  # Cyan
        ('135deg', '#43e97b', '#38f9d7'),  # Green
        ('135deg', '#fa709a', '#fee140'),  # Orange pink
        ('135deg', '#a8edea', '#fed6e3'),  # Soft pastel
        ('135deg', '#d299c2', '#fef9d7'),  # Lavender
        ('135deg', '#89f7fe', '#66a6ff'),  # Sky
        ('135deg', '#cd9cf2', '#f6f3ff'),  # Light purple
        ('135deg', '#ffecd2', '#fcb69f'),  # Peach
        ('180deg', '#0c0c0c', '#1a1a2e'),  # Dark
        ('180deg', '#1a1a2e', '#16213e'),  # Midnight
        ('135deg', '#ff9a9e', '#fecfef'),  # Soft pink
        ('135deg', '#a18cd1', '#fbc2eb'),  # Violet
        ('135deg', '#fad0c4', '#ffd1ff'),  # Rose
    ]

    @classmethod
    def get_gradient(cls) -> Tuple[str, str, str]:
        """Get a random gradient."""
        return random.choice(cls.GRADIENTS)

    @classmethod
    def get_gradient_css(cls) -> str:
        """Get a random gradient as CSS."""
        direction, color1, color2 = cls.get_gradient()
        return f"linear-gradient({direction}, {color1}, {color2})"

    @classmethod
    def get_mesh_gradient_css(cls) -> str:
        """Generate a more complex mesh-like gradient."""
        g1 = cls.get_gradient()
        g2 = cls.get_gradient()

        return f"""
            radial-gradient(at 40% 20%, {g1[1]} 0px, transparent 50%),
            radial-gradient(at 80% 0%, {g1[2]} 0px, transparent 50%),
            radial-gradient(at 0% 50%, {g2[1]} 0px, transparent 50%),
            radial-gradient(at 80% 50%, {g2[2]} 0px, transparent 50%),
            radial-gradient(at 0% 100%, {g1[1]} 0px, transparent 50%),
            radial-gradient(at 80% 100%, {g2[1]} 0px, transparent 50%),
            radial-gradient(at 0% 0%, {g1[2]} 0px, transparent 50%)
        """.strip()


def main():
    """Main entry point for testing image fetching."""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    fetcher = ImageFetcher()

    # Test keywords
    keywords = ['technology', 'nature', 'abstract', 'city', 'space']

    images = fetcher.fetch_for_keywords(keywords, images_per_keyword=2)

    if images:
        print("\nFetched Images:")
        print("-" * 60)

        for img in images[:5]:
            print(f"ID: {img.id}")
            print(f"  Photographer: {img.photographer} ({img.source})")
            print(f"  Size: {img.width}x{img.height}")
            print(f"  URL: {img.url_medium[:60]}...")
            print()

        # Test hero image
        hero = fetcher.get_hero_image()
        if hero:
            print(f"Hero image: {hero.id}")

        # Test attributions
        print("\nAttributions:")
        for attr in fetcher.get_attributions():
            print(f"  Photo by {attr['photographer']} on {attr['source']}")

        # Save
        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, '..', 'data', 'images.json')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fetcher.save(output_path)

    else:
        print("\nNo images fetched. Using fallback gradients...")
        print(f"Gradient: {FallbackImageGenerator.get_gradient_css()}")


if __name__ == "__main__":
    main()
