"""Compatibility shim for the claims engine module."""

from tldw_Server_API.app.core.Claims_Extraction.claims_engine import (
    Claim,
    ClaimExtractor,
    ClaimsEngine,
    ClaimVerification,
    ClaimVerifier,
    Evidence,
    HeuristicSentenceExtractor,
    HybridClaimVerifier,
    LLMBasedClaimExtractor,
)

__all__ = [
    "Claim",
    "ClaimExtractor",
    "ClaimVerifier",
    "ClaimVerification",
    "ClaimsEngine",
    "Evidence",
    "HeuristicSentenceExtractor",
    "HybridClaimVerifier",
    "LLMBasedClaimExtractor",
]
