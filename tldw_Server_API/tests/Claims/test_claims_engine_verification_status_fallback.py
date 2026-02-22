from enum import Enum

import pytest

import tldw_Server_API.app.core.Claims_Extraction.claims_engine as claims_engine


@pytest.mark.unit
def test_claim_verification_label_does_not_raise_without_contested_enum(monkeypatch):
    class _FallbackStatus(Enum):
        VERIFIED = "verified"
        CITATION_NOT_FOUND = "citation_not_found"
        MISQUOTED = "misquoted"
        MISLEADING = "misleading"
        HALLUCINATION = "hallucination"
        UNVERIFIED = "unverified"
        NUMERICAL_ERROR = "numerical_error"
        REFUTED = "refuted"

    monkeypatch.setattr(claims_engine, "VerificationStatus", _FallbackStatus)

    verification = claims_engine.ClaimVerification(
        claim=claims_engine.Claim(id="c1", text="A claim"),
        status=_FallbackStatus.UNVERIFIED,
    )
    assert verification.label == "nei"
