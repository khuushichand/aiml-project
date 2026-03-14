from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .models import GovernancePack
from .normalize import NormalizedGovernancePackIR, normalize_governance_pack


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass
class GeneratedGovernancePackBundle:
    ir: NormalizedGovernancePackIR
    bundle_json: dict[str, Any]
    digest: str


def build_opa_bundle(pack: GovernancePack) -> GeneratedGovernancePackBundle:
    ir = normalize_governance_pack(pack)
    bundle_json = ir.to_dict()
    digest = hashlib.sha256(_canonical_json(bundle_json).encode("utf-8")).hexdigest()
    return GeneratedGovernancePackBundle(
        ir=ir,
        bundle_json=bundle_json,
        digest=digest,
    )
