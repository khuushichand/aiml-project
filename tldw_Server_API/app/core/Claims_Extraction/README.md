# Claims_Extraction

## 1. Descriptive of Current Feature Set

- Purpose: Extract and verify factual claims from generated answers and optionally overlay them into RAG streaming responses for grounding and citations.
- Capabilities:
  - LLM-based claim extraction with strict JSON parsing and safe fallbacks
  - Heuristic sentence extractor; optional NER-assisted mode; APS-style propositions via Chunking strategy
  - Hybrid verification: numeric/date heuristics, evidence retrieval, optional NLI, and LLM judge with citations and offsets
  - RAG integration: incremental claims overlay events during streaming
- Inputs/Outputs:
  - Input: model answer text, user query, candidate context documents (or a retrieve function)
  - Output: list of claims, per-claim verification labels (supported/refuted/nei), confidence, evidence snippets, citation offsets
- Related Endpoints:
  - Claims API: `tldw_Server_API/app/api/v1/endpoints/claims.py:1` (status, list, rebuild, rebuild_fts)
  - RAG streaming (claims overlay): `tldw_Server_API/app/api/v1/endpoints/rag_unified.py:1176`, `tldw_Server_API/app/api/v1/endpoints/rag_unified.py:1348`
- Related Engine/Libs:
  - Core engine: `tldw_Server_API/app/core/Ingestion_Media_Processing/Claims/claims_engine.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - ClaimsEngine.run(answer, query, documents, …) orchestrates extraction then verification.
  - Verification composes heuristics + optional retrieval + LLM judgment; citations computed via offset search.
- Key Classes/Functions:
  - `ClaimsEngine`, `LLMBasedClaimExtractor`, `HeuristicSentenceExtractor`, `HybridClaimVerifier` in `claims_engine.py`
  - RAG overlay publisher in `rag_unified.py` emits `claims_overlay` events during streaming
- Dependencies:
  - Internal: `Utils.prompt_loader`, `RAG.rag_service.types.Document`, optional `Chunking.strategies.propositions`
  - External (optional): `transformers` NLI pipeline; provider LLMs via unified analyze function
- Data Models & DB:
  - Claims persisted in per-user Media DB (tables `Claims`, FTS `claims_fts`); rebuild endpoints trigger maintenance
- Configuration (env/config.txt):
  - `CLAIMS_LLM_PROVIDER`, `CLAIMS_LLM_MODEL`, `CLAIMS_LLM_TEMPERATURE`; RAG fallbacks: `RAG.default_llm_provider`, `RAG.default_llm_model`
  - Tuning: `claims_top_k`, `claims_conf_threshold`, `claims_max`, `claims_concurrency` (request-level)
- Concurrency & Performance:
  - Async extract/verify; bounded `claims_concurrency`; lightweight numeric/date heuristics short-circuit
- Error Handling:
  - Robust JSON extraction with fenced-block detection and heuristic fallback; verifier falls back on base docs when retrieval fails
- Security:
  - No network calls unless a provider/NLI is configured; inputs validated; respects AuthNZ and RBAC at API layer

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - Engine: `app/core/Ingestion_Media_Processing/Claims/claims_engine.py`
  - API: `app/api/v1/endpoints/claims.py`
- Extension Points:
  - Add a new extractor (Protocol `ClaimExtractor`) or verifier (Protocol `ClaimVerifier`) and register in `ClaimsEngine`
  - Inject custom `retrieve_fn` for domain-specific evidence selection
- Coding Patterns:
  - Use loguru for diagnostics; prefer async boundaries; avoid raw SQL (use DB_Management)
- Related Tests:
  - `tldw_Server_API/app/api/v1/endpoints/claims.py:1` (integration tests should cover list/rebuild behaviors)
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/Claims/claims_engine.py:1` (unit tests for extraction/verifier; see tracker TODOs)
- Local Dev Tips:
  - Enable claims in RAG requests, set `claims_top_k`/`claims_max` to small values while iterating
- Pitfalls & Gotchas:
  - Citation offset computation is best-effort; guard against long contexts and partial matches
- Roadmap/TODOs:
  - Property-based tests for offsets and numeric/date heuristics; tighten FTS rebuild reporting
