from __future__ import annotations

from typer.testing import CliRunner

from tldw_Server_API.cli.wizard.cli import app
from tldw_Server_API.tests.wizard.helpers import (
    assert_action_fields,
    assert_wizard_error,
    assert_wizard_json,
)


runner = CliRunner()


def test_init_dry_run_json():
    result = runner.invoke(app, ["init", "--dry-run", "--json"])  # type: ignore[arg-type]
    assert result.exit_code == 0, result.output
    data = assert_wizard_json(result.output, command="init", status="ok")
    assert "facts" in data
    assert "actions" in data


def test_auth_single_user_json():
    result = runner.invoke(app, ["auth", "--mode", "single_user", "--json", "--dry-run"])  # type: ignore[arg-type]
    assert result.exit_code == 0, result.output
    data = assert_wizard_json(result.output, command="auth", status="ok")
    assert data.get("mode") == "single_user"


def test_verify_json():
    result = runner.invoke(app, ["verify", "--json"])  # type: ignore[arg-type]
    assert result.exit_code == 0, result.output
    data = assert_wizard_json(result.output, command="verify", status="ok")
    assert "facts" in data


def test_init_multi_user_missing_database_url_errors():
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["init", "--dry-run", "--json"],
            env={"AUTH_MODE": "multi_user", "DATABASE_URL": ""},
        )
        assert result.exit_code == 2, result.output
        payload = assert_wizard_json(result.output, command="init", status="error")
        assert_wizard_error(payload, action_key="validate_database_url")
        actions = payload.get("actions") or []
        assert_action_fields(actions, "validate_database_url", {"present": False, "valid": False})
