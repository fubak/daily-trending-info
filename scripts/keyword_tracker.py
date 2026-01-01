#!/usr/bin/env python3
"""
Keyword Tracker - Tracks keyword frequency over time for trend analysis.

Maintains a 30-day rolling history of keywords to identify:
- Rising trends (new or rapidly increasing keywords)
- Falling trends (declining frequency)
- Persistent topics (consistently appearing keywords)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict, field

from config import (
    setup_logging, KEYWORD_HISTORY_FILE, KEYWORD_HISTORY_DAYS, DATA_DIR
)

# Setup logging
logger = setup_logging("keywords")


@dataclass
class KeywordTrend:
    """Represents a keyword's trending status."""
    keyword: str
    current_count: int
    previous_count: int  # Count from 7 days ago
    trend: str  # 'rising', 'falling', 'stable', 'new'
    change_percent: float
    first_seen: str  # ISO date
    last_seen: str  # ISO date
    total_appearances: int


class KeywordTracker:
    """Tracks keyword frequency over a rolling 30-day period."""

    def __init__(self, history_file: Path = None):
        self.history_file = history_file or KEYWORD_HISTORY_FILE
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        """Load keyword history from disk."""
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load keyword history: {e}")
        return {"daily": {}, "metadata": {"created": datetime.now().isoformat()}}

    def _save_history(self):
        """Save keyword history to disk."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except IOError as e:
            logger.error(f"Could not save keyword history: {e}")

    def _cleanup_old_entries(self):
        """Remove entries older than KEYWORD_HISTORY_DAYS."""
        cutoff = datetime.now() - timedelta(days=KEYWORD_HISTORY_DAYS)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        daily = self.history.get("daily", {})
        dates_to_remove = [d for d in daily.keys() if d < cutoff_str]

        for date in dates_to_remove:
            del daily[date]

        if dates_to_remove:
            logger.info(f"Cleaned up {len(dates_to_remove)} old keyword entries")

    def record_keywords(self, keywords: List[str], date: str = None):
        """
        Record keyword occurrences for a given date.

        Args:
            keywords: List of keywords extracted from today's trends
            date: Date string (YYYY-MM-DD), defaults to today
        """
        date = date or datetime.now().strftime("%Y-%m-%d")

        # Initialize daily entry if needed
        if "daily" not in self.history:
            self.history["daily"] = {}

        # Count keyword frequencies
        counts = defaultdict(int)
        for kw in keywords:
            kw_lower = kw.lower().strip()
            if kw_lower and len(kw_lower) > 1:  # Skip single chars
                counts[kw_lower] += 1

        # Store counts for this date
        self.history["daily"][date] = dict(counts)

        # Cleanup old entries
        self._cleanup_old_entries()

        # Save
        self._save_history()
        logger.info(f"Recorded {len(counts)} keywords for {date}")

    def get_trending_keywords(self, limit: int = 20) -> List[KeywordTrend]:
        """
        Get keywords sorted by trending status.

        Returns keywords that are:
        1. New (appeared in last 3 days, not before)
        2. Rising (higher frequency in recent 7 days vs previous 7 days)
        3. Stable (consistent frequency)
        4. Falling (lower frequency in recent 7 days)
        """
        daily = self.history.get("daily", {})
        if not daily:
            return []

        today = datetime.now()
        dates = sorted(daily.keys(), reverse=True)

        if not dates:
            return []

        # Time periods
        recent_7_days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        previous_7_days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7, 14)]
        last_3_days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]

        # Aggregate counts
        recent_counts = defaultdict(int)
        previous_counts = defaultdict(int)
        recent_3_day_counts = defaultdict(int)
        all_time_counts = defaultdict(int)
        first_seen = {}
        last_seen = {}

        for date in dates:
            day_counts = daily.get(date, {})
            for kw, count in day_counts.items():
                all_time_counts[kw] += count

                if date in recent_7_days:
                    recent_counts[kw] += count
                if date in previous_7_days:
                    previous_counts[kw] += count
                if date in last_3_days:
                    recent_3_day_counts[kw] += count

                # Track first/last seen
                if kw not in first_seen or date < first_seen[kw]:
                    first_seen[kw] = date
                if kw not in last_seen or date > last_seen[kw]:
                    last_seen[kw] = date

        # Calculate trends
        trends = []
        all_keywords = set(recent_counts.keys()) | set(previous_counts.keys())

        for kw in all_keywords:
            recent = recent_counts.get(kw, 0)
            previous = previous_counts.get(kw, 0)
            recent_3 = recent_3_day_counts.get(kw, 0)

            # Determine trend type
            if previous == 0 and recent > 0:
                # New keyword (not seen in previous 7 days)
                trend_type = "new"
                change = 100.0
            elif recent > previous:
                trend_type = "rising"
                change = ((recent - previous) / max(previous, 1)) * 100
            elif recent < previous:
                trend_type = "falling"
                change = ((recent - previous) / max(previous, 1)) * 100
            else:
                trend_type = "stable"
                change = 0.0

            trends.append(KeywordTrend(
                keyword=kw,
                current_count=recent,
                previous_count=previous,
                trend=trend_type,
                change_percent=round(change, 1),
                first_seen=first_seen.get(kw, ""),
                last_seen=last_seen.get(kw, ""),
                total_appearances=all_time_counts.get(kw, 0)
            ))

        # Sort: new first, then rising by change %, then stable, then falling
        def sort_key(t: KeywordTrend) -> Tuple:
            order = {"new": 0, "rising": 1, "stable": 2, "falling": 3}
            return (order.get(t.trend, 4), -abs(t.change_percent), -t.current_count)

        trends.sort(key=sort_key)
        return trends[:limit]

    def get_persistent_keywords(self, min_days: int = 7, limit: int = 10) -> List[str]:
        """
        Get keywords that appear consistently over multiple days.

        Args:
            min_days: Minimum number of days a keyword must appear
            limit: Maximum number of keywords to return
        """
        daily = self.history.get("daily", {})
        if not daily:
            return []

        # Count days each keyword appears
        keyword_days = defaultdict(set)
        for date, counts in daily.items():
            for kw in counts.keys():
                keyword_days[kw].add(date)

        # Filter by minimum days
        persistent = [
            (kw, len(days))
            for kw, days in keyword_days.items()
            if len(days) >= min_days
        ]

        # Sort by frequency
        persistent.sort(key=lambda x: -x[1])
        return [kw for kw, _ in persistent[:limit]]

    def get_summary(self) -> Dict:
        """Get a summary of keyword tracking data."""
        daily = self.history.get("daily", {})

        if not daily:
            return {
                "total_days": 0,
                "total_unique_keywords": 0,
                "date_range": None
            }

        dates = sorted(daily.keys())
        all_keywords = set()
        for counts in daily.values():
            all_keywords.update(counts.keys())

        return {
            "total_days": len(dates),
            "total_unique_keywords": len(all_keywords),
            "date_range": {
                "start": dates[0] if dates else None,
                "end": dates[-1] if dates else None
            },
            "trending": [asdict(t) for t in self.get_trending_keywords(5)],
            "persistent": self.get_persistent_keywords(7, 5)
        }


def main():
    """Test the keyword tracker."""
    tracker = KeywordTracker()

    # Get summary
    summary = tracker.get_summary()
    print("Keyword Tracking Summary:")
    print(f"  Days tracked: {summary['total_days']}")
    print(f"  Unique keywords: {summary['total_unique_keywords']}")

    if summary['date_range'] and summary['date_range']['start']:
        print(f"  Date range: {summary['date_range']['start']} to {summary['date_range']['end']}")

    # Get trending
    print("\nTrending Keywords:")
    for trend in tracker.get_trending_keywords(10):
        arrow = "↑" if trend.trend == "rising" else "↓" if trend.trend == "falling" else "★" if trend.trend == "new" else "→"
        print(f"  {arrow} {trend.keyword}: {trend.current_count} ({trend.change_percent:+.1f}%)")

    # Get persistent
    print("\nPersistent Keywords:")
    for kw in tracker.get_persistent_keywords(5, 10):
        print(f"  • {kw}")


if __name__ == "__main__":
    main()
