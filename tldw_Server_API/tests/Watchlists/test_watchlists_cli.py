"""Unit tests for watchlists CLI wrapper commands."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tldw_Server_API.cli.commands.watchlists import watchlists_group


def test_audio_smoke_passes_through_args_and_uses_default_python(tmp_path: Path):
    runner = CliRunner()
    script_path = tmp_path / "watchlists_audio_smoke.py"
    script_path.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")

    with (
        patch(
            "tldw_Server_API.cli.commands.watchlists._resolve_audio_smoke_script_path",
            return_value=script_path,
        ),
        patch(
            "tldw_Server_API.cli.commands.watchlists.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_run,
    ):
        result = runner.invoke(
            watchlists_group,
            [
                "audio-smoke",
                "--base-url",
                "http://127.0.0.1:8000",
                "--require-download",
            ],
        )

    assert result.exit_code == 0
    cmd = mock_run.call_args.args[0]
    assert cmd[0] == sys.executable
    assert cmd[1] == str(script_path)
    assert cmd[2:] == ["--base-url", "http://127.0.0.1:8000", "--require-download"]


def test_audio_smoke_honors_python_bin_and_nonzero_exit(tmp_path: Path):
    runner = CliRunner()
    script_path = tmp_path / "watchlists_audio_smoke.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")
    py_bin = tmp_path / "py"
    py_bin.write_text("", encoding="utf-8")

    with (
        patch(
            "tldw_Server_API.cli.commands.watchlists._resolve_audio_smoke_script_path",
            return_value=script_path,
        ),
        patch(
            "tldw_Server_API.cli.commands.watchlists.subprocess.run",
            return_value=MagicMock(returncode=3),
        ) as mock_run,
    ):
        result = runner.invoke(
            watchlists_group,
            ["audio-smoke", "--python-bin", str(py_bin), "--audio-poll-attempts", "2"],
        )

    assert result.exit_code == 3
    cmd = mock_run.call_args.args[0]
    assert cmd[0] == str(py_bin)
    assert cmd[1] == str(script_path)
    assert cmd[2:] == ["--audio-poll-attempts", "2"]


def test_audio_smoke_fails_when_script_is_missing(tmp_path: Path):
    runner = CliRunner()
    missing_script = tmp_path / "missing_script.py"

    with patch(
        "tldw_Server_API.cli.commands.watchlists._resolve_audio_smoke_script_path",
        return_value=missing_script,
    ):
        result = runner.invoke(watchlists_group, ["audio-smoke"])

    assert result.exit_code == 1
    assert "Audio smoke script not found" in result.output
