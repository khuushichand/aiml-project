"""Workspace discovery service.

Scans a directory tree to find candidate workspaces (git repos,
Node.js/Python/Rust/Go projects) and extracts git metadata.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Markers that identify a project root
DEFAULT_MARKERS: list[str] = [
    ".git",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
]


@dataclass
class DiscoveredWorkspace:
    """A candidate workspace found by directory scanning."""
    root_path: str
    name: str
    workspace_type: str = "discovered"
    git_remote_url: str | None = None
    git_default_branch: str | None = None
    git_current_branch: str | None = None
    git_is_dirty: bool | None = None
    markers: list[str] = field(default_factory=list)
    already_registered: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_path": self.root_path,
            "name": self.name,
            "workspace_type": self.workspace_type,
            "git_remote_url": self.git_remote_url,
            "git_default_branch": self.git_default_branch,
            "git_current_branch": self.git_current_branch,
            "git_is_dirty": self.git_is_dirty,
            "markers": list(self.markers),
            "already_registered": self.already_registered,
        }


async def _run_git_command(cwd: str, *args: str) -> str | None:
    """Run a git command and return stdout, or None on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0:
            return stdout.decode().strip()
    except (asyncio.TimeoutError, FileNotFoundError, OSError):
        pass
    return None


async def _extract_git_metadata(
    repo_path: str,
) -> dict[str, Any]:
    """Extract git metadata from a repository directory."""
    result: dict[str, Any] = {
        "git_remote_url": None,
        "git_default_branch": None,
        "git_current_branch": None,
        "git_is_dirty": None,
    }

    remote_url, current_branch, default_branch, porcelain = await asyncio.gather(
        _run_git_command(repo_path, "remote", "get-url", "origin"),
        _run_git_command(repo_path, "rev-parse", "--abbrev-ref", "HEAD"),
        _run_git_command(repo_path, "symbolic-ref", "refs/remotes/origin/HEAD", "--short"),
        _run_git_command(repo_path, "status", "--porcelain"),
        return_exceptions=True,
    )

    if isinstance(remote_url, str):
        result["git_remote_url"] = remote_url
    if isinstance(current_branch, str):
        result["git_current_branch"] = current_branch
    if isinstance(default_branch, str):
        # e.g. "origin/main" → "main"
        result["git_default_branch"] = default_branch.split("/", 1)[-1] if "/" in default_branch else default_branch
    if isinstance(porcelain, str):
        result["git_is_dirty"] = len(porcelain) > 0
    elif porcelain is None:
        # Command succeeded with empty output → clean
        result["git_is_dirty"] = False

    return result


class WorkspaceDiscoveryService:
    """Discovers candidate workspaces by scanning directory trees."""

    async def discover(
        self,
        base_path: str,
        max_depth: int = 3,
        patterns: list[str] | None = None,
        registered_paths: set[str] | None = None,
    ) -> list[DiscoveredWorkspace]:
        """Walk directory tree, identify project roots, extract git metadata.

        Args:
            base_path: Absolute path to start scanning from.
            max_depth: Maximum directory depth to traverse.
            patterns: Marker files/dirs to look for. Defaults to DEFAULT_MARKERS.
            registered_paths: Set of already-registered root_paths for
                ``already_registered`` tagging.

        Returns:
            List of discovered workspace candidates.
        """
        markers = set(patterns or DEFAULT_MARKERS)
        registered = registered_paths or set()
        base = Path(base_path).resolve()

        if not base.is_dir():
            return []

        # Collect candidates synchronously (filesystem I/O is fast for listing)
        candidates = await asyncio.to_thread(
            self._scan_tree, base, markers, max_depth,
        )

        # Extract git metadata concurrently
        results: list[DiscoveredWorkspace] = []
        git_tasks = []
        for path, found_markers in candidates:
            has_git = ".git" in found_markers
            git_tasks.append(
                _extract_git_metadata(str(path)) if has_git else _noop_git()
            )

        git_results = await asyncio.gather(*git_tasks)

        for (path, found_markers), git_meta in zip(candidates, git_results):
            path_str = str(path)
            results.append(DiscoveredWorkspace(
                root_path=path_str,
                name=path.name,
                markers=sorted(found_markers),
                already_registered=path_str in registered,
                **git_meta,
            ))

        results.sort(key=lambda w: w.root_path)
        return results

    @staticmethod
    def _scan_tree(
        base: Path,
        markers: set[str],
        max_depth: int,
    ) -> list[tuple[Path, list[str]]]:
        """Walk a directory tree up to max_depth, collecting marker hits.

        Uses followlinks=False to avoid symlink loops.
        When a directory is identified as a project root (has markers),
        its subtree is still scanned for nested projects (monorepo support).
        """
        candidates: list[tuple[Path, list[str]]] = []

        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            current = Path(dirpath)
            depth = len(current.relative_to(base).parts)
            if depth > max_depth:
                dirnames.clear()
                continue

            # Skip hidden directories (except .git which is a marker)
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") or d in markers
            ]

            # Check for markers
            all_entries = set(dirnames) | set(filenames)
            found = sorted(markers & all_entries)
            if found:
                candidates.append((current, found))

        return candidates


async def _noop_git() -> dict[str, Any]:
    """Return empty git metadata for non-git directories."""
    return {
        "git_remote_url": None,
        "git_default_branch": None,
        "git_current_branch": None,
        "git_is_dirty": None,
    }
