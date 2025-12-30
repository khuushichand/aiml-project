from pathlib import Path

from tldw_Server_API.app.core.Ingestion_Media_Processing import path_utils


def test_is_safe_local_path_allows_relative_inside(tmp_path: Path) -> None:
    base_dir = tmp_path
    relative_path = Path("uploaded.txt")

    assert path_utils.is_safe_local_path(relative_path, base_dir)


def test_is_safe_local_path_allows_absolute_inside(tmp_path: Path) -> None:
    base_dir = tmp_path
    absolute_path = base_dir / "uploaded.txt"

    assert path_utils.is_safe_local_path(absolute_path, base_dir)


def test_is_safe_local_path_rejects_relative_escape(tmp_path: Path) -> None:
    base_dir = tmp_path
    escaping_path = Path("..") / "escape.txt"

    assert not path_utils.is_safe_local_path(escaping_path, base_dir)


def test_is_safe_local_path_rejects_absolute_outside(tmp_path: Path) -> None:
    base_dir = tmp_path
    outside_path = base_dir.parent / "escape.txt"

    assert not path_utils.is_safe_local_path(outside_path, base_dir)
