"""
Backward-compatible wrapper that re-exports claim extraction/verification
from the new ingestion-time claims engine module.
"""

from tldw_Server_API.app.core.Claims_Extraction.claims_engine import (
    Claim,
    Evidence,
    ClaimVerification,
    ClaimExtractor,
    ClaimVerifier,
    HeuristicSentenceExtractor,
    LLMBasedClaimExtractor,
    HybridClaimVerifier,
    ClaimsEngine,
)
