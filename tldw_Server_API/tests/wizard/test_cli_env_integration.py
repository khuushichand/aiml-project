from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from tldw_Server_API.cli.wizard.cli import app
from tldw_Server_API.cli.wizard.utils import env as env_utils
from tldw_Server_API.tests.wizard.helpers import (
    assert_action_field,
    assert_action_fields,
    assert_wizard_error,
    assert_wizard_json,
)


runner = CliRunner()


def test_init_generates_single_user_key():
    with runner.isolated_filesystem() as tmp_dir:
        result = runner.invoke(
            app,
            ["init", "--default", "--install-dir", tmp_dir, "--json", "--no-format"],
        )
        assert result.exit_code == 0, result.output

        env_path = Path(tmp_dir) / ".env"
        values = env_utils.load_env(env_path)
        assert values.get("AUTH_MODE") == "single_user"
        key = values.get("SINGLE_USER_API_KEY")
        assert key
        env_key = os.getenv("SINGLE_USER_API_KEY") or os.getenv("API_KEY")
        if env_key:
            assert key == env_key
        else:
            assert key.startswith("tldw_")


def test_auth_updates_env_and_creates_backup():
    with runner.isolated_filesystem():
        env_path = Path(".env")
        original = "AUTH_MODE=multi_user\n"
        env_path.write_text(original, encoding="utf-8")

        result = runner.invoke(app, ["auth", "--mode", "single_user", "--json"])
        assert result.exit_code == 0, result.output

        values = env_utils.load_env(env_path)
        assert values.get("AUTH_MODE") == "single_user"
        assert values.get("SINGLE_USER_API_KEY")

        backups = list(Path(".").glob(".env.*.bak"))
        assert backups
        assert backups[0].read_text(encoding="utf-8") == original


def test_auth_dry_run_does_not_write_or_backup():
    with runner.isolated_filesystem():
        env_path = Path(".env")
        original = "AUTH_MODE=multi_user\n"
        env_path.write_text(original, encoding="utf-8")

        result = runner.invoke(app, ["auth", "--mode", "single_user", "--json", "--dry-run"])
        assert result.exit_code == 0, result.output

        assert env_path.read_text(encoding="utf-8") == original
        assert list(Path(".").glob(".env.*.bak")) == []


def test_auth_multi_user_invalid_database_url_errors():
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["auth", "--mode", "multi_user", "--json", "--dry-run"],
            env={"DATABASE_URL": "sqlite:///./Databases/users.db"},
        )
        assert result.exit_code == 2, result.output
        payload = assert_wizard_json(result.output, command="auth", status="error")
        assert_wizard_error(payload, action_key="validate_database_url")
        actions = payload.get("actions") or []
        assert_action_field(actions, "validate_database_url", "database_url.valid", False)
        assert Path(".env").exists() is False


def test_auth_multi_user_yes_sets_initializer_action():
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["auth", "--mode", "multi_user", "--json", "--dry-run", "--yes"],
            env={"DATABASE_URL": "postgresql://user:pass@localhost:5432/tldw_users"},
        )
        assert result.exit_code == 0, result.output
        payload = assert_wizard_json(result.output, command="auth", status="ok")
        actions = payload.get("actions") or []
        assert_action_field(actions, "authnz_initializer", "status", "would_run")


def test_init_multi_user_yes_sets_initializer_action():
    with runner.isolated_filesystem() as tmp_dir:
        result = runner.invoke(
            app,
            ["init", "--dry-run", "--json", "--yes", "--install-dir", tmp_dir, "--no-format"],
            env={
                "AUTH_MODE": "multi_user",
                "DATABASE_URL": "postgresql://user:pass@localhost:5432/tldw_users",
            },
        )
        assert result.exit_code == 0, result.output
        payload = assert_wizard_json(result.output, command="init", status="ok")
        actions = payload.get("actions") or []
        assert_action_field(actions, "authnz_initializer", "status", "would_run")


def test_init_multi_user_valid_database_url_sets_present_true():
    with runner.isolated_filesystem() as tmp_dir:
        result = runner.invoke(
            app,
            ["init", "--dry-run", "--json", "--install-dir", tmp_dir, "--no-format"],
            env={
                "AUTH_MODE": "multi_user",
                "DATABASE_URL": "postgresql://user:pass@localhost:5432/tldw_users",
            },
        )
        assert result.exit_code == 0, result.output
        payload = assert_wizard_json(result.output, command="init", status="ok")
        actions = payload.get("actions") or []
        assert_action_fields(actions, "validate_database_url", {"present": True, "valid": True})


def test_init_multi_user_invalid_database_url_errors():
    with runner.isolated_filesystem() as tmp_dir:
        result = runner.invoke(
            app,
            ["init", "--dry-run", "--json", "--install-dir", tmp_dir, "--no-format"],
            env={
                "AUTH_MODE": "multi_user",
                "DATABASE_URL": "sqlite:///./Databases/users.db",
            },
        )
        assert result.exit_code == 2, result.output
        payload = assert_wizard_json(result.output, command="init", status="error")
        assert_wizard_error(payload, action_key="validate_database_url")
        actions = payload.get("actions") or []
        assert_action_fields(actions, "validate_database_url", {"present": True, "valid": False})
