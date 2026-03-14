from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.MCP_unified.governance_packs import (
    ApprovalTemplate,
    AssignmentTemplate,
    CapabilityProfile,
    GovernancePack,
    GovernancePackManifest,
    PersonaTemplate,
    build_opa_bundle,
    normalize_governance_pack,
    validate_governance_pack,
)

_RUNTIME_APPROVAL_MODE_MAP = {
    "allow": "allow_silently",
    "ask": "ask_every_time",
}
_SUPPORTED_PORTABLE_CAPABILITIES = {
    "filesystem.read",
    "filesystem.write",
    "mcp.server.connect",
    "network.external.fetch",
    "network.external.search",
    "process.execute.safe",
    "tool.invoke.code_edit",
    "tool.invoke.research",
}
_SUPPORTED_ENVIRONMENT_REQUIREMENTS = {
    "local_mapping_required",
    "no_external_secrets",
    "workspace_bounded_read",
    "workspace_bounded_write",
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


class GovernancePackDryRunReport(BaseModel):
    manifest: dict[str, Any] = Field(default_factory=dict)
    digest: str
    resolved_capabilities: list[str] = Field(default_factory=list)
    unresolved_capabilities: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocked_objects: list[str] = Field(default_factory=list)
    verdict: str


class McpHubGovernancePackService:
    """Materialize schema-first governance packs into immutable MCP Hub base objects."""

    def __init__(self, repo: McpHubRepo):
        self.repo = repo

    @staticmethod
    def build_pack_from_document(document: dict[str, Any]) -> GovernancePack:
        payload = dict(document or {})
        return GovernancePack(
            source_path=Path("<api>"),
            manifest=GovernancePackManifest.model_validate(payload.get("manifest") or {}),
            profiles=[
                CapabilityProfile.model_validate(item)
                for item in payload.get("profiles") or []
            ],
            approvals=[
                ApprovalTemplate.model_validate(item)
                for item in payload.get("approvals") or []
            ],
            personas=[
                PersonaTemplate.model_validate(item)
                for item in payload.get("personas") or []
            ],
            assignments=[
                AssignmentTemplate.model_validate(item)
                for item in payload.get("assignments") or []
            ],
            raw_profiles=[dict(item) for item in payload.get("profiles") or []],
            raw_approvals=[dict(item) for item in payload.get("approvals") or []],
            raw_personas=[dict(item) for item in payload.get("personas") or []],
            raw_assignments=[dict(item) for item in payload.get("assignments") or []],
        )

    async def dry_run_pack(
        self,
        *,
        pack: GovernancePack,
        owner_scope_type: str,
        owner_scope_id: int | None,
    ) -> GovernancePackDryRunReport:
        del owner_scope_type, owner_scope_id

        validation = validate_governance_pack(pack)
        if validation.errors:
            raise ValueError("; ".join(validation.errors))

        bundle = build_opa_bundle(pack)
        resolved_capabilities: list[str] = []
        unresolved_capabilities: list[str] = []
        warnings: list[str] = []
        blocked_objects: list[str] = []

        for profile in pack.profiles:
            for capability in list(profile.capabilities.allow) + list(profile.capabilities.deny):
                capability_value = str(capability or "").strip()
                if not capability_value:
                    continue
                if capability_value in _SUPPORTED_PORTABLE_CAPABILITIES:
                    if capability_value not in resolved_capabilities:
                        resolved_capabilities.append(capability_value)
                elif capability_value not in unresolved_capabilities:
                    unresolved_capabilities.append(capability_value)
            for requirement in profile.environment_requirements:
                requirement_value = str(requirement or "").strip()
                if requirement_value and requirement_value not in _SUPPORTED_ENVIRONMENT_REQUIREMENTS:
                    warnings.append(
                        f"profile:{profile.profile_id} uses unsupported environment requirement '{requirement_value}'"
                    )

        for approval in pack.approvals:
            if str(approval.mode or "").strip().lower() not in _RUNTIME_APPROVAL_MODE_MAP:
                blocked_objects.append(f"approval_template:{approval.approval_template_id}")
                warnings.append(
                    f"approval template '{approval.approval_template_id}' cannot map to a local runtime approval mode"
                )

        verdict = "importable"
        if unresolved_capabilities or blocked_objects:
            verdict = "blocked"

        return GovernancePackDryRunReport(
            manifest={
                "pack_id": pack.manifest.pack_id,
                "pack_version": pack.manifest.pack_version,
                "title": pack.manifest.title,
                "description": pack.manifest.description,
            },
            digest=bundle.digest,
            resolved_capabilities=resolved_capabilities,
            unresolved_capabilities=unresolved_capabilities,
            warnings=warnings,
            blocked_objects=blocked_objects,
            verdict=verdict,
        )

    async def dry_run_pack_document(
        self,
        *,
        document: dict[str, Any],
        owner_scope_type: str,
        owner_scope_id: int | None,
    ) -> GovernancePackDryRunReport:
        pack = self.build_pack_from_document(document)
        return await self.dry_run_pack(
            pack=pack,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )

    async def import_pack_document(
        self,
        *,
        document: dict[str, Any],
        owner_scope_type: str,
        owner_scope_id: int | None,
        actor_id: int | None,
    ) -> dict[str, Any]:
        pack = self.build_pack_from_document(document)
        report = await self.dry_run_pack(
            pack=pack,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )
        if report.verdict != "importable":
            raise ValueError("Governance pack dry-run did not pass")
        imported = await self.import_pack(
            pack=pack,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            actor_id=actor_id,
        )
        return {
            "governance_pack_id": imported.governance_pack_id,
            "imported_object_counts": dict(imported.imported_object_counts),
            "blocked_objects": list(imported.blocked_objects),
            "report": report.model_dump(),
        }

    async def list_governance_packs(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repo.list_governance_packs(
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )

    async def get_governance_pack_detail(self, governance_pack_id: int) -> dict[str, Any] | None:
        pack_row = await self.repo.get_governance_pack(governance_pack_id)
        if pack_row is None:
            return None
        return {
            **pack_row,
            "imported_objects": await self.repo.list_governance_pack_objects(governance_pack_id),
        }

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
