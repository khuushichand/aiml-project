"""
Dynamic Granularity Router for RAG queries.

This module provides automatic selection of retrieval granularity
(document/chunk/passage) based on query type classification.

Design:
- Rule-based classification with embedding heuristics (no LLM calls)
- Query patterns analyzed for broad/specific/factoid intent
- Maps query type to optimal retrieval parameters
"""

import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

from loguru import logger

from .types import QueryType, Granularity


# Patterns for query classification
BROAD_PATTERNS = [
    r"\b(overview|summary|summarize|explain|describe|what is|introduction)\b",
    r"\b(how does .+ work|tell me about|general|overall)\b",
    r"\b(compare|contrast|difference|differences between)\b",
    r"\b(main (idea|point|concept|theme)s?)\b",
    r"\b(in general|broadly|generally speaking)\b",
]

FACTOID_PATTERNS = [
    r"\b(what (year|date|number|percentage|amount|time))\b",
    r"\b(how (much|many|long|often|old))\b",
    r"\b(when did|where is|who (is|was|are|were))\b",
    r"\b(name of|called|known as|defined as)\b",
    r"\b(exact|precisely|specifically|exactly)\b",
    r"\b(the value|the count|the rate|the ratio)\b",
    r"^\s*(what|when|where|who|which)\s+\w+\s*\??\s*$",  # Short wh-questions
]

SPECIFIC_PATTERNS = [
    r"\b(how (to|do|can|should|would))\b",
    r"\b(step[s]?|procedure|process|method)\b",
    r"\b(implement|configure|setup|install)\b",
    r"\b(example|code|snippet|sample)\b",
    r"\b(detail[s]?|specific[s]?|particular)\b",
    r"\b(section|chapter|part|paragraph)\b",
]


@dataclass
class GranularityDecision:
    """Result of granularity routing decision."""
    query_type: QueryType
    granularity: Granularity
    confidence: float
    reasoning: str
    retrieval_params: Dict[str, Any]


class GranularityRouter:
    """
    Routes queries to appropriate retrieval granularity based on query classification.

    Uses lightweight rule-based classification with optional embedding heuristics.
    No LLM calls for low latency.
    """

    def __init__(
        self,
        broad_patterns: Optional[List[str]] = None,
        factoid_patterns: Optional[List[str]] = None,
        specific_patterns: Optional[List[str]] = None,
        enable_length_heuristic: bool = True,
        short_query_threshold: int = 8,  # words
        long_query_threshold: int = 25,  # words
    ):
        """
        Initialize the granularity router.

        Args:
            broad_patterns: Regex patterns indicating broad/overview queries
            factoid_patterns: Regex patterns indicating factoid queries
            specific_patterns: Regex patterns indicating specific/detail queries
            enable_length_heuristic: Use query length as additional signal
            short_query_threshold: Word count below which queries lean factoid
            long_query_threshold: Word count above which queries lean broad
        """
        self.broad_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (broad_patterns or BROAD_PATTERNS)
        ]
        self.factoid_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (factoid_patterns or FACTOID_PATTERNS)
        ]
        self.specific_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (specific_patterns or SPECIFIC_PATTERNS)
        ]
        self.enable_length_heuristic = enable_length_heuristic
        self.short_query_threshold = short_query_threshold
        self.long_query_threshold = long_query_threshold

    def classify_query(self, query: str) -> Tuple[QueryType, float, str]:
        """
        Classify a query into broad/specific/factoid categories.

        Args:
            query: The search query

        Returns:
            Tuple of (QueryType, confidence, reasoning)
        """
        if not query or not query.strip():
            return QueryType.SPECIFIC, 0.5, "Empty query defaults to specific"

        query_lower = query.lower().strip()
        word_count = len(query.split())

        # Score each category
        scores = {
            QueryType.BROAD: 0.0,
            QueryType.SPECIFIC: 0.0,
            QueryType.FACTOID: 0.0,
        }
        reasons = []

        # Pattern matching
        for pattern in self.broad_patterns:
            if pattern.search(query_lower):
                scores[QueryType.BROAD] += 1.0
                reasons.append(f"Broad pattern: {pattern.pattern[:30]}")

        for pattern in self.factoid_patterns:
            if pattern.search(query_lower):
                scores[QueryType.FACTOID] += 1.0
                reasons.append(f"Factoid pattern: {pattern.pattern[:30]}")

        for pattern in self.specific_patterns:
            if pattern.search(query_lower):
                scores[QueryType.SPECIFIC] += 1.0
                reasons.append(f"Specific pattern: {pattern.pattern[:30]}")

        # Length heuristics
        if self.enable_length_heuristic:
            if word_count <= self.short_query_threshold:
                scores[QueryType.FACTOID] += 0.3
                reasons.append(f"Short query ({word_count} words)")
            elif word_count >= self.long_query_threshold:
                scores[QueryType.BROAD] += 0.3
                reasons.append(f"Long query ({word_count} words)")
            else:
                scores[QueryType.SPECIFIC] += 0.2
                reasons.append(f"Medium query ({word_count} words)")

        # Question word analysis
        if query_lower.startswith(("what", "when", "where", "who", "which")):
            if "?" in query and word_count <= 10:
                scores[QueryType.FACTOID] += 0.5
                reasons.append("Short wh-question")
            else:
                scores[QueryType.SPECIFIC] += 0.2
        elif query_lower.startswith("how"):
            if "how to" in query_lower or "how do" in query_lower:
                scores[QueryType.SPECIFIC] += 0.5
                reasons.append("How-to query")
            elif "how much" in query_lower or "how many" in query_lower:
                scores[QueryType.FACTOID] += 0.5
                reasons.append("Quantitative how-query")
            else:
                scores[QueryType.BROAD] += 0.3
                reasons.append("Explanatory how-query")
        elif query_lower.startswith("why"):
            scores[QueryType.BROAD] += 0.4
            reasons.append("Why-query (explanatory)")

        # Find winner
        max_score = max(scores.values())
        if max_score == 0:
            # No patterns matched, default to specific
            return QueryType.SPECIFIC, 0.5, "Default to specific (no patterns matched)"

        # Normalize confidence
        total_score = sum(scores.values())
        winner = max(scores, key=scores.get)
        confidence = scores[winner] / total_score if total_score > 0 else 0.5

        reasoning = "; ".join(reasons[:3]) if reasons else "Pattern match"

        return winner, confidence, reasoning

    def select_granularity(self, query_type: QueryType) -> Granularity:
        """
        Map query type to retrieval granularity.

        Args:
            query_type: The classified query type

        Returns:
            Appropriate granularity level
        """
        mapping = {
            QueryType.BROAD: Granularity.DOCUMENT,
            QueryType.SPECIFIC: Granularity.CHUNK,
            QueryType.FACTOID: Granularity.PASSAGE,
        }
        return mapping.get(query_type, Granularity.CHUNK)

    def get_retrieval_params(self, granularity: Granularity) -> Dict[str, Any]:
        """
        Get retrieval parameters for a given granularity level.

        Args:
            granularity: The granularity level

        Returns:
            Dictionary of retrieval parameters
        """
        if granularity == Granularity.DOCUMENT:
            return {
                "top_k": 5,
                "fts_level": "media",
                "enable_parent_expansion": True,
                "parent_context_size": 1000,
                "include_parent_document": True,
                "parent_max_tokens": 2000,
                "chunk_type_filter": None,  # All types
                "enable_multi_vector_passages": False,
            }
        elif granularity == Granularity.PASSAGE:
            return {
                "top_k": 15,
                "fts_level": "chunk",
                "enable_parent_expansion": False,
                "parent_context_size": 200,
                "include_parent_document": False,
                "chunk_type_filter": None,
                "enable_multi_vector_passages": True,
                "mv_span_chars": 200,
                "mv_stride": 100,
                "mv_max_spans": 10,
            }
        else:  # CHUNK (default)
            return {
                "top_k": 10,
                "fts_level": "chunk",
                "enable_parent_expansion": False,
                "parent_context_size": 500,
                "include_parent_document": False,
                "chunk_type_filter": None,
                "enable_multi_vector_passages": False,
            }

    def route(self, query: str) -> GranularityDecision:
        """
        Route a query to the appropriate granularity with full decision info.

        Args:
            query: The search query

        Returns:
            GranularityDecision with all routing information
        """
        query_type, confidence, reasoning = self.classify_query(query)
        granularity = self.select_granularity(query_type)
        retrieval_params = self.get_retrieval_params(granularity)

        logger.debug(
            f"Granularity routing: query_type={query_type.value}, "
            f"granularity={granularity.value}, confidence={confidence:.2f}"
        )

        return GranularityDecision(
            query_type=query_type,
            granularity=granularity,
            confidence=confidence,
            reasoning=reasoning,
            retrieval_params=retrieval_params,
        )


# Module-level singleton for convenience
_default_router: Optional[GranularityRouter] = None


def get_granularity_router() -> GranularityRouter:
    """Get or create the default granularity router singleton."""
    global _default_router
    if _default_router is None:
        _default_router = GranularityRouter()
    return _default_router


def route_query_granularity(query: str) -> GranularityDecision:
    """
    Convenience function to route a query using the default router.

    Args:
        query: The search query

    Returns:
        GranularityDecision with routing information
    """
    return get_granularity_router().route(query)
