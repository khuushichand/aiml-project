"""Workspace health monitoring service.

Checks workspace health: path existence, git status, disk space.
"""
from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Agent_Orchestration.models import ACPWorkspace
from tldw_Server_API.app.core.DB_Management.Orchestration_DB import OrchestrationDB
from tldw_Server_API.app.services.workspace_discovery_service import (
    _extract_git_metadata,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Disk threshold in MB below which we flag as degraded
_LOW_DISK_THRESHOLD_MB = 100


@dataclass
class WorkspaceHealthResult:
    """Result of a single workspace health check."""
    workspace_id: int
    health_status: str  # healthy | degraded | missing
    path_exists: bool
    git_current_branch: str | None = None
    git_is_dirty: bool | None = None
    git_remote_url: str | None = None
    git_default_branch: str | None = None
    disk_free_mb: int | None = None
    checked_at: str = ""
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "health_status": self.health_status,
            "path_exists": self.path_exists,
            "git_current_branch": self.git_current_branch,
            "git_is_dirty": self.git_is_dirty,
            "git_remote_url": self.git_remote_url,
            "git_default_branch": self.git_default_branch,
            "disk_free_mb": self.disk_free_mb,
            "checked_at": self.checked_at,
            "issues": list(self.issues),
        }


class WorkspaceHealthService:
    """Checks and reports workspace health."""

    async def check_health(self, workspace: ACPWorkspace) -> WorkspaceHealthResult:
        """Check a single workspace's health.

        Checks:
        1. Path existence
        2. Git status (if .git present)
        3. Disk free space
        """
        checked_at = _now_iso()
        issues: list[str] = []
        path = Path(workspace.root_path)

        # 1. Path existence
        path_exists = path.is_dir()
        if not path_exists:
            return WorkspaceHealthResult(
                workspace_id=workspace.id,
                health_status="missing",
                path_exists=False,
                checked_at=checked_at,
                issues=[f"Path does not exist: {workspace.root_path}"],
            )

        # 2. Disk space
        disk_free_mb: int | None = None
        try:
            usage = shutil.disk_usage(workspace.root_path)
            disk_free_mb = int(usage.free / (1024 * 1024))
            if disk_free_mb < _LOW_DISK_THRESHOLD_MB:
                issues.append(f"Low disk space: {disk_free_mb}MB free")
        except OSError as exc:
            issues.append(f"Could not check disk space: {exc}")

        # 3. Git metadata
        git_meta: dict[str, Any] = {
            "git_remote_url": None,
            "git_default_branch": None,
            "git_current_branch": None,
            "git_is_dirty": None,
        }
        git_dir = path / ".git"
        if git_dir.exists():
            try:
                git_meta = await _extract_git_metadata(workspace.root_path)
            except Exception as exc:
                issues.append(f"Git metadata extraction failed: {exc}")

        # Classify health
        if issues:
            health_status = "degraded"
        else:
            health_status = "healthy"

        return WorkspaceHealthResult(
            workspace_id=workspace.id,
            health_status=health_status,
            path_exists=True,
            git_current_branch=git_meta.get("git_current_branch"),
            git_is_dirty=git_meta.get("git_is_dirty"),
            git_remote_url=git_meta.get("git_remote_url"),
            git_default_branch=git_meta.get("git_default_branch"),
            disk_free_mb=disk_free_mb,
            checked_at=checked_at,
            issues=issues,
        )

    async def refresh_all(
        self,
        db: OrchestrationDB,
    ) -> list[WorkspaceHealthResult]:
        """Refresh health for all workspaces of a user and persist results.

        Health checks run concurrently; DB persistence is sequential
        (SQLite is single-writer).
        """
        workspaces = db.list_workspaces()
        if not workspaces:
            return []

        # Run all health checks concurrently
        check_results = await asyncio.gather(
            *(self.check_health(ws) for ws in workspaces)
        )

        # Persist sequentially (SQLite single-writer)
        for result in check_results:
            try:
                db.update_workspace_health(
                    workspace_id=result.workspace_id,
                    health_status=result.health_status,
                    git_remote_url=result.git_remote_url,
                    git_default_branch=result.git_default_branch,
                    git_current_branch=result.git_current_branch,
                    git_is_dirty=result.git_is_dirty,
                    last_health_check=result.checked_at,
                )
            except Exception as exc:
                logger.warning("Failed to persist health for workspace {}: {}", result.workspace_id, exc)

        return list(check_results)
