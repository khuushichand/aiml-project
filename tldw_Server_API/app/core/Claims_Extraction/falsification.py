"""
falsification.py - Falsification trigger logic for FVA pipeline.

This module implements the decision logic for when to actively seek
counter-evidence (anti-context) for claims during verification.

Inspired by FVA-RAG paper (arXiv:2512.07015).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tldw_Server_API.app.core.Claims_Extraction.claims_engine import Claim

# Import ClaimType - matches existing pattern in claims_engine.py
try:
    from tldw_Server_API.app.core.RAG.rag_service.types import ClaimType
except Exception:
    from enum import Enum as _Enum

    class ClaimType(_Enum):  # type: ignore
        STATISTIC = "statistic"
        COMPARATIVE = "comparative"
        TEMPORAL = "temporal"
        ATTRIBUTION = "attribution"
        CAUSAL = "causal"
        EXISTENCE = "existence"
        RANKING = "ranking"
        QUOTE = "quote"
        GENERAL = "general"


class FalsificationReason(str, Enum):
    """Reason why falsification was triggered for a claim."""

    LOW_CONFIDENCE = "low_confidence"
    HIGH_RISK_TYPE = "high_risk_type"
    CONTROVERSIAL_TOPIC = "controversial_topic"
    WEAK_EVIDENCE = "weak_evidence"
    USER_REQUESTED = "user_requested"


@dataclass
class FalsificationDecision:
    """Decision result from falsification trigger evaluation."""

    should_falsify: bool
    reason: Optional[FalsificationReason]
    priority: int  # 1-10, higher = more urgent to falsify


# Claim types that benefit most from counter-evidence retrieval
HIGH_RISK_CLAIM_TYPES = {
    ClaimType.STATISTIC,
    ClaimType.CAUSAL,
    ClaimType.COMPARATIVE,
    ClaimType.RANKING,
}

# Keywords suggesting controversial or contested domains
CONTROVERSIAL_INDICATORS = [
    "always",
    "never",
    "proven",
    "disproven",
    "consensus",
    "controversial",
    "debated",
    "studies show",
    "research proves",
    "scientists agree",
    "experts say",
    "it is known",
    "undisputed",
    "settled science",
]


def should_trigger_falsification(
    claim: "Claim",
    verification_confidence: float,
    evidence_count: int,
    force_falsification: bool = False,
    confidence_threshold: float = 0.7,
    weak_evidence_threshold: float = 0.85,
) -> FalsificationDecision:
    """
    Decide whether to actively seek counter-evidence for a claim.

    This function implements the falsification trigger logic inspired by
    the FVA-RAG paper. It determines whether a claim warrants additional
    scrutiny via anti-context retrieval.

    Args:
        claim: The claim to evaluate
        verification_confidence: Confidence score from initial verification (0-1)
        evidence_count: Number of evidence snippets found for the claim
        force_falsification: Override to always trigger falsification
        confidence_threshold: Confidence below which to trigger (default 0.7)
        weak_evidence_threshold: Threshold for weak evidence check (default 0.85)

    Returns:
        FalsificationDecision with should_falsify flag, reason, and priority

    Example:
        >>> decision = should_trigger_falsification(
        ...     claim=claim,
        ...     verification_confidence=0.5,
        ...     evidence_count=1,
        ... )
        >>> if decision.should_falsify:
        ...     anti_context = await retrieve_anti_context(claim)
    """
    # User/API explicitly requested falsification
    if force_falsification:
        return FalsificationDecision(
            should_falsify=True,
            reason=FalsificationReason.USER_REQUESTED,
            priority=10,
        )

    # Low confidence verification warrants counter-check
    if verification_confidence < confidence_threshold:
        # Higher priority for lower confidence
        priority = int(10 - verification_confidence * 10)
        return FalsificationDecision(
            should_falsify=True,
            reason=FalsificationReason.LOW_CONFIDENCE,
            priority=max(1, min(10, priority)),
        )

    # High-risk claim types need extra scrutiny
    if claim.claim_type in HIGH_RISK_CLAIM_TYPES:
        return FalsificationDecision(
            should_falsify=True,
            reason=FalsificationReason.HIGH_RISK_TYPE,
            priority=6,
        )

    # Check for controversial language
    claim_lower = claim.text.lower()
    if any(indicator in claim_lower for indicator in CONTROVERSIAL_INDICATORS):
        return FalsificationDecision(
            should_falsify=True,
            reason=FalsificationReason.CONTROVERSIAL_TOPIC,
            priority=5,
        )

    # Weak evidence base - few sources and moderate confidence
    if evidence_count < 2 and verification_confidence < weak_evidence_threshold:
        return FalsificationDecision(
            should_falsify=True,
            reason=FalsificationReason.WEAK_EVIDENCE,
            priority=4,
        )

    # No falsification needed
    return FalsificationDecision(
        should_falsify=False,
        reason=None,
        priority=0,
    )


def estimate_falsification_rate(
    claims: list["Claim"],
    verification_confidences: list[float],
    evidence_counts: list[int],
) -> float:
    """
    Estimate what percentage of claims would trigger falsification.

    Useful for budget estimation before running the full FVA pipeline.

    Args:
        claims: List of claims to evaluate
        verification_confidences: Confidence scores for each claim
        evidence_counts: Evidence counts for each claim

    Returns:
        Estimated falsification rate (0.0 to 1.0)
    """
    if not claims:
        return 0.0

    triggered = 0
    for claim, conf, ev_count in zip(claims, verification_confidences, evidence_counts):
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=conf,
            evidence_count=ev_count,
        )
        if decision.should_falsify:
            triggered += 1

    return triggered / len(claims)
