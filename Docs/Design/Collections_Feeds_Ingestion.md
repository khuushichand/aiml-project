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
- Watchlists pipeline fetches RSS/site sources and upserts into Collections with origin `watchlist`.
  - Fetchers: `tldw_Server_API/app/core/Watchlists/fetchers.py`
  - Pipeline: `tldw_Server_API/app/core/Watchlists/pipeline.py`
- Collections data lives in `content_items` (per-user DB) with `origin`, `origin_type`, `origin_id`.
  - Adapter: `tldw_Server_API/app/core/DB_Management/Collections_DB.py`
- Items API supports filtering by `origin` for a unified list.
  - Endpoint: `tldw_Server_API/app/api/v1/endpoints/items.py`

## Phase 1: Feed ingestion wiring (polling)

### Origin override
Add an optional override key so RSS sources can land as `origin=feed` without changing existing watchlists defaults.

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
3. Items are deduped by `guid || url || title` in Watchlists "seen items".
4. Content is fetched from the article URL (or feed content if configured).
5. Collections upsert uses:
   - `origin = collections_origin` (default `watchlist` or overridden `feed`)
   - `origin_type = src.source_type` (rss or site)
   - `origin_id = src.id`
6. Embeddings enqueue metadata includes `origin` for downstream traceability.

### Minimal feed subscription model
Reuse Watchlists sources for subscriptions. A "Collections Feeds" UI/endpoint can create RSS sources with:
- `source_type="rss"`
- `settings_json.collections_origin="feed"`
- `tags` for topic categorization
- Optional `settings_json.history` for backfill behavior

## Phase 2: WebSub (push)
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
- Subscribe/unsubscribe endpoint validates callback URL, avoids SSRF, stores pending subscription.
- Background job performs hub verification using `hub.challenge`.
- On notification, parse feed payload and upsert items through the same pipeline path.
- Validate `X-Hub-Signature` when `secret` is present.

## Phase 3: Email ingestion (newsletters)
Support "email -> content_items" using a mailbox or inbound webhook.

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
2. Parse message (subject, from, html/text, attachments).
3. Store attachments in `file_artifacts` and link them in metadata.
4. Upsert content_items with:
   - `origin="email"`
   - `origin_type="newsletter"`
   - `origin_id = email_inboxes.id`
   - metadata: sender, message-id, subject, tags, source_identity_id
5. Dedupe on message-id + inbox id, with fallback to hash of body.

## Phase 4: Webhook ingestion
Add a generic inbound source that writes to Collections with `origin="webhook"`.

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
- Validate signature, size, and content-type.
- Normalize payload into title/summary/content.
- Upsert content_items with `origin="webhook"`, `origin_type="alert"`.

## Source identity tracking
To support "emails from kevin@gmail.com about X" and "alerts from webhook X":
- Use `source_identities` keyed by `(type, key, topic)` to track sender identity.
- Store `source_identity_id` in content_items metadata for grouping and filtering.
- Tags can capture the higher-level topic or newsletter name.

## Security and abuse controls
- Enforce URL allowlists for feed fetching (existing RG checks).
- Validate WebSub callbacks: scheme, hostname, and avoid local/private ranges.
- Verify HMAC signatures on WebSub notifications and webhooks.
- Cap email and attachment sizes; sanitize HTML before storing.
- Do not log secrets (email tokens, webhook secrets).

## Testing plan (Phase 1)
- Unit test: `collections_origin` override yields `origin="feed"` for RSS sources.
- Existing Watchlists tests remain unchanged because default origin is still `watchlist`.

## Reference patterns from "Kill the Newsletter" (MIT)
These are useful implementation references for later phases:
- SMTP ingestion + attachment parsing and storage (email -> entries with enclosures).
- Atom feed rendering (self/hub links, enclosures, icon) and HTML entry views.
- WebSub verification flow: hub.challenge, callback validation, signature support.
- UI patterns for feed settings (title, icon, delete confirmation) and copy-to-clipboard UX.

