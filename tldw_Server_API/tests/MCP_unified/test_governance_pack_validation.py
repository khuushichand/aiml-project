from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tldw_Server_API.app.core.MCP_unified.governance_packs.fixtures import (
    load_governance_pack_fixture,
)
from tldw_Server_API.app.core.MCP_unified.governance_packs.validation import (
    validate_governance_pack,
)


def _copy_pack_to_tmp(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parent / "fixtures" / "governance_packs" / "minimal_researcher_pack"
    target = tmp_path / "minimal_researcher_pack"
    shutil.copytree(source, target)
    return target


@pytest.mark.unit
def test_validate_minimal_pack() -> None:
    pack = load_governance_pack_fixture("minimal_researcher_pack")

    result = validate_governance_pack(pack)

    assert result.errors == []
    assert result.manifest is not None
    assert result.manifest.pack_id == "researcher-pack"


@pytest.mark.unit
def test_validate_pack_reports_missing_profile_reference(tmp_path: Path) -> None:
    pack_dir = _copy_pack_to_tmp(tmp_path)
    persona_path = pack_dir / "personas" / "researcher.yaml"
    persona_path.write_text(
        "\n".join(
            [
                "persona_template_id: researcher.persona",
                "name: Research Companion",
                "description: Research-oriented persona template.",
                "capability_profile_id: missing.profile",
                "approval_template_id: researcher.ask",
                "persona_traits:",
                "  - researcher",
            ]
        ),
        encoding="utf-8",
    )
    pack = load_governance_pack_fixture(pack_dir)

    result = validate_governance_pack(pack)

    assert "Unknown capability profile reference: missing.profile" in result.errors


@pytest.mark.unit
def test_validate_pack_reports_duplicate_stable_ids(tmp_path: Path) -> None:
    pack_dir = _copy_pack_to_tmp(tmp_path)
    duplicate_profile_path = pack_dir / "profiles" / "duplicate.yaml"
    duplicate_profile_path.write_text(
        "\n".join(
            [
                "profile_id: researcher.profile",
                "name: Duplicate",
                "description: Intentional duplicate id.",
                "capabilities:",
                "  allow:",
                "    - tool.invoke.notes",
                "approval_intent: ask",
                "environment_requirements: []",
            ]
        ),
        encoding="utf-8",
    )
    pack = load_governance_pack_fixture(pack_dir)

    result = validate_governance_pack(pack)

    assert "Duplicate profile_id: researcher.profile" in result.errors


@pytest.mark.unit
def test_validate_pack_reports_unsupported_taxonomy_version(tmp_path: Path) -> None:
    pack_dir = _copy_pack_to_tmp(tmp_path)
    manifest_path = pack_dir / "manifest.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "pack_id: researcher-pack",
                "pack_version: 1.0.0",
                "pack_schema_version: 1",
                "capability_taxonomy_version: 99",
                "adapter_contract_version: 1",
                "title: Researcher Pack",
                "description: Minimal governance pack fixture for validation tests.",
                "authors:",
                "  - codex",
                "compatible_runtime_targets:",
                "  - tldw",
                "  - acp",
            ]
        ),
        encoding="utf-8",
    )
    pack = load_governance_pack_fixture(pack_dir)

    result = validate_governance_pack(pack)

    assert "Unsupported capability_taxonomy_version: 99" in result.errors


@pytest.mark.unit
def test_validate_pack_rejects_runtime_only_persona_fields(tmp_path: Path) -> None:
    pack_dir = _copy_pack_to_tmp(tmp_path)
    persona_path = pack_dir / "personas" / "researcher.yaml"
    persona_path.write_text(
        "\n".join(
            [
                "persona_template_id: researcher.persona",
                "name: Research Companion",
                "description: Research-oriented persona template.",
                "capability_profile_id: researcher.profile",
                "approval_template_id: researcher.ask",
                "persona_traits:",
                "  - researcher",
                "memory_snapshot:",
                "  note: forbidden",
            ]
        ),
        encoding="utf-8",
    )
    pack = load_governance_pack_fixture(pack_dir)

    result = validate_governance_pack(pack)

    assert "Persona template researcher.persona contains runtime-only field: memory_snapshot" in result.errors
