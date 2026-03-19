"""Tests for workspace discovery service."""
from __future__ import annotations

import asyncio
import os

import pytest

from tldw_Server_API.app.services.workspace_discovery_service import (
    DiscoveredWorkspace,
    WorkspaceDiscoveryService,
    _extract_git_metadata,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def svc():
    return WorkspaceDiscoveryService()


@pytest.fixture
def mock_tree(tmp_path):
    """Create a mock directory tree with various project types."""
    # Git repo with package.json (Node.js project)
    node_project = tmp_path / "my-app"
    node_project.mkdir()
    (node_project / ".git").mkdir()
    (node_project / "package.json").write_text("{}")

    # Python project
    py_project = tmp_path / "my-lib"
    py_project.mkdir()
    (py_project / ".git").mkdir()
    (py_project / "pyproject.toml").write_text("[project]\nname='my-lib'")

    # Rust project (nested deeper)
    nested = tmp_path / "repos" / "rust-tool"
    nested.mkdir(parents=True)
    (nested / "Cargo.toml").write_text("[package]\nname='rust-tool'")

    # Non-project directory (should not be discovered)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("# Hello")

    # Hidden directory (should be skipped)
    hidden = tmp_path / ".config"
    hidden.mkdir()
    (hidden / "package.json").write_text("{}")

    return tmp_path


async def test_discover_finds_projects(svc, mock_tree):
    """Discovery should find projects with markers."""
    results = await svc.discover(str(mock_tree), max_depth=3)
    root_paths = {r.root_path for r in results}
    assert str(mock_tree / "my-app") in root_paths
    assert str(mock_tree / "my-lib") in root_paths
    assert str(mock_tree / "repos" / "rust-tool") in root_paths


async def test_discover_skips_non_projects(svc, mock_tree):
    """Directories without markers should not be discovered."""
    results = await svc.discover(str(mock_tree), max_depth=3)
    root_paths = {r.root_path for r in results}
    assert str(mock_tree / "docs") not in root_paths


async def test_discover_skips_hidden_dirs(svc, mock_tree):
    """Hidden directories should be skipped."""
    results = await svc.discover(str(mock_tree), max_depth=3)
    root_paths = {r.root_path for r in results}
    assert str(mock_tree / ".config") not in root_paths


async def test_discover_respects_depth_limit(svc, tmp_path):
    """Depth limit should prevent deep traversal."""
    # Create project at depth 5
    deep = tmp_path / "a" / "b" / "c" / "d" / "deep-project"
    deep.mkdir(parents=True)
    (deep / "package.json").write_text("{}")

    results = await svc.discover(str(tmp_path), max_depth=2)
    root_paths = {r.root_path for r in results}
    assert str(deep) not in root_paths


async def test_discover_markers_returned(svc, mock_tree):
    """Discovered workspaces should list which markers were found."""
    results = await svc.discover(str(mock_tree), max_depth=3)
    node = next(r for r in results if "my-app" in r.root_path)
    assert ".git" in node.markers
    assert "package.json" in node.markers


async def test_discover_custom_patterns(svc, tmp_path):
    """Custom patterns should override defaults."""
    project = tmp_path / "my-project"
    project.mkdir()
    (project / "Makefile").write_text("all:")

    results = await svc.discover(str(tmp_path), patterns=["Makefile"])
    assert len(results) == 1
    assert results[0].markers == ["Makefile"]


async def test_discover_already_registered(svc, mock_tree):
    """Already-registered paths should be flagged."""
    node_path = str(mock_tree / "my-app")
    results = await svc.discover(
        str(mock_tree),
        max_depth=3,
        registered_paths={node_path},
    )
    node = next(r for r in results if r.root_path == node_path)
    assert node.already_registered is True
    # Others should not be registered
    others = [r for r in results if r.root_path != node_path]
    assert all(not r.already_registered for r in others)


async def test_discover_empty_dir(svc, tmp_path):
    """Empty directory should return no results."""
    results = await svc.discover(str(tmp_path))
    assert results == []


async def test_discover_nonexistent_path(svc):
    """Non-existent path should return empty list."""
    results = await svc.discover("/this/path/does/not/exist")
    assert results == []


async def test_discover_workspace_type(svc, mock_tree):
    """All discovered workspaces should have type 'discovered'."""
    results = await svc.discover(str(mock_tree), max_depth=3)
    assert all(r.workspace_type == "discovered" for r in results)


async def test_discover_name_from_dirname(svc, mock_tree):
    """Workspace name should be derived from directory name."""
    results = await svc.discover(str(mock_tree), max_depth=3)
    node = next(r for r in results if "my-app" in r.root_path)
    assert node.name == "my-app"


async def test_discovered_workspace_to_dict(svc, mock_tree):
    """to_dict should include all fields."""
    results = await svc.discover(str(mock_tree), max_depth=3)
    d = results[0].to_dict()
    assert "root_path" in d
    assert "name" in d
    assert "markers" in d
    assert "already_registered" in d
    assert "workspace_type" in d


# ---------------------------------------------------------------------------
# Git metadata extraction
# ---------------------------------------------------------------------------


async def test_extract_git_metadata_non_repo(tmp_path):
    """Non-git directory should return None values."""
    meta = await _extract_git_metadata(str(tmp_path))
    assert meta["git_remote_url"] is None
    assert meta["git_current_branch"] is None
