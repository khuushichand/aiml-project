import os
from pathlib import Path


def test_prompts_dir_default_points_to_api_config_prompts():
    from tldw_Server_API.app.core.Utils import prompt_loader as pl

    p = Path(pl._prompts_dir()).resolve()
    # Exists and has expected structure: .../tldw_Server_API/Config_Files/Prompts
    assert p.exists(), f"Prompts dir does not exist: {p}"
    assert p.name == "Prompts", f"Unexpected leaf dir: {p.name}"
    assert p.parent.name == "Config_Files", f"Unexpected parent dir: {p.parent}"
    assert p.parent.parent.name == "tldw_Server_API", f"Unexpected api root: {p.parent.parent}"


def test_prompts_dir_respects_env_override(tmp_path, monkeypatch):
    # Create an override config dir with Prompts subfolder
    cfg_dir = tmp_path / "my_config"
    prompts = cfg_dir / "Prompts"
    prompts.mkdir(parents=True)
    # Set env to override
    monkeypatch.setenv("TLDW_CONFIG_DIR", str(cfg_dir))
    try:
        from tldw_Server_API.app.core.Utils import prompt_loader as pl
        p = Path(pl._prompts_dir()).resolve()
        assert p == prompts.resolve(), f"Env override not respected: {p} vs {prompts}"
    finally:
        monkeypatch.delenv("TLDW_CONFIG_DIR", raising=False)
