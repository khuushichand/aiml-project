from __future__ import annotations

from collections import Counter

from .models import GovernancePack, GovernancePackValidationResult

SUPPORTED_CAPABILITY_TAXONOMY_VERSIONS = {1}
RUNTIME_ONLY_PERSONA_FIELDS = {
    "memory_snapshot",
    "session_history",
    "live_state",
    "workspace_history",
}


def _collect_duplicates(documents: list[dict[str, object]], key: str) -> list[str]:
    values = [str(item.get(key) or "").strip() for item in documents if str(item.get(key) or "").strip()]
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def validate_governance_pack(pack: GovernancePack) -> GovernancePackValidationResult:
    """Validate a schema-first governance pack and return collected structural errors."""
    errors: list[str] = []
    manifest = pack.manifest

    if manifest.capability_taxonomy_version not in SUPPORTED_CAPABILITY_TAXONOMY_VERSIONS:
        errors.append(f"Unsupported capability_taxonomy_version: {manifest.capability_taxonomy_version}")

    for duplicate in _collect_duplicates(pack.raw_profiles, "profile_id"):
        errors.append(f"Duplicate profile_id: {duplicate}")
    for duplicate in _collect_duplicates(pack.raw_approvals, "approval_template_id"):
        errors.append(f"Duplicate approval_template_id: {duplicate}")
    for duplicate in _collect_duplicates(pack.raw_personas, "persona_template_id"):
        errors.append(f"Duplicate persona_template_id: {duplicate}")
    for duplicate in _collect_duplicates(pack.raw_assignments, "assignment_template_id"):
        errors.append(f"Duplicate assignment_template_id: {duplicate}")

    profile_ids = {profile.profile_id for profile in pack.profiles}
    approval_ids = {approval.approval_template_id for approval in pack.approvals}
    persona_ids = {persona.persona_template_id for persona in pack.personas}

    for raw_persona, persona in zip(pack.raw_personas, pack.personas, strict=False):
        if persona.capability_profile_id not in profile_ids:
            errors.append(f"Unknown capability profile reference: {persona.capability_profile_id}")
        if persona.approval_template_id not in approval_ids:
            errors.append(f"Unknown approval template reference: {persona.approval_template_id}")

        for field_name in sorted(RUNTIME_ONLY_PERSONA_FIELDS.intersection(raw_persona.keys())):
            errors.append(
                f"Persona template {persona.persona_template_id} contains runtime-only field: {field_name}"
            )

    for assignment in pack.assignments:
        if assignment.capability_profile_id not in profile_ids:
            errors.append(f"Unknown capability profile reference: {assignment.capability_profile_id}")
        if assignment.persona_template_id and assignment.persona_template_id not in persona_ids:
            errors.append(f"Unknown persona template reference: {assignment.persona_template_id}")
        if assignment.approval_template_id and assignment.approval_template_id not in approval_ids:
            errors.append(f"Unknown approval template reference: {assignment.approval_template_id}")

    return GovernancePackValidationResult(
        manifest=manifest,
        errors=errors,
    )
