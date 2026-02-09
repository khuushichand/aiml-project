## Chatbooks Export/Import — Implementation Plan

This plan tracks staged implementation for Chatbooks export/import as specified in `Docs/Product/Chatbooks_PRD.md`. Each stage lists goals, success criteria, and concrete test notes. Update **Status** as work progresses.

> **Last reviewed:** 2026-02-08 — Statuses corrected to reflect incremental delivery; Stage 3 split into sub-stages; dependency annotations and GA-priority classifications added.

---

## Cross-Cutting Dependencies

The following dependencies affect multiple stages and should be tracked centrally:

| Dependency | Affects | Status |
|---|---|---|
| ChaChaNotes citation storage (upstream) | Stage 3b (citation import) | **Export complete** — citation export already works via `rag_context` in `chatbook_service.py:2981-3021`; import still blocked on ChaChaNotes upstream |
| Chatbook-Tools dictionary validator API surface | Stage 3b (dictionary import validation) | **Blocked** — depends on Chatbook-Tools implementation |
| AuthNZ org/team hierarchy stability | Stages 3b, 4, 5 (multi-tenant scoping) | **In progress** — current implementation is single-user scoped; multi-tenant operations deferred |
| `chatbook_service.py` monolith refactoring | Stage 3b (adding more import handlers) | **Recommended** — split into `chatbook_export_service.py` and `chatbook_import_service.py` before adding remaining import content-type handlers |

---

## GA-Priority Classification

Items are classified to help prioritize remaining work:

- **GA-blocking**: Required before general availability release
- **Post-GA**: Desirable but can ship after GA
- **Deferred**: Explicitly deferred pending external decisions or dependencies

| Item | Priority | Stage |
|---|---|---|
| Import parity for prompts and media | GA-blocking | 3b |
| `overwrite` conflict strategy | GA-blocking | 3c |
| Fix stale status tracking (this document) | GA-blocking | N/A (done) |
| ~~Warn users when unsupported import types are silently skipped~~ | **Complete** — endpoint already rejects unsupported types with HTTP 400 (see `chatbooks.py:480-500`) | 3a |
| Import parity for evaluations, embeddings, generated docs | Post-GA | 3b |
| `merge` conflict strategy (full per-type semantics) | Post-GA | 3c |
| Evaluation continuation tokens | Post-GA | 2 |
| Full metrics registry (histograms) and SLO validation | Post-GA | 5 |
| Structured audit events for all operations | Post-GA | 5 |
| Large binary bundling | Post-GA | 6 |
| Client-side encryption | Deferred | 7 |
| Multi-tenant scoped operations (org/team) | Post-GA | Cross-cutting |
| Citation metadata export | **Complete** — already functional in `chatbook_service.py` | 2 |
| Citation metadata import | Blocked (ChaChaNotes upstream) | 3b |

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

**Status**: **Completed** — 15 endpoints, manifest schema, job lifecycle all working.

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

**Resolved dependency**: Citation metadata export is already functional via per-message `rag_context` extraction at `chatbook_service.py:2981-3021`. No upstream work needed for export.

**Implementation note**: Evaluation continuation tokens that append to the same chatbook ZIP add significant complexity (reopening/appending streaming ZIPs, updating manifest in-place). Consider a simpler alternative for v1: linked chatbook exports (separate ZIPs with a shared `export_id`) rather than appending to the same ZIP. Full append-to-same-ZIP can be a post-GA enhancement.

**Stage 2 Sub-task Checklist**:
- [x] Citation metadata export (already complete)
- [x] Binary limits extension to media embeddings
- [x] ChromaDB collection-level embedding export
- [x] Truncation metadata consistency (media capping + standardized format)
- [x] Evaluation continuation export (linked chatbooks)
- [x] Implementation plan status update

**Status**: **Complete**

---

## Stage 3a: Import Framework (Core Pipeline)
**Goal**: Establish the import/preview endpoint framework, validator, quota manager, and basic conflict resolution (`skip` + `rename`).

**Checklist** (all done):
- [x] `POST /api/v1/chatbooks/import` endpoint accepting v1 archives
- [x] `POST /api/v1/chatbooks/preview` endpoint returning manifest summary without persisting
- [x] ChatbookValidator wired for file integrity, path sanitization, zip-bomb protection, reference consistency
- [x] QuotaManager enforcing tier-based storage, daily operation limits, concurrent job caps, per-file size caps
- [x] `skip` conflict strategy working across all currently-supported import types
- [x] `rename` conflict strategy working across all currently-supported import types
- [x] Import handlers for: conversations, notes, characters, world books, dictionaries
- [x] Per-item outcomes and warnings returned in job results

**Tests**:
- Unit: ChatbookValidator scenarios (zip bombs, traversal attempts, missing references); quota checks with mocked tiers; `skip` and `rename` conflict resolution for each supported type.
- Integration: import + preview of valid and invalid archives; basic conflict-strategy tests for conversations/notes/characters/world books/dictionaries.

**Status**: **Completed**

---

## Stage 3b: Import Content-Type Parity
**Goal**: Add import handlers for the remaining content types so import coverage matches export coverage.

**Checklist**:
- [ ] Media descriptor import handler (with transcript/attachment rehydration)
- [ ] Prompt Studio prompt import handler
- [ ] Evaluation definition + run import handler
- [ ] Embedding set import handler
- [ ] Generated document import handler
- [x] ~~Return explicit warnings (not silent skips) when a user requests import of unsupported content types~~ — **Already implemented**: the import endpoint raises HTTP 400 listing unsupported types by name (see `chatbooks.py:480-500`); the inner service fallback at `chatbook_service.py:2091-2108` is defense-in-depth only and unreachable through the normal API
- [ ] Dictionary/templating validation from Chatbook-Tools wired into import (**blocked** on Chatbook-Tools validator)
- [ ] Content-type policy controls: operators can disable/restrict specific types via config flags

**Blocked dependencies**:
- Dictionary validation: depends on Chatbook-Tools implementation plan completion
- Citation metadata: depends on ChaChaNotes upstream storage

**Prerequisite recommendation**: Split `chatbook_service.py` (~5,354 lines) into `chatbook_export_service.py` and `chatbook_import_service.py` before adding more import handlers, to prevent further monolith growth.

**Tests**:
- Unit: import handler for each new content type; content-type policy flag handling; dictionary validator wiring and strict/non-strict behavior; explicit warning generation for unsupported types.
- Integration: import of archives with media/prompts/evaluations/embeddings/generated docs; enforcement of disabled content types; contract tests importing chatbooks generated by the previous minor version.

**Status**: **Not Started**

---

## Stage 3c: Advanced Conflict Resolution (`overwrite` + `merge`)
**Goal**: Implement the remaining conflict resolution strategies beyond `skip` and `rename`.

**Checklist**:
- [ ] `overwrite` strategy: imported entity replaces existing entity's mutable fields while preserving audit history and provenance
- [ ] `merge` strategy (simplified for v1 GA): append-only union with `rename` fallback on ambiguity — see PRD note on simplification
- [ ] Full per-type `merge` semantics as defined in the PRD identity/merge table (post-GA)

**Implementation notes**:
- `overwrite` is GA-blocking and should be straightforward — replace mutable fields, keep audit trail.
- Full `merge` semantics (per the PRD table) require a revision system in ChaChaNotes that doesn't currently exist for notes, characters, or prompts. For v1 GA, `merge` should behave as "append-only union with `rename` on ambiguity" — full revision-based merge is post-GA.
- Slug-based `prompt_id` fallback to `rename` is a policy decision that needs explicit test coverage.

**Tests**:
- Unit: `overwrite` conflict resolution per content type; simplified `merge` behavior; slug-based prompt fallback.
- Integration: conflict-strategy matrix across all content types including `overwrite` and `merge`; verification that `merge` degrades to `rename` for types where safe merging is ambiguous.

**Status**: **Not Started**

---

## Stage 4: Retention & Cleanup (Scheduled + Manual)
**Goal**: Implement scheduled retention cleanup plus manual cleanup triggering with scoped access control.

**Checklist**:
- [x] `POST /api/v1/chatbooks/cleanup` endpoint exists and triggers cleanup
- [x] `chatbooks_cleanup_service.py` runs on a configurable schedule
- [x] `expired` state transition works (completed → expired when archives removed)
- [x] Respects `CHATBOOKS_EXPORT_RETENTION_DEFAULT_HOURS`
- [ ] `deleted` state transition for privileged metadata removal
- [ ] Scoped access control: team leads clean their team, org owners clean their org, admins clean all
- [ ] Audit events emitted for cross-user cleanup operations
- [ ] Batching and scope filters to avoid unbounded scans in large deployments
- [ ] Cleanup handles orphaned temp files from failed/crashed export/import jobs

**Tests**:
- Unit: retention cutoff calculations; scope filters for cleanup; state transitions (`completed → expired`, `expired → deleted`); orphaned temp file detection.
- Integration: scheduled cleanup runs against test archives; manual cleanup endpoint for user/admin scopes; verification that expired archives are removed while metadata is retained unless explicitly deleted.

**Status**: **Partially Implemented** — core cleanup endpoint and scheduled service work; multi-tenant scoping, audit events, and orphan cleanup remain.

---

## Stage 5: Observability, Health & SLOs
**Goal**: Provide clear observability, health signals, and performance SLOs for Chatbooks jobs.

**Checklist**:
- [x] Health endpoint `GET /api/v1/chatbooks/health` reflects storage readiness
- [x] Counter metrics exist (`chatbooks_exports_total`, etc.)
- [x] Signed URL support (`CHATBOOKS_SIGNED_URLS`, `CHATBOOKS_SIGNING_SECRET`)
- [ ] Full metrics registry integration (histograms for latency, `chatbooks_export_bytes_total`, failure breakdowns)
- [ ] Structured log context (user/team/org scope, job_id, kind, status transitions) in all job operations
- [ ] Audit events emitted for cross-user operations
- [ ] Health endpoint checks: background worker availability, configuration sanity (signing secret when required)
- [ ] SLO validation on reference setup (async export throughput, import handling 10k+ items under 5 min)
- [ ] Documentation of target SLOs as reference benchmarks (not hard guarantees)

**Tests**:
- Unit: health check components (storage, worker connectivity) and metrics registration; log/audit helpers for job operations; signed URL HMAC generation and expiry handling.
- Integration: simulated job loads with exports/imports under various sizes; verification that health/metrics reflect backlogs and failures; cross-scope job listings remain within acceptable latency; spot checks that target SLOs are met on the reference environment.

**Status**: **Partially Implemented** — health endpoint (storage checks), counter metrics, and signed URL support work; full metrics registry, structured audit events, and SLO validation remain.

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

**Status**: **Not Started** (Post-GA)

---

## Stage 7: Optional Client-Side Encryption (TBD)
**Goal**: Track potential client-side/password-protected Chatbooks encryption without changing the server-managed encryption stance.

**Success Criteria**:
- Any adopted approach for client-provided encryption (for example, password-protected archives) is consistent with the PRD non-goal that server-managed, per-chatbook encryption keys remain out of scope.
- UX/API and key-handling responsibilities are clearly documented (client vs server), and import/export flows surface appropriate error messages when encrypted archives cannot be processed.
- Backwards compatibility is maintained: unencrypted Chatbooks continue to work as before, and encrypted Chatbooks are either supported explicitly or rejected with clear, non-ambiguous errors.

**Tests**:
- To be defined once Open Question #3 in `Docs/Product/Chatbooks_PRD.md` is resolved and a concrete design is selected.

**Status**: **Deferred** (pending resolution of PRD Open Question #3)
