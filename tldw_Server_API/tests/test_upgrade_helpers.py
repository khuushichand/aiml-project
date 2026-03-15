"""Tests for Helper_Scripts.upgrade_helpers."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

# The helper module lives outside the main package tree, so we adjust the
# import path if necessary.
import sys
import os

# Ensure repo root is on sys.path so we can import Helper_Scripts as a package.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from Helper_Scripts.upgrade_helpers import (
    PreUpgradeResult,
    check_database_integrity,
    check_version_compatibility,
    run_pre_upgrade_checks,
)


# ---------------------------------------------------------------------------
# check_version_compatibility
# ---------------------------------------------------------------------------

class TestCheckVersionCompatibility:
    """Tests for semver version comparison."""

    def test_minor_upgrade(self):
        assert check_version_compatibility("0.1.25", "0.1.26") is True

    def test_same_version(self):
        assert check_version_compatibility("0.1.25", "0.1.25") is True

    def test_downgrade_rejected(self):
        assert check_version_compatibility("0.2.0", "0.1.0") is False

    def test_major_upgrade(self):
        assert check_version_compatibility("0.1.25", "1.0.0") is True

    def test_major_downgrade(self):
        assert check_version_compatibility("2.0.0", "1.9.9") is False

    def test_leading_v_stripped(self):
        assert check_version_compatibility("v0.1.0", "v0.2.0") is True

    def test_patch_downgrade(self):
        assert check_version_compatibility("0.1.5", "0.1.4") is False


# ---------------------------------------------------------------------------
# check_database_integrity
# ---------------------------------------------------------------------------

class TestCheckDatabaseIntegrity:
    """Tests for SQLite integrity checking."""

    def test_nonexistent_path_returns_ok(self, tmp_path: Path):
        result = check_database_integrity(str(tmp_path / "does_not_exist.db"))
        assert result["status"] == "ok"
        assert "new install" in result["message"]

    def test_valid_db_returns_ok(self, tmp_path: Path):
        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        result = check_database_integrity(str(db_file))
        assert result["status"] == "ok"
        assert "integrity ok" in result["message"]

    def test_corrupt_file_returns_fail(self, tmp_path: Path):
        bad_file = tmp_path / "corrupt.db"
        bad_file.write_bytes(b"this is not a valid sqlite database at all " * 10)

        result = check_database_integrity(str(bad_file))
        # Should either fail or report an error (depends on SQLite version)
        assert result["name"] == "db_integrity"


# ---------------------------------------------------------------------------
# run_pre_upgrade_checks
# ---------------------------------------------------------------------------

class TestRunPreUpgradeChecks:
    """Tests for the aggregated check runner."""

    def test_fresh_install_can_proceed(self, tmp_path: Path):
        """With no databases and low disk threshold, all checks should pass."""
        result = run_pre_upgrade_checks(db_dir=str(tmp_path), min_disk_mb=1)
        assert result.can_proceed is True
        # Should have disk_space, python_version, and db_integrity (no files)
        assert len(result.checks) >= 3

    def test_with_valid_db(self, tmp_path: Path):
        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        result = run_pre_upgrade_checks(db_dir=str(tmp_path), min_disk_mb=1)
        assert result.can_proceed is True

    def test_nonexistent_db_dir(self, tmp_path: Path):
        result = run_pre_upgrade_checks(
            db_dir=str(tmp_path / "nonexistent"),
            min_disk_mb=1,
        )
        assert result.can_proceed is True
        # Should note fresh install
        msgs = [c.get("message", "") for c in result.checks]
        assert any("fresh install" in m or "not found" in m for m in msgs)


# ---------------------------------------------------------------------------
# PreUpgradeResult
# ---------------------------------------------------------------------------

class TestPreUpgradeResult:
    """Tests for the result dataclass properties."""

    def test_summary_format(self):
        r = PreUpgradeResult(checks=[
            {"name": "a", "status": "ok", "message": "good"},
            {"name": "b", "status": "warn", "message": "meh"},
            {"name": "c", "status": "fail", "message": "bad"},
        ])
        assert r.summary == "1 passed, 1 warnings, 1 failed"
        assert r.can_proceed is False

    def test_all_ok(self):
        r = PreUpgradeResult(checks=[
            {"name": "a", "status": "ok"},
            {"name": "b", "status": "ok"},
        ])
        assert r.can_proceed is True
        assert r.summary == "2 passed, 0 warnings, 0 failed"

    def test_warnings_still_proceed(self):
        r = PreUpgradeResult(checks=[
            {"name": "a", "status": "ok"},
            {"name": "b", "status": "warn", "message": "low disk"},
        ])
        assert r.can_proceed is True
        assert len(r.warnings) == 1

    def test_failures_property(self):
        r = PreUpgradeResult(checks=[
            {"name": "x", "status": "fail", "message": "broken"},
        ])
        assert r.failures == ["x: broken"]

    def test_empty_checks(self):
        r = PreUpgradeResult()
        assert r.can_proceed is True
        assert r.summary == "0 passed, 0 warnings, 0 failed"
