from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from tldw_Server_API.app.core.AuthNZ import migrate_to_multiuser as migration


pytestmark = pytest.mark.unit


class _StubPasswordService:
    def hash_password(self, password: str) -> str:
        return f"hashed::{password}"


class _StubRegistrationCodeDB:
    def __init__(self) -> None:
        self._issued = 0

    def create_registration_code(self, *, created_by: int, expires_in_days: int, max_uses: int, role: str) -> str:
        self._issued += 1
        return f"code-{self._issued}"


def _input_sequence(values: list[str]):
    iterator = iter(values)
    return lambda _prompt="": next(iterator)


def _getpass_sequence(values: list[str]):
    iterator = iter(values)
    return lambda _prompt="": next(iterator)


def test_verify_migration_runs_with_userdatabase_v2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    user_db = migration._build_user_db(str(tmp_path / "users.db"))
    admin_id = user_db.create_user(
        username="verify_admin",
        email="verify_admin@example.com",
        password_hash="hashed",
        role="admin",
    )
    assert user_db.update_user(admin_id, is_verified=True)

    migration.verify_migration(user_db)

    output = capsys.readouterr().out
    assert "MIGRATION VERIFICATION" in output
    assert "Users in database" in output


def test_create_admin_user_persists_verified_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_db = migration._build_user_db(str(tmp_path / "users.db"))

    monkeypatch.setattr("builtins.input", _input_sequence(["review_admin", "review_admin@example.com"]))
    monkeypatch.setattr(
        migration.getpass,
        "getpass",
        _getpass_sequence(["Aa!9QwErTy1$", "Aa!9QwErTy1$"]),
    )

    admin_info = migration.create_admin_user(user_db, _StubPasswordService())

    stored = user_db.get_user(user_id=admin_info["id"])
    assert stored is not None
    assert stored["is_verified"] is True


def test_generate_registration_codes_writes_owner_only_file_permissions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", _input_sequence(["y"]))

    codes = migration.generate_registration_codes(_StubRegistrationCodeDB(), admin_id=7, count=2)

    assert codes == ["code-1", "code-2"]
    codes_path = tmp_path / "registration_codes.txt"
    assert codes_path.exists()

    if os.name == "posix":
        assert stat.S_IMODE(codes_path.stat().st_mode) == 0o600


def test_main_skip_admin_uses_existing_admin_without_connection_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "users.db"
    user_db = migration._build_user_db(str(db_path))
    admin_id = user_db.create_user(
        username="existing_admin",
        email="existing_admin@example.com",
        password_hash="hashed",
        role="admin",
    )
    assert user_db.update_user(admin_id, is_verified=True)

    monkeypatch.setattr(migration, "_build_user_db", lambda _db_path: user_db)
    monkeypatch.setattr(migration, "PasswordService", lambda: _StubPasswordService())
    monkeypatch.setattr(migration, "generate_registration_codes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(migration, "migrate_existing_data", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(migration, "update_configuration", lambda: None)
    monkeypatch.setattr(migration, "verify_migration", lambda _user_db: None)
    monkeypatch.setattr("builtins.input", _input_sequence(["y"]))
    monkeypatch.setattr(
        migration.sys,
        "argv",
        [
            "migrate_to_multiuser.py",
            "--skip-admin",
            "--no-codes",
            "--db-path",
            str(db_path),
        ],
    )

    migration.main()

    output = capsys.readouterr().out
    assert "Using existing admin" in output
