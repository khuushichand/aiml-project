# Doc-Researcher Features

This document describes the three advanced RAG features for improved document research and evidence gathering.

## Overview

The Doc-Researcher features enhance the RAG pipeline with:

1. **Dynamic Granularity Selection** - Auto-selects retrieval granularity based on query type
2. **Progressive Evidence Accumulation** - Iteratively refines search until evidence is sufficient
3. **Multi-Hop Evidence Chains** - Tracks evidence dependencies across documents

All features are **opt-in** via explicit parameters and do not affect existing behavior when disabled.

---

## 1. Dynamic Granularity Selection

### Purpose
Automatically selects the optimal retrieval granularity (document/chunk/passage) based on query classification.

### How It Works
The `GranularityRouter` classifies queries into three types using rule-based pattern matching:

| Query Type | Example | Granularity | Retrieval Strategy |
|------------|---------|-------------|-------------------|
| **Broad** | "What is the overview of..." | Document | Full document retrieval with parent expansion |
| **Specific** | "How do I implement..." | Chunk | Standard chunk-level retrieval |
| **Factoid** | "When was X founded?" | Passage | Fine-grained passage retrieval with multi-vector |

### Usage

```python
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline

result = await unified_rag_pipeline(
    query="What is the main idea of the document?",
    enable_dynamic_granularity=True,  # Enable feature
    # ... other parameters
)

# Check routing decision in metadata
print(result.metadata.get("granularity_routing"))
# {
#     "query_type": "broad",
#     "granularity": "document",
#     "confidence": 0.85,
#     "reasoning": "Broad pattern: overview|summary..."
# }
```

### Direct API Usage

```python
from tldw_Server_API.app.core.RAG.rag_service.granularity_router import (
    GranularityRouter,
    route_query_granularity,
)

# Using convenience function
decision = route_query_granularity("When was the company founded?")
print(f"Type: {decision.query_type.value}")  # factoid
print(f"Granularity: {decision.granularity.value}")  # passage

# Using router directly for custom patterns
router = GranularityRouter(
    short_query_threshold=6,  # Customize thresholds
    long_query_threshold=30,
)
decision = router.route("My query")
params = decision.retrieval_params  # Get suggested retrieval parameters
```

### Configuration

The router applies these retrieval parameters automatically:

**Document Granularity:**
- `top_k: 5`
- `enable_parent_expansion: True`
- `include_parent_document: True`
- `parent_max_tokens: 2000`

**Passage Granularity:**
- `top_k: 15`
- `enable_multi_vector_passages: True`
- `mv_span_chars: 200`

**Chunk Granularity (default):**
- `top_k: 10`
- Standard chunk retrieval

---

## 2. Progressive Evidence Accumulation

### Purpose
Iteratively gathers evidence through multiple retrieval rounds until sufficient evidence is found or budget is exhausted.

### How It Works

1. Initial retrieval returns documents
2. Evidence is assessed for sufficiency (coverage of query terms, document scores)
3. If insufficient, gap queries are generated to find missing evidence
4. Process repeats up to `max_rounds` (default: 3)
5. Results are deduplicated and merged

### Usage

```python
result = await unified_rag_pipeline(
    query="What are the key findings about X?",
    enable_evidence_accumulation=True,
    accumulation_max_rounds=3,  # Max retrieval rounds
    accumulation_time_budget_sec=10.0,  # Optional time limit
    # ... other parameters
)

# Check accumulation results in metadata
print(result.metadata.get("evidence_accumulation"))
# {
#     "total_rounds": 2,
#     "is_sufficient": True,
#     "sufficiency_reason": "Coverage: 85%, Avg score: 0.72",
#     "initial_docs": 5,
#     "final_docs": 8,
#     "docs_added": 3
# }
```

### Direct API Usage

```python
from tldw_Server_API.app.core.RAG.rag_service.evidence_accumulator import (
    EvidenceAccumulator,
    accumulate_evidence,
)

accumulator = EvidenceAccumulator(
    max_rounds=3,
    min_docs_per_round=3,
    max_docs_total=20,
    sufficiency_threshold=0.8,
    enable_gap_assessment=True,  # Use LLM for gap analysis
)

# Custom retrieval function
async def my_retrieval(query: str, exclude_ids: set):
    # Your retrieval logic here
    return documents

result = await accumulator.accumulate(
    query="my query",
    initial_results=initial_docs,
    retrieval_fn=my_retrieval,
    time_budget_sec=10.0,
)

print(f"Rounds: {result.total_rounds}")
print(f"Sufficient: {result.is_sufficient}")
print(f"Documents: {len(result.documents)}")
```

### Gap Assessment

The accumulator can assess evidence gaps using:

1. **Heuristic mode** (default when LLM unavailable): Checks term coverage and document scores
2. **LLM mode**: Uses an LLM to identify specific gaps and generate follow-up queries

---

## 3. Multi-Hop Evidence Chains

### Purpose
Tracks how facts from multiple source documents support claims in the generated response, enabling transparency in multi-hop reasoning.

### How It Works

1. Facts are extracted from retrieved documents (heuristic or LLM-based)
2. Claims are extracted from the generated answer
3. Facts are matched to claims based on text similarity
4. Evidence chains are built showing the reasoning path
5. Chain confidence is computed as product of node confidences

### Data Model

```
EvidenceNode:
  - document_id: Source document
  - chunk_id: Specific chunk
  - fact: The extracted fact
  - confidence: Extraction confidence (0-1)
  - supports: List of claim IDs this fact supports

EvidenceChain:
  - query: Original query
  - nodes: List of EvidenceNodes
  - root_claims: Top-level claims being supported
  - chain_confidence: Aggregate confidence (product)
  - hop_count: Number of unique source documents
```

### Usage

```python
result = await unified_rag_pipeline(
    query="What caused X and what were the effects?",
    enable_evidence_chains=True,
    enable_generation=True,  # Needed for claim extraction
    debug_mode=True,  # Include full chain data
    # ... other parameters
)

# Check evidence chains in metadata
print(result.metadata.get("evidence_chains"))
# {
#     "total_chains": 3,
#     "overall_confidence": 0.72,
#     "multi_hop_detected": True,
#     "total_claims": 5,
#     "supported_claims": 4,
#     "chains": [
#         {
#             "hop_count": 2,
#             "chain_confidence": 0.68,
#             "source_documents": ["doc1", "doc2"],
#             "root_claims": ["claim_0_abc123"],
#             "nodes_count": 3
#         },
#         ...
#     ]
# }
```

### Direct API Usage

```python
from tldw_Server_API.app.core.RAG.rag_service.evidence_chains import (
    EvidenceChainBuilder,
    build_evidence_chains,
)

builder = EvidenceChainBuilder(
    min_confidence=0.3,
    max_chain_length=5,
    similarity_threshold=0.3,
    enable_llm_extraction=True,
)

result = await builder.build_chains(
    query="my query",
    documents=retrieved_docs,
    generated_answer="The answer text...",
)

print(f"Chains: {len(result.chains)}")
print(f"Multi-hop: {result.multi_hop_detected}")

for chain in result.chains:
    print(f"  Confidence: {chain.chain_confidence:.2f}")
    print(f"  Hops: {chain.hop_count}")
    for node in chain.nodes:
        print(f"    - {node.fact[:50]}... (conf: {node.confidence:.2f})")
```

### Integration with Citations

Evidence chains can be linked to citations for enhanced traceability:

```python
from tldw_Server_API.app.core.RAG.rag_service.citations import CitationGenerator

generator = CitationGenerator()

# Generate citations with chain information
citations, chain_result = await generator.generate_citations_with_chains(
    documents=docs,
    query=query,
    generated_answer=answer,
)

# Citations now include chain metadata in usage_context
```

---

## API Reference

### Pipeline Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_dynamic_granularity` | bool | False | Enable automatic granularity selection |
| `enable_evidence_accumulation` | bool | False | Enable iterative evidence gathering |
| `accumulation_max_rounds` | int | 3 | Maximum retrieval rounds for accumulation |
| `accumulation_time_budget_sec` | float | None | Optional time budget for accumulation |
| `enable_evidence_chains` | bool | False | Enable evidence chain building |

### Metadata Fields

When enabled, features add these metadata fields to the result:

- `granularity_routing`: Query classification and routing decision
- `evidence_accumulation`: Accumulation statistics
- `evidence_chains`: Chain information and confidence scores

### Timing Information

Features add timing data to `result.timings`:

- `granularity_routing`: Time for query classification
- `evidence_accumulation`: Time for all accumulation rounds
- `evidence_chains`: Time for chain building

---

## Best Practices

1. **Start with granularity routing** - It's lightweight and improves retrieval quality with minimal overhead

2. **Use evidence accumulation for complex queries** - Best for queries that may require information from multiple sources

3. **Enable evidence chains for transparency** - Useful when you need to show users how conclusions were reached

4. **Combine features thoughtfully** - All three can be used together, but each adds latency

5. **Set time budgets in production** - Use `accumulation_time_budget_sec` to prevent runaway retrieval

6. **Monitor metadata** - Check the metadata fields to understand feature behavior and tune parameters

---

## Performance Considerations

| Feature | Latency Impact | When to Use |
|---------|---------------|-------------|
| Dynamic Granularity | Minimal (~5ms) | Always recommended |
| Evidence Accumulation | Moderate (depends on rounds) | Complex research queries |
| Evidence Chains | Moderate (~100-500ms) | When transparency needed |

All features are designed to fail gracefully - if any component fails, the pipeline continues with default behavior.
