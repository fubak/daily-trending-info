#!/usr/bin/env python3
"""Tests for Pipeline orchestrator in main.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest


def make_pipeline(temp_dir):
    """Create a Pipeline instance with all external components mocked."""
    patches = [
        patch("main.TrendCollector"),
        patch("main.ImageFetcher"),
        patch("main.ArchiveManager"),
        patch("main.KeywordTracker"),
        patch("main.ContentEnricher"),
        patch("main.EditorialGenerator"),
        patch("main.MediaOfDayFetcher"),
        patch("main.MetricsCollector"),
    ]
    mocks = [p.start() for p in patches]
    try:
        from main import Pipeline

        pipeline = Pipeline(project_root=temp_dir)
        return pipeline, patches, mocks
    except Exception:
        for p in patches:
            p.stop()
        raise


@pytest.fixture
def pipeline(temp_dir):
    pipeline, patches, mocks = make_pipeline(temp_dir)
    yield pipeline
    for p in patches:
        p.stop()


class TestPipelineInit:
    def test_creates_public_dir(self, temp_dir):
        with (
            patch("main.TrendCollector"),
            patch("main.ImageFetcher"),
            patch("main.ArchiveManager"),
            patch("main.KeywordTracker"),
            patch("main.ContentEnricher"),
            patch("main.EditorialGenerator"),
            patch("main.MediaOfDayFetcher"),
            patch("main.MetricsCollector"),
        ):
            from main import Pipeline

            p = Pipeline(project_root=temp_dir)
            assert (temp_dir / "public").is_dir()

    def test_creates_data_dir(self, temp_dir):
        with (
            patch("main.TrendCollector"),
            patch("main.ImageFetcher"),
            patch("main.ArchiveManager"),
            patch("main.KeywordTracker"),
            patch("main.ContentEnricher"),
            patch("main.EditorialGenerator"),
            patch("main.MediaOfDayFetcher"),
            patch("main.MetricsCollector"),
        ):
            from main import Pipeline

            p = Pipeline(project_root=temp_dir)
            assert (temp_dir / "data").is_dir()


class TestRunStep:
    def test_step_success_records_metrics(self, pipeline):
        called = []
        pipeline._run_step("test_step", lambda: called.append(True))
        assert called == [True]
        pipeline.metrics.record_step.assert_called()

    def test_step_exception_is_reraised(self, pipeline):
        def bad():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            pipeline._run_step("bad_step", bad)

    def test_step_failure_records_metrics(self, pipeline):
        def bad():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            pipeline._run_step("bad_step", bad)

        # record_step should have been called with success=False
        calls = pipeline.metrics.record_step.call_args_list
        assert any(c.kwargs.get("success") is False for c in calls)

    def test_disabled_step_is_skipped(self, pipeline):
        called = []
        pipeline._run_step("skipped", lambda: called.append(True), enabled=False)
        assert called == []
        pipeline.metrics.record_step.assert_called_with("skipped", 0.0, skipped=True)


class TestQualityGate:
    def test_aborts_when_too_few_trends(self, pipeline):
        from config import MIN_TRENDS

        mock_trend = MagicMock()
        mock_trend.title = "Test"
        mock_trend.source = "test"

        # Return fewer trends than the minimum
        pipeline.trend_collector.collect_all.return_value = [mock_trend] * (
            MIN_TRENDS - 1
        )
        pipeline.trend_collector.get_all_keywords.return_value = []
        pipeline.trend_collector.get_global_keywords.return_value = []
        pipeline.trend_collector.get_freshness_ratio.return_value = 1.0
        pipeline.keyword_tracker.record_keywords.return_value = None
        pipeline.keyword_tracker.get_trending_keywords.return_value = []

        with pytest.raises(Exception, match="Insufficient content"):
            pipeline._step_collect_trends()

    def test_passes_quality_gate_with_enough_trends(self, pipeline):
        from config import MIN_TRENDS

        mock_trend = MagicMock()
        mock_trend.title = "Test Trend Title"
        mock_trend.source = "hackernews"

        pipeline.trend_collector.collect_all.return_value = [mock_trend] * MIN_TRENDS
        pipeline.trend_collector.get_all_keywords.return_value = ["tech"]
        pipeline.trend_collector.get_global_keywords.return_value = []
        pipeline.trend_collector.get_freshness_ratio.return_value = 1.0
        pipeline.keyword_tracker.record_keywords.return_value = None
        pipeline.keyword_tracker.get_trending_keywords.return_value = []

        # Should not raise
        pipeline._step_collect_trends()
        assert len(pipeline.trends) == MIN_TRENDS


class TestValidateEnvironment:
    def test_warns_when_no_image_keys(self, pipeline):
        with patch.dict("os.environ", {}, clear=True):
            warnings = pipeline._validate_environment()
        image_warning = any("image" in w.lower() or "PEXELS" in w for w in warnings)
        assert image_warning

    def test_no_warnings_with_image_keys(self, pipeline):
        with patch.dict("os.environ", {"PEXELS_API_KEY": "key123"}, clear=False):
            warnings = pipeline._validate_environment()
        image_warning = any("PEXELS" in w or "image API" in w.lower() for w in warnings)
        assert not image_warning
