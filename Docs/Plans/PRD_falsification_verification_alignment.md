# PRD: Falsification-Verification Alignment (FVA) for Claims Module

## Overview

This PRD describes enhancements to the existing claims verification system inspired by the FVA-RAG paper (arXiv:2512.07015). The core insight is that **actively seeking contradicting evidence** (falsification) alongside verification significantly reduces sycophantic hallucinations and improves claim reliability.

### Problem Statement

The current verification pipeline validates claims against retrieved documents but operates in a **confirmation-seeking** mode. It answers: "Does evidence support this claim?" but does not ask: "Does evidence contradict this claim?"

This asymmetry can lead to:
- False confidence in weakly-supported claims
- Missed contradictions in the source corpus
- Over-reliance on retrieval quality for the original query

### Proposed Solution

Implement a **dual-process verification system** that:
1. Performs standard verification (existing)
2. Actively retrieves "anti-context" (contradicting evidence) for uncertain or high-risk claims
3. Adjudicates between supporting and contradicting evidence
4. Surfaces "contested" claims where legitimate disagreement exists

### Reference

- **Paper**: "FVA-RAG: Falsification-Verification Alignment for Mitigating Sycophantic Hallucinations"
- **Authors**: Mayank Ravishankara
- **Key Result**: ~80% accuracy on TruthfulQA-Generation, outperforming Self-RAG and CRAG (p < 10⁻⁶)
- **Falsification Rate**: 24.5-29.3% of queries triggered counter-evidence retrieval

---

## Goals

| Goal | Metric | Target |
|------|--------|--------|
| Reduce false-positive verifications | Claims marked VERIFIED that have contradicting evidence | < 5% |
| Surface contested claims | Claims with both supporting and refuting evidence identified | New capability |
| Targeted falsification | Avoid unnecessary anti-retrieval overhead | 20-30% of claims trigger falsification |
| Maintain performance | P95 latency for standard verification path | < 10% regression |

### Non-Goals

- Replacing the existing verification pipeline (this extends it)
- External fact-checking APIs (use internal corpus only)
- Real-time falsification for streaming responses (batch/post-generation only)

---

## User Stories

1. **As a researcher**, I want the system to tell me when a claim has contradicting evidence in my corpus, so I don't unknowingly cite disputed facts.

2. **As a content reviewer**, I want to see "contested" claims flagged separately from "verified" and "refuted" claims, so I can prioritize human review.

3. **As a system operator**, I want falsification to trigger selectively (not on every claim), so verification costs remain predictable.

---

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claims Verification Pipeline                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌───────────────────┐    ┌──────────────┐  │
│  │   Extract    │───▶│  Standard Verify  │───▶│   Classify   │  │
│  │   Claims     │    │  (existing)       │    │   Results    │  │
│  └──────────────┘    └───────────────────┘    └──────┬───────┘  │
│                                                       │          │
│                              ┌────────────────────────┘          │
│                              ▼                                   │
│                      ┌───────────────┐                           │
│                      │  Falsification │  (triggered for          │
│                      │    Trigger?    │   uncertain/high-risk)   │
│                      └───────┬───────┘                           │
│                              │ yes                               │
│                              ▼                                   │
│  ┌──────────────┐    ┌───────────────────┐    ┌──────────────┐  │
│  │ Anti-Context │───▶│   Adjudicate      │───▶│    Final     │  │
│  │  Retrieval   │    │   (NLI + LLM)     │    │   Verdict    │  │
│  └──────────────┘    └───────────────────┘    └──────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Details

#### 1. New Verification Status: `CONTESTED`

**File**: `tldw_Server_API/app/core/RAG/rag_service/types.py`

```python
class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    REFUTED = "refuted"
    UNVERIFIED = "unverified"
    HALLUCINATION = "hallucination"
    NUMERICAL_ERROR = "numerical_error"
    MISQUOTED = "misquoted"
    CITATION_NOT_FOUND = "citation_not_found"
    MISLEADING = "misleading"
    CONTESTED = "contested"  # NEW: Evidence exists both for and against
```

**Semantics**: A claim is `CONTESTED` when:
- Supporting evidence exists with confidence ≥ 0.6
- Contradicting evidence also exists with confidence ≥ 0.5
- Neither clearly dominates (support/contradict ratio between 0.4-0.6)

**Required Updates to Existing Code**:

1. Update `ClaimVerification.label` property in `claims_engine.py`:
```python
@property
def label(self) -> str:
    status_to_label = {
        VerificationStatus.VERIFIED: "supported",
        VerificationStatus.REFUTED: "refuted",
        VerificationStatus.CONTESTED: "contested",  # ADD THIS
        # ... rest unchanged
    }
    return status_to_label.get(self.status, "nei")
```

2. Update `VerificationReport` in `verification_report.py` (see Stage 1 checklist).

#### 2. Falsification Trigger Logic

**File**: `tldw_Server_API/app/core/Claims_Extraction/falsification.py` (new)

```python
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

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
        CAUSAL = "causal"
        RANKING = "ranking"
        GENERAL = "general"


class FalsificationReason(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    HIGH_RISK_TYPE = "high_risk_type"
    CONTROVERSIAL_TOPIC = "controversial_topic"
    WEAK_EVIDENCE = "weak_evidence"
    USER_REQUESTED = "user_requested"


@dataclass
class FalsificationDecision:
    should_falsify: bool
    reason: Optional[FalsificationReason]
    priority: int  # 1-10, higher = more urgent


# Claim types that benefit most from counter-evidence retrieval
HIGH_RISK_CLAIM_TYPES = {
    ClaimType.STATISTIC,
    ClaimType.CAUSAL,
    ClaimType.COMPARATIVE,
    ClaimType.RANKING,
}

# Keywords suggesting controversial or contested domains
CONTROVERSIAL_INDICATORS = [
    "always", "never", "proven", "disproven", "consensus",
    "controversial", "debated", "studies show", "research proves",
]


def should_trigger_falsification(
    claim: "Claim",
    verification_confidence: float,
    evidence_count: int,
    force_falsification: bool = False,
) -> FalsificationDecision:
    """
    Decide whether to actively seek counter-evidence for a claim.

    Args:
        claim: The claim to evaluate
        verification_confidence: Confidence score from initial verification (0-1)
        evidence_count: Number of evidence snippets found
        force_falsification: Override to always trigger

    Returns:
        FalsificationDecision with reasoning
    """
    if force_falsification:
        return FalsificationDecision(True, FalsificationReason.USER_REQUESTED, 10)

    # Low confidence verification warrants counter-check
    if verification_confidence < 0.7:
        priority = int(10 - verification_confidence * 10)
        return FalsificationDecision(True, FalsificationReason.LOW_CONFIDENCE, priority)

    # High-risk claim types need extra scrutiny
    if claim.claim_type in HIGH_RISK_CLAIM_TYPES:
        return FalsificationDecision(True, FalsificationReason.HIGH_RISK_TYPE, 6)

    # Check for controversial language
    claim_lower = claim.text.lower()
    if any(indicator in claim_lower for indicator in CONTROVERSIAL_INDICATORS):
        return FalsificationDecision(True, FalsificationReason.CONTROVERSIAL_TOPIC, 5)

    # Weak evidence base
    if evidence_count < 2 and verification_confidence < 0.85:
        return FalsificationDecision(True, FalsificationReason.WEAK_EVIDENCE, 4)

    return FalsificationDecision(False, None, 0)
```

#### 3. Anti-Context Retrieval

**File**: `tldw_Server_API/app/core/Claims_Extraction/anti_context_retriever.py` (new)

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from tldw_Server_API.app.core.Claims_Extraction.claims_engine import Claim
    from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MultiDatabaseRetriever

# Import Document - matches existing pattern
try:
    from tldw_Server_API.app.core.RAG.rag_service.types import Document
except Exception:
    from dataclasses import dataclass as _dc
    @_dc
    class Document:  # type: ignore
        id: str
        content: str
        metadata: Dict[str, Any] = field(default_factory=dict)
        score: float = 0.0


@dataclass
class AntiContextConfig:
    """Configuration for anti-context retrieval."""
    max_queries: int = 3
    max_docs_per_query: int = 5
    min_relevance_score: float = 0.3
    exclude_original_doc_ids: bool = True
    use_negation_templates: bool = True
    use_antonym_expansion: bool = True
    max_docs_per_source: int = 2  # Diversity: limit docs from same source
    cache_ttl_seconds: int = 300  # Query result caching


@dataclass
class AntiContextResult:
    """Result from a single anti-context query."""
    query_used: str
    documents: List[Document]
    strategy: str  # negation | antonym | contrary


# Templates for generating negation queries
NEGATION_TEMPLATES = [
    "evidence against {claim}",
    "contradicts {claim}",
    "disproves {claim}",
    "counterarguments to {claim}",
    "studies refuting {claim}",
    "criticism of {claim}",
    "problems with {claim}",
]

# Domain-specific contrary templates
CONTRARY_TEMPLATES = {
    "statistic": [
        "different statistics for {topic}",
        "conflicting data on {topic}",
    ],
    "causal": [
        "alternative causes of {effect}",
        "factors besides {cause} that affect {effect}",
    ],
    "comparative": [
        "{item_b} better than {item_a}",
        "advantages of {item_b} over {item_a}",
    ],
}


class AntiContextRetriever:
    """
    Retrieves documents that may contradict a given claim.
    Inspired by FVA-RAG's anti-context retrieval strategy.
    """

    def __init__(
        self,
        retriever: "MultiDatabaseRetriever",
        config: Optional[AntiContextConfig] = None,
    ):
        """
        Initialize the anti-context retriever.

        Args:
            retriever: MultiDatabaseRetriever instance for searching
            config: Configuration options
        """
        self.retriever = retriever
        self.config = config or AntiContextConfig()
        self._query_cache: Dict[str, List[Document]] = {}

    async def retrieve_anti_context(
        self,
        claim: "Claim",
        original_doc_ids: Set[str],
        user_id: Optional[str] = None,
        search_mode: str = "hybrid",
    ) -> List[AntiContextResult]:
        """
        Generate negation/contrary queries and retrieve potential counter-evidence.

        Args:
            claim: The claim to find counter-evidence for
            original_doc_ids: Document IDs from original retrieval to exclude
            user_id: User ID for scoped retrieval
            search_mode: Retrieval mode (hybrid, fts, vector)

        Returns:
            List of AntiContextResult with retrieved documents
        """
        results = []
        seen_doc_ids = set(original_doc_ids) if self.config.exclude_original_doc_ids else set()

        # Generate queries
        queries = self._generate_anti_queries(claim)

        for query, strategy in queries[:self.config.max_queries]:
            # Check cache
            cache_key = f"{query}:{user_id}:{search_mode}"
            if cache_key in self._query_cache:
                docs = self._query_cache[cache_key]
            else:
                # Use actual retriever interface (MultiDatabaseRetriever.retrieve)
                try:
                    docs = await self.retriever.retrieve(
                        query=query,
                        top_k=self.config.max_docs_per_query,
                        search_mode=search_mode,
                    )
                    self._query_cache[cache_key] = docs
                except Exception as e:
                    logger.warning(f"Anti-context retrieval failed for query '{query[:50]}...': {e}")
                    continue

            # Filter by minimum score
            docs = [d for d in docs if d.score >= self.config.min_relevance_score]

            # Filter already-seen documents
            new_docs = [d for d in docs if d.id not in seen_doc_ids]
            seen_doc_ids.update(d.id for d in new_docs)

            # Apply source diversity
            new_docs = self._diversify_by_source(new_docs)

            if new_docs:
                results.append(AntiContextResult(
                    query_used=query,
                    documents=new_docs,
                    strategy=strategy,
                ))

        return results

    def _generate_anti_queries(self, claim: "Claim") -> List[tuple]:
        """Generate queries designed to find contradicting evidence."""
        queries: List[tuple] = []

        # Standard negation templates
        if self.config.use_negation_templates:
            for template in NEGATION_TEMPLATES[:3]:
                queries.append((
                    template.format(claim=claim.text),
                    "negation",
                ))

        # Claim-type specific contrary queries
        claim_type_key = claim.claim_type.value if claim.claim_type else None
        if claim_type_key and claim_type_key in CONTRARY_TEMPLATES:
            for template in CONTRARY_TEMPLATES[claim_type_key][:2]:
                filled = self._fill_contrary_template(template, claim)
                if filled:
                    queries.append((filled, "contrary"))

        return queries

    def _fill_contrary_template(self, template: str, claim: "Claim") -> Optional[str]:
        """Fill contrary template with extracted claim entities."""
        # Use extracted_values (plural) from claim if available
        if claim.extracted_values:
            try:
                return template.format(
                    topic=claim.text[:50],
                    claim=claim.text,
                    **claim.extracted_values,
                )
            except KeyError:
                pass
        return template.format(topic=claim.text[:50], claim=claim.text)

    def _diversify_by_source(self, docs: List[Document]) -> List[Document]:
        """Ensure diversity by limiting docs per source."""
        source_counts: Dict[str, int] = {}
        diverse_docs = []

        for doc in sorted(docs, key=lambda d: d.score, reverse=True):
            source_id = doc.metadata.get("media_id", doc.id)
            if source_counts.get(source_id, 0) < self.config.max_docs_per_source:
                diverse_docs.append(doc)
                source_counts[source_id] = source_counts.get(source_id, 0) + 1

        return diverse_docs

    def clear_cache(self) -> None:
        """Clear the query result cache."""
        self._query_cache.clear()
```

#### 4. Adjudicator (Evidence Weighing)

**File**: `tldw_Server_API/app/core/Claims_Extraction/adjudicator.py` (new)

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from enum import Enum

from loguru import logger

if TYPE_CHECKING:
    from tldw_Server_API.app.core.Claims_Extraction.claims_engine import Claim, ClaimVerification

# Import types - matches existing pattern
try:
    from tldw_Server_API.app.core.RAG.rag_service.types import (
        Document,
        VerificationStatus,
    )
except Exception:
    from enum import Enum as _Enum
    from dataclasses import dataclass as _dc

    class VerificationStatus(_Enum):  # type: ignore
        VERIFIED = "verified"
        REFUTED = "refuted"
        CONTESTED = "contested"
        UNVERIFIED = "unverified"

    @_dc
    class Document:  # type: ignore
        id: str
        content: str
        metadata: Dict[str, Any] = field(default_factory=dict)
        score: float = 0.0


class EvidenceStance(str, Enum):
    """Stance of evidence toward a claim."""
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


@dataclass
class EvidenceAssessment:
    """Assessment of a single document's stance toward a claim."""
    document: Document
    stance: EvidenceStance
    confidence: float
    rationale: Optional[str] = None  # Use 'rationale' to match existing ClaimVerification


@dataclass
class AdjudicationResult:
    """Result of adjudicating between supporting and contradicting evidence."""
    final_status: VerificationStatus
    support_score: float  # 0-1
    contradict_score: float  # 0-1
    supporting_evidence: List[EvidenceAssessment]
    contradicting_evidence: List[EvidenceAssessment]
    adjudication_rationale: str  # Use 'rationale' to match existing pattern
    contestation_score: float = 0.0  # 0 = one-sided, 1 = perfectly balanced

    def __post_init__(self):
        """Calculate contestation score after initialization."""
        total = self.support_score + self.contradict_score
        if total > 0:
            ratio = min(self.support_score, self.contradict_score) / max(self.support_score, self.contradict_score)
            self.contestation_score = ratio
        else:
            self.contestation_score = 0.0


class ClaimAdjudicator:
    """
    Weighs supporting vs contradicting evidence to reach a final verdict.
    """

    def __init__(
        self,
        nli_pipeline: Optional[Any] = None,
        llm_analyze_fn: Optional[Any] = None,
        contested_threshold: float = 0.4,
    ):
        """
        Initialize the adjudicator.

        Args:
            nli_pipeline: Transformers NLI pipeline (from claims_engine)
            llm_analyze_fn: LLM analyze function for fallback
            contested_threshold: Ratio threshold for CONTESTED status (0.4 means 40-60% split)
        """
        self.nli_pipeline = nli_pipeline
        self.llm_analyze_fn = llm_analyze_fn
        self.contested_threshold = contested_threshold

    async def adjudicate(
        self,
        claim: "Claim",
        supporting_docs: List[Document],
        contradicting_docs: List[Document],
        original_verification: "ClaimVerification",
    ) -> AdjudicationResult:
        """
        Given both supporting and potentially contradicting documents,
        determine final verification status.

        Args:
            claim: The claim being adjudicated
            supporting_docs: Documents from original retrieval
            contradicting_docs: Documents from anti-context retrieval
            original_verification: Initial verification result

        Returns:
            AdjudicationResult with final status and evidence assessments
        """
        # Assess stance of each document
        support_assessments = await self._assess_documents(
            claim, supporting_docs, expected_stance=EvidenceStance.SUPPORTS
        )
        contradict_assessments = await self._assess_documents(
            claim, contradicting_docs, expected_stance=EvidenceStance.CONTRADICTS
        )

        # Calculate aggregate scores
        support_score = self._aggregate_score(
            [a for a in support_assessments if a.stance == EvidenceStance.SUPPORTS]
        )
        contradict_score = self._aggregate_score(
            [a for a in contradict_assessments if a.stance == EvidenceStance.CONTRADICTS]
        )

        # Determine final status
        final_status, rationale = self._determine_status(
            support_score,
            contradict_score,
            original_verification,
        )

        return AdjudicationResult(
            final_status=final_status,
            support_score=support_score,
            contradict_score=contradict_score,
            supporting_evidence=[a for a in support_assessments if a.stance == EvidenceStance.SUPPORTS],
            contradicting_evidence=[a for a in contradict_assessments if a.stance == EvidenceStance.CONTRADICTS],
            adjudication_rationale=rationale,
        )

    async def _assess_documents(
        self,
        claim: "Claim",
        documents: List[Document],
        expected_stance: EvidenceStance,
    ) -> List[EvidenceAssessment]:
        """Assess each document's actual stance toward the claim."""
        assessments = []

        for doc in documents:
            try:
                # Use NLI pipeline if available (matches claims_engine pattern)
                if self.nli_pipeline:
                    stance, confidence = await self._nli_assess(claim.text, doc.content)
                elif self.llm_analyze_fn:
                    stance, confidence = await self._llm_assess(claim.text, doc.content)
                else:
                    # No model available - assume expected stance with low confidence
                    stance = expected_stance
                    confidence = 0.5

                assessments.append(EvidenceAssessment(
                    document=doc,
                    stance=stance,
                    confidence=confidence,
                ))
            except Exception as e:
                logger.warning(f"Failed to assess document {doc.id}: {e}")
                continue

        return assessments

    async def _nli_assess(self, claim: str, evidence: str) -> tuple:
        """
        Use NLI pipeline to assess evidence stance.
        Matches the transformers pipeline interface used in claims_engine.py.
        """
        import asyncio

        # Format for transformers NLI: "premise </s></s> hypothesis"
        # Truncate to avoid token limits
        evidence_truncated = evidence[:1000] if len(evidence) > 1000 else evidence
        input_text = f"{evidence_truncated} </s></s> {claim}"

        # Run in executor since transformers is sync
        loop = asyncio.get_event_loop()
        try:
            results = await loop.run_in_executor(None, lambda: self.nli_pipeline(input_text))
        except Exception as e:
            logger.warning(f"NLI assessment failed: {e}")
            return EvidenceStance.NEUTRAL, 0.5

        # results is [[{label, score}, ...]] - extract scores
        if not results or not results[0]:
            return EvidenceStance.NEUTRAL, 0.5

        scores = {r["label"].lower(): r["score"] for r in results[0]}

        entailment = scores.get("entailment", 0)
        contradiction = scores.get("contradiction", 0)
        neutral = scores.get("neutral", 0)

        if entailment > contradiction and entailment > neutral:
            return EvidenceStance.SUPPORTS, entailment
        elif contradiction > entailment and contradiction > neutral:
            return EvidenceStance.CONTRADICTS, contradiction
        return EvidenceStance.NEUTRAL, neutral

    async def _llm_assess(self, claim: str, evidence: str) -> tuple:
        """Fallback: Use LLM to assess evidence stance."""
        prompt = f"""Assess whether the following evidence SUPPORTS, CONTRADICTS, or is NEUTRAL toward the claim.

Claim: {claim}

Evidence: {evidence[:1500]}

Respond with a JSON object:
{{"stance": "SUPPORTS" | "CONTRADICTS" | "NEUTRAL", "confidence": 0.0-1.0}}"""

        try:
            response = await self.llm_analyze_fn(prompt)
            import json
            # Try to parse JSON from response
            result = json.loads(response)
            stance_str = result.get("stance", "NEUTRAL").upper()
            confidence = float(result.get("confidence", 0.5))

            stance_map = {
                "SUPPORTS": EvidenceStance.SUPPORTS,
                "CONTRADICTS": EvidenceStance.CONTRADICTS,
                "NEUTRAL": EvidenceStance.NEUTRAL,
            }
            return stance_map.get(stance_str, EvidenceStance.NEUTRAL), confidence
        except Exception as e:
            logger.warning(f"LLM assessment failed: {e}")
            return EvidenceStance.NEUTRAL, 0.5

    def _aggregate_score(self, assessments: List[EvidenceAssessment]) -> float:
        """Aggregate multiple evidence assessments into a single score."""
        if not assessments:
            return 0.0

        # Weight by confidence and source authority
        total_weight = 0.0
        weighted_sum = 0.0

        for assessment in assessments:
            # Get authority from document metadata if available
            authority = assessment.document.metadata.get("authority_score", 1.0)
            weight = assessment.confidence * authority
            weighted_sum += weight
            total_weight += authority

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _determine_status(
        self,
        support_score: float,
        contradict_score: float,
        original: "ClaimVerification",
    ) -> tuple:
        """Determine final verification status based on evidence balance."""

        # No contradicting evidence found - keep original
        if contradict_score < 0.1:
            return original.status, "No significant contradicting evidence found."

        # Strong contradiction, weak support -> REFUTED
        if contradict_score > 0.7 and support_score < 0.4:
            return VerificationStatus.REFUTED, (
                f"Strong contradicting evidence (score={contradict_score:.2f}) "
                f"outweighs support (score={support_score:.2f})."
            )

        # Both have significant evidence -> CONTESTED
        total = support_score + contradict_score
        ratio = support_score / total if total > 0 else 0.5

        if self.contested_threshold < ratio < (1 - self.contested_threshold):
            return VerificationStatus.CONTESTED, (
                f"Evidence is contested: support={support_score:.2f}, "
                f"contradict={contradict_score:.2f}, ratio={ratio:.2f}."
            )

        # Support dominates -> keep VERIFIED (if original was verified)
        if ratio >= (1 - self.contested_threshold) and original.status == VerificationStatus.VERIFIED:
            return VerificationStatus.VERIFIED, (
                f"Supporting evidence ({support_score:.2f}) dominates "
                f"despite some contradiction ({contradict_score:.2f})."
            )

        # Contradiction dominates
        if ratio <= self.contested_threshold:
            return VerificationStatus.REFUTED, (
                f"Contradicting evidence ({contradict_score:.2f}) dominates "
                f"over support ({support_score:.2f})."
            )

        # Default: keep original with note
        return original.status, (
            f"Adjudication inconclusive. Support={support_score:.2f}, "
            f"Contradict={contradict_score:.2f}. Keeping original status."
        )
```

#### 5. Integration: FVA Pipeline

**File**: `tldw_Server_API/app/core/Claims_Extraction/fva_pipeline.py` (new)

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
import asyncio

from loguru import logger

if TYPE_CHECKING:
    from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MultiDatabaseRetriever

from tldw_Server_API.app.core.Claims_Extraction.claims_engine import (
    Claim,
    ClaimVerification,
    ClaimsEngine,
)
from tldw_Server_API.app.core.Claims_Extraction.falsification import (
    should_trigger_falsification,
    FalsificationDecision,
)
from tldw_Server_API.app.core.Claims_Extraction.anti_context_retriever import (
    AntiContextRetriever,
    AntiContextConfig,
)
from tldw_Server_API.app.core.Claims_Extraction.adjudicator import (
    ClaimAdjudicator,
    AdjudicationResult,
)
from tldw_Server_API.app.core.Claims_Extraction.budget_guard import (
    ClaimsJobBudget,
    ClaimsJobContext,
)

# Import types
try:
    from tldw_Server_API.app.core.RAG.rag_service.types import Document, VerificationStatus
except Exception:
    from enum import Enum as _Enum
    from dataclasses import dataclass as _dc

    class VerificationStatus(_Enum):  # type: ignore
        VERIFIED = "verified"
        CONTESTED = "contested"

    @_dc
    class Document:  # type: ignore
        id: str
        content: str
        metadata: Dict[str, Any] = field(default_factory=dict)
        score: float = 0.0

# Metrics integration
try:
    from tldw_Server_API.app.core.Metrics.metrics_manager import (
        increment_counter,
        observe_histogram,
    )
except Exception:
    def increment_counter(*args, **kwargs): return None
    def observe_histogram(*args, **kwargs): return None


@dataclass
class FVAConfig:
    """Configuration for Falsification-Verification Alignment pipeline."""
    enabled: bool = True
    max_concurrent_falsifications: int = 5
    falsification_timeout_seconds: float = 30.0
    min_confidence_for_skip: float = 0.9  # Skip falsification if very confident
    force_falsification_claim_types: List[str] = field(default_factory=list)
    anti_context_config: Optional[AntiContextConfig] = None
    # Budget integration
    max_budget_ratio_for_fva: float = 0.3  # Max 30% of budget for FVA
    # Rate limiting
    max_anti_queries_per_minute: int = 60


@dataclass
class FVAResult:
    """Result of FVA pipeline processing for a single claim."""
    original_verification: ClaimVerification
    falsification_triggered: bool
    falsification_decision: Optional[FalsificationDecision]
    anti_context_found: int
    adjudication: Optional[AdjudicationResult]
    final_verification: ClaimVerification
    processing_time_ms: float


@dataclass
class FVABatchResult:
    """Batch result for multiple claims."""
    results: List[FVAResult]
    total_claims: int
    falsification_triggered_count: int
    status_changes: Dict[str, int]  # e.g., {"verified->contested": 2}
    total_time_ms: float
    budget_exhausted: bool = False


class FVAPipeline:
    """
    Falsification-Verification Alignment Pipeline.

    Extends standard verification with active counter-evidence retrieval
    for uncertain or high-risk claims.
    """

    def __init__(
        self,
        claims_engine: ClaimsEngine,
        retriever: "MultiDatabaseRetriever",
        config: Optional[FVAConfig] = None,
    ):
        """
        Initialize the FVA pipeline.

        Args:
            claims_engine: Existing ClaimsEngine instance
            retriever: MultiDatabaseRetriever for anti-context retrieval
            config: FVA configuration options
        """
        self.claims_engine = claims_engine
        self.retriever = retriever
        self.config = config or FVAConfig()

        self.anti_retriever = AntiContextRetriever(
            retriever,
            self.config.anti_context_config,
        )

        # Get NLI pipeline from claims_engine if available
        nli_pipeline = getattr(claims_engine, '_nli', None)
        if asyncio.iscoroutine(nli_pipeline) or asyncio.isfuture(nli_pipeline):
            # It's a future from lazy loading - will be resolved later
            nli_pipeline = None

        self.adjudicator = ClaimAdjudicator(
            nli_pipeline=nli_pipeline,
            llm_analyze_fn=getattr(claims_engine, '_analyze', None),
        )

    async def process_claim(
        self,
        claim: Claim,
        query: str,
        documents: List[Document],
        user_id: Optional[str] = None,
        budget: Optional[ClaimsJobBudget] = None,
        job_context: Optional[ClaimsJobContext] = None,
    ) -> FVAResult:
        """
        Process a single claim through the FVA pipeline.

        1. Standard verification
        2. Decide if falsification needed
        3. If yes, retrieve anti-context and adjudicate

        Args:
            claim: The claim to process
            query: Original user query (required for verification)
            documents: Documents from original retrieval
            user_id: User ID for scoped retrieval
            budget: Budget constraints for cost tracking
            job_context: Job context for logging

        Returns:
            FVAResult with verification outcome
        """
        start_time = datetime.utcnow()

        # Step 1: Standard verification using existing verifier
        original_verification = await self.claims_engine.verifier.verify(
            claim=claim,
            query=query,
            base_documents=documents,
            budget=budget,
            job_context=job_context,
        )

        # Step 2: Falsification trigger decision
        falsification_decision: Optional[FalsificationDecision] = None
        anti_context_count = 0
        adjudication: Optional[AdjudicationResult] = None
        final_verification = original_verification

        if self.config.enabled:
            # Check budget before proceeding
            if budget and not self._can_afford_falsification(budget):
                logger.debug("Skipping falsification due to budget constraints")
            else:
                force = (
                    claim.claim_type and
                    claim.claim_type.value in self.config.force_falsification_claim_types
                )

                falsification_decision = should_trigger_falsification(
                    claim=claim,
                    verification_confidence=original_verification.confidence,
                    evidence_count=len(original_verification.evidence),
                    force_falsification=force,
                )

                # Step 3: If triggered, retrieve anti-context and adjudicate
                if falsification_decision.should_falsify:
                    increment_counter(
                        "fva_falsification_triggered_total",
                        labels={"reason": falsification_decision.reason.value if falsification_decision.reason else "unknown"}
                    )

                    try:
                        anti_results = await asyncio.wait_for(
                            self.anti_retriever.retrieve_anti_context(
                                claim=claim,
                                original_doc_ids={d.id for d in documents},
                                user_id=user_id,
                            ),
                            timeout=self.config.falsification_timeout_seconds,
                        )

                        anti_docs = []
                        for result in anti_results:
                            anti_docs.extend(result.documents)
                        anti_context_count = len(anti_docs)

                        observe_histogram(
                            "fva_anti_context_docs",
                            anti_context_count,
                        )

                        if anti_docs:
                            # Ensure adjudicator has NLI pipeline
                            if self.adjudicator.nli_pipeline is None:
                                nli = await self._get_nli_pipeline()
                                if nli:
                                    self.adjudicator.nli_pipeline = nli

                            adjudication = await self.adjudicator.adjudicate(
                                claim=claim,
                                supporting_docs=documents,
                                contradicting_docs=anti_docs,
                                original_verification=original_verification,
                            )

                            # Update final verification based on adjudication
                            final_verification = ClaimVerification(
                                claim=claim,
                                status=adjudication.final_status,
                                confidence=max(adjudication.support_score, adjudication.contradict_score),
                                evidence=original_verification.evidence,
                                rationale=adjudication.adjudication_rationale,
                                match_level=original_verification.match_level,
                                source_authority=original_verification.source_authority,
                            )

                            # Track status changes
                            if original_verification.status != final_verification.status:
                                increment_counter(
                                    "fva_status_changes_total",
                                    labels={
                                        "from_status": original_verification.status.value,
                                        "to_status": final_verification.status.value,
                                    }
                                )
                        else:
                            increment_counter("fva_wasted_falsification_total")

                    except asyncio.TimeoutError:
                        logger.warning(f"Falsification timeout for claim: {claim.text[:50]}...")
                        # Explicit: keep original verification on timeout
                        final_verification = original_verification

                    except Exception as e:
                        logger.error(f"Falsification error for claim {claim.id}: {e}")
                        # Explicit: keep original verification on error
                        final_verification = original_verification

        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        observe_histogram("fva_processing_duration_seconds", elapsed_ms / 1000, labels={"phase": "total"})

        return FVAResult(
            original_verification=original_verification,
            falsification_triggered=falsification_decision.should_falsify if falsification_decision else False,
            falsification_decision=falsification_decision,
            anti_context_found=anti_context_count,
            adjudication=adjudication,
            final_verification=final_verification,
            processing_time_ms=elapsed_ms,
        )

    async def process_batch(
        self,
        claims: List[Claim],
        query: str,
        documents: List[Document],
        user_id: Optional[str] = None,
        budget: Optional[ClaimsJobBudget] = None,
        job_context: Optional[ClaimsJobContext] = None,
    ) -> FVABatchResult:
        """
        Process multiple claims with concurrency control.

        Args:
            claims: List of claims to process
            query: Original user query
            documents: Documents from original retrieval
            user_id: User ID for scoped retrieval
            budget: Budget constraints
            job_context: Job context for logging

        Returns:
            FVABatchResult with all results and summary
        """
        start_time = datetime.utcnow()
        budget_exhausted = False

        semaphore = asyncio.Semaphore(self.config.max_concurrent_falsifications)

        async def process_with_semaphore(claim: Claim) -> FVAResult:
            async with semaphore:
                return await self.process_claim(
                    claim=claim,
                    query=query,
                    documents=documents,
                    user_id=user_id,
                    budget=budget,
                    job_context=job_context,
                )

        results = await asyncio.gather(
            *[process_with_semaphore(c) for c in claims],
            return_exceptions=True,
        )

        # Filter out exceptions
        valid_results = [r for r in results if isinstance(r, FVAResult)]

        # Check for budget exhaustion
        if budget and budget.exhausted:
            budget_exhausted = True

        # Calculate status changes
        status_changes: Dict[str, int] = {}
        for r in valid_results:
            if r.original_verification.status != r.final_verification.status:
                key = f"{r.original_verification.status.value}->{r.final_verification.status.value}"
                status_changes[key] = status_changes.get(key, 0) + 1

        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        return FVABatchResult(
            results=valid_results,
            total_claims=len(claims),
            falsification_triggered_count=sum(1 for r in valid_results if r.falsification_triggered),
            status_changes=status_changes,
            total_time_ms=elapsed_ms,
            budget_exhausted=budget_exhausted,
        )

    def _can_afford_falsification(self, budget: ClaimsJobBudget) -> bool:
        """Check if budget allows for falsification overhead."""
        if budget.max_cost_usd is None:
            return True

        # Estimate FVA cost (rough: 3 queries + 1 adjudication)
        estimated_fva_cost = 0.01  # $0.01 per claim for FVA

        remaining = budget.max_cost_usd - budget.used_cost_usd
        allowed_for_fva = budget.max_cost_usd * self.config.max_budget_ratio_for_fva

        return remaining >= estimated_fva_cost and budget.used_cost_usd < allowed_for_fva

    async def _get_nli_pipeline(self) -> Optional[Any]:
        """Get NLI pipeline from claims engine, resolving lazy loading if needed."""
        nli = getattr(self.claims_engine, '_nli', None)
        if nli is None:
            return None

        if asyncio.isfuture(nli) or asyncio.iscoroutine(nli):
            try:
                return await nli
            except Exception:
                return None

        return nli
```

---

## API Changes

### New Endpoint: FVA Verification

**Path**: `POST /api/v1/claims/verify/fva`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

router = APIRouter()


class FVAConfigInput(BaseModel):
    """Configuration options for FVA verification."""
    force_falsification: bool = Field(False, description="Force falsification for all claims")
    max_anti_context_docs: int = Field(10, ge=1, le=50, description="Max anti-context documents to retrieve")
    contested_threshold: float = Field(0.4, ge=0.1, le=0.5, description="Threshold for CONTESTED status")


class ClaimInput(BaseModel):
    """Input for a claim to verify."""
    text: str = Field(..., min_length=1, max_length=2000)
    claim_type: Optional[str] = None


class FVAVerificationRequest(BaseModel):
    """Request for FVA verification."""
    claims: Optional[List[ClaimInput]] = Field(None, description="Claims to verify (or use text)")
    text: Optional[str] = Field(None, description="Text to extract claims from")
    query: str = Field(..., description="Original query for context")
    document_ids: Optional[List[str]] = Field(None, description="Restrict to specific documents")
    config: Optional[FVAConfigInput] = None


class FVAClaimResult(BaseModel):
    """Result for a single claim."""
    claim_text: str
    original_status: str
    final_status: str
    falsification_triggered: bool
    anti_context_count: int
    support_score: Optional[float] = None
    contradict_score: Optional[float] = None
    contestation_score: Optional[float] = None
    rationale: str


class FVASummary(BaseModel):
    """Summary statistics for FVA verification."""
    total_claims: int
    falsification_rate: float
    status_changes: Dict[str, int]
    contested_count: int
    verified_count: int
    refuted_count: int


class FVAVerificationResponse(BaseModel):
    """Response from FVA verification."""
    results: List[FVAClaimResult]
    summary: FVASummary


@router.post("/verify/fva", response_model=FVAVerificationResponse)
async def verify_claims_with_fva(
    request: FVAVerificationRequest,
    current_user = Depends(get_current_user),
    db = Depends(get_media_db),
):
    """
    Verify claims using Falsification-Verification Alignment.

    This extends standard verification by actively seeking
    contradicting evidence for uncertain or high-risk claims.
    """
    # Implementation in Stage 5
    pass
```

### Modified Endpoint: Post-Generation Verification

**Path**: `POST /api/v1/rag/generate` (existing, with new option)

Add `use_fva: bool = False` to request schema. When enabled, the post-generation verifier uses FVA pipeline.

---

## Configuration

### Environment Variables

```bash
# Enable FVA pipeline (master switch)
FVA_ENABLED=true

# Auto-trigger vs explicit only
FVA_AUTO_TRIGGER=true

# Persist adjudications to database
FVA_PERSIST_ADJUDICATIONS=true

# Falsification trigger thresholds
FVA_MIN_CONFIDENCE_THRESHOLD=0.7
FVA_FORCE_FOR_CLAIM_TYPES=statistic,causal,comparative

# Anti-context retrieval settings
FVA_MAX_ANTI_QUERIES=3
FVA_MAX_ANTI_DOCS_PER_QUERY=5
FVA_ANTI_MIN_RELEVANCE=0.3

# Adjudication settings
FVA_CONTESTED_THRESHOLD=0.4

# Performance limits
FVA_MAX_CONCURRENT=5
FVA_TIMEOUT_SECONDS=30

# Budget controls
FVA_MAX_BUDGET_RATIO=0.3

# Rate limiting
FVA_MAX_ANTI_QUERIES_PER_MINUTE=60
```

### Config File Addition

**File**: `tldw_Server_API/Config_Files/config.txt`

Add section (verify actual config.txt format first):

```
# FVA (Falsification-Verification Alignment) Settings
fva_enabled = true
fva_auto_trigger = true
fva_persist_adjudications = true
fva_min_confidence_threshold = 0.7
fva_force_claim_types = statistic,causal,comparative
fva_max_anti_queries = 3
fva_contested_threshold = 0.4
fva_timeout_seconds = 30
fva_max_budget_ratio = 0.3
```

---

## Database Changes

### New Table: `claim_adjudications`

```sql
CREATE TABLE claim_adjudications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Claim identification (supports both persisted and ephemeral claims)
    claim_id INTEGER NULL REFERENCES claims(id) ON DELETE SET NULL,
    claim_text TEXT NOT NULL,
    claim_hash TEXT NOT NULL,  -- SHA256 of normalized claim_text for deduplication

    -- Adjudication results
    original_status TEXT NOT NULL,
    final_status TEXT NOT NULL,
    support_score REAL NOT NULL,
    contradict_score REAL NOT NULL,
    contestation_score REAL NOT NULL DEFAULT 0.0,
    anti_context_count INTEGER NOT NULL,
    rationale TEXT,

    -- Context
    query_text TEXT,
    user_id TEXT,

    -- Timestamps and audit
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uuid TEXT UNIQUE NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_adjudications_claim ON claim_adjudications(claim_id);
CREATE INDEX idx_adjudications_claim_hash ON claim_adjudications(claim_hash);
CREATE INDEX idx_adjudications_status_change ON claim_adjudications(original_status, final_status);
CREATE INDEX idx_adjudications_user ON claim_adjudications(user_id);
CREATE INDEX idx_adjudications_created ON claim_adjudications(created_at);
```

### New Table: `anti_context_evidence`

```sql
CREATE TABLE anti_context_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adjudication_id INTEGER NOT NULL REFERENCES claim_adjudications(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL,
    query_used TEXT NOT NULL,
    strategy TEXT NOT NULL,  -- negation, contrary, antonym
    stance TEXT NOT NULL,  -- supports, contradicts, neutral
    confidence REAL NOT NULL,
    snippet TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_anti_evidence_adjudication ON anti_context_evidence(adjudication_id);
CREATE INDEX idx_anti_evidence_document ON anti_context_evidence(document_id);
```

### Migration for Existing Tables

**File**: Update `verification_report.py` to handle CONTESTED:

```python
# In VerificationReport dataclass, add:
contested_count: int = 0

# In from_verification_result(), add handling:
elif status == VerificationStatus.CONTESTED:
    contested += 1

# Update metrics calculations to include contested
```

---

## Metrics & Observability

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram

# Claims processed through FVA
fva_claims_processed_total = Counter(
    "fva_claims_processed_total",
    "Total claims processed through FVA",
    ["status"]
)

# Falsification triggers
fva_falsification_triggered_total = Counter(
    "fva_falsification_triggered_total",
    "Claims that triggered falsification",
    ["reason"]
)

# Status changes from FVA
fva_status_changes_total = Counter(
    "fva_status_changes_total",
    "Verification status changes from FVA",
    ["from_status", "to_status"]
)

# Anti-context document counts
fva_anti_context_docs = Histogram(
    "fva_anti_context_docs",
    "Number of anti-context documents retrieved",
    buckets=[0, 1, 2, 5, 10, 20]
)

# Processing duration
fva_processing_duration_seconds = Histogram(
    "fva_processing_duration_seconds",
    "FVA pipeline processing time",
    ["phase"],  # trigger, retrieval, adjudication, total
)

# Effectiveness metrics
fva_false_positive_prevention_total = Counter(
    "fva_false_positive_prevention_total",
    "Claims where falsification changed VERIFIED to REFUTED/CONTESTED"
)

fva_wasted_falsification_total = Counter(
    "fva_wasted_falsification_total",
    "Falsifications that found no useful counter-evidence"
)

fva_anti_context_relevance = Histogram(
    "fva_anti_context_relevance_score",
    "Relevance scores of retrieved anti-context documents",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)
```

### Logging

```python
# Structured logging for FVA events (using loguru bind pattern)
logger.bind(
    claim_id=claim.id,
    original_status=original.status.value,
    final_status=final.status.value,
    support_score=adjudication.support_score,
    contradict_score=adjudication.contradict_score,
    anti_context_count=len(anti_docs),
    falsification_reason=decision.reason.value if decision and decision.reason else None,
).info("FVA adjudication complete")
```

---

## Testing Strategy

### Unit Tests

| Test | Description |
|------|-------------|
| `test_falsification_trigger_low_confidence` | Triggers falsification when confidence < 0.7 |
| `test_falsification_trigger_high_risk_types` | Triggers for STATISTIC, CAUSAL, COMPARATIVE |
| `test_falsification_skip_high_confidence` | Skips when confidence ≥ 0.9 |
| `test_anti_context_query_generation` | Generates appropriate negation queries |
| `test_anti_context_source_diversity` | Limits docs per source |
| `test_adjudicator_contested_detection` | Marks as CONTESTED when evidence balanced |
| `test_adjudicator_refuted_override` | Changes VERIFIED→REFUTED when contradiction dominates |
| `test_adjudicator_verified_preservation` | Keeps VERIFIED when support dominates |
| `test_contestation_score_calculation` | Correctly calculates contestation score |
| `test_budget_integration` | Respects budget constraints |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_fva_pipeline_end_to_end` | Full pipeline with mock retriever/NLI |
| `test_fva_api_endpoint` | API contract validation |
| `test_fva_with_real_corpus` | Against test document corpus |
| `test_fva_concurrency_limits` | Respects semaphore limits |
| `test_fva_timeout_handling` | Graceful timeout behavior |
| `test_fva_with_media_db_retriever` | Integration with MediaDBRetriever |
| `test_fva_with_multi_database_retriever` | Integration with MultiDatabaseRetriever |
| `test_fva_in_post_generation_flow` | Integration with PostGenerationVerifier |
| `test_fva_rag_generate_endpoint` | End-to-end with `/api/v1/rag/generate?use_fva=true` |

### Benchmark Tests

| Test | Target |
|------|--------|
| `bench_fva_latency_no_falsification` | < 50ms overhead vs standard |
| `bench_fva_latency_with_falsification` | < 500ms for single claim |
| `bench_fva_batch_throughput` | ≥ 10 claims/sec with falsification |

---

## Implementation Stages

## Stage 1: Core Types and Falsification Trigger
**Goal**: Add CONTESTED status and implement falsification decision logic.
**Success Criteria**: Falsification trigger correctly identifies high-risk claims; new status integrates with existing verification report.
**Tests**: Unit tests for trigger logic; integration with VerificationReport.
**Status**: Not Started

**Checklist**:
- [ ] Add `CONTESTED` to `VerificationStatus` enum in `types.py`
- [ ] Add `CONTESTED` mapping to `ClaimVerification.label` property in `claims_engine.py`
- [ ] Update `VerificationReport` dataclass to add `contested_count: int`
- [ ] Update `VerificationReport.from_verification_result()` to count CONTESTED
- [ ] Update `VerificationReport.to_dict()` and `get_summary()` to include contested
- [ ] Update `VerificationReport.get_problematic_claims()` to optionally include CONTESTED
- [ ] Create `falsification.py` with `should_trigger_falsification()`
- [ ] Add unit tests for trigger logic edge cases
- [ ] Update claims API schemas for CONTESTED status
- [ ] Add backward compatibility test for existing verification reports

## Stage 2: Anti-Context Retrieval
**Goal**: Implement query generation and retrieval for contradicting evidence.
**Success Criteria**: Generates diverse negation queries; retrieves relevant counter-documents; excludes original evidence; respects source diversity.
**Tests**: Unit tests for query generation; integration with RAG retriever.
**Status**: Not Started

**Checklist**:
- [ ] Create `anti_context_retriever.py`
- [ ] Implement negation template expansion
- [ ] Implement claim-type-specific contrary queries
- [ ] Add document deduplication logic
- [ ] Add source diversity filtering (`_diversify_by_source`)
- [ ] Add query result caching
- [ ] Integration tests with mock retriever
- [ ] Integration tests with real MultiDatabaseRetriever

## Stage 3: Adjudicator Implementation
**Goal**: Build evidence weighing system that determines final status.
**Success Criteria**: Correctly identifies CONTESTED claims; integrates with existing NLI model; LLM fallback works; calculates contestation score.
**Tests**: Unit tests for score aggregation and status determination.
**Status**: Not Started

**Checklist**:
- [ ] Create `adjudicator.py` with `ClaimAdjudicator`
- [ ] Implement NLI-based stance assessment (matching transformers pipeline interface)
- [ ] Implement LLM fallback assessment with JSON parsing
- [ ] Implement score aggregation with authority weighting
- [ ] Implement status determination logic
- [ ] Add contestation score calculation
- [ ] Unit tests for all adjudication paths
- [ ] Test NLI pipeline integration with claims_engine pattern

## Stage 4: FVA Pipeline Integration
**Goal**: Assemble components into complete pipeline with concurrency control and budget integration.
**Success Criteria**: Pipeline processes claims end-to-end; respects timeout/concurrency limits; integrates with ClaimsJobBudget; produces FVAResult.
**Tests**: Integration tests for full pipeline; benchmark tests.
**Status**: Not Started

**Checklist**:
- [ ] Create `fva_pipeline.py` with `FVAPipeline`
- [ ] Implement `process_claim()` with query parameter
- [ ] Implement `process_batch()` with semaphore
- [ ] Add timeout handling with explicit fallback
- [ ] Integrate with `ClaimsJobBudget` for cost tracking
- [ ] Add metrics emission
- [ ] Integration tests with mock components
- [ ] Benchmark tests for latency targets

## Stage 5: API and Database
**Goal**: Expose FVA through API; persist adjudication results.
**Success Criteria**: API endpoint works; results persisted; queryable for audit.
**Tests**: API contract tests; database migration tests.
**Status**: Not Started

**Checklist**:
- [ ] Add database migrations for `claim_adjudications` (with nullable claim_id + claim_hash)
- [ ] Add database migrations for `anti_context_evidence`
- [ ] Create API schemas for FVA request/response
- [ ] Create `/api/v1/claims/verify/fva` endpoint
- [ ] Add `use_fva` option to RAG generate endpoint
- [ ] Add admin endpoint `GET /api/v1/claims/fva/stats`
- [ ] Add debug endpoint `POST /api/v1/claims/fva/debug`
- [ ] API integration tests
- [ ] Database round-trip tests

## Stage 6: Configuration and Observability
**Goal**: Add configuration options and monitoring.
**Success Criteria**: Configurable via env vars and config file; metrics exposed; logs structured.
**Tests**: Config loading tests; metrics emission tests.
**Status**: Not Started

**Checklist**:
- [ ] Verify actual `config.txt` format and add FVA section accordingly
- [ ] Add environment variable handling with all flags
- [ ] Add Prometheus metrics (all defined above)
- [ ] Add structured logging with loguru bind pattern
- [ ] Add telemetry events for product analytics
- [ ] Config validation tests
- [ ] Metrics emission tests

## Stage 7: Documentation and Rollout
**Goal**: Document feature; enable for beta users.
**Success Criteria**: API docs updated; feature flag allows gradual rollout.
**Tests**: Documentation review; staging environment validation.
**Status**: Not Started

**Checklist**:
- [ ] Update API documentation
- [ ] Add usage examples to docs
- [ ] Create feature flags for gradual rollout (FVA_ENABLED, FVA_AUTO_TRIGGER, FVA_PERSIST_ADJUDICATIONS)
- [ ] Add migration guide for existing data
- [ ] Staging environment testing
- [ ] Performance validation under load

---

## Rollback Plan

FVA is additive and can be disabled without data loss:

1. Set `FVA_ENABLED=false` - pipeline skips falsification
2. API endpoints continue to work (return standard verification)
3. Existing `claim_adjudications` data remains for audit
4. No schema changes to core `claims` table
5. CONTESTED status in existing reports will display correctly (backward compatible)

---

## Open Questions

1. **Should CONTESTED claims block content publication?** - Needs product decision on workflow integration.

2. **Anti-context retrieval scope** - Should it search external sources (web) or only internal corpus?

3. **Cost implications** - Additional LLM calls for adjudication. Need to quantify and potentially add budget controls. *(Partially addressed with budget integration)*

4. **UI representation** - How should CONTESTED claims appear in the frontend? Need design input.

5. **Claim clustering** - Should we batch similar claims to reduce redundant anti-context retrieval? *(Consider using existing `claims_clustering.py`)*

---

## References

- [FVA-RAG Paper](https://arxiv.org/abs/2512.07015) - Mayank Ravishankara
- Existing claims engine: `tldw_Server_API/app/core/Claims_Extraction/claims_engine.py`
- Existing post-generation verifier: `tldw_Server_API/app/core/RAG/rag_service/post_generation_verifier.py`
- Existing verification report: `tldw_Server_API/app/core/Claims_Extraction/verification_report.py`
- Existing budget guard: `tldw_Server_API/app/core/Claims_Extraction/budget_guard.py`
- Existing claims clustering: `tldw_Server_API/app/core/Claims_Extraction/claims_clustering.py`
- Retriever interface: `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py`
