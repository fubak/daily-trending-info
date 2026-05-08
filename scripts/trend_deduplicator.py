"""Trend deduplication via token overlap + semantic similarity.

Extracted from collect_trends.TrendCollector._deduplicate() so the
clustering logic is testable and reusable independently of the collector.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Set, Tuple

from config import DEDUP_SIMILARITY_THRESHOLD, DEDUP_SEMANTIC_THRESHOLD
from source_registry import source_quality_multiplier

logger = logging.getLogger("collect_trends")


_DEDUP_STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "on",
    "with", "from", "after", "before", "about",
    "update", "latest", "news", "today",
}


def deduplicate_trends(trends: List) -> List:
    """Cluster near-duplicate trends and keep the highest-quality one per cluster.

    Uses an inverted-token index to bound pairwise comparisons, then
    measures four similarity signals (overlap ratio, Jaccard, sequence
    matcher, token-sorted sequence matcher). Above the configured
    thresholds the trends are merged; the canonical entry is the one
    with the best score × source quality × diversity bonus.

    Returns a new list of unique Trend objects (not the input list).
    """
    if not trends:
        return []

    normalized_titles: List[str] = []
    token_sets: List[Set[str]] = []
    inverted_index: Dict[str, List[int]] = {}

    for idx, trend in enumerate(trends):
        normalized = re.sub(r"[^\w\s]", " ", (trend.title or "").lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = {
            token
            for token in normalized.split()
            if len(token) >= 3 and not token.isdigit() and token not in _DEDUP_STOP_WORDS
        }
        if not tokens:
            tokens = {token for token in normalized.split() if token}

        normalized_titles.append(normalized)
        token_sets.append(tokens)

        for token in tokens:
            inverted_index.setdefault(token, []).append(idx)

    clusters: List[List[int]] = []
    assigned: Set[int] = set()

    for index in range(len(trends)):
        if index in assigned:
            continue
        cluster = [index]
        assigned.add(index)
        tokens_i = token_sets[index]
        normalized_i = normalized_titles[index]

        candidate_indices: Set[int] = set()
        for token in tokens_i:
            for candidate_idx in inverted_index.get(token, []):
                if candidate_idx > index:
                    candidate_indices.add(candidate_idx)

        for candidate_idx in sorted(candidate_indices):
            if candidate_idx in assigned:
                continue

            tokens_j = token_sets[candidate_idx]
            normalized_j = normalized_titles[candidate_idx]

            if not tokens_i or not tokens_j:
                overlap_ratio = 0.0
                jaccard = 0.0
            else:
                intersection = len(tokens_i & tokens_j)
                overlap_ratio = intersection / max(
                    1, min(len(tokens_i), len(tokens_j))
                )
                jaccard = intersection / max(1, len(tokens_i | tokens_j))

            semantic_ratio = SequenceMatcher(None, normalized_i, normalized_j).ratio()
            token_semantic_ratio = SequenceMatcher(
                None,
                " ".join(sorted(tokens_i)),
                " ".join(sorted(tokens_j)),
            ).ratio()

            is_duplicate = (
                overlap_ratio >= DEDUP_SIMILARITY_THRESHOLD
                or jaccard >= max(0.55, DEDUP_SIMILARITY_THRESHOLD - 0.25)
                or semantic_ratio >= DEDUP_SEMANTIC_THRESHOLD
                or token_semantic_ratio >= DEDUP_SEMANTIC_THRESHOLD
            )
            if not is_duplicate:
                continue

            cluster.append(candidate_idx)
            assigned.add(candidate_idx)

        clusters.append(cluster)

    unique_trends: List = []
    for cluster in clusters:
        if len(cluster) == 1:
            unique_trends.append(trends[cluster[0]])
            continue

        def _quality(cluster_idx: int) -> Tuple[float, float]:
            candidate = trends[cluster_idx]
            quality = candidate.score * source_quality_multiplier(candidate.source)
            quality *= 1.0 + min((candidate.source_diversity - 1) * 0.05, 0.25)
            timestamp = (
                candidate.timestamp.timestamp() if candidate.timestamp else 0.0
            )
            return quality, timestamp

        canonical_idx = max(cluster, key=_quality)
        canonical = trends[canonical_idx]
        for cluster_idx in cluster:
            if cluster_idx == canonical_idx:
                continue
            canonical.register_corroboration(trends[cluster_idx])
        unique_trends.append(canonical)

    removed_count = len(trends) - len(unique_trends)
    if removed_count > 0:
        logger.info(f"Removed {removed_count} duplicate trends")

    return unique_trends
