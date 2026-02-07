from __future__ import annotations

from pathlib import Path
import tomllib


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_chat_fixtures_plugin_not_globally_registered():
    pyproject_path = _repo_root() / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    plugins = data["tool"]["pytest"]["ini_options"]["plugins"]
    assert "tldw_Server_API.tests._plugins.chat_fixtures" not in plugins

    root_conftest = (_repo_root() / "conftest.py").read_text(encoding="utf-8")
    assert "tldw_Server_API.tests._plugins.chat_fixtures" not in root_conftest


def test_chat_suite_conftest_opt_in_for_chat_fixtures():
    chat_conftest = _repo_root() / "tldw_Server_API" / "tests" / "Chat" / "conftest.py"
    text = chat_conftest.read_text(encoding="utf-8")
    assert "tests._plugins.chat_fixtures" in text


def test_chat_fixtures_plugin_not_loaded_for_logging_run(pytestconfig):
    plugin_names = {name for name, _plugin in pytestconfig.pluginmanager.list_name_plugin()}
    assert "tldw_Server_API.tests._plugins.chat_fixtures" not in plugin_names
