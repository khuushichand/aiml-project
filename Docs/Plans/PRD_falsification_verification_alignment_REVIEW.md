# PRD Review: Falsification-Verification Alignment

**Reviewer**: Claude
**Date**: 2026-02-01
**PRD**: `PRD_falsification_verification_alignment.md`

---

## Executive Summary

The PRD is well-structured and captures the FVA-RAG paper's key insights. However, there are **12 critical issues** that need resolution before implementation, **8 design improvements** worth considering, and **5 minor corrections** for consistency with the existing codebase.

---

## Critical Issues (Must Fix)

### 1. Field Name Mismatch: `reasoning` vs `rationale`

**Location**: PRD Section 4 (Adjudicator), FVA Pipeline

**Problem**: The PRD uses `reasoning` in `ClaimVerification`:
```python
final_verification = ClaimVerification(
    ...
    reasoning=adjudication.adjudication_reasoning,
)
```

**Actual codebase** (`claims_engine.py:113-122`):
```python
@dataclass
class ClaimVerification:
    ...
    rationale: Optional[str] = None  # NOT reasoning
```

**Fix**: Change all occurrences of `reasoning` to `rationale` in the PRD.

---

### 2. `extracted_value` vs `extracted_values` (Singular vs Plural)

**Location**: PRD Section 3 (Anti-Context Retriever)

**Problem**: PRD uses:
```python
if claim.extracted_value:
    return template.format(..., **claim.extracted_value)
```

**Actual codebase** (`claims_engine.py:94-100`):
```python
@dataclass
class Claim:
    ...
    extracted_values: Dict[str, Any] = field(default_factory=dict)  # PLURAL
```

**Fix**: Change `extracted_value` to `extracted_values`.

---

### 3. Non-Existent Method: `verify_single_claim`

**Location**: PRD Section 5 (FVA Pipeline)

**Problem**: PRD references:
```python
original_verification = await self.claims_engine.verify_single_claim(claim, documents)
```

**Actual interface** (`claims_engine.py:173-185`): The verifier protocol is:
```python
class ClaimVerifier(Protocol):
    async def verify(
        self,
        claim: Claim,
        query: str,  # REQUIRED
        base_documents: List[Document],
        ...
    ) -> ClaimVerification
```

**Issues**:
1. Method is `verify()`, not `verify_single_claim()`
2. `query` parameter is required but PRD doesn't pass it
3. Method is on `self.verifier`, not `self.claims_engine`

**Fix**: Update to:
```python
original_verification = await self.claims_engine.verifier.verify(
    claim=claim,
    query=query,  # Need to add query param to process_claim()
    base_documents=documents,
)
```

---

### 4. Retriever Interface Mismatch

**Location**: PRD Section 3 (Anti-Context Retriever)

**Problem**: PRD assumes:
```python
docs = await self.retriever.search(
    query=query,
    limit=self.config.max_docs_per_query,
    user_id=user_id,
    min_score=self.config.min_relevance_score,
)
```

**Actual interface** (`database_retrievers.py:152-200`): `BaseRetriever` uses:
```python
async def retrieve(
    self,
    query: str,
    config: Optional[RetrievalConfig] = None,
) -> List[Document]
```

And `MultiDatabaseRetriever.retrieve()` has a different signature:
```python
async def retrieve(
    self,
    query: str,
    sources: Optional[List[DataSource]] = None,
    search_mode: str = "hybrid",
    top_k: int = 10,
    ...
) -> List[Document]
```

**Fix**: Align with actual retriever interface:
```python
docs = await self.retriever.retrieve(
    query=query,
    top_k=self.config.max_docs_per_query,
    search_mode="hybrid",
)
# Filter by score after retrieval
docs = [d for d in docs if d.score >= self.config.min_relevance_score]
```

---

### 5. NLI Model Interface Mismatch

**Location**: PRD Section 4 (Adjudicator)

**Problem**: PRD assumes:
```python
result = await self.nli_model.predict(premise=evidence, hypothesis=claim)
# result.label, result.score
```

**Actual implementation** (`claims_engine.py:783-795`):
```python
# Uses transformers pipeline
pipeline("text-classification", model=model_name, return_all_scores=True)
# Returns: [[{"label": "ENTAILMENT", "score": 0.9}, {"label": "CONTRADICTION", ...}]]
```

**Fix**: Adapt to actual NLI interface:
```python
async def _nli_assess(self, claim: str, evidence: str) -> tuple[EvidenceStance, float]:
    """Use NLI model - matches existing claims_engine pattern."""
    if not self.nli_model:
        return await self._llm_assess(claim, evidence)

    # Format for transformers NLI: "premise </s></s> hypothesis"
    input_text = f"{evidence} </s></s> {claim}"
    results = self.nli_model(input_text)

    # results is [[{label, score}, ...]] - find best
    scores = {r["label"].lower(): r["score"] for r in results[0]}

    if scores.get("entailment", 0) > scores.get("contradiction", 0):
        return EvidenceStance.SUPPORTS, scores["entailment"]
    elif scores.get("contradiction", 0) > 0.5:
        return EvidenceStance.CONTRADICTS, scores["contradiction"]
    return EvidenceStance.NEUTRAL, scores.get("neutral", 0.5)
```

---

### 6. Missing Budget Integration

**Location**: Entire PRD

**Problem**: The existing claims system has comprehensive budget tracking (`ClaimsJobBudget` in `budget_guard.py`), but FVA adds:
- Additional retrieval queries (3 per uncertain claim)
- Additional NLI/LLM calls for adjudication

PRD doesn't integrate with budget system, risking cost overruns.

**Fix**: Add budget integration:
```python
@dataclass
class FVAConfig:
    ...
    budget: Optional[ClaimsJobBudget] = None
    max_anti_context_cost_ratio: float = 0.3  # Max 30% of budget for anti-context

async def process_claim(self, claim, documents, user_id, budget=None):
    # Check budget before falsification
    if budget and self.should_skip_for_budget(budget):
        return self._skip_falsification_result(claim, original_verification)

    # Reserve budget for anti-context retrieval
    if budget:
        estimated_cost = self._estimate_falsification_cost(claim)
        if not budget.reserve(cost_usd=estimated_cost):
            return self._skip_falsification_result(claim, original_verification)
```

---

### 7. Missing CONTESTED Status in VerificationReport

**Location**: `verification_report.py` (existing file, needs update)

**Problem**: `VerificationReport.from_verification_result()` doesn't handle `CONTESTED`:
```python
# Lines 165-178 - no CONTESTED handling
if status == VerificationStatus.VERIFIED:
    verified += 1
elif status == VerificationStatus.REFUTED:
    refuted += 1
# ... no CONTESTED
```

**Fix**: Add to Stage 1 checklist:
- [ ] Update `VerificationReport` dataclass to add `contested_count: int`
- [ ] Update `from_verification_result()` to count CONTESTED
- [ ] Update `to_dict()` and `get_summary()` to include contested
- [ ] Update `get_problematic_claims()` to optionally include CONTESTED

---

### 8. Missing `label` Property Update for CONTESTED

**Location**: `claims_engine.py` (existing file, needs update)

**Problem**: `ClaimVerification.label` property doesn't map CONTESTED:
```python
@property
def label(self) -> str:
    status_to_label = {
        VerificationStatus.VERIFIED: "supported",
        VerificationStatus.REFUTED: "refuted",
        # ... no CONTESTED mapping
    }
```

**Fix**: Add mapping:
```python
VerificationStatus.CONTESTED: "contested",  # or "nei" for backward compatibility
```

---

### 9. Database FK Dependency Issue

**Location**: PRD Database Changes section

**Problem**:
```sql
claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
```

During post-generation verification, claims are extracted and verified but **not necessarily persisted to the Claims table**. The `claims(id)` FK assumes claims exist in DB.

**Fix**: Either:

**Option A**: Make `claim_id` nullable, use `claim_text` + `claim_hash` for identification:
```sql
CREATE TABLE claim_adjudications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NULL REFERENCES claims(id) ON DELETE SET NULL,
    claim_text TEXT NOT NULL,
    claim_hash TEXT NOT NULL,  -- SHA256 of normalized claim_text
    ...
);
CREATE INDEX idx_adjudications_claim_hash ON claim_adjudications(claim_hash);
```

**Option B**: Require claims persistence before adjudication (adds latency)

**Option C**: Store adjudications in-memory only, don't persist unless claims are persisted (loses audit trail)

**Recommendation**: Option A provides best balance of audit capability and flexibility.

---

### 10. Config File Format Mismatch

**Location**: PRD Configuration section

**Problem**: PRD shows INI-style config:
```ini
[FVA]
enabled = true
```

**Actual format** (`config.txt` uses a different style - need to verify):

**Fix**: Check actual `config.txt` format and align. If different, update PRD to match.

---

### 11. Missing Query Parameter in Pipeline

**Location**: PRD Section 5 (FVA Pipeline)

**Problem**: `process_claim()` signature:
```python
async def process_claim(
    self,
    claim: Claim,
    documents: List[Document],
    user_id: Optional[str] = None,
) -> FVAResult:
```

But verification requires `query`:
```python
await self.claims_engine.verifier.verify(claim, query=???, ...)
```

**Fix**: Add `query` parameter:
```python
async def process_claim(
    self,
    claim: Claim,
    query: str,  # ADD THIS
    documents: List[Document],
    user_id: Optional[str] = None,
) -> FVAResult:
```

---

### 12. Missing Error Recovery Strategy

**Location**: PRD Section 5 (FVA Pipeline)

**Problem**: Current error handling:
```python
except asyncio.TimeoutError:
    logger.warning(...)
except Exception as e:
    logger.error(...)
```

But no explicit recovery - what happens to `final_verification`? It remains as `original_verification`, which is correct, but this should be explicit.

**Fix**: Make recovery explicit:
```python
except asyncio.TimeoutError:
    logger.warning(f"Falsification timeout for claim: {claim.text[:50]}...")
    # Explicit: keep original verification on timeout
    final_verification = original_verification
except Exception as e:
    logger.error(f"Falsification error: {e}")
    # Explicit: keep original verification on error
    final_verification = original_verification
```

---

## Design Improvements (Should Consider)

### 1. Add Caching for Anti-Context Queries

**Rationale**: Similar claims will generate similar negation queries. Caching reduces redundant retrievals.

```python
@dataclass
class AntiContextRetriever:
    _query_cache: Dict[str, List[Document]] = field(default_factory=dict)
    cache_ttl_seconds: int = 300

    async def retrieve_anti_context(self, claim, ...):
        cache_key = self._make_cache_key(claim)
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]
        ...
```

---

### 2. Add Claim Clustering Before Falsification

**Rationale**: If multiple claims are semantically similar, batch their falsification to avoid redundant anti-context retrieval.

```python
# In FVAPipeline.process_batch():
claim_clusters = self._cluster_similar_claims(claims)
for cluster in claim_clusters:
    # Single anti-context retrieval for cluster
    anti_context = await self.retrieve_anti_context_for_cluster(cluster)
    for claim in cluster:
        await self.adjudicate_with_shared_context(claim, anti_context)
```

Note: You already have `claims_clustering.py` - consider reusing it.

---

### 3. Add Confidence Degradation for Contested Claims

**Rationale**: CONTESTED status alone doesn't indicate how contested. Add a "contestation score".

```python
@dataclass
class AdjudicationResult:
    ...
    contestation_score: float  # 0 = one-sided, 1 = perfectly balanced

    @property
    def contestation_score(self) -> float:
        total = self.support_score + self.contradict_score
        if total == 0:
            return 0.0
        # Higher when scores are balanced
        return 1.0 - abs(self.support_score - self.contradict_score) / total
```

---

### 4. Add Streaming/Progressive Results

**Rationale**: For batch processing, return results as they complete rather than waiting for all.

```python
async def process_batch_streaming(
    self, claims, documents, user_id
) -> AsyncIterator[FVAResult]:
    """Yield results as each claim completes."""
    semaphore = asyncio.Semaphore(self.config.max_concurrent_falsifications)

    async def process_one(claim):
        async with semaphore:
            return await self.process_claim(claim, documents, user_id)

    tasks = [asyncio.create_task(process_one(c)) for c in claims]
    for coro in asyncio.as_completed(tasks):
        yield await coro
```

---

### 5. Add Source Diversity in Anti-Context Retrieval

**Rationale**: Counter-evidence from diverse sources is more meaningful than multiple snippets from one document.

```python
def _diversify_anti_context(self, docs: List[Document], max_per_source: int = 2) -> List[Document]:
    """Ensure diversity by limiting docs per source."""
    source_counts: Dict[str, int] = {}
    diverse_docs = []

    for doc in sorted(docs, key=lambda d: d.score, reverse=True):
        source_id = doc.metadata.get("media_id", doc.id)
        if source_counts.get(source_id, 0) < max_per_source:
            diverse_docs.append(doc)
            source_counts[source_id] = source_counts.get(source_id, 0) + 1

    return diverse_docs
```

---

### 6. Add Explanation Generation for Contested Claims

**Rationale**: Users need to understand *why* a claim is contested, not just that it is.

```python
async def generate_contestation_explanation(
    self,
    claim: Claim,
    supporting: List[EvidenceAssessment],
    contradicting: List[EvidenceAssessment],
) -> str:
    """Generate human-readable explanation of the contestation."""
    prompt = f"""Summarize why this claim is contested:

Claim: {claim.text}

Supporting evidence:
{self._format_evidence(supporting)}

Contradicting evidence:
{self._format_evidence(contradicting)}

Provide a 2-3 sentence neutral explanation of the disagreement."""

    return await self.llm_judge.complete(prompt)
```

---

### 7. Add Metrics for Falsification Effectiveness

**Rationale**: Track whether falsification is actually finding useful counter-evidence or just adding latency.

```python
# Additional metrics
fva_false_positive_prevention = Counter(
    "fva_false_positive_prevention_total",
    "Claims where falsification changed VERIFIED to REFUTED/CONTESTED"
)

fva_anti_context_relevance = Histogram(
    "fva_anti_context_relevance_score",
    "Relevance scores of retrieved anti-context documents",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

fva_wasted_falsification = Counter(
    "fva_wasted_falsification_total",
    "Falsifications that found no useful counter-evidence"
)
```

---

### 8. Add Integration Tests with Real RAG Pipeline

**Rationale**: PRD tests are mostly unit tests. Need integration with actual RAG flow.

Add to Stage 5 checklist:
- [ ] Integration test: FVA with MediaDBRetriever
- [ ] Integration test: FVA with MultiDatabaseRetriever
- [ ] Integration test: FVA in PostGenerationVerifier flow
- [ ] End-to-end test: `/api/v1/rag/generate` with `use_fva=true`

---

## Minor Corrections

### 1. Import Path Consistency

PRD uses:
```python
from ..RAG.rag_service.types import Document, VerificationStatus
```

Should match existing pattern in `claims_engine.py`:
```python
from tldw_Server_API.app.core.RAG.rag_service.types import (
    Document,
    VerificationStatus,
    ...
)
```

---

### 2. Logging Format

PRD uses:
```python
logger.info(
    "FVA adjudication complete",
    claim_id=claim.id,
    ...
)
```

Verify this matches project's loguru configuration. Some setups require:
```python
logger.info(f"FVA adjudication complete claim_id={claim.id} ...")
# or
logger.bind(claim_id=claim.id).info("FVA adjudication complete")
```

---

### 3. Enum String Values

PRD uses:
```python
class FalsificationReason(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
```

This is correct (matches `VerificationStatus` pattern), but verify consistency.

---

### 4. Async Context Manager Pattern

In `AntiContextRetriever`, if retriever needs lifecycle management:
```python
class AntiContextRetriever:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        # Cleanup if needed
        pass
```

---

### 5. Type Hints Completeness

Several places in PRD have incomplete type hints:
```python
def __init__(
    self,
    retriever,  # Should be: retriever: MultiDatabaseRetriever
    config: Optional[AntiContextConfig] = None,
):
```

---

## Missing from PRD

### 1. Migration Strategy for Existing Data

What happens to existing `VerificationReport` data when CONTESTED is added? Need migration path or backward compatibility note.

### 2. Feature Flag Granularity

PRD has one flag (`FVA_ENABLED`). Consider:
- `FVA_ENABLED` - Master switch
- `FVA_AUTO_TRIGGER` - Auto-trigger vs explicit only
- `FVA_PERSIST_ADJUDICATIONS` - Store in DB or in-memory only

### 3. Rate Limiting for Anti-Context Retrieval

If retriever has rate limits, FVA could exhaust them. Add rate limiting consideration:
```python
@dataclass
class FVAConfig:
    ...
    max_anti_queries_per_minute: int = 60
```

### 4. Telemetry/Analytics Events

For product analytics:
```python
# Track FVA usage patterns
emit_event("fva_triggered", {
    "reason": decision.reason.value,
    "claim_type": claim.claim_type.value,
    "original_status": original.status.value,
    "final_status": final.status.value,
})
```

### 5. Admin/Debug Endpoints

For debugging FVA in production:
- `GET /api/v1/claims/fva/stats` - Aggregated FVA metrics
- `POST /api/v1/claims/fva/debug` - Run FVA with verbose output

---

## Updated Stage Checklist

Based on this review, here's a revised Stage 1 checklist:

### Stage 1: Core Types and Falsification Trigger (Revised)

**Checklist**:
- [ ] Add `CONTESTED` to `VerificationStatus` enum in `types.py`
- [ ] Add `CONTESTED` mapping to `ClaimVerification.label` property in `claims_engine.py`
- [ ] Update `VerificationReport` to handle CONTESTED (add count, update methods)
- [ ] Create `falsification.py` with `should_trigger_falsification()`
- [ ] Use `rationale` (not `reasoning`) in all new code
- [ ] Use `extracted_values` (not `extracted_value`)
- [ ] Add unit tests for trigger logic edge cases
- [ ] Update claims API schemas for CONTESTED status
- [ ] Add backward compatibility test for existing verification reports

---

## Summary

| Category | Count | Priority |
|----------|-------|----------|
| Critical Issues | 12 | Must fix before implementation |
| Design Improvements | 8 | Should consider |
| Minor Corrections | 5 | Nice to have |
| Missing Items | 5 | Add to PRD |

**Recommendation**: Address all critical issues before starting Stage 1. Design improvements can be added incrementally in later stages.
