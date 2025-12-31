#!/usr/bin/env python3
"""
Trend Collector - Aggregates trending topics from multiple sources.
Sources: Google Trends, Google News RSS, NYT/BBC/Verge RSS, Hacker News API, Reddit API
"""

import os
import json
import re
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus

import requests
import feedparser
from bs4 import BeautifulSoup


@dataclass
class Trend:
    """Represents a single trending topic."""
    title: str
    source: str
    url: Optional[str] = None
    description: Optional[str] = None
    score: float = 1.0
    keywords: List[str] = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = self._extract_keywords()

    def _extract_keywords(self) -> List[str]:
        """Extract meaningful keywords from title."""
        # Remove common words and extract meaningful terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them',
            'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'why', 'how',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
            'such', 'no', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
            'just', 'about', 'after', 'before', 'between', 'into', 'through',
            'during', 'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under',
            'again', 'further', 'then', 'once', 'here', 'there', 'new', 'says',
            'said', 'get', 'got', 'getting', 'make', 'made', 'making', 'know',
            'think', 'take', 'see', 'come', 'want', 'look', 'use', 'find', 'give',
            'tell', 'ask', 'work', 'seem', 'feel', 'try', 'leave', 'call', 'keep',
            'let', 'begin', 'show', 'hear', 'play', 'run', 'move', 'like', 'live',
            'believe', 'hold', 'bring', 'happen', 'write', 'provide', 'sit', 'stand',
            'lose', 'pay', 'meet', 'include', 'continue', 'set', 'learn', 'change',
            'lead', 'understand', 'watch', 'follow', 'stop', 'create', 'speak',
            'read', 'allow', 'add', 'spend', 'grow', 'open', 'walk', 'win', 'offer',
            'remember', 'love', 'consider', 'appear', 'buy', 'wait', 'serve', 'die',
            'send', 'expect', 'build', 'stay', 'fall', 'cut', 'reach', 'kill',
            'remain', 'suggest', 'raise', 'pass', 'sell', 'require', 'report',
            'decide', 'pull', 'breaking', 'update', 'latest', 'news', 'today',
        }

        # Clean and tokenize
        text = re.sub(r'[^\w\s]', ' ', self.title.lower())
        words = text.split()

        # Filter and return meaningful keywords
        keywords = [
            word for word in words
            if word not in stop_words and len(word) > 2 and not word.isdigit()
        ]

        return keywords[:5]  # Top 5 keywords


class TrendCollector:
    """Collects and aggregates trends from multiple sources."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.trends: List[Trend] = []

    def collect_all(self) -> List[Trend]:
        """Collect trends from all available sources."""
        print("Collecting trends from all sources...")

        collectors = [
            ("Google Trends", self._collect_google_trends),
            ("RSS Feeds", self._collect_rss_feeds),
            ("Hacker News", self._collect_hackernews),
            ("Reddit", self._collect_reddit),
        ]

        for name, collector in collectors:
            try:
                print(f"  Fetching from {name}...")
                trends = collector()
                self.trends.extend(trends)
                print(f"    Found {len(trends)} trends")
            except Exception as e:
                print(f"    Error: {e}")
                continue

            # Small delay between sources
            time.sleep(0.5)

        # Deduplicate and score
        self._deduplicate()
        self._calculate_scores()

        # Sort by score
        self.trends.sort(key=lambda t: t.score, reverse=True)

        print(f"Total unique trends: {len(self.trends)}")
        return self.trends

    def _collect_google_trends(self) -> List[Trend]:
        """Collect trends from Google Trends RSS."""
        trends = []

        # Google Trends Daily RSS
        url = "https://trends.google.com/trending/rss?geo=US"

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            for entry in feed.entries[:20]:
                trend = Trend(
                    title=entry.get('title', '').strip(),
                    source='google_trends',
                    url=entry.get('link'),
                    description=entry.get('summary', '').strip() if entry.get('summary') else None,
                    score=2.0  # Google Trends gets higher base score
                )
                if trend.title:
                    trends.append(trend)

        except Exception as e:
            print(f"    Google Trends error: {e}")

        return trends

    def _collect_rss_feeds(self) -> List[Trend]:
        """Collect trends from major news RSS feeds."""
        trends = []

        feeds = [
            ('NYT', 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml'),
            ('BBC', 'https://feeds.bbci.co.uk/news/rss.xml'),
            ('Verge', 'https://www.theverge.com/rss/index.xml'),
            ('Ars Technica', 'https://feeds.arstechnica.com/arstechnica/index'),
            ('Wired', 'https://www.wired.com/feed/rss'),
            ('TechCrunch', 'https://techcrunch.com/feed/'),
            ('Reuters', 'https://www.reutersagency.com/feed/'),
        ]

        for name, url in feeds:
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                feed = feedparser.parse(response.content)

                for entry in feed.entries[:10]:
                    title = entry.get('title', '').strip()

                    # Clean up title
                    title = re.sub(r'\s+', ' ', title)
                    title = title.replace(' - The New York Times', '')
                    title = title.replace(' - BBC News', '')
                    title = title.replace(' | Ars Technica', '')

                    if title:
                        trend = Trend(
                            title=title,
                            source=f'rss_{name.lower().replace(" ", "_")}',
                            url=entry.get('link'),
                            description=self._clean_html(entry.get('summary', '')),
                            score=1.5
                        )
                        trends.append(trend)

            except Exception as e:
                print(f"      {name} RSS error: {e}")
                continue

            time.sleep(0.2)

        return trends

    def _collect_hackernews(self) -> List[Trend]:
        """Collect top stories from Hacker News API."""
        trends = []

        try:
            # Get top story IDs
            response = self.session.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=10
            )
            response.raise_for_status()

            story_ids = response.json()[:25]

            for story_id in story_ids:
                try:
                    story_response = self.session.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                        timeout=5
                    )
                    story = story_response.json()

                    if story and story.get('title'):
                        score = story.get('score', 0)
                        normalized_score = min(score / 100, 3.0)  # Cap at 3x

                        trend = Trend(
                            title=story['title'],
                            source='hackernews',
                            url=story.get('url'),
                            score=1.0 + normalized_score
                        )
                        trends.append(trend)

                except Exception:
                    continue

        except Exception as e:
            print(f"    Hacker News error: {e}")

        return trends

    def _collect_reddit(self) -> List[Trend]:
        """Collect trending posts from Reddit."""
        trends = []

        subreddits = ['technology', 'worldnews', 'science', 'futurology', 'programming']

        for subreddit in subreddits:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=10"

                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                data = response.json()
                posts = data.get('data', {}).get('children', [])

                for post in posts:
                    post_data = post.get('data', {})
                    title = post_data.get('title', '').strip()

                    if title and not post_data.get('stickied'):
                        ups = post_data.get('ups', 0)
                        normalized_score = min(ups / 1000, 2.0)

                        trend = Trend(
                            title=title,
                            source=f'reddit_{subreddit}',
                            url=f"https://reddit.com{post_data.get('permalink', '')}",
                            score=1.0 + normalized_score
                        )
                        trends.append(trend)

            except Exception as e:
                print(f"      Reddit r/{subreddit} error: {e}")
                continue

            time.sleep(0.3)

        return trends

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        soup = BeautifulSoup(text, 'html.parser')
        clean = soup.get_text(separator=' ').strip()
        return re.sub(r'\s+', ' ', clean)[:500]

    def _deduplicate(self):
        """Remove duplicate trends based on title similarity."""
        seen_titles = set()
        unique_trends = []

        for trend in self.trends:
            # Normalize title for comparison
            normalized = trend.title.lower().strip()
            normalized = re.sub(r'[^\w\s]', '', normalized)

            # Simple dedup - skip if very similar title exists
            if normalized not in seen_titles:
                # Check for partial matches
                is_dupe = False
                for seen in seen_titles:
                    # If 80% of words match, consider it a duplicate
                    words1 = set(normalized.split())
                    words2 = set(seen.split())
                    if words1 and words2:
                        overlap = len(words1 & words2) / min(len(words1), len(words2))
                        if overlap > 0.8:
                            is_dupe = True
                            break

                if not is_dupe:
                    seen_titles.add(normalized)
                    unique_trends.append(trend)

        self.trends = unique_trends

    def _calculate_scores(self):
        """Recalculate trend scores based on various factors."""
        # Boost trends that appear in multiple sources
        keyword_counts = {}

        for trend in self.trends:
            for keyword in trend.keywords:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

        for trend in self.trends:
            # Boost for common keywords (trending across sources)
            keyword_boost = sum(
                0.2 for kw in trend.keywords
                if keyword_counts.get(kw, 0) > 1
            )
            trend.score += keyword_boost

    def get_top_trends(self, limit: int = 10) -> List[Trend]:
        """Get top N trends by score."""
        return self.trends[:limit]

    def get_all_keywords(self) -> List[str]:
        """Get all unique keywords from trends."""
        keywords = []
        seen = set()

        for trend in self.trends:
            for kw in trend.keywords:
                if kw not in seen:
                    seen.add(kw)
                    keywords.append(kw)

        return keywords

    def to_json(self) -> str:
        """Export trends as JSON."""
        return json.dumps([asdict(t) for t in self.trends], indent=2)

    def save(self, filepath: str):
        """Save trends to a JSON file."""
        with open(filepath, 'w') as f:
            f.write(self.to_json())
        print(f"Saved {len(self.trends)} trends to {filepath}")


def main():
    """Main entry point for trend collection."""
    collector = TrendCollector()
    trends = collector.collect_all()

    print("\nTop 10 Trends:")
    print("-" * 60)

    for i, trend in enumerate(collector.get_top_trends(10), 1):
        print(f"{i:2}. [{trend.source}] {trend.title}")
        print(f"    Keywords: {', '.join(trend.keywords)}")
        print(f"    Score: {trend.score:.2f}")
        print()

    # Save to file
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, '..', 'data', 'trends.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    collector.save(output_path)

    return collector


if __name__ == "__main__":
    main()
