import os
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.path_utils import (
    open_safe_local_path,
)


def test_open_safe_local_path_reads_file(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    file_path = base_dir / "example.txt"
    file_path.write_bytes(b"hello")

    handle = open_safe_local_path(file_path, base_dir, mode="rb")
    assert handle is not None
    with handle:
        assert handle.read() == b"hello"


def test_open_safe_local_path_rejects_outside_base(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")

    handle = open_safe_local_path(outside, base_dir, mode="rb")
    assert handle is None


@pytest.mark.skipif(
    os.name == "nt" or not hasattr(os, "O_NOFOLLOW"),
    reason="POSIX-only symlink hardening",
)
def test_open_safe_local_path_rejects_symlink(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    symlink_path = base_dir / "link.txt"
    symlink_path.symlink_to(outside)

    handle = open_safe_local_path(symlink_path, base_dir, mode="rb")
    assert handle is None
