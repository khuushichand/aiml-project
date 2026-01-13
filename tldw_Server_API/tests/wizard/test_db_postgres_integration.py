from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tldw_Server_API.cli.wizard.cli import app
from tldw_Server_API.tests.wizard.helpers import assert_action_field, assert_wizard_json

# Reuse Postgres AuthNZ fixtures (isolated_test_environment) as a plugin.
pytest_plugins = ["tldw_Server_API.tests.AuthNZ.conftest"]

runner = CliRunner()


@pytest.mark.postgres
def test_db_multi_user_postgres_connectivity(request: pytest.FixtureRequest):
    request.getfixturevalue("isolated_test_environment")  # type: ignore[assignment]

    with runner.isolated_filesystem() as tmp_dir:
        db_url = os.environ.get("DATABASE_URL")
        assert db_url
        env = {
            "AUTH_MODE": "multi_user",
            "DATABASE_URL": db_url,
            "USER_DB_BASE_DIR": str((Path(tmp_dir) / "user_dbs").resolve()),
        }
        result = runner.invoke(app, ["db", "--json"], env=env)
        assert result.exit_code == 0, result.output
        payload = assert_wizard_json(result.output, command="db", status="ok")
        actions = payload.get("actions") or []
        assert_action_field(actions, "postgres_check", "status", "ok")
