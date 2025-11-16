# Chatbooks Product Requirements Document

- **Document Owner:** tldw_server core team (product + backend)
- **Last Updated:** 2025-11-16
- **Status:** In progress (v1 metadata-complete exports live; v2 large-binary bundling planned)

---

## 1. Purpose & Vision

Chatbooks provide a portable, trustworthy backup format for all user knowledge assets across conversations, notes, characters, world books, prompts, media artifacts, embeddings, and evaluations. The feature enables safe migration between deployments (self-hosted instances, future SaaS, collaborative spaces) while preserving relationships, metadata, and replayability. Chatbooks support the tldw vision of a personal research assistant by letting users curate “books” of their learning journeys to archive or share.

## 2. Problem Statement

- Users accumulate high-value knowledge across disparate modules with no unified export/import story.
- Backups are manual and lossy; sharing curated knowledge with collaborators or secondary devices is cumbersome.
- Compliance and retention requests require auditable exports and structured deletion.
- Teams need a repeatable way to package curated context for downstream LLM workflows without exposing entire databases.

## 3. Goals

1. Deliver a single workflow that exports selected assets with a manifest-driven structure and associated binary artifacts (v1: metadata-complete exports with references for large media; v2: full large-binary bundling).
2. Provide import tooling that respects ownership, handles conflicts, and records provenance.
3. Offer synchronous (small) and asynchronous (large) flows usable via REST API, CLI/SDK, and WebUI.
4. Enforce quotas, validation, and security controls so operators can trust shared artifacts.
5. Expose job telemetry for monitoring and analytics.

v1 (GA) focuses on metadata-complete, replayable exports/imports for all supported content types, bundling only small/attached binaries (for example, chat image attachments). Full packaging of large media binaries (video/audio source files and other heavyweight artifacts) is a staged v2 goal and is reflected in the Implementation Status section.

**Current Limitation (v1):** Only small/attached binaries (for example, chat image attachments) are physically bundled into chatbooks. Large media assets (video/audio source files and other heavyweight artifacts) are referenced via metadata and must be re-hydrated from the source deployment or external storage. See Implementation Status & TODOs for the v2 large-binary bundling plan.

## 4. Non-Goals

- Real-time sync between instances (batch import/export only).
- In-place editing of chatbook contents.
- Collaborative library UX (per-user packaging is the current scope; team/org personas use per-user chatbooks plus admin-driven imports, not a shared global library).
- General-purpose ZIP ingestion beyond the chatbook schema.
- Automatic resolution of complex cross-tenant version conflicts outside supported strategies.
- Dedicated Chatbooks-level at-rest encryption; server-side encryption is handled by the underlying storage and deployment configuration. Server-managed, per-chatbook encryption keys are out of scope for this feature; client-side or password-protected archives remain under evaluation (see Open Question #3).

## 5. Target Users & Core Use Cases

| User Persona | Scenario |
| --- | --- |
| Knowledge Worker (solo researcher) | Snapshot an investigation (source media + transcripts + notes) for archive or device migration. |
| Team Facilitator (small group admin) | Curate a “primer” (prompts, conversations, world books) to distribute and re-import to a shared environment. |
| Field Analyst (air-gapped ops) | Prepare offline bundles containing prompts, summaries, embeddings for disconnected environments. |
| Compliance Officer / Admin | Satisfy data portability requests, demonstrate retention expiry, manage export audit logs. |

Team Facilitator and Compliance Officer / Admin personas operate within this per-user packaging model: shared/team/org scenarios are implemented via scoped exports/imports plus admin/owner overrides, not via a global shared chatbook library.

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
   - `GET /api/v1/chatbooks/export/jobs` and `GET /api/v1/chatbooks/import/jobs` - list jobs in the caller’s scope (per-user by default; admins/org owners/team leads can add org/team/user filters).
   - `GET /api/v1/chatbooks/export/jobs/{job_id}` and `/import/jobs/{job_id}` - inspect a single job.
   - `DELETE /api/v1/chatbooks/export/jobs/{job_id}` and `/import/jobs/{job_id}` - cancel in-flight jobs or mark completed jobs as deleted within the caller’s permitted scope.
   - `GET /api/v1/chatbooks/download/{job_id}` - serve completed exports; returns either a direct download or a signed URL (with `expires_at`, default 1 hour) depending on deployment mode.
   - `POST /api/v1/chatbooks/cleanup` - authenticated cleanup of expired exports/imports; standard users can clean up their own jobs, while team leads/org owners/admins can clean up within their scopes.
   - `GET /api/v1/chatbooks/health` - report storage readiness and service status.

   **Response shapes (high level)**
   - `POST /api/v1/chatbooks/export` (async): `{"job_id", "status", "mode": "async", "download_url"?, "expires_at"?, "estimated_size_bytes"?, "created_at"}`. For async exports, `download_url` and `expires_at` are only populated once the job reaches `completed` status.
   - `POST /api/v1/chatbooks/import` (async): `{"job_id", "status", "mode": "async", "created_at"}`.
   - `POST /api/v1/chatbooks/preview`: `{"manifest_version", "summary": {"counts": {per_type}, "estimated_size_bytes"?, "truncated_flags"?}}`.
   - `GET /api/v1/chatbooks/*/jobs`: `{"jobs": [...], "next_page_token"?}` with each job including `{"job_id", "kind": "export"|"import", "status", "created_at", "updated_at", "scope": {"user_id", "team_id"?, "org_id"?}}`. `status` is one of `pending`, `in_progress`, `completed`, `failed`, `cancelled`, `expired`, `deleted`.
   - `GET /api/v1/chatbooks/download/{job_id}`: either a ZIP file response or `{"download_url", "expires_at"}` when using signed URLs.

2. **Manifest Schema**
   - Versioned JSON (`manifest_version`) describing metadata, content entries, relationships, file references, locale/timezone, export provenance (user, time, app version). The canonical JSON Schema lives in `Docs/Schemas/chatbooks_manifest_v1.json`.
   - Content coverage: conversations (messages, attachments, citations), notes, characters, world books, dictionaries, prompts, media descriptors, generated documents, embeddings, evaluation runs.
   - Manifest entries include stable identity keys per content type and record conflict handling metadata (`conflict_strategy`, `source_instance_id`, `provenance`) so imports can apply `skip`/`overwrite`/`rename`/`merge` consistently.
   - Template-related metadata: the manifest reserves optional fields such as `metadata.template_mode`, `metadata.template_defaults`, `metadata.template_timezone`, and `metadata.template_locale` for content that participates in templating (for example, certain Chatbooks text fields and dictionaries). Their evaluation semantics and feature flags are defined in `Docs/Product/Chatbook-Tools-PRD.md` and must remain backward compatible across manifest versions.

   **Identity keys & merge semantics (v1)**

   | Content type | Identity key | `merge` behavior (v1) |
   | --- | --- | --- |
   | Conversations | `conversation_id` (UUID) | Append non-duplicate messages ordered by `created_at`; on message-id collisions, keep the existing message and import the conflicting message as a new revision with provenance. |
   | Notes | `note_id` (UUID) | Add imported note content as a new revision; existing title/body remain, with imported content available in revision history. |
   | Characters & World Books | `character_id` / `worldbook_id` (UUID) | Union tags/metadata; preserve existing core fields, attach imported description as an additional revision/version with provenance. |
   | Prompts | `prompt_id` (UUID or slug) | Union tags and test cases; existing prompt body wins on field conflicts, imported body stored as an alternate/prior revision. Slug-based `prompt_id` values are treated as soft identifiers: when conflicts are ambiguous, imports fall back to `rename` behavior to avoid destructive merges. |
   | Media & Generated Docs | `media_id` / `doc_id` (UUID) | Union tags and metadata; maintain references to additional transcripts/derivatives without dropping existing ones. |
   | Embeddings | `embedding_set_id` + `source_hash` | Union vectors; duplicates by `embedding_id` (a stable, per-vector identifier generated by the embeddings subsystem and preserved across exports/imports) are skipped with per-vector warnings. |
   | Evaluations | `evaluation_id` (UUID) | Union evaluation runs up to export caps; duplicates detected via `run_id` are skipped with per-run warnings. |

   For content types not listed or where safe merging is ambiguous, `merge` behaves like `rename` by default (the imported entity is created with a new identifier and provenance).

   **Conflict strategies (high level)**

   - `skip`: When a conflict is detected for a given identity key, the existing entity is left unchanged and the conflicting imported entity is omitted, with a per-item warning recorded in job results.
   - `overwrite`: The conflicting imported entity replaces the existing entity’s mutable fields for that identity key (for example, prompt body, character/world book description, note content), while preserving audit history and provenance where available.
   - `rename`: The conflicting imported entity is created as a new entity with a new identifier (and, where applicable, a disambiguated human-readable name/slug) while preserving all imported metadata and provenance.
   - `merge`: Applies per-type semantics as described in the identity/merge table above; where `merge` is unsupported or ambiguous for a type, it degrades to `rename`.

3. **Storage & Security**
   - Per-user directories under `TLDW_USER_DATA_PATH` (default `/var/lib/tldw/user_data/users/<id>/chatbooks/{exports,imports,temp}`) with sanitized names and 0700 permissions.
   - HMAC-signed download URLs (`CHATBOOKS_SIGNED_URLS`, `CHATBOOKS_SIGNING_SECRET`); in `AUTH_MODE=multi_user` or when org features are enabled, signed URLs are required and default to enabled with 1-hour expiry (`expires_at`), extendable by privileged roles up to a configured maximum.
   - Access control ensures users interact only with their own jobs/files by default; team leads can act on their team, org owners on their org, and admins across all users, with all cross-user operations emitting audit events including actor and target scopes. Imported entities are always materialized under the importing user’s account; at higher scopes, organizations are considered owners of all team and user artifacts within their hierarchy, and teams own artifacts created by their members.
   - Cleanup and cross-user job operations (`POST /api/v1/chatbooks/cleanup`, job deletion for other users, org- or team-wide listing) are always authenticated and subject to these role scopes to avoid unbounded cleanup scans or job enumeration.
   - Export archives are retained for a configurable period (`CHATBOOKS_EXPORT_RETENTION_DEFAULT_HOURS`, default 24h); after retention, archives are removed and jobs transition to `expired` while metadata is retained for audit unless explicitly deleted.

4. **Job Processing**
   - Export/import jobs persisted in each user’s ChaChaNotes DB with states `pending → in_progress → completed|failed|cancelled|expired|deleted`.
   - `expired` indicates archives removed by retention/cleanup while metadata remains for audit; `deleted` indicates job metadata removed by privileged cleanup operations.
   - Async processing via core Jobs worker by default; optional Prompt Studio JobManager adapter when `CHATBOOKS_JOBS_BACKEND=prompt_studio`. Cross-scope listings (for example, org-wide views) are backed by an index over per-user job records or by fan-out queries with batching; for large orgs, operators should expect eventual consistency and slightly higher latencies for these aggregated views.
   - Lease renewal and retry semantics align with core Jobs standards.

5. **Validation & Quotas**
   - ChatbookValidator applies file integrity checks, path sanitization, zip bomb protection, metadata bounds, and conflict detection.
   - For chat dictionaries embedded in chatbooks, the Chat dictionary validator (see `Docs/Product/Chatbook-Tools-PRD.md`) is invoked during `/api/v1/chatbooks/import` to perform schema, regex, and template validation. Its findings are surfaced via per-item warnings/errors in job results, and when `CHATBOOKS_IMPORT_DICT_STRICT=true`, dictionaries with fatal validation errors are skipped rather than imported while the rest of the chatbook continues to process.
   - QuotaManager enforces tier-based storage usage, daily operation limits, concurrent job caps, and per-file size caps. Errors are actionable and localized. Operators can further disable or restrict specific export/import content types (for example, evaluations or embeddings) via configuration/policy flags to meet local compliance requirements.
   - Missing or inconsistent references (for example, manifests referring to media or embeddings that are not present in the archive) are treated as validation errors and surfaced as per-item failures in job results rather than being silently dropped.
   - Evaluation exports respect a configurable per-run row cap (`CHATBOOKS_EVAL_EXPORT_MAX_ROWS`, default 200). When truncation occurs, both manifest entries and API responses flag `truncated: true` and record the applied `max_rows`.
   - Rate limiting (default 5 exports/minute and 5 imports/minute per user) via SlowAPI limiter; configurable overrides for privileged roles and service accounts.

## 8. Non-Functional Requirements

- **Security:** Reject malicious archives (zip bombs, traversal). Never expose absolute filesystem paths. Avoid logging sensitive data.
- **Reliability:** Async jobs recover from restarts (idempotent writes, lease renewal). Cleanup keeps storage bounded. Imports use a best-effort strategy with per-item status; partial failures are surfaced in job results instead of being silently dropped or rolled back wholesale.
- **Performance:** Sync exports limited to manageable payloads (<128 MB default). Async exports stream ZIP creation to prevent memory spikes. As a target SLO on a representative production profile (for example, 4 vCPU, SSD-backed storage, and local network), imports handle 10k+ items under 5 minutes using streaming I/O.
- **Observability:** Structured Loguru logs with job context; audit trail entries for compliance. Health endpoint reflects storage readiness. Metrics hooks (post-GA) capture throughput/failures (for example, `chatbooks_exports_total`, `chatbooks_imports_failed_total`, `chatbooks_export_bytes_total`).
- **Extensibility:** Adding content types requires updates to enums, schemas, service aggregators, and tests; manifest versioning ensures backward compatibility.

## 9. Dependencies & Integrations

- ChaChaNotes database for job tracking and content retrieval.
- Core Jobs infrastructure and optional Prompt Studio JobManager adapter.
- Media/storage subsystems for referenced artifacts.
- Authentication & authorization (user id, tier) for scoping quotas and access.
- Unified audit service for compliance logging.
- Environment configuration: `CHATBOOKS_*`, `TLDW_USER_DATA_PATH`, job tuning variables.

## 10. Success Metrics

1. ≥80% of active users with significant assets (>50 items) create at least one chatbook per quarter.
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

1. How should import warnings (renamed items, partial merges) be surfaced in the WebUI beyond basic job logs (for example, toasts vs detail views vs inline diffs)?
2. Do we need checksum verification across instances for compliance workflows, and if so, at what granularity (per-file vs per-chatbook)?
3. For optional client-provided encryption (password-protected archives), what UX/API and key management approach do we want, given that server-managed Chatbooks encryption is out of scope?


## 14. Next Steps

1. Circulate this PRD for stakeholder review (backend, security, product).
2. Update the document’s “Last Updated” date and publish to internal knowledge base once approved.
3. Track open questions as backlog issues and prioritize for upcoming sprints.

## 15. Implementation Status & TODOs

**What’s working now**
- Export pipeline pulls conversations (with image attachments persisted alongside messages), notes, characters, world books, dictionaries, generated docs, Prompt Studio prompts, media metadata (including transcripts, media-linked prompts, optional vector embeddings), and evaluation definitions with associated runs.
- Manifest schema and API responses expose per-type statistics for prompts, media, evaluations, and derived embeddings, keeping external contracts aligned with the feature scope.
- Core Jobs worker and FastAPI dependency flow pass numeric user ids into the service so per-user Prompts/Media/Evaluations databases can be resolved automatically, guarding multi-database exports against permission issues.

**To-Do items surfaced during implementation**
- Binary media payload export is still metadata-only; follow-up work is required to package large artifacts safely (streaming, quota-aware storage).
- Explicit embedding exports beyond media vectors remain pending; current builds only capture embeddings discovered while exporting media records.
- Evaluation run export is currently capped using `CHATBOOKS_EVAL_EXPORT_MAX_ROWS` (default 200 rows per run); add pagination/continuation support for long-running experiments and expose continuation tokens via the API.
- Conversation citation metadata is stubbed until upstream storage lands; revisit once citations are persisted in ChaChaNotes.
- Import flows for prompts, media, evaluations, and derived embeddings need parity with the new export surface (conflict handling, quota application, validation).
