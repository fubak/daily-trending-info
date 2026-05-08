#!/usr/bin/env python3
"""
Simple validation script for topic_page_generator module.
Runs basic tests without requiring pytest.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from topic_page_generator import (
    get_topic_configurations,
    extract_headline_keywords,
    score_image_relevance,
    find_topic_hero_image,
    matches_topic_source,
    filter_trends_by_topic,
    should_generate_topic_page
)


def test_topic_configurations():
    """Test topic configuration retrieval."""
    configs = get_topic_configurations()
    assert len(configs) > 0, "Should return topic configurations"
    assert all('slug' in c for c in configs), "All configs should have slug"
    print("✓ Topic configurations working")


def test_keyword_extraction():
    """Test headline keyword extraction."""
    headline = "Apple releases new iPhone with amazing features"
    keywords = extract_headline_keywords(headline)
    assert 'apple' in keywords, "Should extract 'apple'"
    assert 'iphone' in keywords, "Should extract 'iphone'"
    assert 'the' not in keywords, "Should filter stop words"
    print("✓ Keyword extraction working")


def test_image_scoring():
    """Test image relevance scoring."""
    image = {
        'query': 'technology innovation',
        'description': 'modern tech',
        'alt': '',
        'width': 1200
    }
    score = score_image_relevance(
        image,
        headline_keywords=['technology', 'innovation'],
        category_keywords=[]
    )
    assert score > 0, "Should score image with keyword matches"
    assert score == 4.5, f"Expected 4.5, got {score}"  # 2+2 for keywords, 0.5 for size
    print("✓ Image scoring working")


def test_source_matching():
    """Test source-to-topic matching."""
    assert matches_topic_source('hackernews', ['hackernews']), "Should match exact"
    assert matches_topic_source('tech_verge', ['tech_']), "Should match prefix"
    assert not matches_topic_source('reddit', ['hackernews']), "Should not match different source"
    print("✓ Source matching working")


def test_trend_filtering():
    """Test trend filtering by topic."""
    trends = [
        {'title': 'Story 1', 'source': 'hackernews'},
        {'title': 'Story 2', 'source': 'reddit'},
        {'title': 'Story 3', 'source': 'tech_verge'},
    ]
    filtered = filter_trends_by_topic(trends, ['hackernews', 'tech_'])
    assert len(filtered) == 2, "Should filter to matching sources"
    print("✓ Trend filtering working")


def test_hero_image_finding():
    """Test hero image selection."""
    images = [
        {'id': '1', 'query': 'random', 'description': '', 'alt': '', 'width': 1000},
        {'id': '2', 'query': 'technology innovation', 'description': '', 'alt': '', 'width': 1000},
    ]
    used_ids = set()
    hero = find_topic_hero_image(
        images,
        headline='New technology breakthrough',
        category_keywords=[],
        fallback_index=0,
        used_image_ids=used_ids
    )
    assert hero['id'] == '2', "Should find best matching image"
    assert '2' in used_ids, "Should track used image"
    print("✓ Hero image finding working")


def test_page_generation_decision():
    """Test topic page generation decision."""
    trends_enough = [{'title': f'Story {i}'} for i in range(5)]
    trends_few = [{'title': 'Story 1'}]

    assert should_generate_topic_page(trends_enough, min_stories=3), "Should generate with enough stories"
    assert not should_generate_topic_page(trends_few, min_stories=3), "Should not generate with few stories"
    print("✓ Page generation decision working")


def main():
    """Run all validation tests."""
    print("Validating topic_page_generator module...\n")

    try:
        test_topic_configurations()
        test_keyword_extraction()
        test_image_scoring()
        test_source_matching()
        test_trend_filtering()
        test_hero_image_finding()
        test_page_generation_decision()

        print("\n✅ All validations passed!")
        return 0

    except AssertionError as e:
        print(f"\n❌ Validation failed: {e}")
        return 1
    except (OSError, ValueError, KeyError, AttributeError) as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
