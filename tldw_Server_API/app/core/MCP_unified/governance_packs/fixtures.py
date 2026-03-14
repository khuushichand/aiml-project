from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import (
    ApprovalTemplate,
    AssignmentTemplate,
    CapabilityProfile,
    GovernancePack,
    GovernancePackManifest,
    PersonaTemplate,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _fixture_root() -> Path:
    return _repo_root() / "tldw_Server_API" / "tests" / "MCP_unified" / "fixtures" / "governance_packs"


def _load_yaml_file(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in {path}")
    return loaded


def _load_yaml_directory(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    documents: list[dict[str, Any]] = []
    for file_path in sorted(
        candidate
        for candidate in path.iterdir()
        if candidate.is_file() and candidate.suffix.lower() in {".yaml", ".yml"}
    ):
        documents.append(_load_yaml_file(file_path))
    return documents


def load_governance_pack_fixture(name_or_path: str | Path) -> GovernancePack:
    """Load a governance-pack fixture directory by fixture name or explicit path."""
    candidate_path = Path(name_or_path)
    pack_path = candidate_path if candidate_path.exists() else _fixture_root() / str(name_or_path)

    manifest = GovernancePackManifest(**_load_yaml_file(pack_path / "manifest.yaml"))
    raw_profiles = _load_yaml_directory(pack_path / "profiles")
    raw_approvals = _load_yaml_directory(pack_path / "approvals")
    raw_personas = _load_yaml_directory(pack_path / "personas")
    raw_assignments = _load_yaml_directory(pack_path / "assignments")

    return GovernancePack(
        source_path=pack_path,
        manifest=manifest,
        profiles=[CapabilityProfile(**item) for item in raw_profiles],
        approvals=[ApprovalTemplate(**item) for item in raw_approvals],
        personas=[PersonaTemplate(**item) for item in raw_personas],
        assignments=[AssignmentTemplate(**item) for item in raw_assignments],
        raw_profiles=raw_profiles,
        raw_approvals=raw_approvals,
        raw_personas=raw_personas,
        raw_assignments=raw_assignments,
    )
