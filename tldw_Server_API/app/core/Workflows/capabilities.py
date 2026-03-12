"""Workflow step replay and evidence capabilities.

This registry is intentionally small and stable. Execution and diagnostics code
uses it to decide whether reruns are safe by default and how much evidence to
capture for a given step type.
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass


@dataclass(frozen=True)
class StepCapability:
    """Static replay, compensation, and evidence characteristics for a step type."""

    replay_safe: bool = False
    idempotency_strategy: str = "none"
    compensation_supported: bool = False
    requires_human_review_for_rerun: bool = False
    evidence_level: str = "standard"

    def to_dict(self) -> dict[str, bool | str]:
        return asdict(self)


_DEFAULT_CAPABILITY = StepCapability()

_CAPABILITY_OVERRIDES: dict[str, StepCapability] = {
    "prompt": StepCapability(
        replay_safe=True,
        idempotency_strategy="run_scoped",
        compensation_supported=False,
        requires_human_review_for_rerun=False,
        evidence_level="standard",
    ),
    "rag_search": StepCapability(
        replay_safe=True,
        idempotency_strategy="run_scoped",
        compensation_supported=False,
        requires_human_review_for_rerun=False,
        evidence_level="standard",
    ),
    "delay": StepCapability(
        replay_safe=True,
        idempotency_strategy="run_scoped",
        compensation_supported=False,
        requires_human_review_for_rerun=False,
        evidence_level="minimal",
    ),
    "log": StepCapability(
        replay_safe=True,
        idempotency_strategy="run_scoped",
        compensation_supported=False,
        requires_human_review_for_rerun=False,
        evidence_level="minimal",
    ),
    "branch": StepCapability(
        replay_safe=True,
        idempotency_strategy="run_scoped",
        compensation_supported=False,
        requires_human_review_for_rerun=False,
        evidence_level="standard",
    ),
    "webhook": StepCapability(
        replay_safe=False,
        idempotency_strategy="external",
        compensation_supported=False,
        requires_human_review_for_rerun=True,
        evidence_level="detailed",
    ),
    "notify": StepCapability(
        replay_safe=False,
        idempotency_strategy="external",
        compensation_supported=False,
        requires_human_review_for_rerun=True,
        evidence_level="detailed",
    ),
    "mcp_tool": StepCapability(
        replay_safe=False,
        idempotency_strategy="external",
        compensation_supported=False,
        requires_human_review_for_rerun=True,
        evidence_level="detailed",
    ),
    "kanban": StepCapability(
        replay_safe=False,
        idempotency_strategy="external",
        compensation_supported=True,
        requires_human_review_for_rerun=True,
        evidence_level="detailed",
    ),
    "media_ingest": StepCapability(
        replay_safe=False,
        idempotency_strategy="asset_scoped",
        compensation_supported=False,
        requires_human_review_for_rerun=True,
        evidence_level="detailed",
    ),
}


def get_step_capability(step_type: str) -> StepCapability:
    """Return the normalized capability record for a step type.

    Unknown or blank step types intentionally fall back to the default unsafe
    capability so new adapters do not become replay-safe implicitly.
    """

    normalized = str(step_type or "").strip()
    if not normalized:
        return _DEFAULT_CAPABILITY
    return _CAPABILITY_OVERRIDES.get(normalized, _DEFAULT_CAPABILITY)
