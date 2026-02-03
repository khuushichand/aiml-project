"""
verification_report.py - Structured verification reports for machine-readable audit.

This module provides dataclasses and utilities for generating structured
JSON reports from claim verification results.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    from tldw_Server_API.app.core.RAG.rag_service.types import (
        ClaimType,
        MatchLevel,
        SourceAuthority,
        VerificationStatus,
    )
except Exception:
    from enum import Enum

    class ClaimType(Enum):  # type: ignore
        GENERAL = "general"

    class VerificationStatus(Enum):  # type: ignore
        VERIFIED = "verified"
        UNVERIFIED = "unverified"

    class MatchLevel(Enum):  # type: ignore
        EXACT = "exact"

    class SourceAuthority(Enum):  # type: ignore
        SECONDARY = 1


def _enum_to_str(val: Any) -> str:
    """Convert enum or value to string, handling various input types."""
    if hasattr(val, "value"):
        v = val.value
        return str(v) if not isinstance(v, str) else v
    return str(val)


@dataclass
class EvidenceReport:
    """Evidence snippet in a verification report."""
    doc_id: str
    snippet: str
    score: float
    authority: str
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass
class ClaimReport:
    """Individual claim report within a verification report."""
    claim_id: str
    claim_text: str
    claim_type: str
    status: str
    confidence: float
    match_level: str
    source_authority: str
    requires_external_knowledge: bool
    rationale: str | None
    evidence: list[EvidenceReport] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type,
            "status": self.status,
            "confidence": self.confidence,
            "match_level": self.match_level,
            "source_authority": self.source_authority,
            "requires_external_knowledge": self.requires_external_knowledge,
            "rationale": self.rationale,
            "evidence": [asdict(e) for e in self.evidence],
            "citations": self.citations,
        }


@dataclass
class VerificationReport:
    """
    Structured verification report for machine-readable audit.

    Provides a complete summary of claim verification results including
    per-claim details, aggregate statistics, and metadata.
    """
    report_id: str
    generated_at: str
    query: str | None
    answer_text: str | None
    total_claims: int
    verified_count: int
    refuted_count: int
    unverified_count: int
    hallucination_count: int
    numerical_error_count: int
    misquoted_count: int
    citation_not_found_count: int
    verification_rate: float
    precision: float
    coverage: float
    claims: list[ClaimReport] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_verification_result(
        cls,
        verifications: list[Any],
        query: str | None = None,
        answer_text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "VerificationReport":
        """
        Create a VerificationReport from a list of ClaimVerification objects.

        Args:
            verifications: List of ClaimVerification objects
            query: Original query (optional)
            answer_text: Original answer text (optional)
            metadata: Additional metadata (optional)

        Returns:
            VerificationReport instance
        """
        report_id = str(uuid.uuid4())
        generated_at = datetime.now(timezone.utc).isoformat()

        total = len(verifications)
        verified = 0
        refuted = 0
        unverified = 0
        hallucination = 0
        numerical_error = 0
        misquoted = 0
        citation_not_found = 0
        claim_reports: list[ClaimReport] = []

        for v in verifications:
            status = getattr(v, "status", None)
            if status is None:
                # Fallback for old-style label
                label = getattr(v, "label", "nei")
                if label == "supported":
                    status = VerificationStatus.VERIFIED
                    verified += 1
                elif label == "refuted":
                    status = VerificationStatus.REFUTED
                    refuted += 1
                else:
                    status = VerificationStatus.UNVERIFIED
                    unverified += 1
            else:
                if status == VerificationStatus.VERIFIED:
                    verified += 1
                elif status == VerificationStatus.REFUTED:
                    refuted += 1
                elif status == VerificationStatus.HALLUCINATION:
                    hallucination += 1
                elif status == VerificationStatus.NUMERICAL_ERROR:
                    numerical_error += 1
                elif status == VerificationStatus.MISQUOTED:
                    misquoted += 1
                elif status == VerificationStatus.CITATION_NOT_FOUND:
                    citation_not_found += 1
                else:
                    unverified += 1

            # Build evidence reports
            evidence_reports = []
            for e in getattr(v, "evidence", []):
                auth = getattr(e, "authority", SourceAuthority.SECONDARY)
                evidence_reports.append(EvidenceReport(
                    doc_id=getattr(e, "doc_id", ""),
                    snippet=getattr(e, "snippet", ""),
                    score=getattr(e, "score", 0.0),
                    authority=_enum_to_str(auth),
                ))

            claim = getattr(v, "claim", None)
            claim_type = getattr(claim, "claim_type", ClaimType.GENERAL) if claim else ClaimType.GENERAL
            match_level = getattr(v, "match_level", MatchLevel.EXACT)
            source_auth = getattr(v, "source_authority", SourceAuthority.SECONDARY)

            claim_reports.append(ClaimReport(
                claim_id=getattr(claim, "id", "") if claim else "",
                claim_text=getattr(claim, "text", "") if claim else "",
                claim_type=_enum_to_str(claim_type),
                status=_enum_to_str(status),
                confidence=getattr(v, "confidence", 0.0),
                match_level=_enum_to_str(match_level),
                source_authority=_enum_to_str(source_auth),
                requires_external_knowledge=getattr(v, "requires_external_knowledge", False),
                rationale=getattr(v, "rationale", None),
                evidence=evidence_reports,
                citations=getattr(v, "citations", []),
            ))

        # Calculate metrics
        precision = verified / total if total > 0 else 0.0
        coverage = (verified + refuted) / total if total > 0 else 0.0
        verification_rate = verified / total if total > 0 else 0.0

        return cls(
            report_id=report_id,
            generated_at=generated_at,
            query=query,
            answer_text=answer_text,
            total_claims=total,
            verified_count=verified,
            refuted_count=refuted,
            unverified_count=unverified,
            hallucination_count=hallucination,
            numerical_error_count=numerical_error,
            misquoted_count=misquoted,
            citation_not_found_count=citation_not_found,
            verification_rate=verification_rate,
            precision=precision,
            coverage=coverage,
            claims=claim_reports,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "query": self.query,
            "answer_text": self.answer_text,
            "total_claims": self.total_claims,
            "verified_count": self.verified_count,
            "refuted_count": self.refuted_count,
            "unverified_count": self.unverified_count,
            "hallucination_count": self.hallucination_count,
            "numerical_error_count": self.numerical_error_count,
            "misquoted_count": self.misquoted_count,
            "citation_not_found_count": self.citation_not_found_count,
            "verification_rate": self.verification_rate,
            "precision": self.precision,
            "coverage": self.coverage,
            "claims": [c.to_dict() for c in self.claims],
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the verification report."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "total_claims": self.total_claims,
            "verified_count": self.verified_count,
            "refuted_count": self.refuted_count,
            "unverified_count": self.unverified_count,
            "hallucination_count": self.hallucination_count,
            "citation_not_found_count": self.citation_not_found_count,
            "verification_rate": self.verification_rate,
            "precision": self.precision,
            "coverage": self.coverage,
        }

    def get_problematic_claims(self) -> list[ClaimReport]:
        """Get claims that have issues (not verified)."""
        problematic_statuses = {
            "refuted", "hallucination", "numerical_error", "misquoted", "citation_not_found"
        }
        return [c for c in self.claims if c.status in problematic_statuses]

    def get_claims_by_status(self, status: str) -> list[ClaimReport]:
        """Get claims filtered by status."""
        return [c for c in self.claims if c.status == status]

    def get_claims_requiring_external_knowledge(self) -> list[ClaimReport]:
        """Get claims that require external knowledge to verify."""
        return [c for c in self.claims if c.requires_external_knowledge]


def generate_verification_report(
    verifications: list[Any],
    query: str | None = None,
    answer_text: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> VerificationReport:
    """
    Generate a structured verification report from verification results.

    Args:
        verifications: List of ClaimVerification objects
        query: Original query (optional)
        answer_text: Original answer text (optional)
        metadata: Additional metadata (optional)

    Returns:
        VerificationReport instance
    """
    return VerificationReport.from_verification_result(
        verifications=verifications,
        query=query,
        answer_text=answer_text,
        metadata=metadata,
    )
