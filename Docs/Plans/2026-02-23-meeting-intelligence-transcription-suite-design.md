# Meeting Intelligence Transcription Suite Design

Date: 2026-02-23  
Status: Approved for planning  
Approval: User-validated in Codex review thread on 2026-02-23  
Source PRD: `Docs/Product/Meeting-Transcripts-PRD.md`

## 1. Scope Decisions (Locked)

- Delivery style: API-first
- v1 scope: full PRD core
- Auth/deployment support: both single-user and multi-user (org/team)
- v1 integrations: Slack + generic webhooks only
- Domain shape: dedicated `/api/v1/meetings/*` (adapter-based reuse of existing systems)

## 2. Problem and Constraints

Current capabilities already provide strong STT, streaming, diarization, and live insights foundations, but meeting intelligence is not yet a first-class product domain. The main gap is a coherent meeting contract across sessions, templates, artifacts, and integrations.

Constraints:
- Reuse existing audio, jobs, outputs, and AuthNZ systems.
- Avoid breaking `/api/v1/audio/*` behavior.
- Keep storage additive and compatible with current Media DB ingestion flows.
- Keep governance and quota behavior aligned with existing org/team policy patterns.

## 3. Recommended Architecture

Create a dedicated meetings bounded domain:
- API router: `/api/v1/meetings/*`
- Core services: `tldw_Server_API/app/core/Meetings/`
  - `session_service.py`
  - `template_service.py`
  - `artifact_service.py`
  - `integration_service.py`

The meetings domain orchestrates existing primitives:
- Streaming/STT/diarization: existing audio streaming pipeline
- Artifact generation: existing LLM and output rendering utilities
- Jobs/events: existing job and streaming infrastructure
- AuthNZ and org/team controls: existing principal/permission/policy surfaces

Compatibility strategy:
- Keep `/api/v1/audio/*` stable and supported.
- Position `/api/v1/meetings/*` as the meeting product contract.

## 4. API Surface (v1)

### Sessions
- `POST /api/v1/meetings/sessions`
- `GET /api/v1/meetings/sessions`
- `GET /api/v1/meetings/sessions/{session_id}`
- `PATCH /api/v1/meetings/sessions/{session_id}`
- `POST /api/v1/meetings/sessions/{session_id}/start`
- `POST /api/v1/meetings/sessions/{session_id}/commit`
- `POST /api/v1/meetings/sessions/{session_id}/ingest`
- `GET /api/v1/meetings/sessions/{session_id}/events` (SSE fallback)
- `WS /api/v1/meetings/sessions/{session_id}/stream` (primary real-time transport)

### Templates
- `POST /api/v1/meetings/templates`
- `GET /api/v1/meetings/templates`
- `GET /api/v1/meetings/templates/{template_id}`
- `PATCH /api/v1/meetings/templates/{template_id}`
- `DELETE /api/v1/meetings/templates/{template_id}`
- `POST /api/v1/meetings/templates/{template_id}/validate`

### Artifacts and Sharing
- `GET /api/v1/meetings/sessions/{session_id}/artifacts`
- `GET /api/v1/meetings/sessions/{session_id}/artifacts/{artifact_id}`
- `POST /api/v1/meetings/sessions/{session_id}/exports`
- `POST /api/v1/meetings/sessions/{session_id}/share/slack`
- `POST /api/v1/meetings/sessions/{session_id}/share/webhook`

### Integrations/Webhooks
- `POST /api/v1/meetings/events/webhooks` (register)
- `GET /api/v1/meetings/events/webhooks`
- `DELETE /api/v1/meetings/events/webhooks/{id}`

## 5. Data Model (Additive)

### `meeting_sessions`
- `id`, `user_id`, `org_id`, `team_id`
- `title`, `meeting_type`, `status`
- `language`, `source_type`, `source_ref`
- `started_at`, `ended_at`, `created_at`, `updated_at`

### `meeting_templates`
- `id`, `name`, `scope` (`builtin|org|team|personal`)
- `enabled`, `is_default`, `owner_user_id`, `org_id`, `team_id`
- `schema_json`, `version`, `created_at`, `updated_at`

### `meeting_artifacts`
- `id`, `session_id`, `kind`
- `payload_json`, `format`, `version`
- `redaction_state`, `created_at`, `updated_at`

### `meeting_integration_dispatch`
- `id`, `session_id`, `target_type` (`slack|webhook`)
- `target_ref`, `status`, `attempts`, `last_error`, `response_meta_json`
- `created_at`, `updated_at`

### `meeting_event_log` (optional persisted stream for replay/debug)
- `id`, `session_id`, `event_type`, `event_payload_json`, `created_at`

## 6. Real-Time Event Contract

Standardized event types for WS/SSE:
- `transcript.partial`
- `transcript.final`
- `diarization.update`
- `insight.update`
- `artifact.ready`
- `session.status`
- `error`

Event payloads include session ID and timestamp, and should be schema-versioned for forward compatibility.

## 7. Governance and Security

Template governance model:
- Built-in templates ship enabled by default.
- Org/team owners can enable or disable built-ins for their scope.
- Org/team owners can manage shared templates in their scope.
- End users can manage personal templates when org policy allows.

Security requirements:
- Respect current AuthNZ modes and permission claims.
- Enforce row-level data ownership and org/team scope rules.
- Apply redaction controls for exports and logs.
- Keep secret material out of logs and responses.

## 8. Core Processing Flow

1. Create session and select template.
2. Start stream (WS) or upload/import recording.
3. Transcription + diarization pipeline emits live events.
4. Template engine structures notes and insights incrementally.
5. Commit session to generate final artifacts.
6. Export/share via Slack or webhook dispatch.
7. Session and artifacts become searchable via meetings endpoints.

Error semantics:
- Partial results are valid (for example, summary available even if sentiment generation fails).
- Integration dispatch retries are isolated from artifact generation completion.

## 9. Performance and Reliability Targets

- Streaming update latency target: under 2 seconds (best-effort)
- Median end-of-meeting summary target: under 5 minutes
- Tenant-aware concurrency controls and duration-based throttling
- Idempotent lifecycle operations (`start`, `commit`, dispatch)

## 10. Testing Strategy

Unit:
- Template schema validation
- Action item extraction and ownership confidence logic
- Session lifecycle state transitions

Integration:
- Live session flow end-to-end
- Upload/offline flow end-to-end
- Slack + webhook dispatch and retry paths
- Single-user and multi-user authorization behavior
- Scope governance checks for template visibility and management

Load:
- Concurrent live sessions with quotas enabled
- Long recording processing and artifact completion

Security:
- Access control regression tests
- Redaction behavior in exports/logging

## 11. Phased Delivery (API-first)

### Phase A: Contract and Persistence
- `/meetings/*` routers, schemas, and additive DB entities
- Adapter wiring into existing audio pipelines

### Phase B: Live Core and Artifacts
- WS primary + SSE fallback via meetings domain
- Final artifact generation and retrieval
- Meeting search/list filters and index wiring

### Phase C: Integrations and Hardening
- Slack + webhook dispatch with retries and audit logs
- Governance policy controls and instrumentation stabilization

## 12. Explicit Deferrals (Post-v1)

- Notion/Trello native push
- Calendar auto-ingest and owner auto-mapping
- CRM connectors
- Additional analytics dashboards beyond baseline instrumentation

## 13. Why This Approach

This design preserves existing platform investments, minimizes rework risk, and creates a stable long-term product contract. A dedicated meetings domain gives clean evolution boundaries while allowing internal reuse of proven STT, streaming, templating, and AuthNZ components.
