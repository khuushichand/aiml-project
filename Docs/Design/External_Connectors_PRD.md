# External Connectors (Google Drive, OneDrive, Notion, Dropbox)
Product Requirements Document (PRD)

Status: In Progress v0.2 • Owner: tldw_server • Target: v0.2.x

## 1. Summary
Add “Import from external sources” so users can connect third-party providers (Google Drive, Microsoft OneDrive, Notion, Dropbox) to ingest documents and media into tldw_server. Support one-off imports initially and evolve to continuous sync with delta tokens and webhooks (deferred to v2). Keep provider specifics behind a clean connector abstraction, integrate with existing ingestion pipeline, and provide job visibility with robust error handling.

## 2. Goals and Non-Goals
### Goals
- Users connect provider accounts via OAuth and manage connections per user.
- Users register sources (folders, pages, databases, shared links) to import.
- One-off imports for selected sources with progress and error reporting.
- Continuous sync (phase 2): delta tokens/webhooks to keep content up-to-date.
- Normalize provider files into ingestion-ready bytes/streams with metadata.
- Dedup/versioning to avoid re-processing unchanged items.
- Secure token storage, rate limiting, and observability.

### Non-Goals (v1)
- Full WebUI polish (basic flows are enough to start).
- Universal support for every provider feature (start with core file/page types).
- Cross-account sharing management UI (respect provider permissions only).
- Full export fidelity for rich docs (acceptable defaults with clear trade-offs).

## 3. Personas and Use Cases
- Researcher: Import PDFs, docs, and notes from Google Drive/Notion into a project.
- Team member: Keep a shared folder synced for ongoing meeting notes and reports.
- Individual learner: One-off import a course folder from OneDrive.

Primary use cases:
- Connect account, pick a folder/page, run a one-off import.
- Enable continuous sync to reflect upstream edits/new files.
- Monitor job status, errors, and last sync time.
- Revoke account and remove cached tokens.

## 4. Scope (v1) and Out-of-Scope
### In-Scope (v1)
- Providers: Google Drive and Notion (priority); OneDrive and Dropbox planned for v2.
- OAuth flows; secure token storage; token refresh; basic account list/remove.
- Source registration (folder/page/db) with simple options (recursive, filters).
- One-off import jobs; progress, status, and error surfaces.
- Normalize content to bytes/streams; default exports constrained to Markdown, TXT, and PDF. Notion exports to Markdown; Google Slides export to PDF (for better text extraction); Google Docs export to TXT; Sheets export to CSV (treated as text). (DOCX/HTML→MD optional later.)
- Dedup by provider + external_id + version/hash/modified timestamp.

- Webhooks and delta-based continuous sync (explicitly deferred to v2).
- Advanced export controls (fine-grained per-type mappings beyond defaults).
- Complex org admin features (multi-tenant enterprise policies).

## 5. Functional Requirements
1) Account connections
- Start OAuth with provider; complete callback; store access/refresh tokens and expiry.
- List user’s connected accounts; remove/revoke connection.

2) Source management
- Add a “source” (folder/page/database or shared link) tied to an account.
- Options: recursive (bool), include_types (e.g., pdf, docx, md), exclude_patterns (glob), export_format_overrides (map).
- Enable/disable source; view last_synced_at and basic metadata.

3) Import jobs (v1)
- Trigger one-off import for a source; enqueue background job; show status and progress.
- Download files/pages, perform required exports, attach metadata, and pass to ingestion pipeline. For PDFs and Slides→PDF, extract text via existing PDF pipeline (Docling preferred, PyMuPDF4LLM fallback).
- Dedup: skip items unchanged since last ingest; configurable max items per job.

4) Sync (v2)
- Maintain provider delta token/cursor per source.
- Webhook subscriptions where supported; fallback to scheduled polling.
- Soft delete on remote deletion; update on modification.

5) Status and observability
- Job detail: status, progress_pct, counts (processed, skipped, failed), errors sample.
- Per-source last_synced_at, last_job_id, last_error.

6) Security and auth
- Encrypt tokens at rest; redact sensitive logs.
- Scope accounts to user_id (multi-user) or API key (single-user).
- Rate limiting per provider and per user.

## 6. Non-Functional Requirements
- Reliability: At-least-once ingestion; idempotent job execution.
- Performance: Import 500 small files (<50 MB each) under 10 minutes on typical network; stream large files with chunking.
- Resilience: Exponential backoff with jitter on provider errors; circuit breaker per provider.
- Observability: Loguru logs, job metrics, error contexts; no telemetry or data collection.
- Configurability: Provider client IDs/secrets via .env or Config_Files; per-job limits via config.

## 7. User Flows (v1)
1) Connect account
- User requests auth URL → browser OAuth → callback stores account → success response.

2) Register source
- User lists provider tree/pages via API, selects folder/page/db, sets options, saves source.

3) Run import
- User triggers one-off import for source → background job → monitor via job endpoint.

4) Review results
- Imported items appear in search and content listings as usual; job shows summary.

5) Revoke
- User deletes account; tokens removed; sources disabled.

## 8. API Design (v1)
Base prefix: `/api/v1/connectors`

- GET `/providers` → list supported providers and scopes
- POST `/providers/{provider}/authorize` → { auth_url }
  - Body: { redirect_uri (optional), scopes (optional) }
- GET `/providers/{provider}/callback` → stores account, returns `ConnectorAccount`.
  - Query: code, state
- GET `/accounts` → list `ConnectorAccount[]` for current user.
- DELETE `/accounts/{account_id}` → revoke and delete tokens; disable its sources.
- GET `/providers/{provider}/sources/browse` → provider-specific listing for selection (folders/pages/databases).
  - Query: `account_id`, `parent_remote_id` (optional)
- POST `/sources` → create `ConnectorSource`
  - Body: { account_id, provider, remote_id, type, path/name, options }
- PATCH `/sources/{source_id}` → update options; enable/disable.
- GET `/sources` → list sources for current user.
- POST `/sources/{source_id}/import` → create import job; returns `ImportJob`.
- GET `/jobs/{job_id}` → job status/details.
- GET `/admin/policy` (admin) → org policy
- PUT `/admin/policy` (admin) → upsert org policy

Schemas (outline):
- ConnectorProvider(name, auth_type, scopes_required)
- ConnectorAccount(id, provider, display_name, created_at, connected)
- ConnectorSource(id, account_id, provider, remote_id, type, path, options, enabled, last_synced_at)
- SyncOptions(recursive: bool, include_types: list[str], exclude_patterns: list[str], export_format_overrides: dict)
- ImportJob(id, source_id, type, status, progress_pct, counts, started_at, finished_at, error)

## 9. Data Model (SQLite default)
Tables under DB_Management (exact implementation via existing abstractions):

- external_accounts
  - id (pk), user_id, provider (enum), display_name, access_token (encrypted), refresh_token (encrypted), token_expires_at (ts), scopes (text/json), created_at, updated_at

- external_sources
  - id (pk), account_id (fk), provider, remote_id, type (folder/page/db/link), path (text), options (json), enabled (bool), last_synced_at (ts), last_job_id (fk nullable)

- external_sync_state (v2)
  - source_id (pk/fk), delta_token (text), last_cursor (text), last_synced_at (ts)

- Jobs
  - Use the existing unified Jobs manager (domain = "connectors") instead of a dedicated `external_jobs` table; job payload contains `source_id` and `user_id`.

- external_items (cache for dedup)
  - id (pk), source_id (fk), provider, external_id, name, mime, size, modified_at, version, hash, last_ingested_at, content_ref (fk to media item if available)

Notes
- Encrypt tokens using an application secret (e.g., Fernet). Never log tokens.
- Use MediaDatabase and existing DB abstractions for operations; no raw SQL in endpoints.

## 10. Ingestion Integration
- Normalize items to a stream + metadata:
  - metadata: provider, external_id, name, mime, size, modified_at, path, parents, version, hash, source_id
- Call existing ingestion pipeline (`app/core/Ingestion_Media_Processing/`) exactly as local files.
- Dedup strategy: skip if unchanged vs last entry in `external_items` (by version/hash/modified_at).

## 11. Sync and Eventing (v2)
- Google Drive: `changes.list` with `pageToken`; `changes.watch` for push.
- OneDrive: `/delta` endpoints; Graph subscriptions for webhooks.
- Dropbox: `files/list_folder` with cursor; account-level webhook.
- Notion: incremental by `last_edited_time` (no universal delta token). Poll by window.
- Background service consumes webhook events or runs periodic polling jobs to enqueue sync tasks.

## 12. Provider Details and Export Defaults
- Google Drive
  - Files API v3.
  - Export defaults (aligned to org policy allowing Markdown, TXT, PDF):
    - Google Docs → TXT (text/plain)
    - Google Sheets → CSV (treated as text)
    - Google Slides → PDF (then extract text)
  - Shared drives listing supported when scopes allow (supportsAllDrives/includeItemsFromAllDrives).
- OneDrive (Microsoft Graph)
  - `/me/drive` or site drives; delta with `/delta`.
- Notion
  - Retrieve pages/blocks; export as Markdown with assets; databases → each row page.
- Dropbox
  - Direct files; shared links when scopes allow.

## 13. Error Handling, Limits, and Backoff
- Per-provider throttler; exponential backoff with jitter on 429/5xx.
- Chunked downloads for large files; retry with resume when supported.
- Job timeouts; partial progress saved; clear error messages.
- Configurable quotas: max files per job, max concurrent jobs per user/provider.

## 14. Security & Privacy
- All tokens encrypted at rest; minimum scopes required; secrets from `.env` or `Config_Files`.
- Multi-user: accounts and sources strictly scoped to `user_id`.
- No telemetry. Logs redact PII/secrets; include provider request IDs when possible.
- CORS and auth modes respected; rate limits enforced at endpoints.

## 14.1 Org-Level Settings & Governance
- Policy model
  - Org-level policy defines which providers are enabled, allowed export formats (defaults: Markdown, TXT, PDF), allowed file types/mime categories, max file size, and quotas (max files per job, max concurrent jobs per user/provider).
  - Role gates: which roles/users are allowed to connect accounts and run imports (e.g., Admin-only account linking; Members can run imports).
  - Account constraints: allowed email domains for provider accounts (e.g., `@company.com` only), optional allowlist/denylist for provider scopes.
  - Resource constraints: optional allowlist/denylist for remote paths/Notion workspace IDs.

- Enforcement
  - Endpoints validate requests against policy; reject disallowed providers, file types, oversize files, or disallowed roles with clear errors.
  - Jobs enforce allowed export formats (md/txt/pdf), allowed file types/mime categories, maximum file size; apply include/exclude patterns; skip items that violate policy and record reasons.
  - In single_user mode, treat org policy as global config from `.env`/`Config_Files`; in multi_user mode, store in DB and evaluate per tenant/org.

- Administration
  - Admin APIs to read/update policy (e.g., `/api/v1/connectors/admin/policy`), audited via existing logging.
  - Policy changes take effect for new jobs; running jobs keep previous limits unless marked interruptible.

## 15. Configuration
Environment variables (examples):
- CONNECTOR_DRIVE_CLIENT_ID / CONNECTOR_DRIVE_CLIENT_SECRET
- CONNECTOR_MS_CLIENT_ID / CONNECTOR_MS_CLIENT_SECRET
- CONNECTOR_NOTION_SECRET (internal token for Notion OAuth or integration secret)
- CONNECTOR_DROPBOX_CLIENT_ID / CONNECTOR_DROPBOX_CLIENT_SECRET
- CONNECTOR_REDIRECT_BASE_URL
- CONNECTOR_DEFAULT_EXPORTS (json)
- CONNECTOR_JOB_LIMITS (json)
- ORG_CONNECTORS_ENABLED_PROVIDERS (csv or json)
- ORG_CONNECTORS_ALLOWED_EXPORT_FORMATS (default: md,txt,pdf)
- ORG_CONNECTORS_ALLOWED_FILE_TYPES (csv/json of mime/file extensions)
- ORG_CONNECTORS_MAX_FILE_SIZE_MB
- ORG_CONNECTORS_ALLOWED_ACCOUNT_DOMAINS (csv)
- ORG_CONNECTORS_ACCOUNT_LINKING_ROLE (e.g., admin, owner)

Defaults (seed):
- ORG_CONNECTORS_ENABLED_PROVIDERS=drive,notion
- ORG_CONNECTORS_ALLOWED_EXPORT_FORMATS=md,txt,pdf
- ORG_CONNECTORS_ACCOUNT_LINKING_ROLE=admin
- ORG_CONNECTORS_MAX_FILE_SIZE_MB=500

## 16. Testing Strategy
- Unit tests: connector adapters (mock SDKs), token refresh, exporters, dedup logic.
- Integration tests: OAuth callback flow (fake), import job through ingestion pipeline with fixtures.
- Property-based: path filters, exclude patterns, idempotency.
- Markers: `unit`, `integration`, `external_api` (skipped unless creds present).

Initial tests implemented (v0.2):
- Policy unit tests for file-type/mime allow rules.
- Notion export unit test covering nested blocks, code fences, and tables.
- Worker traversal test for Drive recursion (fake connector; stubbed DB/media writes).

## 17. Rollout Plan
Phase 1 (v1)
- Core connectors module, endpoints, DB tables.
- Google Drive and Notion: one-off import.
- Basic WebUI screens (connect, pick, import, job status).
 - Org-level policy (minimum): enable/disable providers; allowed export formats (md/txt/pdf); allowed file types; max file size; who can connect accounts.

Phase 2 (v2)
- OneDrive and Dropbox support.
- Delta tokens and webhook subscriptions; background sync service.
- Deletion handling and versioned updates.

Phase 3 (v3)
- Export customization UI, richer job dashboards, admin controls.

## 18. Success Metrics
- Adoption: % of users with ≥1 connected account; # of sources created.
- Reliability: job success rate ≥ 98%; <1% reprocessing due to dedup misses.
- Performance: median time to import 100 files < 3 min.
- User satisfaction: fewer than 2% of jobs end with error.

## 19. Acceptance Criteria (v1)
- Users can connect Drive and Notion accounts and see them listed.
- Users can register at least one folder (Drive) or page/database (Notion) as a source.
- One-off import processes files/pages into the ingestion pipeline with metadata.
- Dedup prevents re-ingesting unchanged items in subsequent imports.
- Job status exposes progress and errors; logs contain actionable info without secrets.
- Tokens are stored encrypted; removing an account deletes tokens and disables sources.
- Admins can configure org policy to enable/disable providers, restrict export formats to Markdown/TXT/PDF, restrict allowed file types and max file size, and restrict who can link accounts; policy is enforced at API endpoints and during job execution.

Implementation status (v0.2 - partial):
- Endpoints, DB tables, and worker processing for Drive + Notion (one-off import) merged.
- Drive: shared drives listing enabled; recursive traversal implemented when `options.recursive=true`.
- Exports: Slides→PDF, Docs→TXT, Sheets→CSV; PDF text extraction integrated.
- Notion: nested Markdown export for headings, lists, code blocks, tables, images (basic).
- Policy: allowed providers, export formats, file types/mimes, max file size, per-role daily job quota; enforced on submit and during import.
- UI: basic Next.js routes (`/connectors`, `/connectors/browse`, `/connectors/sources`, `/connectors/jobs`) and basic WebUI tab at `/webui/tabs/connectors.html`.

Outstanding (next):
- OAuth token refresh + persistence; retry on 401 then persist refreshed tokens.
- Account email/domain enforcement at callback (Drive profile email; Notion workspace id) per org policy.
- Backoff/retry on 429/5xx; streaming large downloads; per-minute throttling.
- Jobs UI list/detail; endpoints to list user connector jobs.

## 20. Open Questions
- Priority providers to ship first (default: Drive + Notion)?
- Default export formats for Google Docs/Slides/Sheets and Notion pages?
- v1 scope: one-off import only, or minimal continuous sync for Drive?
- Where to store OAuth client secrets in production (per-deployment policy)?
- Data retention for `external_items` cache (how long; per-user purge controls)?

## 21. Decision Log
- 2025-10-27: Start with Drive + Notion, one-off imports, encrypted tokens, dedup by (provider, external_id, version/hash/modified). Continuous sync deferred to v2. Default allowed exports limited to Markdown, TXT, and PDF. Introduce org-level governance for provider enablement, export/file type restrictions, quotas, and role-based account linking.

## 22. Appendix: Export Mappings (defaults)
- Google Docs → PDF (docx optional)
- Google Sheets → CSV
- Google Slides → PDF
- Notion Pages → Markdown + assets
- OneDrive/Dropbox → original file type
