# Implementation Plan: HCI Review - API Key & Secret Management

## Scope

Pages: `app/api-keys/`, `app/byok/`, `app/users/[id]/api-keys/`
Finding IDs: `3.1` through `3.6`

## Finding Coverage

- `3.1` (Important): API key page is just a user directory, not a key management hub
- `3.2` (Important): No key expiration warnings or hygiene indicators
- `3.3` (Important): No per-key usage metrics (request count, error rate, last used)
- `3.4` (Important): BYOK page lacks per-user cost attribution
- `3.5` (Nice-to-Have): No bulk key rotation capability
- `3.6` (Nice-to-Have): "Validation sweep" button disabled with no ETA

## Key Files

- `admin-ui/app/api-keys/page.tsx` -- User directory listing for key navigation
- `admin-ui/app/byok/page.tsx` -- BYOK dashboard (resolution mix, missing creds, org keys, activity)
- `admin-ui/app/users/[id]/api-keys/` -- Per-user API key management
- `admin-ui/lib/api-client.ts` -- API methods including key CRUD, rotate, audit-log

## Stage 1: Unified Key List with Usage Metrics

**Goal**: Transform the `/api-keys` page from a user directory into a true key management hub.
**Success Criteria**:
- `/api-keys` page shows a flat table of all API keys across all users.
- Columns: Key ID (truncated), Owner (username + link), Created, Last Used, Status (active/revoked/expired), Request Count (24h), Error Rate (24h).
- Filterable by: owner, status, age (created before date).
- Searchable by key prefix or owner username.
- Each row links to per-user key detail for management operations.
- Existing per-user key management pages remain accessible via user detail.
- Data sourced from new aggregate endpoint or client-side aggregation of per-user key lists.
**Tests**:
- Unit test for unified key table rendering with mixed statuses.
- Unit test for filter/search combinations.
- Test for graceful handling when usage metrics are unavailable.
**Status**: Complete

## Stage 2: Key Hygiene Indicators + Expiration Warnings

**Goal**: Help admins identify keys that need attention (old, unused, approaching expiration).
**Success Criteria**:
- Key rows show age badge: green (<90 days), yellow (90-180 days), red (>180 days).
- Keys with expiration dates show countdown badge: "Expires in X days" (yellow <30d, red <7d).
- Keys unused for >30 days show "Inactive" warning badge.
- Dashboard-level summary: X keys need rotation, Y keys expiring soon, Z keys inactive.
- Optional "Key Hygiene Score" card on `/api-keys` page header (similar to security risk score pattern).
**Tests**:
- Unit tests for age badge calculation and color thresholds.
- Unit tests for expiration countdown formatting.
- Unit tests for hygiene score calculation.
**Status**: Complete

## Stage 3: BYOK Cost Attribution + Bulk Operations

**Goal**: Give admins visibility into per-user BYOK costs and enable batch key management.
**Success Criteria**:
- BYOK page adds "Per-User Usage" tab or section showing: user, provider, requests, tokens, cost (USD) for each BYOK key.
- Data sourced from LLM usage telemetry (`/admin/llm-usage` logs, with `/admin/llm-usage/summary` acceptable when grouping supports required dimensions) and cross-referenced with BYOK key configuration.
- Bulk key rotation: select multiple keys from unified list, click "Rotate Selected", confirmation dialog, batch rotation.
- "Validation sweep" button either implemented (runs key validity check across all BYOK keys and reports results) or removed from the UI to avoid dead functionality.
**Tests**:
- Unit test for per-user BYOK usage table rendering.
- Unit test for bulk rotation selection + confirmation flow.
- Unit test for validation sweep results display (if implemented).
**Status**: Complete

## Dependencies

- Stage 1 may require a new backend endpoint `GET /admin/api-keys` (aggregate across users) unless client-side aggregation of `GET /admin/users` + per-user key fetches is acceptable for small deployments.
- Stage 2 key age/expiration data must be available from existing key objects (`created_at`, `expires_at` fields).
- Stage 3 BYOK cost correlation requires joining BYOK resolution metrics with LLM usage data; this may need a dedicated backend endpoint or client-side join.
