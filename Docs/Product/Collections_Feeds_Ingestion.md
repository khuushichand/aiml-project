# Collections Feeds + Ingestion Sources

## Summary
Introduce a first-class "feed" origin for Collections items by wiring RSS/Atom ingestion through the existing Watchlists pipeline, with optional overrides per source. Define a unified ingestion model that can later accept newsletters via email and arbitrary webhook sources while preserving per-source identity and dedupe behavior.

## Goals
- Ingest RSS/Atom feeds into Collections with origin `feed` when configured.
- Reuse Watchlists fetchers (ETag/Last-Modified, Retry-After, RFC5005 history) for polling.
- Provide a consistent source identity model so feed items, emails, and webhooks can be tracked uniquely.
- Keep future email ingestion and WebSub push support aligned with the same content_items schema.

## Non-Goals
- Publishing feeds or rendering HTML/Atom in this phase.
- Full UI/UX implementation for feed subscription management.
- Production SMTP server deployment in the first phase.

## Current State

### Watchlists + Collections pipeline (Phase 1 foundation)
- Watchlists pipeline fetches RSS/site sources and upserts into Collections with origin `watchlist`.
  - Fetchers: `tldw_Server_API/app/core/Watchlists/fetchers.py`
  - Pipeline: `tldw_Server_API/app/core/Watchlists/pipeline.py`
- Collections data lives in `content_items` (per-user DB) with `origin` (NOT NULL), `origin_type`, `origin_id`.
  - Adapter: `tldw_Server_API/app/core/DB_Management/Collections_DB.py`
  - Origin is a free-form string; recognized values: `"watchlist"`, `"feed"`, `"reading"`
- Items API supports filtering by `origin` for a unified list.
  - Endpoint: `tldw_Server_API/app/api/v1/endpoints/items.py`

### Email processing infrastructure (Phase 3 building blocks)
- **EML parsing library**: `tldw_Server_API/app/core/Ingestion_Media_Processing/Email/Email_Processing_Lib.py`
  - `parse_eml_bytes(file_bytes, filename)` extracts subject, from, to, cc, bcc, date, message_id, attachments, headers
  - `process_email_task(...)` produces normalized result dicts with content, metadata, optional chunks and LLM analysis
  - `process_eml_archive_bytes(...)` handles ZIP archives of EML files (max 100 files, 200 MB)
  - `process_mbox_bytes(...)` handles MBOX mailbox files
  - `process_pst_bytes(...)` handles PST/OST files via optional pypff library
- **Upload endpoint**: `POST /api/v1/media/process-emails` accepts EML/ZIP/MBOX/PST file uploads (no DB persistence; returns in-memory results)
  - Endpoint: `tldw_Server_API/app/api/v1/endpoints/media/process_emails.py`
- **Outbound email**: Workflows `email_send` adapter provides SMTP sending via `tldw_Server_API/app/core/Workflows/adapters/integration/email.py`
- **Newsletter templates**: `newsletter_markdown` and `newsletter_html` built-in templates in `tldw_Server_API/app/core/Watchlists/template_store.py`
- **Newsletter generation**: Workflows `newsletter_generate` adapter produces LLM-generated newsletters from content items

### Security infrastructure (Phase 2/4 building blocks)
- **Egress policy**: `tldw_Server_API/app/core/Security/egress.py`
  - `is_url_allowed(url)` validates URLs against allowlist/denylist and blocks private IP ranges
  - Blocks RFC 1918, RFC 4193, link-local, loopback, multicast, reserved ranges
  - DNS rebinding prevention: resolves hostname to IP before validation
  - Strict/permissive profiles configurable via `WORKFLOWS_EGRESS_PROFILE` env
- **Webhook URL validation**: `tldw_Server_API/app/core/Evaluations/webhook_security.py`
  - `WebhookSecurityValidator.validate_webhook_url(url, user_id)` with tiered security levels (permissive/standard/strict)
  - Checks: scheme, HTTPS requirement, hostname, port blocking, domain allow/block lists, path traversal, SSL certificate, connectivity
  - HMAC signature verification support
  - Per-user webhook registration limits

### Reading digests (downstream consumer)
- `tldw_Server_API/app/core/Collections/reading_digest_jobs.py` renders output templates from content_items
- Uses `origin="reading"` for its own items; template-based output (markdown/HTML)

---

## Phase 1: Feed ingestion wiring (polling) — COMPLETE

> **Status**: Implemented and tested.

### Origin override
Optional override key so RSS sources can land as `origin=feed` without changing existing watchlists defaults.

- Implemented in `_resolve_collections_origin()` at `pipeline.py:192-209`
- Source-level override (preferred):
  - `sources.settings_json.collections_origin = "feed"`
  - Or `sources.settings_json.collections.origin = "feed"`
- Job-level default override (fallback):
  - `scrape_jobs.output_prefs_json.collections_origin = "feed"`
  - Or `scrape_jobs.output_prefs_json.collections.origin = "feed"`
- Default remains `origin=watchlist` to avoid breaking current behavior/tests.

### Ingestion flow (polling)
1. Watchlists job selects RSS sources.
2. `fetch_rss_feed` or `fetch_rss_feed_history` runs with ETag/Last-Modified.
3. Items are deduped by `guid || url || title` in Watchlists "seen items" (`pipeline.py:775`).
4. Content is fetched from the article URL (or feed content if configured).
5. Collections upsert uses:
   - `origin = collections_origin` (default `watchlist` or overridden `feed`)
   - `origin_type = src.source_type` (rss or site)
   - `origin_id = src.id`
6. Embeddings enqueue metadata includes `origin` for downstream traceability.

Default polling cadence (implemented in `_maybe_promote_feed_schedule()` at `pipeline.py:212-276`):
- If `schedule_expr` is not provided at subscription time, a default hourly schedule (`0 * * * *`) is used.
- After 24 hours, the schedule auto-promotes to daily (cron `0 0 * * *`) unless manually overridden.
- Config stored in `job.output_prefs_json.collections_schedule` with keys: `mode`, `daily_expr`, `promote_after_hours`, `promoted`, `promoted_at`.

### Minimal feed subscription model
Implemented via `collections_feeds.py` endpoint:
- `POST /api/v1/collections/feeds` — create feed subscription
- `GET /api/v1/collections/feeds` — list feeds (pagination, query, tags)
- `GET /api/v1/collections/feeds/{feed_id}` — get single feed
- `PATCH /api/v1/collections/feeds/{feed_id}` — update feed
- `DELETE /api/v1/collections/feeds/{feed_id}` — delete feed

Creates RSS sources with `source_type="rss"` (auto-detected via URL pattern), `settings_json.collections_origin="feed"`, tags, optional history for backfill.

### Known limitations (Phase 1)
- **Empty dedupe key**: If an item has no guid, no link, and no title, the key becomes `""` and all such items collide. Consider adding a content-hash fallback.
- **Schedule promotion is silent**: `promoted_at` is stored but never surfaced to the user. No event or notification.
- **Feed content sanitization**: RSS `<content:encoded>` and `<description>` fields may contain malicious HTML/scripts. No sanitization is applied before storing.
- **No feed health tracking**: Repeated fetch failures don't trigger backoff, health status, or auto-disable.
- **No retention policy**: No item limits, age-based pruning, or per-user storage quotas.

### Tests
- `tldw_Server_API/tests/Collections/test_collections_feeds_api.py` — feed CRUD, origin override, schedule config
- `tldw_Server_API/tests/Watchlists/test_dedup_edge_cases.py` — per-source dedupe, mark/clear operations
- Existing Watchlists tests remain unchanged because default origin is still `watchlist`.

---

## Phase 2: WebSub (push) — NOT STARTED

Add a subscription table and callback endpoints to receive push updates from hubs.

### Suggested table (Collections or Watchlists DB)
`feed_websub_subscriptions`:
- id
- user_id
- source_id (watchlists source id)
- created_at
- callback
- secret
- last_verified_at

### Flow
- Subscribe/unsubscribe endpoint validates callback URL via existing egress checks (`Security/egress.py`).
- Background job performs hub verification using `hub.challenge`.
- On notification, parse feed payload and upsert items through the same pipeline path.
- Validate `X-Hub-Signature` when `secret` is present (reuse HMAC patterns from `Evaluations/webhook_security.py`).

### Security requirements
- Validate callback URLs using `is_url_allowed()` from `Security/egress.py` (blocks private IPs, supports allow/deny lists).
- HTTPS-only for callback URLs in production (strict egress profile).
- DNS rebinding prevention already handled by egress module.
- HMAC signature verification on all incoming notifications.

---

## Phase 3: Email ingestion (newsletters) — NOT STARTED

Support "email -> content_items" using a mailbox or inbound webhook.

### Existing infrastructure to reuse
- `Email_Processing_Lib.parse_eml_bytes()` already extracts subject, from, to, message_id, body, and attachments.
- `process_email_task()` produces normalized result dicts compatible with the media processing pipeline.
- Newsletter templates (`newsletter_markdown`, `newsletter_html`) exist for downstream rendering.
- Outbound email adapter (`email_send`) provides SMTP configuration patterns.

### Suggested tables
`email_inboxes`:
- id
- user_id
- public_id (local-part or alias)
- source_id (logical subscription record)
- allowed_senders_json (optional allowlist)
- tags_json
- created_at

`source_identities`:
- id
- user_id
- source_type ("email")
- source_key (normalized sender email)
- source_topic (newsletter/category)
- metadata_json

### Flow
1. Receive email (SMTP or provider webhook).
2. Parse message using existing `parse_eml_bytes()` (subject, from, html/text, attachments).
3. Store attachments in `file_artifacts` and link them in metadata.
4. Upsert content_items with:
   - `origin="email"`
   - `origin_type="newsletter"`
   - `origin_id = email_inboxes.id`
   - metadata: sender, message-id, subject, tags, source_identity_id
5. Dedupe on message-id + inbox id, with fallback to hash of body.

---

## Phase 4: Webhook ingestion — NOT STARTED

Add a generic inbound source that writes to Collections with `origin="webhook"`.

### Existing infrastructure to reuse
- `WebhookSecurityValidator` from `Evaluations/webhook_security.py` provides URL validation, security levels, and HMAC signature verification.
- `Security/egress.py` provides IP allowlist/denylist and private range blocking.

### Suggested tables
`webhook_sources`:
- id
- user_id
- public_id
- shared_secret
- allowed_ips_json
- tags_json
- created_at

### Flow
- Validate signature using existing `WebhookSecurityValidator` patterns (tiered security levels).
- Validate size (max payload size TBD — suggest 1 MB default, configurable) and content-type (JSON, form-urlencoded).
- Rate limit per webhook source (suggest 60 req/min default).
- Normalize payload into title/summary/content.
- Dedupe on idempotency key (client-provided) or content hash.
- Upsert content_items with `origin="webhook"`, `origin_type="alert"`.

---

## Source identity tracking

Cross-cutting concern for Phases 3 and 4. Consider introducing the `source_identities` table alongside whichever phase ships first.

To support "emails from kevin@gmail.com about X" and "alerts from webhook X":
- Use `source_identities` keyed by `(type, key, topic)` to track sender identity.
- Store `source_identity_id` in content_items metadata for grouping and filtering.
- Tags can capture the higher-level topic or newsletter name.

---

## Security and abuse controls
- Enforce URL allowlists for feed fetching (existing egress checks via `Security/egress.py`).
- Validate WebSub callbacks using `is_url_allowed()` — blocks private IP ranges, supports DNS rebinding prevention, enforces HTTPS in strict mode.
- Verify HMAC signatures on WebSub notifications and webhooks (reuse patterns from `Evaluations/webhook_security.py`).
- Cap email and attachment sizes; sanitize HTML before storing (applies to both feed content and email bodies).
- Rate limit inbound webhook sources.
- Do not log secrets (email tokens, webhook secrets).

---

## Testing plan

### Phase 1 (complete)
- Unit test: `collections_origin` override yields `origin="feed"` for RSS sources.
- Existing Watchlists tests remain unchanged because default origin is still `watchlist`.
- Dedupe edge case tests cover per-source tracking.

### Phase 1 gaps to fill
- Feed content sanitization (HTML in `<content:encoded>`).
- Empty dedupe key edge case.
- Feed health/error accumulation.

### Phase 2
- WebSub subscription creation and hub challenge verification.
- HMAC signature validation on incoming notifications.
- Callback URL validation (private IP blocking, HTTPS requirement).
- Push notification → content_items upsert pipeline.

### Phase 3
- Email parsing via existing `parse_eml_bytes()` → content_items upsert.
- Dedupe on message-id + inbox id.
- Sender allowlist enforcement.
- Attachment storage and metadata linking.

### Phase 4
- Webhook signature validation.
- Payload normalization.
- Rate limiting per source.
- Idempotency/dedupe.

---

## Reference patterns from "Kill the Newsletter" (MIT)
These are useful implementation references for later phases:
- SMTP ingestion + attachment parsing and storage (email -> entries with enclosures).
- Atom feed rendering (self/hub links, enclosures, icon) and HTML entry views.
- WebSub verification flow: hub.challenge, callback validation, signature support.
- UI patterns for feed settings (title, icon, delete confirmation) and copy-to-clipboard UX.
