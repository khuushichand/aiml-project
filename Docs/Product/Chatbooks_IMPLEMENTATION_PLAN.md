## Chatbooks Export/Import — Implementation Plan

This plan tracks staged implementation for Chatbooks export/import as specified in `Docs/Product/Chatbooks_PRD.md`. Each stage lists goals, success criteria, and concrete test notes. Update **Status** as work progresses.

---

## Stage 1: Core Export & Manifest v1
**Goal**: Ship metadata-complete Chatbooks exports with manifest v1 and job plumbing.

**Success Criteria**:
- `POST /api/v1/chatbooks/export` (sync + async) produces a ZIP containing a valid `manifest.json` conforming to `Docs/Schemas/chatbooks_manifest_v1.json`.
- `GET /api/v1/chatbooks/download/{job_id}` returns a ZIP for completed async exports (direct download when signed URLs are not required).
- Export pipeline covers the v1 scope: conversations (messages + image attachments), notes, characters, world books, dictionaries, generated docs, Prompt Studio prompts, media descriptors (including transcripts, media-linked prompts, optional media embeddings), and evaluation definitions with associated runs.
- Jobs are persisted per user in ChaChaNotes with states `pending → in_progress → completed|failed|cancelled|expired|deleted`, and `GET /api/v1/chatbooks/*/jobs` returns consistent job metadata and scopes.

**Tests**:
- Unit: manifest builder (per-type mappers and statistics), JSON Schema validation against `Docs/Schemas/chatbooks_manifest_v1.json`, job model/state transitions, per-user storage path construction (`USER_DB_BASE_DIR`, defined in `tldw_Server_API.app.core.config`; override via environment variable or `Config_Files/config.txt`).
- Integration: end-to-end export for a user with mixed content types; verification of manifest counts and identities; retry/export of large-but-metadata-only archives; download completed exports; listing jobs by user and (for admins) by team/org.

**Status**: Completed (per “What’s working now” in the PRD)

---

## Stage 2: Export Coverage Gaps & Bundling Policy (Embeddings, Evaluations, Citations)
**Goal**: Close outstanding export TODOs for embeddings, evaluation runs, conversation citation metadata, and per content-type bundling policy transparency.

**Success Criteria**:
- Embedding exports support explicit embedding sets beyond media-linked vectors, with stable `embedding_set_id` and `embedding_id` semantics preserved across export/import, and a defined `source_hash` based on normalized source payload, embedding model identifier, and chunking parameters.
- Evaluation exports add pagination/continuation support when `CHATBOOKS_EVAL_EXPORT_MAX_ROWS` is exceeded; continuation tokens are surfaced via API and captured in the manifest so clients can resume the same chatbook export instead of generating multiple chatbooks.
- Conversation citation metadata is exported once upstream storage lands in ChaChaNotes; manifest entries include citation references in line with the v1 schema.
- Manifest flags `truncated` and `max_rows` are populated consistently for any capped evaluation exports and are reflected both in manifest entries and API responses.
- Per content-type binary bundling limits are enforced during export and recorded in the manifest (for example, `metadata.binary_limits`) so clients can see the thresholds applied.

**Tests**:
- Unit: embedding-set selection and dedupe by `embedding_id`; evaluation run pagination and continuation token generation; per content-type bundling limit enforcement and manifest recording; citation serialization and schema validation.
- Integration: exports from users with large evaluation histories and multiple embedding sets; resumable evaluation exports appended to the same chatbook; verification that truncated exports are correctly marked and discoverable to clients.

**Status**: Not Started (open items listed under PRD “To-Do items surfaced during implementation”)

---

## Stage 3: Import Pipeline, Conflict Handling & Validation
**Goal**: Implement robust import/preview flows with conflict strategies, validation, quotas, and provenance.

**Success Criteria**:
- `POST /api/v1/chatbooks/import` and `POST /api/v1/chatbooks/preview` accept v1 archives, apply `skip` / `overwrite` / `rename` / `merge` consistently per content type, and return per-item outcomes and warnings without partial silent failures.
- Identity and ownership semantics match the PRD: imported entities are materialized under the importing user; organizations own artifacts across their teams/users; teams own artifacts created by their members; cross-scope imports respect role-based access controls.
- ChatbookValidator is wired into import/preview to enforce file integrity, path sanitization, zip-bomb protection, and reference consistency (no dangling media/embedding references without manifest entries).
- QuotaManager enforces Chatbooks-specific limits (tier-based storage, daily exports/imports, concurrent jobs, per-file caps), surfaces actionable errors, and respects overrides for privileged roles/service accounts.
- Content-type policy controls are respected: operators can disable or restrict specific export/import content types (for example, evaluations or embeddings) via configuration/policy flags, and those policies are enforced consistently across API flows.
- Dictionary/templating validation from `Docs/Product/Chatbook-Tools-PRD.md` is integrated into Chatbooks import: embedded dictionaries are validated, `ImportJob.warnings` populated, and `CHATBOOKS_IMPORT_DICT_STRICT` semantics honored without blocking entire imports on dictionary-only issues. This stage depends on the validator and API surface defined in the Chatbook-Tools implementation plan; Chatbooks-specific work focuses on wiring and verification.

**Tests**:
- Unit: conflict-resolution functions for each content type; ChatbookValidator scenarios (zip bombs, traversal attempts, missing references); quota checks with mocked tiers; content-type policy flag handling; dictionary validator wiring and strict/non-strict behavior.
- Integration: import + preview of valid and invalid archives; conflict-strategy matrix across conversations/notes/prompts/characters/media/evaluations/embeddings; org/team-scope imports with correct ownership and audit logging; enforcement of disabled content types in exports/imports; rate limits under load (RG policy configuration); contract tests importing chatbooks generated by the previous minor version.

**Status**: Not Started

---

## Stage 4: Retention & Cleanup (Scheduled + Manual)
**Goal**: Implement scheduled retention cleanup plus manual cleanup triggering with scoped access control.

**Success Criteria**:
- `POST /api/v1/chatbooks/cleanup` triggers cleanup for the caller's allowed scope, transitioning completed jobs to `expired` when archives are removed and to `deleted` when metadata is removed by privileged operations.
- Scheduled cleanup runs via the Chatbooks worker on a configurable interval, respects `CHATBOOKS_EXPORT_RETENTION_DEFAULT_HOURS`, and avoids unbounded scans through batching and scope filters.
- Cleanup emits audit events for cross-user operations and records per-job outcomes so operators can trace retention actions.

**Tests**:
- Unit: retention cutoff calculations; scope filters for cleanup; state transitions (`completed → expired`, `expired → deleted`).
- Integration: scheduled cleanup runs against test archives; manual cleanup endpoint for user/admin scopes; verification that expired archives are removed while metadata is retained unless explicitly deleted.

**Status**: Not Started

---

## Stage 5: Observability, Health & SLOs
**Goal**: Provide clear observability, health signals, and performance SLOs for Chatbooks jobs.

**Success Criteria**:
- Health endpoint `GET /api/v1/chatbooks/health` reflects storage readiness, background worker availability, and configuration sanity (for example, configured `USER_DB_BASE_DIR`, signing secret when required).
- Metrics are emitted for exports/imports (e.g., `chatbooks_exports_total`, `chatbooks_imports_failed_total`, `chatbooks_export_bytes_total`, latency histograms) and integrated into the existing metrics registry.
- Logs include structured job context (user/team/org scope, job_id, kind, status transitions) and audit events are emitted for any cross-user operations in line with the AuthNZ/audit modules.
- Signed download URLs (`CHATBOOKS_SIGNED_URLS`, `CHATBOOKS_SIGNING_SECRET`) work in multi-user/org modes; `GET /api/v1/chatbooks/download/{job_id}` returns either a ZIP file or a signed URL honoring `expires_at`, and this behavior is covered by metrics and logs.
- Performance targets from the PRD are validated on a reference setup (for example, ~4 vCPU, SSD-backed storage, local network) and documented as target SLOs (not hard guarantees for all deployments), including: async export throughput and import handling of 10k+ items under the stated time budgets.

**Tests**:
- Unit: health check components (storage, worker connectivity) and metrics registration; log/audit helpers for job operations; signed URL HMAC generation and expiry handling.
- Integration: simulated job loads with exports/imports under various sizes; verification that health/metrics reflect backlogs and failures; cross-scope job listings (large-org scenarios with many users/jobs) remain within acceptable latency; spot checks that target SLOs are met on the reference environment.

**Status**: Not Started

---

## Stage 6: Large Binary Bundling (v2)
**Goal**: Add optional large-binary packaging for media artifacts while preserving v1 compatibility.

**Success Criteria**:
- Async exports can optionally bundle large media binaries (video/audio source files and other heavyweight artifacts) into Chatbooks archives with streaming ZIP creation and quota-aware storage usage.
- Operators can configure whether large-binary bundling is enabled, and how retention/quota policies apply to these larger archives, without affecting v1 metadata-only behavior.
- Manifest versioning cleanly distinguishes v1 (metadata-only for large media) from v2 (optional large-binary bundling) with migration helpers and backward-compatibility guarantees for v1 archives.
- Import flows can rehydrate large media from bundled binaries when present, or fall back to existing metadata-only behavior when binaries are omitted, without changing ownership or provenance semantics.

**Tests**:
- Unit: streaming large-file writers, bundle-size accounting, and retention/quota calculations for large archives.
- Integration: exports/imports with mixed small attachments and large media binaries; verification of offline rehydration from a v2 Chatbook; compatibility tests confirming that v1-only manifests still import correctly after v2 is introduced.

**Status**: Not Started

---

## Stage 7: Optional Client-Side Encryption (TBD)
**Goal**: Track potential client-side/password-protected Chatbooks encryption without changing the server-managed encryption stance.

**Success Criteria**:
- Any adopted approach for client-provided encryption (for example, password-protected archives) is consistent with the PRD non-goal that server-managed, per-chatbook encryption keys remain out of scope.
- UX/API and key-handling responsibilities are clearly documented (client vs server), and import/export flows surface appropriate error messages when encrypted archives cannot be processed.
- Backwards compatibility is maintained: unencrypted Chatbooks continue to work as before, and encrypted Chatbooks are either supported explicitly or rejected with clear, non-ambiguous errors.

**Tests**:
- To be defined once Open Question #3 in `Docs/Product/Chatbooks_PRD.md` is resolved and a concrete design is selected.

**Status**: Deferred (pending resolution of PRD Open Question #3)
