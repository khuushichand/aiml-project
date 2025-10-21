# Claims Extraction & Analysis PRD

## 1. Background
- The ingestion pipeline optionally extracts factual statements from media chunks and stores them in `MediaDatabase.Claims`, with optional vector embeddings (`tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py`).
- The answer-time `ClaimsEngine` extracts and verifies claims for RAG outputs, providing supported/refuted/NEI labels, evidence, and citations (`tldw_Server_API/app/core/Ingestion_Media_Processing/Claims/claims_engine.py`).
- REST endpoints and a background rebuild worker expose lifecycle controls, while the front-end search page provides toggles for claim extraction and verification.

## 2. Problem Statement
Analysts and downstream automations need grounded, inspectable factual statements across ingested media and generated answers. The system already produces claims, but ownership requires a clear articulation of capabilities, dependencies, gaps, and roadmap to ensure reliable operation and future evolution.

## 3. Objectives & Success Criteria
- Maintain end-to-end claim extraction, storage, and verification for all enabled ingestion and RAG scenarios.
- Ensure ≥80% of processed media persist claims without manual intervention; rebuild jobs resolve the remainder.
- Deliver claim overlays and unsupported ratios in RAG responses with latency compatible with `claims_concurrency` defaults (8) and provider timeouts (≤8 s per extraction call).
- Provide operators APIs and UI controls to inspect, rebuild, and configure claims without direct DB access.

## 4. Out of Scope (v1)
- Manual review workflow (status updates, notes, audit trails).
- Automated veracity scoring beyond supported/refuted/NEI labels.
- Multilingual extraction/verification beyond existing English-centric models.
- External fact-check provider integrations or cross-media claim deduplication.
- Browser extension or export channels beyond existing chatbooks.

## 5. Personas & Key Use Cases
- **Research analyst**: Surface factual highlights from lengthy transcripts ahead of deep review.
- **RAG operator**: Enable claim overlays and unsupported metrics to monitor live answers and evaluations.
- **Platform admin**: Rebuild or inspect claims for maintenance without manual SQL.
- **Product engineer**: Wire claims into UI components, analytics, or exports using stable APIs.

## 6. Functional Requirements
### 6.1 Ingestion-Time Claims
- After chunking, extract up to `CLAIMS_MAX_PER_CHUNK` statements using configured mode (`heuristic`, `ner`, provider, or fallback) and store with chunk hashes (`tldw_Server_API/app/core/Ingestion_Media_Processing/Claims/ingestion_claims.py`).
- When `CLAIMS_EMBED` is enabled, upsert claim embeddings into a per-user Chroma collection with metadata linking to media/chunk/extractor (`tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py`).
- Soft-delete prior claims before inserting rebuilt sets to maintain version history.

### 6.2 Answer-Time Claims
- `ClaimsEngine.run` supports extractor modes (`auto`/LLM, `aps`, `ner`) and verifier strategies (`hybrid`, `nli`, `llm`) with evidence snippets, citations, confidence, and rationale.
- Expose configuration knobs through RAG requests (`enable_claims`, `claim_extractor`, `claims_top_k`, `claims_conf_threshold`, `claims_max`, `claims_concurrency`) and propagate to streaming overlays (`claims_overlay`, `final_claims` events).
- Support retrieval hooks so stored claims or additional documents can be used during verification.

### 6.3 Storage & Retrieval
- Maintain `Claims` schema (chunk index, extractor metadata, timestamps, versioning, soft-delete) plus SQLite/PostgreSQL FTS tables and triggers (`tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`).
- For SQLite, rebuild operations reset the virtual table with `INSERT INTO claims_fts(claims_fts) VALUES ('delete-all')` before repopulating to avoid the corruption seen with raw `DELETE` statements; rely on the provided API instead of manual SQL.
- Provide REST endpoint `GET /api/v1/claims/{media_id}` with optional envelope pagination, admin override (`user_id`), and absolute links.
- Deliver `POST` endpoints to rebuild single media, bulk media (`missing`, `all`, `stale` policies), and FTS indexes; expose `GET /status` for worker stats (`tldw_Server_API/app/api/v1/endpoints/claims.py`).

### 6.4 Background Rebuild & Automation
- `ClaimsRebuildService` queues rebuild tasks, chunks stored content, reapplies extraction, soft-deletes old rows, and logs counts (`tldw_Server_API/app/services/claims_rebuild_service.py`).
- Periodic loop in `main.py` optionally enqueues rebuilds based on `CLAIMS_REBUILD_*` settings, obeying single-user defaults until multi-user scheduling is implemented.

### 6.5 UI & Integrations
- Next.js search page exposes toggles for enabling claims, selecting extractor/verifier, confidence thresholds, and NLI model overrides (`tldw-frontend/pages/search.tsx`).
- Streaming RAG responses emit claim events when enabled, enabling clients to display overlays in real time (`tldw_Server_API/app/core/RAG/rag_service/generation.py`).

## 7. Non-Functional Requirements
- **Performance**: LLM extraction guarded by 8 s timeout; verification concurrency defaults to 8 with configurable upper bound to balance latency and provider costs.
- **Reliability**: Rebuild service logs successes/failures and maintains queue stats; ingestion path falls back to heuristics on extractor failures.
- **Security/Tenancy**: API endpoints require authenticated users; admin-only operations (`status`, cross-user rebuilds) enforce role checks and per-user DB isolation.
- **Observability**: Metrics expose unsupported claim ratio, totals, and verification durations (`tldw_Server_API/app/core/Metrics/metrics_manager.py`). Logs record ingest/rebuild outcomes for auditing.

## 8. Configuration
- `ENABLE_INGESTION_CLAIMS`, `CLAIM_EXTRACTOR_MODE`, `CLAIMS_MAX_PER_CHUNK`, `CLAIMS_EMBED`, `CLAIMS_EMBED_MODEL_ID`, `CLAIMS_LLM_PROVIDER`, `CLAIMS_LLM_MODEL`, `CLAIMS_LLM_TEMPERATURE`, `CLAIMS_LOCAL_NER_MODEL` (`tldw_Server_API/app/core/config.py`).
- `CLAIMS_REBUILD_ENABLED`, `CLAIMS_REBUILD_INTERVAL_SEC`, `CLAIMS_REBUILD_POLICY`, `CLAIMS_STALE_DAYS`, `SINGLE_USER_FIXED_ID` for periodic worker behavior.
- RAG request payload keys mirrored in UI to control claim extraction/verification per query.

## 9. Data Model
- Claims table stores: `media_id`, `chunk_index`, `span_start/end`, `claim_text`, `confidence`, extractor metadata, `chunk_hash`, `uuid`, timestamps, version, `client_id`, `deleted`.
- Indices: by media, media/chunk, UUID, deleted flag; SQLite triggers keep `claims_fts` synchronized.
- Optional vector store: `claims_for_{user}` Chroma collection with claim text embeddings and metadata.

## 10. Interfaces
- REST endpoints under `/api/v1/claims/*` for listing, rebuilding, FTS maintenance, and worker status.
- RAG APIs (`/api/v1/rag/search`, `/api/v1/rag/search/stream`) accept claim parameters and emit claim payloads in responses.
- UI controls in `tldw-frontend` reflect backend capabilities and persist query params for shareable URLs.

## 11. Instrumentation & Monitoring
- Metrics: `rag_nli_unsupported_ratio`, `rag_unsupported_claims_total`, `rag_postcheck_duration_seconds`, plus logs emitted by rebuild service and ingestion pipeline.
- Logging: structured messages during claim storage, rebuild outcomes, and extraction/verifier fallbacks for debugging.
- Future observability consideration: per-provider latency/cost tracking for claim-specific workloads.

## 12. Known Gaps & Risks
- No reviewer workflow or claim-level moderation; all claims remain unreviewed after storage.
- Multilingual support limited; spaCy default and prompts assume English.
- Evidence spans rely on heuristic matching and can misalign in longer documents.
- Cost control is limited to concurrency/timeout knobs; no per-job budget guardrails.
- Deduplication across media and watchlist-style analytics are not implemented.

## 13. Roadmap
1. Introduce reviewer states/notes and expose via API/UI to resolve unsupported claims.
2. Expand extractor catalog (multilingual heuristics, lightweight local LLMs) and scheduling heuristics.
3. Implement cross-media claim clustering/deduplication and integrate with watchlists/analytics.
4. Add richer monitoring (provider latency/cost dashboards) and adaptive throttling for rebuild jobs.
