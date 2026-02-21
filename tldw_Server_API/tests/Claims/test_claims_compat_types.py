from __future__ import annotations

from tldw_Server_API.app.core.Claims_Extraction import adjudicator, claims_engine, fva_pipeline
from tldw_Server_API.app.core.Claims_Extraction.compat_types import VerificationStatus


def test_verification_status_includes_contested() -> None:
    assert VerificationStatus.CONTESTED.value == "contested"


def test_modules_share_compat_verification_status() -> None:
    assert claims_engine.VerificationStatus is VerificationStatus
    assert adjudicator.VerificationStatus is VerificationStatus
    assert fva_pipeline.VerificationStatus is VerificationStatus
