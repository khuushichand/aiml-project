from __future__ import annotations

import json

from typer.testing import CliRunner

from tldw_Server_API.cli.wizard.cli import app


runner = CliRunner()


def test_init_dry_run_json():


     result = runner.invoke(app, ["init", "--dry-run", "--json"])  # type: ignore[arg-type]
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("command") == "init"
    assert data.get("status") == "ok"
    assert "facts" in data
    assert "actions" in data


def test_auth_single_user_json():


     result = runner.invoke(app, ["auth", "--mode", "single_user", "--json"])  # type: ignore[arg-type]
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("command") == "auth"
    assert data.get("mode") == "single_user"


def test_verify_json():


     result = runner.invoke(app, ["verify", "--json"])  # type: ignore[arg-type]
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("command") == "verify"
    assert data.get("status") == "ok"
    assert "facts" in data
