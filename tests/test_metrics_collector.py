#!/usr/bin/env python3
"""Tests for pipeline metrics collection and persistence."""

import json
from pathlib import Path

from metrics_collector import MetricsCollector


def _load_runs(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_metrics_collector_writes_daily_report(temp_dir):
    collector = MetricsCollector(temp_dir / "metrics")
    collector.start_run({"dry_run": True, "archive": False})
    collector.record_step("collect_trends", 123.4)
    collector.record_step("build_site", 0.0, skipped=True)
    collector.set_counter("trends_collected", 42)
    collector.set_quality_metric("freshness_ratio", 0.91)

    output_path = collector.finalize(success=True)

    assert output_path.exists()
    runs = _load_runs(output_path)
    assert len(runs) == 1
    run = runs[0]
    assert run["success"] is True
    assert run["context"]["dry_run"] is True
    assert run["counters"]["trends_collected"] == 42
    assert run["quality"]["freshness_ratio"] == 0.91
    assert run["steps"][0]["name"] == "collect_trends"
    assert run["steps"][1]["skipped"] is True


def test_metrics_collector_appends_multiple_runs_same_day(temp_dir):
    collector = MetricsCollector(temp_dir / "metrics")
    collector.start_run({"run": 1})
    path = collector.finalize(success=True)

    collector.start_run({"run": 2})
    collector.record_step("collect_trends", 10.0)
    collector.finalize(success=False, error="test error")

    runs = _load_runs(path)
    assert len(runs) == 2
    assert runs[0]["context"]["run"] == 1
    assert runs[1]["context"]["run"] == 2
    assert runs[1]["success"] is False
    assert runs[1]["error"] == "test error"
