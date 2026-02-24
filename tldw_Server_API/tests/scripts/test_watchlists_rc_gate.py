"""Contract tests for the Watchlists RC gate CI helper script."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "Helper_Scripts" / "ci" / "watchlists_rc_gate.py"


def _load_script_module():
    assert SCRIPT_PATH.exists(), f"Expected script at {SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("watchlists_rc_gate", SCRIPT_PATH)
    assert spec and spec.loader, "Failed to create module spec for watchlists_rc_gate.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_definitions_use_expected_watchlists_order():
    module = _load_script_module()

    gate_ids = [gate["id"] for gate in module.WATCHLISTS_RC_GATES]
    gate_commands = [gate["command"] for gate in module.WATCHLISTS_RC_GATES]

    assert gate_ids == ["help", "onboarding", "uc2", "a11y", "scale"]
    assert gate_commands == [
        "bun run test:watchlists:help",
        "bun run test:watchlists:onboarding",
        "bun run test:watchlists:uc2",
        "bun run test:watchlists:a11y",
        "bun run test:watchlists:scale",
    ]


def test_summary_markdown_contains_rc_metadata_matrix_and_decision_banner():
    module = _load_script_module()

    results = [
        {"id": "help", "command": "bun run test:watchlists:help", "status": "passed", "duration_seconds": 1.5},
        {"id": "onboarding", "command": "bun run test:watchlists:onboarding", "status": "failed", "duration_seconds": 2.25},
    ]
    metadata = {
        "ref": "refs/heads/rc/test",
        "sha": "abc123",
        "run_url": "https://github.com/example/repo/actions/runs/1",
        "generated_at_utc": "2026-02-23T20:00:00Z",
    }

    markdown = module.build_summary_markdown(results=results, metadata=metadata, decision="NO-GO")

    assert "Watchlists RC Gate Summary" in markdown
    assert "refs/heads/rc/test" in markdown
    assert "abc123" in markdown
    assert "NO-GO" in markdown
    assert "| help | passed | 1.50s |" in markdown
    assert "| onboarding | failed | 2.25s |" in markdown


def test_decision_is_no_go_when_any_gate_fails():
    module = _load_script_module()

    all_pass = [{"status": "passed"}, {"status": "passed"}]
    one_fail = [{"status": "passed"}, {"status": "failed"}]

    assert module.determine_decision(all_pass) == "GO"
    assert module.determine_decision(one_fail) == "NO-GO"


def test_main_returns_nonzero_when_any_gate_fails(monkeypatch):
    module = _load_script_module()

    def fake_execute_all_gates(*, gates, working_directory):
        _ = gates, working_directory
        return [
            {"id": "help", "command": "bun run test:watchlists:help", "status": "passed", "duration_seconds": 1.0},
            {"id": "onboarding", "command": "bun run test:watchlists:onboarding", "status": "failed", "duration_seconds": 1.0},
        ]

    monkeypatch.setattr(module, "execute_all_gates", fake_execute_all_gates)

    with tempfile.TemporaryDirectory() as tmp_dir:
        summary_path = Path(tmp_dir) / "summary.md"
        json_path = Path(tmp_dir) / "results.json"
        exit_code = module.main(
            [
                "--summary-output",
                str(summary_path),
                "--json-output",
                str(json_path),
            ]
        )

    assert exit_code == 1


def test_main_returns_zero_when_all_gates_pass(monkeypatch):
    module = _load_script_module()

    def fake_execute_all_gates(*, gates, working_directory):
        _ = gates, working_directory
        return [
            {"id": "help", "command": "bun run test:watchlists:help", "status": "passed", "duration_seconds": 1.0},
            {"id": "onboarding", "command": "bun run test:watchlists:onboarding", "status": "passed", "duration_seconds": 1.0},
        ]

    monkeypatch.setattr(module, "execute_all_gates", fake_execute_all_gates)

    with tempfile.TemporaryDirectory() as tmp_dir:
        summary_path = Path(tmp_dir) / "summary.md"
        json_path = Path(tmp_dir) / "results.json"
        exit_code = module.main(
            [
                "--summary-output",
                str(summary_path),
                "--json-output",
                str(json_path),
            ]
        )

    assert exit_code == 0
