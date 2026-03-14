from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tldw_Server_API.app.core.MCP_unified.governance_packs.fixtures import (
    load_governance_pack_fixture,
)
from tldw_Server_API.app.core.MCP_unified.governance_packs.normalize import (
    normalize_governance_pack,
)
from tldw_Server_API.app.core.MCP_unified.governance_packs.opa_bundle import (
    build_opa_bundle,
)


def _copy_pack_to_tmp(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parent / "fixtures" / "governance_packs" / "minimal_researcher_pack"
    target = tmp_path / "minimal_researcher_pack"
    shutil.copytree(source, target)
    return target


def _load_snapshot(name: str) -> dict[str, object]:
    snapshot_path = Path(__file__).resolve().parent / "snapshots" / name
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


@pytest.mark.unit
def test_normalized_ir_and_bundle_are_deterministic() -> None:
    pack = load_governance_pack_fixture("minimal_researcher_pack")

    first_ir = normalize_governance_pack(pack)
    second_ir = normalize_governance_pack(pack)
    first_bundle = build_opa_bundle(pack)
    second_bundle = build_opa_bundle(pack)

    assert first_ir.to_dict() == second_ir.to_dict()
    assert first_bundle.digest == second_bundle.digest
    assert first_bundle.bundle_json == second_bundle.bundle_json


@pytest.mark.unit
def test_generated_bundle_matches_snapshot() -> None:
    pack = load_governance_pack_fixture("minimal_researcher_pack")

    bundle = build_opa_bundle(pack)

    assert bundle.bundle_json == _load_snapshot("governance_pack_minimal_bundle.json")


@pytest.mark.unit
def test_bundle_digest_changes_when_pack_changes(tmp_path: Path) -> None:
    original_pack = load_governance_pack_fixture("minimal_researcher_pack")
    pack_dir = _copy_pack_to_tmp(tmp_path)
    profile_path = pack_dir / "profiles" / "researcher.yaml"
    profile_path.write_text(
        "\n".join(
            [
                "profile_id: researcher.profile",
                "name: Researcher",
                "description: Read-oriented research capability profile.",
                "capabilities:",
                "  allow:",
                "    - filesystem.read",
                "    - tool.invoke.research",
                "    - network.external.search",
                "approval_intent: ask",
                "environment_requirements:",
                "  - workspace_bounded_read",
            ]
        ),
        encoding="utf-8",
    )
    updated_pack = load_governance_pack_fixture(pack_dir)

    original_bundle = build_opa_bundle(original_pack)
    updated_bundle = build_opa_bundle(updated_pack)

    assert original_bundle.digest != updated_bundle.digest


@pytest.mark.unit
def test_generated_bundle_excludes_runtime_only_persona_fields() -> None:
    pack = load_governance_pack_fixture("minimal_researcher_pack")

    bundle = build_opa_bundle(pack)
    serialized = json.dumps(bundle.bundle_json, sort_keys=True)

    assert "memory_snapshot" not in serialized
    assert "session_history" not in serialized
