from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_repo_file(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_ci_check_imports_helper_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("Helper_Scripts/ci/check_imports_and_methods.py")


def test_readme_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("README.md")


def test_claude_guide_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("CLAUDE.md")


def test_backup_all_script_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("Helper_Scripts/backup_all.sh")


def test_restore_all_script_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("Helper_Scripts/restore_all.sh")
