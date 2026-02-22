#!/usr/bin/env python3
"""
Pipeline Metrics Collector - Persist per-run metrics and timings.

Stores metrics in `data/metrics/YYYY-MM-DD.json` as an array of run records.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore[assignment]


@dataclass
class StepMetric:
    """Single pipeline step execution record."""

    name: str
    duration_ms: float
    success: bool = True
    skipped: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Collects and persists performance/resource/quality metrics for one run."""

    def __init__(self, metrics_dir: Path) -> None:
        self.metrics_dir = Path(metrics_dir)
        self._reset()

    def _reset(self) -> None:
        self.run_id: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.context: Dict[str, Any] = {}
        self.counters: Dict[str, Any] = {}
        self.quality: Dict[str, Any] = {}
        self.resources: Dict[str, Any] = {}
        self.steps: List[StepMetric] = []

    def start_run(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Initialize a new metrics run."""
        self._reset()
        self.run_id = str(uuid.uuid4())
        self.started_at = datetime.now(timezone.utc)
        self.context = dict(context or {})
        self.capture_resource_snapshot("start")
        return self.run_id

    def record_step(
        self,
        name: str,
        duration_ms: float,
        *,
        success: bool = True,
        skipped: bool = False,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record execution metadata for a pipeline step."""
        self.steps.append(
            StepMetric(
                name=name,
                duration_ms=round(duration_ms, 2),
                success=success,
                skipped=skipped,
                error=error,
                metadata=dict(metadata or {}),
            )
        )

    def set_counter(self, key: str, value: Any) -> None:
        """Set a top-level numeric/text counter."""
        self.counters[key] = value

    def increment_counter(self, key: str, amount: float = 1.0) -> None:
        """Increment a numeric counter."""
        current = self.counters.get(key, 0)
        if not isinstance(current, (int, float)):
            current = 0
        self.counters[key] = current + amount

    def set_quality_metric(self, key: str, value: Any) -> None:
        """Set a quality metric value."""
        self.quality[key] = value

    def set_resource_metric(self, key: str, value: Any) -> None:
        """Set a resource metric value."""
        self.resources[key] = value

    def capture_resource_snapshot(self, label: str = "current") -> None:
        """Capture an in-process resource snapshot."""
        if psutil is None:
            return

        try:
            proc = psutil.Process()
            rss_mb = proc.memory_info().rss / (1024 * 1024)
            self.resources[f"{label}_rss_mb"] = round(rss_mb, 2)
        except Exception:
            # Resource snapshots are best-effort and should never fail pipeline.
            return

    def finalize(
        self,
        *,
        success: bool,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Persist this run into the daily metrics file and return the output path."""
        if not self.run_id or not self.started_at:
            self.start_run()

        finished_at = datetime.now(timezone.utc)
        started_at = self.started_at or finished_at
        self.capture_resource_snapshot("end")

        total_duration_ms = (finished_at - started_at).total_seconds() * 1000
        run_record: Dict[str, Any] = {
            "run_id": self.run_id,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "success": success,
            "error": error,
            "duration_ms": round(total_duration_ms, 2),
            "context": self.context,
            "counters": self.counters,
            "quality": self.quality,
            "resources": self.resources,
            "steps": [self._normalize_value(step.__dict__) for step in self.steps],
            "metadata": dict(metadata or {}),
        }

        date_str = finished_at.strftime("%Y-%m-%d")
        output_path = self.metrics_dir / f"{date_str}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        existing: List[Dict[str, Any]] = []
        if output_path.exists():
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, list):
                    existing = payload
            except Exception:
                existing = []

        existing.append(self._normalize_value(run_record))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        return output_path

    def _normalize_value(self, value: Any) -> Any:
        """Convert non-JSON-native values recursively into serializable values."""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(k): self._normalize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._normalize_value(v) for v in value]
        if isinstance(value, tuple):
            return [self._normalize_value(v) for v in value]
        return value
