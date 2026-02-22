from __future__ import annotations

import os
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import clear_config_cache, settings as app_settings
from tldw_Server_API.app.core.Sandbox.models import RuntimeType, SessionSpec
from tldw_Server_API.app.core.Sandbox.service import SandboxService

pytestmark = pytest.mark.unit


def _configure_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = str(tmp_path / "sandbox_store.db")
    root_dir = str(tmp_path / "sandbox_root")
    snapshot_dir = str(tmp_path / "snapshots")
    monkeypatch.setenv("SANDBOX_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SANDBOX_STORE_DB_PATH", db_path)
    monkeypatch.setenv("SANDBOX_ROOT_DIR", root_dir)
    monkeypatch.setenv("SANDBOX_SNAPSHOT_PATH", snapshot_dir)
    if hasattr(app_settings, "SANDBOX_STORE_BACKEND"):
        monkeypatch.setattr(app_settings, "SANDBOX_STORE_BACKEND", "sqlite")
    if hasattr(app_settings, "SANDBOX_STORE_DB_PATH"):
        monkeypatch.setattr(app_settings, "SANDBOX_STORE_DB_PATH", db_path)
    if hasattr(app_settings, "SANDBOX_ROOT_DIR"):
        monkeypatch.setattr(app_settings, "SANDBOX_ROOT_DIR", root_dir)
    if hasattr(app_settings, "SANDBOX_SNAPSHOT_PATH"):
        monkeypatch.setattr(app_settings, "SANDBOX_SNAPSHOT_PATH", snapshot_dir)
    clear_config_cache()


def test_create_snapshot_enforces_count_quota_immediately(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_SNAPSHOT_MAX_COUNT", "2")
    monkeypatch.setenv("SANDBOX_SNAPSHOT_MAX_SIZE_MB", "256")

    svc = SandboxService()
    session = svc.create_session(
        user_id="user-snap",
        spec=SessionSpec(runtime=RuntimeType.docker, base_image="python:3.11-slim"),
        spec_version="1.0",
        idem_key=None,
        raw_body={"spec_version": "1.0", "runtime": "docker"},
    )
    ws = svc.get_session_workspace_path(session.id)
    assert ws is not None
    ws_path = Path(str(ws))

    (ws_path / "state.txt").write_text("v1", encoding="utf-8")
    snap1 = svc.create_snapshot(session.id)
    (ws_path / "state.txt").write_text("v2", encoding="utf-8")
    snap2 = svc.create_snapshot(session.id)
    (ws_path / "state.txt").write_text("v3", encoding="utf-8")
    snap3 = svc.create_snapshot(session.id)

    ids = [s.get("snapshot_id") for s in svc.list_snapshots(session.id)]
    assert len(ids) == 2
    assert snap1["snapshot_id"] not in ids
    assert snap2["snapshot_id"] in ids
    assert snap3["snapshot_id"] in ids


def test_create_snapshot_enforces_size_quota_under_large_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_SNAPSHOT_MAX_COUNT", "10")
    monkeypatch.setenv("SANDBOX_SNAPSHOT_MAX_SIZE_MB", "1")

    svc = SandboxService()
    session = svc.create_session(
        user_id="user-snap-size",
        spec=SessionSpec(runtime=RuntimeType.docker, base_image="python:3.11-slim"),
        spec_version="1.0",
        idem_key=None,
        raw_body={"spec_version": "1.0", "runtime": "docker"},
    )
    ws = svc.get_session_workspace_path(session.id)
    assert ws is not None
    ws_path = Path(str(ws))

    blob = ws_path / "blob.bin"
    blob.write_bytes(os.urandom(800_000))
    snap1 = svc.create_snapshot(session.id)
    blob.write_bytes(os.urandom(800_000))
    snap2 = svc.create_snapshot(session.id)

    snapshots = svc.list_snapshots(session.id)
    ids = [s.get("snapshot_id") for s in snapshots]
    assert len(ids) == 1
    assert snap1["snapshot_id"] not in ids
    assert snap2["snapshot_id"] in ids
