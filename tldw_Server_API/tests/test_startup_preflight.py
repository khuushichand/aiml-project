"""Tests for the startup preflight validation module."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.startup_preflight import (
    PreflightResult,
    check_database_directories,
    check_disk_space,
    check_ffmpeg_available,
    check_python_dependencies,
    run_preflight_checks,
)


# ---------------------------------------------------------------------------
# PreflightResult
# ---------------------------------------------------------------------------

class TestPreflightResult:
    def test_all_passed_when_all_ok(self):
        result = PreflightResult(checks=[
            {"name": "a", "status": "ok"},
            {"name": "b", "status": "ok"},
        ])
        assert result.all_passed is True

    def test_all_passed_false_when_any_fail(self):
        result = PreflightResult(checks=[
            {"name": "a", "status": "ok"},
            {"name": "b", "status": "fail", "message": "bad"},
        ])
        assert result.all_passed is False

    def test_all_passed_true_with_warnings_only(self):
        result = PreflightResult(checks=[
            {"name": "a", "status": "ok"},
            {"name": "b", "status": "warn", "message": "low"},
        ])
        assert result.all_passed is True

    def test_failures_returns_failure_strings(self):
        result = PreflightResult(checks=[
            {"name": "a", "status": "ok"},
            {"name": "b", "status": "fail", "message": "missing"},
            {"name": "c", "status": "fail", "message": "broken"},
        ])
        failures = result.failures
        assert len(failures) == 2
        assert "b: missing" in failures
        assert "c: broken" in failures

    def test_warnings_returns_warning_strings(self):
        result = PreflightResult(checks=[
            {"name": "a", "status": "warn", "message": "low disk"},
            {"name": "b", "status": "ok"},
        ])
        assert result.warnings == ["a: low disk"]

    def test_empty_checks(self):
        result = PreflightResult()
        assert result.all_passed is True
        assert result.failures == []
        assert result.warnings == []


# ---------------------------------------------------------------------------
# check_ffmpeg_available
# ---------------------------------------------------------------------------

class TestCheckFfmpeg:
    def test_returns_dict_with_name_and_status(self):
        result = check_ffmpeg_available()
        assert "name" in result
        assert "status" in result
        assert result["name"] == "ffmpeg_available"
        assert result["status"] in ("ok", "fail")

    def test_fail_when_ffmpeg_not_found(self):
        with patch("tldw_Server_API.app.core.startup_preflight.shutil.which", return_value=None):
            result = check_ffmpeg_available()
        assert result["status"] == "fail"
        assert "not found" in result["message"]

    def test_ok_when_ffmpeg_found(self):
        with patch("tldw_Server_API.app.core.startup_preflight.shutil.which", return_value="/usr/bin/ffmpeg"):
            result = check_ffmpeg_available()
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# check_disk_space
# ---------------------------------------------------------------------------

class TestCheckDiskSpace:
    def test_ok_with_very_low_threshold(self):
        result = check_disk_space(min_mb=1)
        assert result["status"] == "ok"

    def test_warn_with_impossibly_high_threshold(self):
        result = check_disk_space(min_mb=999_999_999)
        assert result["status"] == "warn"


# ---------------------------------------------------------------------------
# check_database_directories
# ---------------------------------------------------------------------------

class TestCheckDatabaseDirectories:
    def test_ok_with_tmp_path(self, tmp_path):
        result = check_database_directories(base_dir=tmp_path)
        assert result["status"] == "ok"

    def test_creates_directory_if_missing(self, tmp_path):
        new_dir = tmp_path / "sub" / "databases"
        result = check_database_directories(base_dir=new_dir)
        assert result["status"] == "ok"
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# check_python_dependencies
# ---------------------------------------------------------------------------

class TestCheckPythonDependencies:
    def test_ok_when_all_importable(self):
        result = check_python_dependencies()
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# run_preflight_checks
# ---------------------------------------------------------------------------

class TestRunPreflightChecks:
    def test_returns_preflight_result_with_checks(self):
        result = run_preflight_checks()
        assert isinstance(result, PreflightResult)
        assert len(result.checks) >= 4

    def test_strict_mode_raises_on_failure(self):
        with patch("tldw_Server_API.app.core.startup_preflight.check_ffmpeg_available",
                    return_value={"name": "ffmpeg_available", "status": "fail", "message": "missing"}):
            with patch.dict("os.environ", {"TLDW_PREFLIGHT_STRICT": "true"}):
                with pytest.raises(RuntimeError, match="Preflight checks failed"):
                    run_preflight_checks()
