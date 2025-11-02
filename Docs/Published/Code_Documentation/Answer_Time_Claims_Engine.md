# Answer-Time Claims Engine

## Overview

The Answer-Time Claims Engine extracts atomic claims from a generated answer and verifies each claim against evidence. It is intended for faithfulness checks, attribution, and analysis within RAG and evaluation pipelines.

Core module: `tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.claims_engine`

## Extraction

- Heuristic extractor: splits answer into sentence-like units (fast baseline).
- LLM extractor: prompts a provider to return strict JSON `{ "claims": [{ "text": "..." }] }`, with prompt overrides via `prompt_loader`.
- APS extractor: uses the Proposition Chunking strategy in LLM mode with the `gemma_aps` profile to produce atomic propositions (one per chunk).

Extractor selection (ClaimsEngine.run argument `claim_extractor`):
- `"aps"`: APS-style propositions via PropositionChunkingStrategy (LLM required).
- `"ner"`: NER-assisted extractor (spaCy). Selects sentences containing named entities; falls back to LLM if unavailable.
- any other (default): LLM JSON extractor with heuristic fallback.

Prompts (override via `Config_Files/Prompts/`):
- module=`ingestion` keys=`claims_extractor_system`, `claims_extractor_prompt`.
- module=`chunking` keys=`proposition_gemma_aps`, `proposition_claimify`, `proposition_generic`.

## Verification

Verifier: `HybridClaimVerifier` (per claim)
- Retrieval: uses provided `retrieve_fn(claim_text, top_k)` when available; otherwise uses passed `documents` (top_k default 5).
- Evidence selection: collects up to 3 snippets; boosts documents containing numbers/dates that appear in the claim.
- Strategy (`claim_verifier`):
  - `"hybrid"` (default): try NLI first; if unavailable/low-confidence, fall back to LLM judge.
  - `"nli"`: use only NLI; if unavailable or below threshold, return `nei` (no LLM fallback).
  - `"llm"`: skip NLI entirely and use only the LLM judge.
- NLI: local model (default `roberta-large-mnli`, override with `RAG_NLI_MODEL`/`RAG_NLI_MODEL_PATH`).
- LLM judge: calls the provided `analyze` function with a strict-JSON judging prompt to return `{ label, confidence, rationale }`.

## Output

`ClaimsEngine.run(...)` returns:
```json
{
  "claims": [
    {
      "id": "c1",
      "text": "...",
      "span": [s, e] | null,
      "label": "supported|refuted|nei",
      "confidence": 0.0,
      "evidence": [{"doc_id": "...", "snippet": "...", "score": 0.0}],
      "citations": [],
      "rationale": "..."
    }
  ],
  "summary": {
    "supported": 0,
    "refuted": 0,
    "nei": 0,
    "precision": 0.0,
    "coverage": 0.0,
    "claim_faithfulness": 0.0
  }
}
```

## Usage Example

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.claims_engine import ClaimsEngine
from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze

# Minimal Document type (id, content, score) - or use RAG types
class Doc:
    def __init__(self, id, content, score=0.0):
        self.id = id
        self.content = content
        self.score = score

answer = "Alice founded Acme in 2020. Bob joined in 2021."
query = "Who founded Acme and when?"
documents = [Doc("d1", "Acme was founded by Alice in 2020."), Doc("d2", "Bob joined Acme in 2021.")]

engine = ClaimsEngine(analyze)
result = await engine.run(
    answer=answer,
    query=query,
    documents=documents,
    claim_extractor="aps",           # or "auto" for LLM+heuristic fallback
    claims_top_k=5,
    claims_concurrency=8,
    claims_conf_threshold=0.7,
    claims_max=25,
    retrieve_fn=None,                # optional callable(claim_text, top_k)
    nli_model=None                   # optional override of NLI model id
)
print(result["summary"])
```

## Notes

- `claim_extractor="auto"` currently prefers the LLM extractor with heuristic fallback; APS requires an LLM.
- `claim_extractor="ner"` uses spaCy if available; configure model via `CLAIMS_LOCAL_NER_MODEL` (e.g., `en_core_web_sm`).
- NLI is attempted first for efficiency; the LLM judge runs only when NLI is unavailable or below confidence threshold.
- This engine is answer-time only; ingestion-time claims and API endpoints are documented separately.
