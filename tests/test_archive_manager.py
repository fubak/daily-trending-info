#!/usr/bin/env python3
"""Tests for ArchiveManager."""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


class TestArchiveManagerInit:
    def test_creates_archive_directory(self, temp_dir):
        from archive_manager import ArchiveManager

        mgr = ArchiveManager(public_dir=str(temp_dir))
        assert (temp_dir / "archive").is_dir()

    def test_custom_archive_subdir(self, temp_dir):
        from archive_manager import ArchiveManager

        mgr = ArchiveManager(public_dir=str(temp_dir), archive_subdir="snapshots")
        assert (temp_dir / "snapshots").is_dir()


class TestArchiveCurrent:
    def test_returns_none_when_no_index(self, temp_dir):
        from archive_manager import ArchiveManager

        mgr = ArchiveManager(public_dir=str(temp_dir))
        result = mgr.archive_current()
        assert result is None

    def test_archives_index_html(self, temp_dir):
        from archive_manager import ArchiveManager

        (temp_dir / "index.html").write_text("<!DOCTYPE html><html></html>")
        today = datetime.now().strftime("%Y-%m-%d")

        with patch.object(
            __import__("archive_manager", fromlist=["ArchiveManager"]).ArchiveManager,
            "generate_index",
        ):
            mgr = ArchiveManager(public_dir=str(temp_dir))
            result = mgr.archive_current()

        assert result is not None
        assert (temp_dir / "archive" / today / "index.html").exists()

    def test_writes_metadata_json(self, temp_dir):
        from archive_manager import ArchiveManager

        (temp_dir / "index.html").write_text("<html></html>")
        today = datetime.now().strftime("%Y-%m-%d")
        design = {"theme_name": "Signal Desk"}

        with patch.object(
            __import__("archive_manager", fromlist=["ArchiveManager"]).ArchiveManager,
            "generate_index",
        ):
            mgr = ArchiveManager(public_dir=str(temp_dir))
            mgr.archive_current(design=design)

        meta_file = temp_dir / "archive" / today / "metadata.json"
        assert meta_file.exists()
        meta = json.loads(meta_file.read_text())
        assert meta["date"] == today
        assert meta["design"]["theme_name"] == "Signal Desk"

    def test_skips_existing_archive(self, temp_dir):
        from archive_manager import ArchiveManager

        (temp_dir / "index.html").write_text("<html></html>")
        today = datetime.now().strftime("%Y-%m-%d")
        existing = temp_dir / "archive" / today
        existing.mkdir(parents=True)
        (existing / "index.html").write_text("<html>OLD</html>")

        with patch.object(
            __import__("archive_manager", fromlist=["ArchiveManager"]).ArchiveManager,
            "generate_index",
        ):
            mgr = ArchiveManager(public_dir=str(temp_dir))
            mgr.archive_current()

        # Original file should be unchanged
        assert (existing / "index.html").read_text() == "<html>OLD</html>"


class TestListArchives:
    def test_empty_archive_dir(self, temp_dir):
        from archive_manager import ArchiveManager

        mgr = ArchiveManager(public_dir=str(temp_dir))
        assert mgr.list_archives() == []

    def test_lists_dated_folders(self, temp_dir):
        from archive_manager import ArchiveManager

        archive_base = temp_dir / "archive"
        for date in ["2026-05-06", "2026-05-07", "2026-05-08"]:
            d = archive_base / date
            d.mkdir(parents=True)
            (d / "index.html").write_text("<html></html>")

        mgr = ArchiveManager(public_dir=str(temp_dir))
        archives = mgr.list_archives()

        assert len(archives) == 3
        # Should be sorted newest-first
        assert archives[0]["folder"] == "2026-05-08"
        assert archives[-1]["folder"] == "2026-05-06"

    def test_skips_folders_without_index(self, temp_dir):
        from archive_manager import ArchiveManager

        archive_base = temp_dir / "archive"
        good = archive_base / "2026-05-08"
        good.mkdir(parents=True)
        (good / "index.html").write_text("<html></html>")

        empty = archive_base / "2026-05-07"
        empty.mkdir(parents=True)

        mgr = ArchiveManager(public_dir=str(temp_dir))
        archives = mgr.list_archives()
        assert len(archives) == 1

    def test_loads_metadata(self, temp_dir):
        from archive_manager import ArchiveManager

        d = temp_dir / "archive" / "2026-05-08"
        d.mkdir(parents=True)
        (d / "index.html").write_text("<html></html>")
        (d / "metadata.json").write_text(
            json.dumps({"date": "2026-05-08", "design": {"theme_name": "TestTheme"}})
        )

        mgr = ArchiveManager(public_dir=str(temp_dir))
        archives = mgr.list_archives()
        assert archives[0]["design"]["theme_name"] == "TestTheme"


class TestCleanupOld:
    def test_removes_old_archives(self, temp_dir):
        from archive_manager import ArchiveManager

        archive_base = temp_dir / "archive"
        old_date = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d")
        old_dir = archive_base / old_date
        old_dir.mkdir(parents=True)
        (old_dir / "index.html").write_text("<html></html>")

        with patch.object(
            __import__("archive_manager", fromlist=["ArchiveManager"]).ArchiveManager,
            "generate_index",
        ):
            mgr = ArchiveManager(public_dir=str(temp_dir))
            removed = mgr.cleanup_old(keep_days=30)

        assert removed == 1
        assert not old_dir.exists()

    def test_keeps_recent_archives(self, temp_dir):
        from archive_manager import ArchiveManager

        archive_base = temp_dir / "archive"
        recent = datetime.now().strftime("%Y-%m-%d")
        d = archive_base / recent
        d.mkdir(parents=True)
        (d / "index.html").write_text("<html></html>")

        mgr = ArchiveManager(public_dir=str(temp_dir))
        removed = mgr.cleanup_old(keep_days=30)

        assert removed == 0
        assert d.exists()
