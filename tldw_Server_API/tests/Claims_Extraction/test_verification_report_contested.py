"""
Tests for CONTESTED status handling in verification reports.

These tests verify that the CONTESTED verification status is properly
handled throughout the verification report generation and serialization.
"""

import pytest
from dataclasses import dataclass, field
from typing import Any

from tldw_Server_API.app.core.Claims_Extraction.verification_report import (
    VerificationReport,
    ClaimReport,
    EvidenceReport,
    generate_verification_report,
)

# Import VerificationStatus
try:
    from tldw_Server_API.app.core.RAG.rag_service.types import (
        VerificationStatus,
        ClaimType,
        MatchLevel,
        SourceAuthority,
    )
except Exception:
    from enum import Enum

    class VerificationStatus(Enum):
        VERIFIED = "verified"
        REFUTED = "refuted"
        UNVERIFIED = "unverified"
        CONTESTED = "contested"
        HALLUCINATION = "hallucination"

    class ClaimType(Enum):
        GENERAL = "general"

    class MatchLevel(Enum):
        EXACT = "exact"

    class SourceAuthority(Enum):
        SECONDARY = 1


@dataclass
class MockClaim:
    """Mock claim for testing."""
    id: str
    text: str
    claim_type: ClaimType = ClaimType.GENERAL


@dataclass
class MockEvidence:
    """Mock evidence for testing."""
    doc_id: str
    snippet: str
    score: float = 0.8
    authority: SourceAuthority = SourceAuthority.SECONDARY


@dataclass
class MockClaimVerification:
    """Mock claim verification for testing."""
    claim: MockClaim
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = 0.5
    evidence: list = field(default_factory=list)
    citations: list = field(default_factory=list)
    rationale: str = None
    match_level: MatchLevel = MatchLevel.EXACT
    source_authority: SourceAuthority = SourceAuthority.SECONDARY
    requires_external_knowledge: bool = False


class TestContestedStatusInReport:
    """Tests for CONTESTED status handling in VerificationReport."""

    @pytest.mark.unit
    def test_contested_status_counted(self):
        """CONTESTED claims should be counted in contested_count."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Claim 1"),
                status=VerificationStatus.VERIFIED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="2", text="Claim 2"),
                status=VerificationStatus.CONTESTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="3", text="Claim 3"),
                status=VerificationStatus.CONTESTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="4", text="Claim 4"),
                status=VerificationStatus.REFUTED,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)

        assert report.total_claims == 4
        assert report.verified_count == 1
        assert report.contested_count == 2
        assert report.refuted_count == 1
        assert report.unverified_count == 0

    @pytest.mark.unit
    def test_contested_in_to_dict(self):
        """contested_count should be included in to_dict() output."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Claim 1"),
                status=VerificationStatus.CONTESTED,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)
        report_dict = report.to_dict()

        assert "contested_count" in report_dict
        assert report_dict["contested_count"] == 1

    @pytest.mark.unit
    def test_contested_in_get_summary(self):
        """contested_count should be included in get_summary() output."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Claim 1"),
                status=VerificationStatus.CONTESTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="2", text="Claim 2"),
                status=VerificationStatus.VERIFIED,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)
        summary = report.get_summary()

        assert "contested_count" in summary
        assert summary["contested_count"] == 1

    @pytest.mark.unit
    def test_contested_in_json(self):
        """contested_count should be included in JSON output."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Claim 1"),
                status=VerificationStatus.CONTESTED,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)
        json_str = report.to_json()

        assert "contested_count" in json_str
        assert '"contested_count": 1' in json_str

    @pytest.mark.unit
    def test_get_contested_claims(self):
        """get_contested_claims() should return only contested claims."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Verified claim"),
                status=VerificationStatus.VERIFIED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="2", text="Contested claim 1"),
                status=VerificationStatus.CONTESTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="3", text="Contested claim 2"),
                status=VerificationStatus.CONTESTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="4", text="Refuted claim"),
                status=VerificationStatus.REFUTED,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)
        contested_claims = report.get_contested_claims()

        assert len(contested_claims) == 2
        assert all(c.status == "contested" for c in contested_claims)

    @pytest.mark.unit
    def test_get_problematic_claims_excludes_contested_by_default(self):
        """get_problematic_claims() should exclude contested by default."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Contested claim"),
                status=VerificationStatus.CONTESTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="2", text="Refuted claim"),
                status=VerificationStatus.REFUTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="3", text="Hallucination"),
                status=VerificationStatus.HALLUCINATION,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)
        problematic = report.get_problematic_claims()

        assert len(problematic) == 2
        assert all(c.status != "contested" for c in problematic)

    @pytest.mark.unit
    def test_get_problematic_claims_includes_contested_when_requested(self):
        """get_problematic_claims(include_contested=True) should include contested."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Contested claim"),
                status=VerificationStatus.CONTESTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="2", text="Refuted claim"),
                status=VerificationStatus.REFUTED,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)
        problematic = report.get_problematic_claims(include_contested=True)

        assert len(problematic) == 2
        statuses = {c.status for c in problematic}
        assert "contested" in statuses
        assert "refuted" in statuses

    @pytest.mark.unit
    def test_get_claims_by_status_contested(self):
        """get_claims_by_status('contested') should work correctly."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Contested claim"),
                status=VerificationStatus.CONTESTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="2", text="Verified claim"),
                status=VerificationStatus.VERIFIED,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)
        contested = report.get_claims_by_status("contested")

        assert len(contested) == 1
        assert contested[0].status == "contested"


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with existing code."""

    @pytest.mark.unit
    def test_report_without_contested_defaults_to_zero(self):
        """Reports with no contested claims should have contested_count=0."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Verified"),
                status=VerificationStatus.VERIFIED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="2", text="Refuted"),
                status=VerificationStatus.REFUTED,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)

        assert report.contested_count == 0

    @pytest.mark.unit
    def test_empty_verifications_list(self):
        """Empty verifications should produce valid report with all zeros."""
        report = VerificationReport.from_verification_result([])

        assert report.total_claims == 0
        assert report.verified_count == 0
        assert report.contested_count == 0
        assert report.refuted_count == 0
        assert report.unverified_count == 0

    @pytest.mark.unit
    def test_coverage_excludes_contested(self):
        """Coverage metric should only count verified + refuted, not contested."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Verified"),
                status=VerificationStatus.VERIFIED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="2", text="Refuted"),
                status=VerificationStatus.REFUTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="3", text="Contested"),
                status=VerificationStatus.CONTESTED,
            ),
            MockClaimVerification(
                claim=MockClaim(id="4", text="Unverified"),
                status=VerificationStatus.UNVERIFIED,
            ),
        ]

        report = VerificationReport.from_verification_result(verifications)

        # Coverage = (verified + refuted) / total = 2/4 = 0.5
        assert report.coverage == 0.5


class TestGenerateVerificationReportHelper:
    """Tests for generate_verification_report helper function."""

    @pytest.mark.unit
    def test_generate_report_with_contested(self):
        """generate_verification_report should handle contested status."""
        verifications = [
            MockClaimVerification(
                claim=MockClaim(id="1", text="Contested"),
                status=VerificationStatus.CONTESTED,
            ),
        ]

        report = generate_verification_report(
            verifications=verifications,
            query="Test query",
            answer_text="Test answer",
        )

        assert report.contested_count == 1
        assert report.query == "Test query"
        assert report.answer_text == "Test answer"
