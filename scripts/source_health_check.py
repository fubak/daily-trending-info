#!/usr/bin/env python3
"""Daily source health checks for trend collection endpoints."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from config import DATA_DIR, setup_logging
from source_catalog import (
    DEFAULT_BROWSER_UA,
    DOMAIN_FETCH_PROFILES,
    HEADER_PROFILES,
    SourceSpec,
    get_health_sources,
)

logger = setup_logging("source_health_check")


def _resolve_domain_profile(url: str) -> Dict[str, Any]:
    host = urlparse(url).hostname or ""
    return dict(DOMAIN_FETCH_PROFILES.get(host, {}))


def _resolve_headers(source: SourceSpec, domain_profile: Dict[str, Any]) -> Dict[str, str]:
    headers = dict(HEADER_PROFILES.get("default", {}))
    headers.update(HEADER_PROFILES.get(source.headers_profile, {}))

    profile_headers = domain_profile.get("headers_profile")
    if isinstance(profile_headers, str):
        headers.update(HEADER_PROFILES.get(profile_headers, {}))

    if "User-Agent" not in headers:
        headers["User-Agent"] = DEFAULT_BROWSER_UA + " DailyTrendingHealthCheck/1.0"

    return headers


def _get_nested_value(payload: Any, path: str) -> Any:
    if not path:
        return payload

    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _base_result(source: SourceSpec) -> Dict[str, Any]:
    result = asdict(source)
    result.update(
        {
            "status": "down",
            "http_status": None,
            "latency_ms": None,
            "entry_count": 0,
            "content_type": "",
            "error": "",
            "attempts": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
            "fallback_used": False,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return result


def _check_rss(response: requests.Response) -> Dict[str, Any]:
    feed = feedparser.parse(response.content)
    entry_count = len(feed.entries)

    status = "healthy" if entry_count > 0 else "degraded"
    error = ""

    if feed.bozo and entry_count == 0:
        status = "down"
        error = str(feed.bozo_exception)
    elif feed.bozo:
        status = "degraded"
        error = str(feed.bozo_exception)

    return {"status": status, "entry_count": entry_count, "error": error}


def _check_json(response: requests.Response, count_path: str | None) -> Dict[str, Any]:
    payload = response.json()
    target = _get_nested_value(payload, count_path or "")

    if isinstance(target, list):
        entry_count = len(target)
    elif isinstance(target, dict):
        entry_count = len(target.keys())
    elif target is None:
        entry_count = 0
    else:
        entry_count = 1

    status = "healthy" if entry_count > 0 else "degraded"
    return {"status": status, "entry_count": entry_count, "error": ""}


def _check_html(response: requests.Response, selector: str | None) -> Dict[str, Any]:
    if not selector:
        return {"status": "healthy", "entry_count": 1, "error": ""}

    soup = BeautifulSoup(response.text, "html.parser")
    matches = soup.select(selector)
    entry_count = len(matches)
    status = "healthy" if entry_count > 0 else "down"
    error = "" if entry_count > 0 else f"No matches for selector: {selector}"
    return {"status": status, "entry_count": entry_count, "error": error}


def _run_single_check(
    session: requests.Session,
    source: SourceSpec,
    url: str,
    timeout: float,
    headers: Dict[str, str],
) -> Dict[str, Any]:
    start = time.perf_counter()
    response = session.get(url, timeout=timeout, headers=headers)
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    result: Dict[str, Any] = {
        "http_status": response.status_code,
        "latency_ms": latency_ms,
        "content_type": response.headers.get("content-type", ""),
        "status": "down",
        "entry_count": 0,
        "error": "",
    }

    if response.status_code >= 400:
        result["error"] = f"HTTP {response.status_code}"
        return result

    if source.kind == "rss":
        check = _check_rss(response)
    elif source.kind == "json":
        check = _check_json(response, source.json_count_path)
    else:
        check = _check_html(response, source.selector)

    result.update(check)
    return result


def check_source(
    session: requests.Session,
    source: SourceSpec,
    timeout: float,
    attempts: int,
) -> Dict[str, Any]:
    result = _base_result(source)
    domain_profile = _resolve_domain_profile(source.url)
    headers = _resolve_headers(source, domain_profile)

    effective_timeout = float(source.timeout_seconds or domain_profile.get("timeout") or timeout)
    effective_attempts = max(1, int(domain_profile.get("attempts") or attempts))
    retry_delay = float(domain_profile.get("retry_delay") or 0.4)

    failures: List[str] = []
    successful_attempts = 0

    for attempt_num in range(1, effective_attempts + 1):
        result["attempts"] = attempt_num
        try:
            attempt_result = _run_single_check(
                session=session,
                source=source,
                url=source.url,
                timeout=effective_timeout,
                headers=headers,
            )

            result.update(
                {
                    "http_status": attempt_result.get("http_status"),
                    "latency_ms": attempt_result.get("latency_ms"),
                    "entry_count": attempt_result.get("entry_count", 0),
                    "content_type": attempt_result.get("content_type", ""),
                }
            )

            status = attempt_result.get("status", "down")
            error = attempt_result.get("error", "")

            if status in {"healthy", "degraded"}:
                successful_attempts += 1
                result["successful_attempts"] = successful_attempts
                result["failed_attempts"] = len(failures)
                # Any prior failure means this source is intermittent/flaky.
                result["status"] = "flaky" if failures else status
                result["error"] = "; ".join(failures) if failures else error
                return result

            failures.append(error or f"Attempt {attempt_num}: down")
        except Exception as exc:  # pragma: no cover - defensive path
            failures.append(str(exc))

        if attempt_num < effective_attempts:
            time.sleep(retry_delay * attempt_num)

    # Primary exhausted. Try configured fallback once when available.
    if source.fallback_url:
        try:
            fallback_profile = _resolve_domain_profile(source.fallback_url)
            fallback_headers = _resolve_headers(source, fallback_profile)
            fallback_timeout = float(
                fallback_profile.get("timeout") or source.timeout_seconds or timeout
            )
            fallback_result = _run_single_check(
                session=session,
                source=source,
                url=source.fallback_url,
                timeout=fallback_timeout,
                headers=fallback_headers,
            )
            result.update(
                {
                    "http_status": fallback_result.get("http_status"),
                    "latency_ms": fallback_result.get("latency_ms"),
                    "entry_count": fallback_result.get("entry_count", 0),
                    "content_type": fallback_result.get("content_type", ""),
                    "successful_attempts": 1,
                    "failed_attempts": len(failures),
                    "attempts": effective_attempts + 1,
                }
            )

            if fallback_result.get("status") in {"healthy", "degraded"}:
                result["status"] = "flaky"
                result["fallback_used"] = True
                primary_error = "; ".join(failures) if failures else "primary feed failed"
                result["error"] = (
                    f"primary failed: {primary_error}; fallback succeeded"
                )
                return result

            failures.append(f"fallback failed: {fallback_result.get('error', 'unknown')}" )
        except Exception as exc:  # pragma: no cover - defensive path
            failures.append(f"fallback exception: {exc}")

    result["status"] = "down"
    result["failed_attempts"] = len(failures)
    result["error"] = "; ".join(failures)
    return result


def run_health_check(timeout: float, workers: int, attempts: int) -> Dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                DEFAULT_BROWSER_UA
                + " DailyTrendingHealthCheck/1.0"
            )
        }
    )

    sources = get_health_sources()
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(check_source, session, source, timeout, attempts): source
            for source in sources
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover - defensive path
                row = _base_result(source)
                row["status"] = "down"
                row["error"] = str(exc)
                results.append(row)

    results.sort(key=lambda row: (row["category"], row["name"]))

    summary = {
        "total": len(results),
        "healthy": sum(1 for r in results if r["status"] == "healthy"),
        "degraded": sum(1 for r in results if r["status"] == "degraded"),
        "flaky": sum(1 for r in results if r["status"] == "flaky"),
        "down": sum(1 for r in results if r["status"] == "down"),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": timeout,
        "workers": workers,
        "attempts": attempts,
        "summary": summary,
        "sources": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check source health for DailyTrending collectors")
    parser.add_argument(
        "--output",
        type=Path,
        default=DATA_DIR / "source_health.json",
        help="Output JSON path (default: data/source_health.json)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="Per-source HTTP timeout in seconds",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Parallel worker count",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=2,
        help="Retry attempts per source before marking down",
    )
    parser.add_argument(
        "--fail-on-down",
        action="store_true",
        help="Exit non-zero when any source is down",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_health_check(timeout=args.timeout, workers=args.workers, attempts=args.attempts)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    summary = report["summary"]
    logger.info(
        "Source health: %s total, %s healthy, %s degraded, %s flaky, %s down",
        summary["total"],
        summary["healthy"],
        summary["degraded"],
        summary["flaky"],
        summary["down"],
    )
    logger.info("Saved source health report to %s", args.output)

    if args.fail_on_down and summary["down"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
