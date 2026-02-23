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
