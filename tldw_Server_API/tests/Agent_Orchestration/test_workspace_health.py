"""Tests for workspace health monitoring service."""
from __future__ import annotations

import os
import tempfile

import pytest

from tldw_Server_API.app.core.Agent_Orchestration.models import ACPWorkspace
from tldw_Server_API.app.core.DB_Management.Orchestration_DB import OrchestrationDB
from tldw_Server_API.app.services.workspace_health_service import (
    WorkspaceHealthResult,
    WorkspaceHealthService,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def svc():
    return WorkspaceHealthService()


def _make_workspace(root_path: str, workspace_id: int = 1) -> ACPWorkspace:
    """Create a minimal ACPWorkspace for testing."""
    return ACPWorkspace(
        id=workspace_id,
        name="test-ws",
        root_path=root_path,
        user_id=1,
        created_at="2025-01-01T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Path existence
# ---------------------------------------------------------------------------


async def test_health_missing_path(svc):
    """Non-existent path should return 'missing' status."""
    ws = _make_workspace("/this/path/does/not/exist")
    result = await svc.check_health(ws)
    assert result.health_status == "missing"
    assert result.path_exists is False
    assert len(result.issues) == 1
    assert "does not exist" in result.issues[0]


async def test_health_existing_path(svc, tmp_path):
    """Existing path should return 'healthy' status."""
    ws = _make_workspace(str(tmp_path))
    result = await svc.check_health(ws)
    assert result.health_status == "healthy"
    assert result.path_exists is True


# ---------------------------------------------------------------------------
# Disk space
# ---------------------------------------------------------------------------


async def test_health_includes_disk_free(svc, tmp_path):
    """Health check should include disk free space."""
    ws = _make_workspace(str(tmp_path))
    result = await svc.check_health(ws)
    assert result.disk_free_mb is not None
    assert result.disk_free_mb > 0


# ---------------------------------------------------------------------------
# Git metadata
# ---------------------------------------------------------------------------


async def test_health_no_git_dir(svc, tmp_path):
    """Non-git directory should have None git fields."""
    ws = _make_workspace(str(tmp_path))
    result = await svc.check_health(ws)
    assert result.git_current_branch is None
    assert result.git_is_dirty is None


async def test_health_with_git_dir(svc, tmp_path):
    """Directory with .git should attempt git metadata extraction."""
    # Create a minimal git repo
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    ws = _make_workspace(str(tmp_path))
    result = await svc.check_health(ws)
    # Even if git commands fail (bare .git dir), path_exists should be True
    assert result.path_exists is True


# ---------------------------------------------------------------------------
# Health result to_dict
# ---------------------------------------------------------------------------


async def test_health_result_to_dict(svc, tmp_path):
    """to_dict should include all fields."""
    ws = _make_workspace(str(tmp_path))
    result = await svc.check_health(ws)
    d = result.to_dict()
    assert "workspace_id" in d
    assert "health_status" in d
    assert "path_exists" in d
    assert "disk_free_mb" in d
    assert "checked_at" in d
    assert "issues" in d


# ---------------------------------------------------------------------------
# Batch refresh
# ---------------------------------------------------------------------------


async def test_refresh_all(tmp_path):
    """refresh_all should check all workspaces and persist results."""
    with tempfile.TemporaryDirectory() as db_dir:
        db = OrchestrationDB(user_id=1, db_dir=db_dir)
        ws1 = db.create_workspace(name="WS1", root_path=str(tmp_path))
        ws2 = db.create_workspace(name="WS2", root_path="/nonexistent/path/xyz")

        svc = WorkspaceHealthService()
        results = await svc.refresh_all(db)

        assert len(results) == 2
        # WS1 (real path) should be healthy
        r1 = next(r for r in results if r.workspace_id == ws1.id)
        assert r1.health_status == "healthy"
        # WS2 (nonexistent) should be missing
        r2 = next(r for r in results if r.workspace_id == ws2.id)
        assert r2.health_status == "missing"

        # Verify persistence
        updated_ws1 = db.get_workspace(ws1.id)
        assert updated_ws1.health_status == "healthy"
        assert updated_ws1.last_health_check is not None
        updated_ws2 = db.get_workspace(ws2.id)
        assert updated_ws2.health_status == "missing"

        db.close()


# ---------------------------------------------------------------------------
# Health classification
# ---------------------------------------------------------------------------


async def test_healthy_classification(svc, tmp_path):
    """Workspace with existing path and no issues is healthy."""
    ws = _make_workspace(str(tmp_path))
    result = await svc.check_health(ws)
    assert result.health_status == "healthy"
    assert result.issues == []
