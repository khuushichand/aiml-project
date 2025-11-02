import os
from configparser import ConfigParser

from tldw_Server_API.app.core.DB_Management import DB_Manager


def _cfg_with(database_type: str = "sqlite", backup_path: str | None = None) -> ConfigParser:
    cfg = ConfigParser()
    cfg.add_section("Database")
    cfg.set("Database", "type", database_type)
    if backup_path is not None:
        cfg.set("Database", "backup_path", backup_path)
    return cfg


def test_backup_dir_env_over_config(monkeypatch, tmp_path):
    # Ensure env var wins over config backup_path
    env_path = str(tmp_path / "env_backups")
    cfg_path = str(tmp_path / "cfg_backups")

    monkeypatch.setenv("TLDW_DB_BACKUP_PATH", env_path)
    monkeypatch.delenv("TLDW_CONTENT_DB_BACKEND", raising=False)

    cfg = _cfg_with(database_type="sqlite", backup_path=cfg_path)
    DB_Manager.reset_content_backend(config=cfg, reload=False)

    assert DB_Manager.single_user_backup_dir == env_path


def test_backup_dir_fallbacks(monkeypatch, tmp_path):
    # When env not set, use config backup_path; otherwise default dir
    monkeypatch.delenv("TLDW_DB_BACKUP_PATH", raising=False)
    monkeypatch.delenv("TLDW_CONTENT_DB_BACKEND", raising=False)

    cfg_path = str(tmp_path / "cfg_backups")
    cfg = _cfg_with(database_type="sqlite", backup_path=cfg_path)
    DB_Manager.reset_content_backend(config=cfg, reload=False)
    assert DB_Manager.single_user_backup_dir == cfg_path

    # No backup_path provided -> use module default
    cfg2 = _cfg_with(database_type="sqlite", backup_path=None)
    DB_Manager.reset_content_backend(config=cfg2, reload=False)
    assert DB_Manager.single_user_backup_dir == DB_Manager._DEFAULT_BACKUP_DIR


def test_db_type_derivation(monkeypatch):
    # Ensure environment does not override type
    monkeypatch.delenv("TLDW_CONTENT_DB_BACKEND", raising=False)

    # sqlite
    DB_Manager.reset_content_backend(config=_cfg_with("sqlite"), reload=False)
    assert DB_Manager.db_type == "sqlite"

    # postgres
    DB_Manager.reset_content_backend(config=_cfg_with("postgres"), reload=False)
    assert DB_Manager.db_type == "postgres"

    # elasticsearch -> explicitly reported as unsupported
    DB_Manager.reset_content_backend(config=_cfg_with("elasticsearch"), reload=False)
    assert DB_Manager.db_type == "elasticsearch"

    # unknown -> warn and fall back to sqlite
    DB_Manager.reset_content_backend(config=_cfg_with("mydb"), reload=False)
    assert DB_Manager.db_type == "sqlite"
