from unittest.mock import MagicMock


def test_load_prompt_prefers_env_prompt_file(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    prompts = cfg_dir / "Prompts"
    prompts.mkdir(parents=True)
    (prompts / "demo.prompts.md").write_text(
        "# Existing Key\n```\nfrom-md\n```\n",
        encoding="utf-8",
    )

    override_file = tmp_path / "override.txt"
    override_file.write_text("from-env-file", encoding="utf-8")

    monkeypatch.setenv("TLDW_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("TLDW_PROMPT_FILE_DEMO__EXISTING_KEY", str(override_file))

    from tldw_Server_API.app.core.Utils import prompt_loader as pl

    assert pl.load_prompt("demo", "Existing Key") == "from-env-file"


def test_load_env_prompt_file_logs_warning_on_oserror(monkeypatch):
    env_name = "TLDW_PROMPT_FILE_DEMO__EXISTING_KEY"
    monkeypatch.setenv(env_name, "/definitely/missing/prompt-override.txt")

    from tldw_Server_API.app.core.Utils import prompt_loader as pl

    mock_warning = MagicMock()
    monkeypatch.setattr(pl.logger, "warning", mock_warning, raising=True)

    assert pl._load_env_prompt_file("demo", "existing key") is None
    mock_warning.assert_called_once()
    warning_call = mock_warning.call_args[0]
    assert "Prompt override file read failed for env" in warning_call[0]
    assert warning_call[1] == env_name
    assert warning_call[2] == "demo"
    assert warning_call[3] == "existing key"
