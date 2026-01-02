#!/usr/bin/env python3
"""
Image Fetcher - Fetches images from Pexels, Unsplash, and Pixabay based on trending keywords.
Provides fallback mechanisms and persistent caching.
Sources: Pexels (primary) → Unsplash → Pixabay (CC0).
"""

import os
import json
import time
import random
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from urllib.parse import quote_plus

import requests

from config import (
    setup_logging, IMAGE_CACHE_DIR, IMAGE_CACHE_MAX_AGE_DAYS,
    IMAGE_CACHE_MAX_ENTRIES, TIMEOUTS, RETRY_MAX_ATTEMPTS,
    RETRY_BACKOFF_FACTOR, RETRY_STATUS_CODES, DELAYS, MIN_IMAGES_REQUIRED
)

# Setup logging
logger = setup_logging("images")

# Cache configuration (using config values)
CACHE_DIR = IMAGE_CACHE_DIR
CACHE_INDEX_FILE = CACHE_DIR / "cache_index.json"
CACHE_MAX_AGE_DAYS = IMAGE_CACHE_MAX_AGE_DAYS
CACHE_MAX_ENTRIES = IMAGE_CACHE_MAX_ENTRIES


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
    source: str  # 'pexels', 'unsplash', 'pixabay', or 'lorem_picsum'
    alt_text: str
    color: Optional[str] = None  # Dominant color
    width: int = 0
    height: int = 0


class ImageCache:
    """Persistent disk cache for images to reduce API calls and provide fallback."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.index_file = cache_dir / "cache_index.json"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index = self._load_index()

    def _load_index(self) -> Dict:
        """Load the cache index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"queries": {}, "images": {}}

    def _save_index(self):
        """Save the cache index to disk using atomic file operations."""
        try:
            # Write to temporary file first, then rename for atomicity
            fd, tmp_path = tempfile.mkstemp(
                dir=self.cache_dir,
                prefix='.cache_index_',
                suffix='.tmp'
            )
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(self.index, f, indent=2)
                # Atomic rename (works on POSIX systems)
                os.replace(tmp_path, self.index_file)
            except Exception:
                # Clean up temp file on failure
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        except IOError as e:
            logger.warning(f"Could not save cache index: {e}")

    def _query_key(self, query: str) -> str:
        """Generate a normalized cache key for a query."""
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def is_cached(self, query: str) -> bool:
        """Check if a query has cached results that aren't expired."""
        key = self._query_key(query)
        if key not in self.index.get("queries", {}):
            return False

        cached = self.index["queries"][key]
        cached_time = datetime.fromisoformat(cached.get("timestamp", "2000-01-01"))
        max_age = timedelta(days=CACHE_MAX_AGE_DAYS)

        return datetime.now() - cached_time < max_age

    def get_cached(self, query: str) -> List[Image]:
        """Get cached images for a query."""
        key = self._query_key(query)
        if key not in self.index.get("queries", {}):
            return []

        cached = self.index["queries"][key]
        image_ids = cached.get("image_ids", [])

        images = []
        for img_id in image_ids:
            if img_id in self.index.get("images", {}):
                img_data = self.index["images"][img_id]
                try:
                    images.append(Image(**img_data))
                except TypeError:
                    continue

        return images

    def cache_results(self, query: str, images: List[Image]):
        """Cache search results for a query."""
        if not images:
            return

        key = self._query_key(query)

        # Store images in the images index
        for img in images:
            self.index.setdefault("images", {})[img.id] = asdict(img)

        # Store query mapping
        self.index.setdefault("queries", {})[key] = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "image_ids": [img.id for img in images]
        }

        # Enforce max entries limit
        self._cleanup_if_needed()

        # Save to disk
        self._save_index()

    def _cleanup_if_needed(self):
        """Remove oldest entries if cache exceeds max size."""
        images = self.index.get("images", {})
        if len(images) <= CACHE_MAX_ENTRIES:
            return

        # Sort queries by timestamp and remove oldest
        queries = self.index.get("queries", {})
        sorted_queries = sorted(
            queries.items(),
            key=lambda x: x[1].get("timestamp", ""),
            reverse=True
        )

        # Keep only the newest entries
        keep_queries = dict(sorted_queries[:CACHE_MAX_ENTRIES // 5])
        keep_image_ids = set()
        for q in keep_queries.values():
            keep_image_ids.update(q.get("image_ids", []))

        # Filter images
        self.index["queries"] = keep_queries
        self.index["images"] = {
            k: v for k, v in images.items() if k in keep_image_ids
        }

        logger.info(f"Cache cleaned: kept {len(self.index['images'])} images")

    def get_random_cached(self, count: int = 10) -> List[Image]:
        """Get random cached images as fallback."""
        all_images = []
        for img_data in self.index.get("images", {}).values():
            try:
                all_images.append(Image(**img_data))
            except TypeError:
                continue

        if not all_images:
            return []

        random.shuffle(all_images)
        return all_images[:count]

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "total_images": len(self.index.get("images", {})),
            "total_queries": len(self.index.get("queries", {})),
            "cache_dir": str(self.cache_dir)
        }


class ImageFetcher:
    """Fetches and manages images from multiple sources."""

    def __init__(self, pexels_key: Optional[str] = None, unsplash_key: Optional[str] = None,
                 pixabay_key: Optional[str] = None, use_cache: bool = True):
        self.pexels_key = pexels_key or os.getenv('PEXELS_API_KEY')
        self.unsplash_key = unsplash_key or os.getenv('UNSPLASH_ACCESS_KEY')
        self.pixabay_key = pixabay_key or os.getenv('PIXABAY_API_KEY')

        self.session = requests.Session()
        self.images: List[Image] = []
        self.used_ids: set = set()

        # Persistent cache
        self.use_cache = use_cache
        self.cache = ImageCache() if use_cache else None

        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = DELAYS.get("between_images", 0.3)

    def _rate_limit(self):
        """Ensure we don't exceed API rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _request_with_retry(self, url: str, headers: Dict, params: Dict,
                            service_name: str) -> Optional[requests.Response]:
        """Make HTTP request with exponential backoff retry."""
        timeout = TIMEOUTS.get("image_api", 15)

        for attempt in range(RETRY_MAX_ATTEMPTS):
            try:
                self._rate_limit()
                response = self.session.get(url, headers=headers, params=params, timeout=timeout)

                # Success
                if response.status_code == 200:
                    return response

                # Retryable error
                if response.status_code in RETRY_STATUS_CODES:
                    wait_time = RETRY_BACKOFF_FACTOR ** attempt
                    logger.warning(
                        f"{service_name} returned {response.status_code}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS})"
                    )
                    time.sleep(wait_time)
                    continue

                # Non-retryable error
                response.raise_for_status()

            except requests.exceptions.Timeout:
                wait_time = RETRY_BACKOFF_FACTOR ** attempt
                logger.warning(
                    f"{service_name} timeout, retrying in {wait_time}s "
                    f"(attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS})"
                )
                time.sleep(wait_time)
            except requests.exceptions.RequestException as e:
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    wait_time = RETRY_BACKOFF_FACTOR ** attempt
                    logger.warning(f"{service_name} error: {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"{service_name} failed after {RETRY_MAX_ATTEMPTS} attempts: {e}")
                    return None

        return None

    def search_pexels(self, query: str, per_page: int = 5) -> List[Image]:
        """Search for images on Pexels with retry logic."""
        if not self.pexels_key:
            logger.debug("Pexels API key not configured")
            return []

        images = []
        headers = {'Authorization': self.pexels_key}
        params = {
            'query': query,
            'per_page': per_page,
            'orientation': 'landscape'
        }

        response = self._request_with_retry(
            'https://api.pexels.com/v1/search',
            headers=headers,
            params=params,
            service_name='Pexels'
        )

        if not response:
            return []

        try:
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

        except Exception as e:
            logger.error(f"Pexels parse error: {e}")

        return images

    def search_unsplash(self, query: str, per_page: int = 5) -> List[Image]:
        """Search for images on Unsplash with retry logic."""
        if not self.unsplash_key:
            logger.debug("Unsplash API key not configured")
            return []

        images = []
        headers = {'Authorization': f'Client-ID {self.unsplash_key}'}
        params = {
            'query': query,
            'per_page': per_page,
            'orientation': 'landscape'
        }

        response = self._request_with_retry(
            'https://api.unsplash.com/search/photos',
            headers=headers,
            params=params,
            service_name='Unsplash'
        )

        if not response:
            return []

        try:
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

        except Exception as e:
            logger.error(f"Unsplash parse error: {e}")

        return images

    def search_pixabay(self, query: str, per_page: int = 5) -> List[Image]:
        """Search for images on Pixabay with retry logic.

        Pixabay offers CC0 licensed images with no attribution required.
        Free tier: 100 requests per minute.
        """
        if not self.pixabay_key:
            logger.debug("Pixabay API key not configured")
            return []

        images = []
        # Pixabay uses query params for auth, not headers
        headers = {}
        params = {
            'key': self.pixabay_key,
            'q': query,
            'image_type': 'photo',
            'orientation': 'horizontal',
            'per_page': per_page,
            'safesearch': 'true'
        }

        response = self._request_with_retry(
            'https://pixabay.com/api/',
            headers=headers,
            params=params,
            service_name='Pixabay'
        )

        if not response:
            return []

        try:
            data = response.json()

            for photo in data.get('hits', []):
                # Pixabay provides different size URLs
                image = Image(
                    id=f"pixabay_{photo['id']}",
                    url_small=photo.get('previewURL', photo.get('webformatURL', '')),
                    url_medium=photo.get('webformatURL', photo.get('largeImageURL', '')),
                    url_large=photo.get('largeImageURL', photo.get('fullHDURL', '')),
                    url_original=photo.get('fullHDURL', photo.get('largeImageURL', '')),
                    photographer=photo.get('user', 'Unknown'),
                    photographer_url=f"https://pixabay.com/users/{photo.get('user', '')}-{photo.get('user_id', '')}",
                    source='pixabay',
                    alt_text=photo.get('tags', query),
                    color=None,  # Pixabay doesn't provide dominant color
                    width=photo.get('imageWidth', 0),
                    height=photo.get('imageHeight', 0)
                )
                images.append(image)

        except Exception as e:
            logger.error(f"Pixabay parse error: {e}")

        return images

    def get_lorem_picsum_images(self, count: int = 5) -> List[Image]:
        """Get random stock-like images from Lorem Picsum as last resort fallback.

        Lorem Picsum provides free random images. No API key required.
        Note: Images are random, not searchable by keyword.
        """
        images = []

        for i in range(count):
            # Use seeded URLs for reproducibility within the same day
            seed = f"dailytrending_{datetime.now().strftime('%Y%m%d')}_{i}"
            base_url = f"https://picsum.photos/seed/{seed}"

            try:
                # Lorem Picsum redirects to the actual image URL
                # We just need to construct the URLs with dimensions
                image = Image(
                    id=f"picsum_{seed}",
                    url_small=f"{base_url}/400/300",
                    url_medium=f"{base_url}/800/600",
                    url_large=f"{base_url}/1200/800",
                    url_original=f"{base_url}/1920/1280",
                    photographer="Lorem Picsum",
                    photographer_url="https://picsum.photos",
                    source='lorem_picsum',
                    alt_text="Stock photo from Lorem Picsum",
                    color=None,
                    width=1200,
                    height=800
                )
                images.append(image)
            except Exception as e:
                logger.debug(f"Lorem Picsum fallback error: {e}")
                continue

        if images:
            logger.info(f"Added {len(images)} Lorem Picsum fallback images")

        return images

    def search(self, query: str, per_page: int = 5) -> List[Image]:
        """Search for images, trying cache first, then Pexels, Unsplash, Pixabay."""
        logger.debug(f"Searching for: '{query}'")

        # Check cache first
        if self.use_cache and self.cache and self.cache.is_cached(query):
            cached_images = self.cache.get_cached(query)
            if cached_images:
                # Filter out already used images
                cached_images = [img for img in cached_images if img.id not in self.used_ids]
                if cached_images:
                    logger.debug(f"Found {len(cached_images)} images (cached)")
                    return cached_images

        # Try Pexels first
        images = self.search_pexels(query, per_page)

        # If no results, try Unsplash
        if not images:
            images = self.search_unsplash(query, per_page)

        # If still no results, try Pixabay (CC0 licensed)
        if not images:
            images = self.search_pixabay(query, per_page)

        # Cache the results for future use
        if self.use_cache and self.cache and images:
            self.cache.cache_results(query, images)

        # Filter out already used images
        images = [img for img in images if img.id not in self.used_ids]

        logger.debug(f"Found {len(images)} images")
        return images

    def fetch_for_keywords(self, keywords: List[str], images_per_keyword: int = 3) -> List[Image]:
        """Fetch images for a list of keywords."""
        logger.info("Fetching images for keywords...")

        if self.use_cache and self.cache:
            stats = self.cache.get_stats()
            logger.info(f"Cache stats: {stats['total_images']} images, {stats['total_queries']} queries")

        all_images = []

        for keyword in keywords:
            images = self.search(keyword, images_per_keyword)
            all_images.extend(images)

            # Mark as used
            for img in images:
                self.used_ids.add(img.id)

            time.sleep(DELAYS.get("between_images", 0.3))

        # If we got very few images, supplement with cached fallback
        if len(all_images) < MIN_IMAGES_REQUIRED and self.use_cache and self.cache:
            logger.info(f"Only {len(all_images)} images found, using cached fallback...")
            fallback = self.cache.get_random_cached(MIN_IMAGES_REQUIRED - len(all_images))
            # Filter out duplicates
            fallback = [img for img in fallback if img.id not in self.used_ids]
            all_images.extend(fallback)
            for img in fallback:
                self.used_ids.add(img.id)
            logger.info(f"Added {len(fallback)} cached images as fallback")

        # Last resort: Lorem Picsum random images (better than gradients)
        if len(all_images) < MIN_IMAGES_REQUIRED:
            logger.info(f"Still only {len(all_images)} images, trying Lorem Picsum fallback...")
            picsum_images = self.get_lorem_picsum_images(MIN_IMAGES_REQUIRED - len(all_images))
            picsum_images = [img for img in picsum_images if img.id not in self.used_ids]
            all_images.extend(picsum_images)
            for img in picsum_images:
                self.used_ids.add(img.id)

        self.images = all_images
        logger.info(f"Total images fetched: {len(all_images)}")

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
        logger.info(f"Saved {len(self.images)} images to {filepath}")


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
