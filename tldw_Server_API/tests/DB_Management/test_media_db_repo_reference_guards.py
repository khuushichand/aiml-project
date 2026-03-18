from __future__ import annotations

from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_ACTIVE_DOCS_WITHOUT_MEDIA_DB_V2 = (
    "Docs/API-related/Chunking_Templates_API_Documentation.md",
    "Docs/Architecture.md",
    "Docs/Chunking/Chunking_Templates.md",
    "Docs/Deployment/Postgres_Migration_Guide.md",
    "Docs/MCP/Unified/Modules.md",
    "Docs/MCP/Unified/User_Guide.md",
    "Docs/MCP/Unified/Using_Modules_YAML.md",
    "Docs/Published/Deployment/Long_Term_Admin_Guide.md",
    "Docs/RAG/Benchmarks/Benchmark_Corpus_Workflow.md",
    "Docs/Release_Checklist.md",
    "Docs/User_Guides/Server/Multi-User_Postgres_Setup.md",
    "Docs/User_Guides/Server/Multi-User_SQLite_Setup.md",
    "Docs/User_Guides/Server/RAG_Deployment_Guide.md",
    "Docs/User_Guides/Server/RAG_Production_Configuration_Guide.md",
)


def _read_repo_file(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_ci_check_imports_helper_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("Helper_Scripts/ci/check_imports_and_methods.py")  # nosec B101


def test_readme_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("README.md")  # nosec B101


def test_claude_guide_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("CLAUDE.md")  # nosec B101


def test_backup_all_script_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("Helper_Scripts/backup_all.sh")  # nosec B101


def test_restore_all_script_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_repo_file("Helper_Scripts/restore_all.sh")  # nosec B101


@pytest.mark.parametrize("relative_path", _ACTIVE_DOCS_WITHOUT_MEDIA_DB_V2)
def test_active_docs_no_longer_mention_media_db_v2_in_source(relative_path: str) -> None:
    assert "Media_DB_v2" not in _read_repo_file(relative_path)  # nosec B101
