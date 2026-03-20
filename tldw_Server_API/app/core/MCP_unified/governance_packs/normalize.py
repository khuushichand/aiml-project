from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import GovernancePack


def _dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


@dataclass
class NormalizedGovernancePackIR:
    manifest: dict[str, Any]
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "data": self.data,
        }


def normalize_governance_pack(pack: GovernancePack) -> NormalizedGovernancePackIR:
    profiles = sorted(
        (_dump_model(profile) for profile in pack.profiles),
        key=lambda item: str(item.get("profile_id") or ""),
    )
    approvals = sorted(
        (_dump_model(approval) for approval in pack.approvals),
        key=lambda item: str(item.get("approval_template_id") or ""),
    )
    personas = sorted(
        (_dump_model(persona) for persona in pack.personas),
        key=lambda item: str(item.get("persona_template_id") or ""),
    )
    assignments = sorted(
        (_dump_model(assignment) for assignment in pack.assignments),
        key=lambda item: str(item.get("assignment_template_id") or ""),
    )

    return NormalizedGovernancePackIR(
        manifest=_dump_model(pack.manifest),
        data={
            "profiles": profiles,
            "approvals": approvals,
            "personas": personas,
            "assignments": assignments,
        },
    )
