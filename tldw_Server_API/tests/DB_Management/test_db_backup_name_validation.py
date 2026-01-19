import pytest

from tldw_Server_API.app.core.DB_Management.DB_Backups import (
    _POSTGRES_BACKUP_EXTS,
    _SQLITE_BACKUP_EXTS,
    _sanitize_backup_label,
    _validate_backup_name,
)


@pytest.mark.parametrize(
    ("label", "fallback", "expected"),
    [
        (" My DB!@# ", "db", "My_DB"),
        ("__leading__", "db", "leading"),
        ("--", "fallback", "fallback"),
        ("", "fallback", "fallback"),
    ],
)
def test_sanitize_backup_label(label: str, fallback: str, expected: str) -> None:
    assert _sanitize_backup_label(label, fallback) == expected


def test_sanitize_backup_label_truncates_long_names() -> None:
    label = "a" * 200
    assert _sanitize_backup_label(label, "db") == "a" * 100


@pytest.mark.parametrize("name", ["backup.db", "data.sqlib"])
def test_validate_backup_name_accepts_sqlite_names(name: str) -> None:
    assert _validate_backup_name(name, _SQLITE_BACKUP_EXTS) == name


def test_validate_backup_name_trims_whitespace() -> None:
    assert _validate_backup_name(" backup.db ", _SQLITE_BACKUP_EXTS) == "backup.db"


def test_validate_backup_name_accepts_postgres_dumps() -> None:
    assert _validate_backup_name("content.dump", _POSTGRES_BACKUP_EXTS) == "content.dump"


@pytest.mark.parametrize(
    "name",
    [
        "../evil.db",
        "subdir/evil.db",
        "/abs.db",
        "-flag.db",
        "backup.txt",
        "",
        "   ",
    ],
)
def test_validate_backup_name_rejects_invalid_names(name: str) -> None:
    assert _validate_backup_name(name, _SQLITE_BACKUP_EXTS) is None
