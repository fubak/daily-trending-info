#!/usr/bin/env python3
"""Tests for keyword_extraction module."""

import pytest
from scripts.keyword_extraction import extract_keywords, _STOP_WORDS


class TestExtractKeywords:
    """Tests for the extract_keywords() function."""

    def test_returns_list(self):
        """Should always return a list."""
        result = extract_keywords("Python programming language")
        assert isinstance(result, list)

    def test_extracts_meaningful_words(self):
        """Should extract content words and exclude stop words."""
        result = extract_keywords("Python is the best programming language")
        assert "python" in result
        assert "programming" in result
        assert "language" in result
        # stop words excluded
        assert "is" not in result
        assert "the" not in result

    def test_returns_at_most_five(self):
        """Should return at most 5 keywords."""
        title = "apple microsoft google amazon facebook twitter meta nvidia tesla openai"
        result = extract_keywords(title)
        assert len(result) <= 5

    def test_empty_string(self):
        """Should handle empty input gracefully."""
        result = extract_keywords("")
        assert result == []

    def test_all_stop_words(self):
        """Should return empty list when title is only stop words."""
        result = extract_keywords("the and or but is was")
        assert result == []

    def test_lowercases_words(self):
        """Keywords should be lowercased."""
        result = extract_keywords("OpenAI Released New Model")
        assert all(kw == kw.lower() for kw in result)

    def test_filters_short_words(self):
        """Words of 2 or fewer characters should be excluded."""
        result = extract_keywords("AI ML DL big language model")
        # 'ai', 'ml', 'dl' are 2 chars — excluded; 'big' is 3 chars but is not a stop word
        for kw in result:
            assert len(kw) > 2

    def test_filters_digits(self):
        """Pure digit tokens should be excluded."""
        result = extract_keywords("Released version 123 with 456 improvements")
        assert "123" not in result
        assert "456" not in result

    def test_punctuation_stripped(self):
        """Punctuation should be stripped before tokenisation."""
        result = extract_keywords("Anthropic's Claude: a new AI model!")
        # 'anthropic' and 'claude' should appear without punctuation
        assert "anthropic" in result or "claude" in result
        for kw in result:
            assert "'" not in kw
            assert "!" not in kw
            assert ":" not in kw

    def test_typical_tech_headline(self):
        """Should extract relevant keywords from a typical tech headline."""
        result = extract_keywords("OpenAI launches GPT-5 with unprecedented reasoning capabilities")
        # 'openai', 'launches', 'gpt', 'unprecedented', 'reasoning', 'capabilities'
        assert len(result) > 0
        assert len(result) <= 5


class TestStopWords:
    """Sanity checks on the _STOP_WORDS set."""

    def test_common_stop_words_present(self):
        """Common English stop words should be in the set."""
        expected = {"the", "a", "an", "and", "or", "is", "was", "in", "on", "at"}
        for word in expected:
            assert word in _STOP_WORDS, f"'{word}' missing from _STOP_WORDS"

    def test_stop_words_are_lowercase(self):
        """All stop words should be lowercase."""
        for word in _STOP_WORDS:
            assert word == word.lower(), f"'{word}' is not lowercase"

    def test_stop_words_is_set(self):
        """_STOP_WORDS should be a set for O(1) lookup."""
        assert isinstance(_STOP_WORDS, set)
