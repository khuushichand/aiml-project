# Chatbooks Product Requirements Document

- **Document Owner:** tldw_server core team (product + backend)
- **Last Updated:** 2025-05-?? (update when publishing)
- **Status:** In progress (implementation tracking below)

---

## 1. Purpose & Vision

Chatbooks provide a portable, trustworthy backup format for all user knowledge assets across conversations, notes, characters, world books, prompts, media artifacts, embeddings, and evaluations. The feature enables safe migration between deployments (self-hosted instances, future SaaS, collaborative spaces) while preserving relationships, metadata, and replayability. Chatbooks support the tldw vision of a personal research assistant by letting users curate “books” of their learning journeys to archive or share.

## 2. Problem Statement

- Users accumulate high-value knowledge across disparate modules with no unified export/import story.
- Backups are manual and lossy; sharing curated knowledge with collaborators or secondary devices is cumbersome.
- Compliance and retention requests require auditable exports and structured deletion.
- Teams need a repeatable way to package curated context for downstream LLM workflows without exposing entire databases.

## 3. Goals

1. Deliver a single workflow that exports selected assets with a manifest-driven structure and associated binary artifacts.
2. Provide import tooling that respects ownership, handles conflicts, and records provenance.
3. Offer synchronous (small) and asynchronous (large) flows usable via REST API, CLI/SDK, and WebUI.
4. Enforce quotas, validation, and security controls so operators can trust shared artifacts.
5. Expose job telemetry for monitoring and analytics.

## 4. Non-Goals

- Real-time sync between instances (batch import/export only).
- In-place editing of chatbook contents.
- Collaborative library UX (per-user packaging is the current scope).
- General-purpose ZIP ingestion beyond the chatbook schema.
- Automatic resolution of complex cross-tenant version conflicts outside supported strategies.

## 5. Target Users & Core Use Cases

| User Persona | Scenario |
| --- | --- |
| Knowledge Worker (solo researcher) | Snapshot an investigation (source media + transcripts + notes) for archive or device migration. |
| Team Facilitator (small group admin) | Curate a “primer” (prompts, conversations, world books) to distribute and re-import to a shared environment. |
| Field Analyst (air-gapped ops) | Prepare offline bundles containing prompts, summaries, embeddings for disconnected environments. |
| Compliance Officer / Admin | Satisfy data portability requests, demonstrate retention expiry, manage export audit logs. |

## 6. User Journeys

- **Export:** Select assets via WebUI or API (filters, tags, time range). Receive synchronous download for small sets or asynchronous job reference with download URL and expiry for large sets.
- **Import:** Upload chatbook, preview manifest, choose conflict strategy (`skip`, `overwrite`, `rename`, `merge`), monitor job status, inspect imported items with provenance notes.
- **Preview:** Inspect manifest without writing to storage; validate before import.
- **Job Management:** List, inspect, or cancel export/import jobs; download completed exports; trigger cleanup of expired archives.

## 7. Functional Requirements

1. **Endpoints**
   - `POST /api/v1/chatbooks/export` - accepts metadata, filters, sync/async flag; returns file (sync) or job reference (async) with download URL + expiry.
   - `POST /api/v1/chatbooks/import` - accepts upload, conflict strategy, async option; records warnings/errors per item.
   - `POST /api/v1/chatbooks/preview` - validates archive and returns manifest summary without persisting data.
   - `GET/DELETE /api/v1/chatbooks/export/jobs[/id]` and `/import/jobs[/id]` - list, inspect, cancel jobs.
   - `GET /api/v1/chatbooks/download/{job_id}` - serve completed exports with optional signed URL.
   - `POST /api/v1/chatbooks/cleanup` - remove expired exports from storage.
   - `GET /api/v1/chatbooks/health` - report storage readiness and service status.

2. **Manifest Schema**
   - Versioned JSON describing metadata, content entries, relationships, file references, locale/timezone, export provenance (user, time, app version).
   - Content coverage: conversations (messages, attachments, citations), notes, characters, world books, dictionaries, prompts, media descriptors, generated documents, embeddings, evaluation runs.

3. **Storage & Security**
   - Per-user directories under `TLDW_USER_DATA_PATH` (default `/var/lib/tldw/user_data/users/<id>/chatbooks/{exports,imports,temp}`) with sanitized names and 0700 permissions.
   - Optional HMAC-signed download URLs (`CHATBOOKS_SIGNED_URLS`, `CHATBOOKS_SIGNING_SECRET`).
   - Access control ensures users interact only with their own jobs/files; audit events emitted for key actions.

4. **Job Processing**
   - Export/import jobs persisted in ChaChaNotes DB with states `pending → in_progress → completed|failed|cancelled`.
   - Async processing via core Jobs worker by default; optional Prompt Studio JobManager adapter when `CHATBOOKS_JOBS_BACKEND=prompt_studio`.
   - Lease renewal and retry semantics align with core Jobs standards.

5. **Validation & Quotas**
   - ChatbookValidator applies file integrity checks, path sanitization, zip bomb protection, metadata bounds, and conflict detection.
   - QuotaManager enforces tier-based storage usage, daily operation limits, concurrent job caps, and per-file size caps. Errors are actionable and localized.
   - Rate limiting (default 5 exports/minute) via SlowAPI limiter; configurable overrides for privileged roles.

## 8. Non-Functional Requirements

- **Security:** Reject malicious archives (zip bombs, traversal). Never expose absolute filesystem paths. Avoid logging sensitive data.
- **Reliability:** Async jobs recover from restarts (idempotent writes, lease renewal). Cleanup keeps storage bounded. Imports roll back or track partial writes safely.
- **Performance:** Sync exports limited to manageable payloads (<128 MB default). Async exports stream ZIP creation to prevent memory spikes. Imports handle 10k+ items under 5 minutes using streaming I/O.
- **Observability:** Structured Loguru logs with job context; audit trail entries for compliance. Health endpoint reflects storage readiness. Metrics hooks (post-GA) capture throughput/failures.
- **Extensibility:** Adding content types requires updates to enums, schemas, service aggregators, and tests; manifest versioning ensures backward compatibility.

## 9. Dependencies & Integrations

- ChaChaNotes database for job tracking and content retrieval.
- Core Jobs infrastructure and optional Prompt Studio JobManager adapter.
- Media/storage subsystems for referenced artifacts.
- Authentication & authorization (user id, tier) for scoping quotas and access.
- Unified audit service for compliance logging.
- Environment configuration: `CHATBOOKS_*`, `TLDW_USER_DATA_PATH`, job tuning variables.

## 10. Success Metrics

1. ≥80% of active users with significant assets (>N items) create at least one chatbook per quarter.
2. <1% export/import jobs fail due to system errors (excluding validation failures) over a rolling 30-day window.
3. Average async export throughput ≥50 MB/minute for bundles containing media attachments.
4. Chatbooks generated by the previous minor version import without manual fixes (manifest backward compatibility).
5. Quota enforcement support tickets <5 per quarter after general availability.

## 11. Rollout & Milestones

1. **Alpha (internal):** Enable sync export/import, collect feedback on manifest completeness, instrument audit logging, manual worker startup.
2. **Beta (selected users):** Async jobs via core worker, enforce quotas, optional signed URLs, WebUI tab gating, docs in `/Docs`.
3. **General Availability:** Prompt Studio job adapter, automated cleanup, policy toggles, default worker enabled, CLI documentation, CI integration tests.
4. **Post-GA Enhancements:** Collaborative chatbooks, delta exports, scheduled backups, analytics dashboards, packaging for third-party ingestion.

## 12. Risks & Mitigations

- **Large archives exhaust storage:** Enforce quotas, stream ZIP outputs, provide cleanup endpoints, allow operator tuning.
- **Corrupt/malicious imports:** Layered validation, processing in sandboxed temp directories, preview-first workflow.
- **Async job starvation:** Lease renewal, per-user concurrency caps, jitter/backoff, monitoring dashboards.
- **Backward compatibility drift:** Manifest semantic versioning, migration helpers, contract tests.
- **User confusion on scope:** Clear WebUI copy and API docs, actionable error messages referencing quotas and filters.

## 13. Open Questions

1. Should signed URLs be mandatory for multi-user deployments?
2. How should import warnings (renamed items, partial merges) be surfaced in the WebUI?
3. Should export retention periods vary by user tier (current default 24h)?
4. Do we need checksum verification across instances for compliance workflows?
5. Should chatbooks support optional client-provided encryption (password-protected archives)?

## 14. Next Steps

1. Circulate this PRD for stakeholder review (backend, security, product).
2. Update the Doc’s “Last Updated” date and publish to internal knowledge base once approved.
3. Track open questions as backlog issues and prioritize for upcoming sprints.

## 15. Implementation Status & TODOs

**What’s working now**
- Export pipeline pulls conversations (with image attachments persisted alongside messages), notes, characters, world books, dictionaries, generated docs, Prompt Studio prompts, media metadata (including transcripts, media-linked prompts, optional vector embeddings), and evaluation definitions with associated runs.
- Manifest schema and API responses expose per-type statistics for prompts, media, evaluations, and derived embeddings, keeping external contracts aligned with the feature scope.
- Core Jobs worker and FastAPI dependency flow pass numeric user ids into the service so per-user Prompts/Media/Evaluations databases can be resolved automatically, guarding multi-database exports against permission issues.

**To-Do items surfaced during implementation**
- Binary media payload export is still metadata-only; follow-up work is required to package large artifacts safely (streaming, quota-aware storage).
- Explicit embedding exports beyond media vectors remain pending; current builds only capture embeddings discovered while exporting media records.
- Evaluation run export is capped at the first 200 rows; add pagination/continuation support for long-running experiments.
- Conversation citation metadata is stubbed until upstream storage lands; revisit once citations are persisted in ChaChaNotes.
- Import flows for prompts, media, evaluations, and derived embeddings need parity with the new export surface (conflict handling, quota application, validation).
