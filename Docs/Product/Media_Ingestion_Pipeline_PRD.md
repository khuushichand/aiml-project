# Media Ingestion Pipeline PRD (Remaining Work)

Status: Stage 3+ roadmap in progress
Owner: Core Maintainers
Audience: Backend & infrastructure contributors
Last Updated: 2026-02-09

## 1. Scope Split
- Completed/shipped scope has been split into: `Docs/Product/Completed/Media_Ingestion_Pipeline_Completed_PRD.md`.
- This document now tracks only remaining product and engineering work.
- Baseline assumptions (validation pipeline, persistence contracts, Stage 1/2 scaling work) are considered already delivered.

## 2. Summary
- **Problem:** The ingestion foundations are now stable, but higher-order automation and quality loops are still incomplete.
- **Need:** Move from "reliable ingestion" to "self-improving ingestion" with agentic follow-ups, structured summaries/highlights, and quality remediation feedback.
- **Outcome Target:** Ingestion outputs should be immediately useful for downstream retrieval and analyst workflows without manual cleanup.

## 3. Remaining Goals
1. Add agentic ingestion workflows that derive and execute follow-up fetch/parse actions from initial media.
2. Persist built-in summaries and highlights alongside media versions with deterministic provenance.
3. Add inline quality scoring and remediation suggestions for failed or low-confidence ingestion runs.
4. Harden streaming transcript partial persistence from initial implementation to full lifecycle support.

## 4. Non-Goals
- Re-implementing Stage 0/1/2 ingestion foundations already in production.
- Replacing Media DB v2 as the core content store.
- Redesigning Resource Governor policy model (remaining work must integrate with existing governor).
- Building a new vector-store architecture (covered by RAG/Collections PRDs).

## 5. Current Baseline (Assumed Complete)
- Core upload/url validation and processor routing are in place.
- Collections/watchlists dual-write bridge and embeddings dispatch contract are in place.
- Async ingestion jobs and queue-based heavy processing routing are in place.
- Postgres parity hardening and Resource Governor ingestion budgeting are in place.
- Structure-index writes and OCR/VLM chunk parity are in place.
- Initial streaming transcript partial/final persistence snapshots are available in `/api/v1/audio/stream/transcribe` (opt-in).

## 6. Remaining Functional Requirements
1. **Agentic Follow-Up Execution:**
   - Ingestion MAY propose follow-up actions (fetch linked sources, enrich metadata, run domain-specific parsers).
   - Proposed actions MUST be policy-gated and attributable to initiating media/job context.
2. **Summary/Highlight Persistence:**
   - Ingestion MUST support writing generated summaries/highlights as versioned artifacts tied to `media_id` + version lineage.
   - Artifact generation failures MUST be non-fatal unless explicitly configured as required.
3. **Quality Scoring + Remediation:**
   - Ingestion MUST produce structured quality assessments (completeness, parse confidence, chunk integrity, downstream handoff health).
   - Low-score runs SHOULD emit actionable remediation hints (retry strategy, parser switch, input normalization guidance).
4. **Streaming Persistence Hardening:**
   - Extend initial WS transcript persistence to full operational lifecycle (session continuity, stronger metadata linkage, retry/idempotency behavior, and clearer operator visibility).
   - Maintain fail-open behavior so persistence errors do not kill active streams.

## 7. Roadmap (Remaining)
### Stage 3A - Agentic Ingestion Workflows
- Auto-derive follow-up fetches from source metadata/content signals.
- Add domain-specific pipeline profiles (e.g., research articles, media bundles, threaded sources).
- Ensure action plans are auditable and Resource Governor-compatible.

### Stage 3B - Built-in Summary/Highlight Artifacts
- Produce summaries/highlights during or immediately after ingestion.
- Store artifacts with provenance and version linkage.
- Surface artifact availability to downstream retrieval/UX modules.

### Stage 3C - Quality Scoring + Remediation
- Compute quality scores for success and degraded outcomes.
- Attach remediation suggestions to ingest/job result payloads.
- Add dashboards/diagnostics for recurring failure classes.

### Stage 3D - Streaming Transcript Persistence Completion
- Expand from initial snapshot persistence to stronger lifecycle semantics.
- Improve model/media/session metadata normalization and operational observability.
- Add parity tests for edge/failure/recovery paths.

## 8. Dependencies and Integration Points
- **Jobs + Scheduler:** Use existing orchestration pathways; avoid introducing parallel queue/governor infrastructure.
- **Resource Governor:** All new ingestion automation must consume existing budget and concurrency controls.
- **Media DB v2 + Collections:** Persist new artifacts through existing DB abstractions and lineage models.
- **RAG/Search:** Summary/highlight/quality artifacts must integrate with existing retrieval pipelines.
- **AuthNZ + Audit:** Agentic actions and quality annotations must remain permission-aware and auditable.

## 9. Remaining Metrics
- Agentic follow-up generation rate and completion success rate.
- Summary/highlight artifact generation success, latency, and retrieval usage.
- Quality score distribution by media type and processor.
- Remediation suggestion acceptance/effectiveness indicators.
- Streaming transcript persistence reliability (attempted vs persisted snapshots, fail-open events).

## 10. Risks and Mitigations
- **Risk:** Agentic actions increase blast radius for bad inputs.
  - **Mitigation:** policy gates, strict provenance, conservative default action scopes.
- **Risk:** Summary/highlight artifacts drift from source truth.
  - **Mitigation:** provenance fields, version pinning, optional regeneration workflows.
- **Risk:** Quality scoring becomes noisy and ignored.
  - **Mitigation:** tie scores to concrete remediation guidance and measurable downstream outcomes.
- **Risk:** Streaming persistence introduces instability.
  - **Mitigation:** retain fail-open semantics, idempotent writes, and targeted regression tests.

## 11. Open Questions (Remaining)
1. What policy model should govern which agentic follow-up actions are auto-executed vs queued for approval?
2. Where should summary/highlight artifacts live for best retrieval parity: Media DB extensions, existing analysis fields, or dedicated artifact records?
3. What minimum quality score taxonomy is actionable without overwhelming operators?
4. How should streaming transcript persistence expose progress and consistency guarantees to API consumers?

## 12. References
- Completed scope: `Docs/Product/Completed/Media_Ingestion_Pipeline_Completed_PRD.md`.
- Ingestion code: `tldw_Server_API/app/core/Ingestion_Media_Processing/`.
- Database: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`.
- Collections & Watchlists: `Docs/Product/Content_Collections_PRD.md`, `Docs/Product/Watchlist_PRD.md`.
- Infrastructure: `Docs/Product/Infrastructure_Module_PRD.md`.
- Related plans: `Docs/Design/Ingest-Plan-1.md`, `Docs/Design/RAG_Plan.md`.
