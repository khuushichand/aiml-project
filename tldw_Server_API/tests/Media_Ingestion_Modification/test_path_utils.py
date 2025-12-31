import os
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import path_utils
from tldw_Server_API.app.core.Ingestion_Media_Processing.path_utils import (
    open_safe_local_path_async,
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


@pytest.mark.asyncio
async def test_open_safe_local_path_async_reads_file(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    file_path = base_dir / "example.txt"
    file_path.write_bytes(b"hello")

    async with open_safe_local_path_async(file_path, base_dir, mode="rb") as handle:
        assert handle is not None
        assert await handle.read() == b"hello"


@pytest.mark.asyncio
async def test_open_safe_local_path_async_rejects_outside_base(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")

    async with open_safe_local_path_async(outside, base_dir, mode="rb") as handle:
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


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only path guard")
def test_open_safe_posix_rejects_parent_traversal(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")

    handle = path_utils._open_safe_posix(Path("..") / "outside.txt", base_dir, mode="rb")
    assert handle is None


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only path guard")
def test_open_safe_posix_rejects_absolute_path(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    file_path = base_dir / "example.txt"
    file_path.write_bytes(b"hello")

    handle = path_utils._open_safe_posix(file_path, base_dir, mode="rb")
    assert handle is None


def test_open_safe_local_path_windows_accepts(monkeypatch, tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    file_path = base_dir / "example.txt"
    file_path.write_bytes(b"hello")

    def fake_realpath(path: object) -> str:
        return os.fspath(path)

    monkeypatch.setattr(path_utils.os.path, "realpath", fake_realpath)

    handle = path_utils._open_safe_windows(file_path, base_dir, mode="rb")
    assert handle is not None
    with handle:
        assert handle.read() == b"hello"


def test_open_safe_local_path_windows_rejects_reparse(
    monkeypatch,
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    file_path = base_dir / "example.txt"
    file_path.write_bytes(b"hello")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_target = outside / "target.txt"

    base_real = os.fspath(base_dir)

    def fake_realpath(path: object) -> str:
        resolved = os.fspath(path)
        if resolved == base_real:
            return base_real
        return os.fspath(outside_target)

    monkeypatch.setattr(path_utils.os.path, "realpath", fake_realpath)

    handle = path_utils._open_safe_windows(file_path, base_dir, mode="rb")
    assert handle is None
