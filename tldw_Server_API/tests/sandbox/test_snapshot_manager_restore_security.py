from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Sandbox.snapshots import SnapshotManager


def test_restore_snapshot_round_trip(tmp_path: Path) -> None:
    manager = SnapshotManager(storage_path=str(tmp_path / "snapshots"))
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "state.txt").write_text("original", encoding="utf-8")

    snapshot = manager.create_snapshot("sess-1", str(workspace))
    assert "snapshot_id" in snapshot

    (workspace / "state.txt").write_text("mutated", encoding="utf-8")
    (workspace / "new.txt").write_text("new", encoding="utf-8")

    assert manager.restore_snapshot("sess-1", snapshot["snapshot_id"], str(workspace)) is True
    assert (workspace / "state.txt").read_text(encoding="utf-8") == "original"
    assert not (workspace / "new.txt").exists()


def test_restore_snapshot_rejects_path_traversal_member(tmp_path: Path) -> None:
    manager = SnapshotManager(storage_path=str(tmp_path / "snapshots"))
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "keep.txt").write_text("ok", encoding="utf-8")

    session_id = "sess-path"
    snapshot_id = "snap-path"
    snapshot_path = manager._snapshot_path(session_id, snapshot_id)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    source = tmp_path / "payload.txt"
    source.write_text("payload", encoding="utf-8")
    with tarfile.open(snapshot_path, "w:gz") as tar:
        tar.add(source, arcname="../outside.txt")

    with pytest.raises(ValueError, match="Path traversal detected"):
        manager.restore_snapshot(session_id, snapshot_id, str(workspace))

    assert (workspace / "keep.txt").read_text(encoding="utf-8") == "ok"
    assert not (workspace.parent / "outside.txt").exists()


def test_restore_snapshot_rejects_symlink_member(tmp_path: Path) -> None:
    manager = SnapshotManager(storage_path=str(tmp_path / "snapshots"))
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "keep.txt").write_text("safe", encoding="utf-8")

    session_id = "sess-link"
    snapshot_id = "snap-link"
    snapshot_path = manager._snapshot_path(session_id, snapshot_id)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(snapshot_path, "w:gz") as tar:
        info = tarfile.TarInfo("danger-link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)

    with pytest.raises(ValueError, match="Refusing to extract link member"):
        manager.restore_snapshot(session_id, snapshot_id, str(workspace))

    assert (workspace / "keep.txt").read_text(encoding="utf-8") == "safe"
