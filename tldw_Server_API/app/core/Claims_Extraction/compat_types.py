"""
Compatibility wrapper for claims verification types.

Prefers canonical RAG type definitions when available and falls back to
lightweight local definitions when claims modules are used without RAG deps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

try:
    from tldw_Server_API.app.core.RAG.rag_service.types import (
        ClaimType,
        Document,
        MatchLevel,
        SourceAuthority,
        VerificationStatus,
    )
except Exception:

    class ClaimType(Enum):  # type: ignore
        STATISTIC = "statistic"
        COMPARATIVE = "comparative"
        TEMPORAL = "temporal"
        ATTRIBUTION = "attribution"
        CAUSAL = "causal"
        EXISTENCE = "existence"
        RANKING = "ranking"
        QUOTE = "quote"
        GENERAL = "general"

    class VerificationStatus(Enum):  # type: ignore
        VERIFIED = "verified"
        CITATION_NOT_FOUND = "citation_not_found"
        MISQUOTED = "misquoted"
        MISLEADING = "misleading"
        HALLUCINATION = "hallucination"
        UNVERIFIED = "unverified"
        NUMERICAL_ERROR = "numerical_error"
        REFUTED = "refuted"
        CONTESTED = "contested"

    class MatchLevel(Enum):  # type: ignore
        EXACT = "exact"
        PARAPHRASE = "paraphrase"
        INTERPRETATION = "interpretation"

    class SourceAuthority(Enum):  # type: ignore
        PRIMARY = 5
        GOVERNMENT = 4
        PEER_REVIEWED = 3
        INDUSTRY = 2
        SECONDARY = 1

    @dataclass
    class Document:  # type: ignore
        id: str
        content: str
        metadata: dict[str, Any] = field(default_factory=dict)
        score: float = 0.0


__all__ = [
    "ClaimType",
    "Document",
    "MatchLevel",
    "SourceAuthority",
    "VerificationStatus",
]
