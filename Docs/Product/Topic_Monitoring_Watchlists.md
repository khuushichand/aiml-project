# Topic Monitoring & Watchlists (Design)

Goal: Provide a configurable, privacy-respecting content monitoring feature that detects when specified topics are mentioned in user activity (chat input/output, ingestion, notes, RAG queries) and emits non-blocking alerts for admins/owners to review.

## Scope (Phase 1)
- Rule-based “watchlists” (literals/regex) with optional categories and severities.
- Scopes: global (all users), per-user; basic support for per-team and per-org when caller provides membership.
- Integration points: chat input and output; notes (create/update/bulk); RAG search (unified/simple/advanced). Hooks emit alerts but NEVER block content.
- Alert storage and retrieval API with mark-as-read.
- Admin endpoints to manage watchlists and list alerts.

## Non-Goals (Phase 1)
- Email/SMS/Slack/webhook delivery (planned in Phase 2).
- Real-time WS push to WebUI (planned in Phase 2).
- ML classifiers or external moderation APIs (local-first only for now).

## Requirements
- Opt-in and auditable: explicit configuration enabling; record the alert but do not alter the content flow.
- Safe by default: local regex engine, bounded scan length, DoS-safe pattern validation (re-use checks from ModerationService).
- Transparent: Admins can inspect effective configuration and rules.

## Data Model
- WatchlistRule
  - `pattern` (literal or `/regex/`)
  - `category` (e.g., `self_harm`, `adult`, `violence`, `custom`)
  - `severity` (`info|warning|critical`)
  - `note` (free-text)
  - Optional per-rule `tags` set

- Watchlist
  - `id`, `name`, `description`
  - `enabled`
  - `scope_type` (`user|team|org`)
  - `scope_id` (string)
  - `rules: List[WatchlistRule]`

- Alert (SQLite table `topic_alerts`)
  - `id` (PK), `created_at`, `user_id`
  - `scope_type`, `scope_id`
  - `source` (`chat.input|chat.output|ingestion|notes|rag`)
  - `watchlist_id`, `rule_category`, `rule_severity`, `pattern`
  - `text_snippet` (truncated), `metadata` (JSON)
  - `is_read` (bool), `read_at`

## Files & Placement
- Core: `tldw_Server_API/app/core/Monitoring/topic_monitoring_service.py`
- Schemas: `tldw_Server_API/app/api/v1/schemas/monitoring_schemas.py`
- Endpoints: `tldw_Server_API/app/api/v1/endpoints/monitoring.py`
- Config (optional): `tldw_Server_API/Config_Files/monitoring_watchlists.json`

## API Endpoints (Phase 1)
- `GET  /api/v1/monitoring/watchlists`        list watchlists (admin)
- `POST /api/v1/monitoring/watchlists`        create/update watchlist (admin)
- `DELETE /api/v1/monitoring/watchlists/{id}` delete watchlist (admin)
- `GET  /api/v1/monitoring/alerts`            list alerts (admin; filters: user_id, since, unread)
- `POST /api/v1/monitoring/alerts/{id}/read`  mark alert as read (admin)
- `POST /api/v1/monitoring/reload`            reload config file (admin)

## Integration (chat only for Phase 1)
At moderation/processing sites in endpoints, MonitoringService is called for:
- chat input (pre-LLM) with `source=chat.input`
- chat output (stream and non-stream) with `source=chat.output`
- notes creation/update/bulk with `source=notes.*`
- RAG queries with `source=rag.*`

Monitoring emits alerts without changing moderation behavior or endpoint results.

## Security & Privacy
- Admin-only APIs. Extend to org/team leads later.
- Opt-in via config or explicit creation of watchlists.
- Store minimal snippets (e.g., first 200 chars around the match).
- All local; no external calls.

## Notifications (Phase 1 scaffolding)
- Local JSONL file sink gated by severity threshold.
- Configure via env or config:
  - `MONITORING_NOTIFY_ENABLED`, `MONITORING_NOTIFY_MIN_SEVERITY`, `MONITORING_NOTIFY_FILE`
  - Placeholder knobs: `MONITORING_NOTIFY_WEBHOOK_URL`, `MONITORING_NOTIFY_EMAIL_TO` (not delivered offline)

## Phase 2 (planned)
- Delivery channels: email, webhook, Slack.
- WebSocket push to WebUI for admins.
- ML topic classifiers & customizable taxonomies.
- Org/team scoping UI in WebUI.

## Tests
- Unit tests for rule parsing, safe regex checks, and alert creation.
- Endpoint tests for list/create/reload/alerts.
