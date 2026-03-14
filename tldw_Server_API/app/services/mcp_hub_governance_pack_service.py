from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.MCP_unified.governance_packs import (
    GovernancePack,
    build_opa_bundle,
    normalize_governance_pack,
    validate_governance_pack,
)

_RUNTIME_APPROVAL_MODE_MAP = {
    "allow": "allow_silently",
    "ask": "ask_every_time",
}


def _dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


def _imported_name(display_name: str, *, pack_id: str, source_object_id: str) -> str:
    return f"{display_name} [{pack_id}:{source_object_id}]"


class GovernancePackImportResult(BaseModel):
    governance_pack_id: int
    imported_object_ids: dict[str, list[int]] = Field(default_factory=dict)
    imported_object_counts: dict[str, int] = Field(default_factory=dict)
    blocked_objects: list[str] = Field(default_factory=list)


class McpHubGovernancePackService:
    """Materialize schema-first governance packs into immutable MCP Hub base objects."""

    def __init__(self, repo: McpHubRepo):
        self.repo = repo

    async def import_pack(
        self,
        *,
        pack: GovernancePack,
        owner_scope_type: str,
        owner_scope_id: int | None,
        actor_id: int | None,
    ) -> GovernancePackImportResult:
        validation = validate_governance_pack(pack)
        if validation.errors:
            raise ValueError("; ".join(validation.errors))

        normalized_ir = normalize_governance_pack(pack)
        bundle = build_opa_bundle(pack)
        manifest = pack.manifest
        pack_row = await self.repo.create_governance_pack(
            pack_id=manifest.pack_id,
            pack_version=manifest.pack_version,
            pack_schema_version=manifest.pack_schema_version,
            capability_taxonomy_version=manifest.capability_taxonomy_version,
            adapter_contract_version=manifest.adapter_contract_version,
            title=manifest.title,
            description=manifest.description,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            bundle_digest=bundle.digest,
            manifest=_dump_model(manifest),
            normalized_ir=normalized_ir.to_dict(),
            actor_id=actor_id,
        )
        if not pack_row:
            raise RuntimeError("Failed to persist governance pack manifest")

        blocked_objects: list[str] = []
        imported_object_ids: dict[str, list[int]] = {
            "approval_policies": [],
            "permission_profiles": [],
            "policy_assignments": [],
        }
        approval_policy_ids_by_template: dict[str, int] = {}
        profile_ids_by_template: dict[str, int] = {}
        persona_ids_by_template: dict[str, str] = {
            persona.persona_template_id: persona.persona_template_id
            for persona in pack.personas
        }
        persona_approval_ids: dict[str, str] = {
            persona.persona_template_id: persona.approval_template_id
            for persona in pack.personas
        }

        for approval in pack.approvals:
            runtime_mode = _RUNTIME_APPROVAL_MODE_MAP.get(str(approval.mode or "").strip().lower())
            if runtime_mode is None:
                blocked_objects.append(f"approval_template:{approval.approval_template_id}")
                continue
            created = await self.repo.create_approval_policy(
                name=_imported_name(
                    approval.name,
                    pack_id=manifest.pack_id,
                    source_object_id=approval.approval_template_id,
                ),
                owner_scope_type=owner_scope_type,
                owner_scope_id=owner_scope_id,
                mode=runtime_mode,
                rules={
                    "portable_mode": approval.mode,
                    "approval_template_id": approval.approval_template_id,
                    "governance_pack": {
                        "pack_id": manifest.pack_id,
                        "pack_version": manifest.pack_version,
                        "source_object_id": approval.approval_template_id,
                    },
                },
                actor_id=actor_id,
                description=approval.name,
                is_active=True,
                is_immutable=True,
            )
            approval_id = int(created["id"])
            approval_policy_ids_by_template[approval.approval_template_id] = approval_id
            imported_object_ids["approval_policies"].append(approval_id)
            await self.repo.create_governance_pack_object(
                governance_pack_id=int(pack_row["id"]),
                object_type="approval_policy",
                object_id=approval_id,
                source_object_id=approval.approval_template_id,
            )

        for profile in pack.profiles:
            created = await self.repo.create_permission_profile(
                name=_imported_name(
                    profile.name,
                    pack_id=manifest.pack_id,
                    source_object_id=profile.profile_id,
                ),
                owner_scope_type=owner_scope_type,
                owner_scope_id=owner_scope_id,
                mode="preset",
                policy_document={
                    "capabilities": list(profile.capabilities.allow),
                    "denied_capabilities": list(profile.capabilities.deny),
                    "environment_requirements": list(profile.environment_requirements),
                    "approval_intent": profile.approval_intent,
                    "governance_pack": {
                        "pack_id": manifest.pack_id,
                        "pack_version": manifest.pack_version,
                        "source_object_id": profile.profile_id,
                    },
                },
                actor_id=actor_id,
                description=profile.description,
                is_active=True,
                is_immutable=True,
            )
            profile_id = int(created["id"])
            profile_ids_by_template[profile.profile_id] = profile_id
            imported_object_ids["permission_profiles"].append(profile_id)
            await self.repo.create_governance_pack_object(
                governance_pack_id=int(pack_row["id"]),
                object_type="permission_profile",
                object_id=profile_id,
                source_object_id=profile.profile_id,
            )

        for assignment in pack.assignments:
            profile_id = profile_ids_by_template.get(assignment.capability_profile_id)
            if profile_id is None:
                blocked_objects.append(f"assignment_template:{assignment.assignment_template_id}")
                continue

            approval_template_id = assignment.approval_template_id
            if approval_template_id is None and assignment.persona_template_id is not None:
                approval_template_id = persona_approval_ids.get(assignment.persona_template_id)
            approval_policy_id = (
                approval_policy_ids_by_template.get(approval_template_id)
                if approval_template_id is not None
                else None
            )
            if approval_template_id is not None and approval_policy_id is None:
                blocked_objects.append(f"assignment_template:{assignment.assignment_template_id}")
                continue

            target_id = None
            if assignment.target_type == "persona" and assignment.persona_template_id is not None:
                target_id = persona_ids_by_template.get(assignment.persona_template_id)

            created = await self.repo.create_policy_assignment(
                target_type=assignment.target_type,
                target_id=target_id,
                owner_scope_type=owner_scope_type,
                owner_scope_id=owner_scope_id,
                profile_id=profile_id,
                inline_policy_document={
                    "persona_template_id": assignment.persona_template_id,
                    "approval_template_id": approval_template_id,
                    "capability_profile_id": assignment.capability_profile_id,
                    "governance_pack": {
                        "pack_id": manifest.pack_id,
                        "pack_version": manifest.pack_version,
                        "source_object_id": assignment.assignment_template_id,
                    },
                },
                approval_policy_id=approval_policy_id,
                actor_id=actor_id,
                is_active=True,
                is_immutable=True,
            )
            assignment_id = int(created["id"])
            imported_object_ids["policy_assignments"].append(assignment_id)
            await self.repo.create_governance_pack_object(
                governance_pack_id=int(pack_row["id"]),
                object_type="policy_assignment",
                object_id=assignment_id,
                source_object_id=assignment.assignment_template_id,
            )

        return GovernancePackImportResult(
            governance_pack_id=int(pack_row["id"]),
            imported_object_ids=imported_object_ids,
            imported_object_counts={
                key: len(value) for key, value in imported_object_ids.items()
            },
            blocked_objects=blocked_objects,
        )
