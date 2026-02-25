"""Contract tests for Watchlists telemetry RC reporting helper."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "Helper_Scripts" / "ci" / "watchlists_telemetry_rc_report.py"


def _load_script_module():
    assert SCRIPT_PATH.exists(), f"Expected script at {SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("watchlists_telemetry_rc_report", SCRIPT_PATH)
    assert spec and spec.loader, "Failed to create module spec for watchlists_telemetry_rc_report.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_threshold_evaluation_marks_potential_breach_without_operational_failure():
    module = _load_script_module()

    baseline = {
        "uc1_f1_first_source_setup_percent": 92.96,
        "uc1_f2_time_to_first_review_seconds": 567.49,
        "uc2_f2_text_output_success_percent": 0.06,
    }
    rc_payload = {
        "onboarding": {
            "rates": {"setup_completion_rate": 0.70},
            "timings": {"median_seconds_to_first_output_success": 1000.0},
        },
        "uc2_backend": {
            "first_output_success_rate": 0.0,
        },
    }

    thresholds = module.evaluate_thresholds(rc_payload=rc_payload, baseline=baseline)
    statuses = {item["id"]: item["status"] for item in thresholds}
    assert statuses["setup_completion_drop_10pp"] == "potential_breach"
    assert statuses["first_output_success_drop_10pp"] == "potential_breach"
    assert statuses["median_first_output_regression_25pct"] == "potential_breach"

    decision = module.determine_decision(thresholds=thresholds, operational_error=None)
    assert decision == "REPORT_ONLY_POTENTIAL_BREACH"
    assert module.decision_exit_code(decision) == 0


def test_markdown_contains_reporting_only_threshold_matrix():
    module = _load_script_module()

    metadata = {
        "ref": "refs/heads/rc/test",
        "sha": "abc123",
        "run_url": "https://github.com/example/repo/actions/runs/2",
        "generated_at_utc": "2026-02-23T22:00:00Z",
    }
    thresholds = [
        {
            "id": "setup_completion_drop_10pp",
            "label": "Setup completion drop >= 10pp vs baseline",
            "status": "ok",
            "metric_value": 93.0,
            "baseline_value": 92.96,
            "delta": 0.04,
        },
        {
            "id": "first_output_success_drop_10pp",
            "label": "First output success drop >= 10pp vs baseline",
            "status": "potential_breach",
            "metric_value": 0.0,
            "baseline_value": 0.06,
            "delta": -0.06,
        },
    ]

    markdown = module.build_summary_markdown(
        metadata=metadata,
        decision="REPORT_ONLY_POTENTIAL_BREACH",
        thresholds=thresholds,
        operational_error=None,
    )

    assert "Watchlists Telemetry RC Report" in markdown
    assert "reporting-only" in markdown.lower()
    assert "REPORT_ONLY_POTENTIAL_BREACH" in markdown
    assert "setup_completion_drop_10pp" in markdown
    assert "first_output_success_drop_10pp" in markdown


def test_main_returns_nonzero_for_operational_failure(monkeypatch):
    module = _load_script_module()

    def _raise_operational_error(*, api_base_url: str, api_key: str | None, timeout_seconds: float):
        _ = api_base_url, api_key, timeout_seconds
        raise RuntimeError("fetch_failed")

    monkeypatch.setattr(module, "fetch_rc_summary", _raise_operational_error)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        baseline_path = tmp / "baseline.json"
        baseline_path.write_text(
            json.dumps(
                {
                    "funnel_metrics": {
                        "UC1_F1_first_source_setup": {"percent": 92.96},
                        "UC1_F2_time_to_first_review": {"median_seconds": 567.49},
                        "UC2_F2_text_output_success": {"percent": 0.06},
                    }
                }
            ),
            encoding="utf-8",
        )
        summary_path = tmp / "report.md"
        json_path = tmp / "report.json"

        exit_code = module.main(
            [
                "--api-base-url",
                "http://127.0.0.1:8000",
                "--baseline-json",
                str(baseline_path),
                "--summary-output",
                str(summary_path),
                "--json-output",
                str(json_path),
            ]
        )

        assert exit_code == 1
        assert summary_path.exists()
        assert json_path.exists()


def test_main_honors_process_argv_when_argv_not_provided(monkeypatch):
    module = _load_script_module()

    def _fake_fetch_rc_summary(*, api_base_url: str, api_key: str | None, timeout_seconds: float):
        _ = api_base_url, api_key, timeout_seconds
        return {
            "onboarding": {"rates": {"setup_completion_rate": 0.93}, "timings": {"median_seconds_to_first_output_success": 500.0}},
            "uc2_backend": {"first_output_success_rate": 0.07},
        }

    monkeypatch.setattr(module, "fetch_rc_summary", _fake_fetch_rc_summary)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        baseline_path = tmp / "baseline.json"
        baseline_path.write_text(
            json.dumps(
                {
                    "funnel_metrics": {
                        "UC1_F1_first_source_setup": {"percent": 92.96},
                        "UC1_F2_time_to_first_review": {"median_seconds": 567.49},
                        "UC2_F2_text_output_success": {"percent": 0.06},
                        "UC2_F3_audio_output_success": {"percent": 0.03},
                    }
                }
            ),
            encoding="utf-8",
        )
        summary_path = tmp / "cli-report.md"
        json_path = tmp / "cli-report.json"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "watchlists_telemetry_rc_report.py",
                "--baseline-json",
                str(baseline_path),
                "--summary-output",
                str(summary_path),
                "--json-output",
                str(json_path),
            ],
        )

        exit_code = module.main()
        assert exit_code == 0
        assert summary_path.exists()
        assert json_path.exists()
