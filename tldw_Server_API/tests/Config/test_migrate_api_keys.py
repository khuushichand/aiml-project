import configparser
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "Config_Files" / "migrate_api_keys.py"
_spec = importlib.util.spec_from_file_location("migrate_api_keys", MODULE_PATH)
assert _spec and _spec.loader
migrate_api_keys = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate_api_keys)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "value",
    [
        "",
        "None",
        "your-api-key-here",
        "your_api_key_here",
        "<openai_api_key>",
    ],
)
def test_collect_env_vars_skips_placeholders(value, capsys):
    config = configparser.ConfigParser()
    config.add_section("API")
    config.set("API", "openai_api_key", value)

    mappings = {("API", "openai_api_key"): "OPENAI_API_KEY"}
    env_vars, keys_found = migrate_api_keys._collect_env_vars(config, mappings, {}, False)

    assert env_vars == {}
    assert keys_found == []
    out = capsys.readouterr().out
    assert "OPENAI_API_KEY" not in out


def test_collect_env_vars_respects_existing_env(capsys):

    config = configparser.ConfigParser()
    config.add_section("API")
    config.set("API", "openai_api_key", "sk-test-value")

    mappings = {("API", "openai_api_key"): "OPENAI_API_KEY"}
    env_vars, keys_found = migrate_api_keys._collect_env_vars(
        config,
        mappings,
        {"OPENAI_API_KEY": "sk-existing"},
        False,
    )

    assert env_vars == {}
    assert keys_found == []
    out = capsys.readouterr().out
    assert "sk-test-value" not in out


def test_collect_env_vars_adds_new_and_hides_value(capsys):

    config = configparser.ConfigParser()
    config.add_section("API")
    config.set("API", "openai_api_key", "sk-test-value")

    mappings = {("API", "openai_api_key"): "OPENAI_API_KEY"}
    env_vars, keys_found = migrate_api_keys._collect_env_vars(config, mappings, {}, False)

    assert env_vars == {"OPENAI_API_KEY": "sk-test-value"}
    assert keys_found == [("API", "openai_api_key", "OPENAI_API_KEY")]
    out = capsys.readouterr().out
    assert "sk-test-value" not in out
    assert "Found OPENAI_API_KEY (value hidden)" in out


def test_build_key_mappings_contains_expected_keys():

    mappings = migrate_api_keys._build_key_mappings()

    assert mappings[("API", "openai_api_key")] == "OPENAI_API_KEY"
    assert mappings[("Search-Engines", "search_engine_id_google")] == "GOOGLE_SEARCH_ENGINE_ID"
    assert mappings[("Embeddings", "embedding_api_key")] == "EMBEDDING_API_KEY"


def test_read_env_lines_missing_returns_empty(tmp_path: Path):
    env_path = tmp_path / ".env"
    assert migrate_api_keys._read_env_lines(env_path) == []


def test_write_env_file_updates_and_appends(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# existing env\nOPENAI_API_KEY=old\nUNCHANGED=value\n",
        encoding="utf-8",
    )

    lines = migrate_api_keys._read_env_lines(env_path)
    env_vars = {"OPENAI_API_KEY": "new", "ANTHROPIC_API_KEY": "anthro"}
    migrate_api_keys._write_env_file(env_path, lines, env_vars)

    contents = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=new" in contents
    assert "UNCHANGED=value" in contents
    assert "ANTHROPIC_API_KEY=anthro" in contents
    assert "Migrated from config.txt on " in contents
