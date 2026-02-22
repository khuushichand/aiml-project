# PRD: Slack Bot Integration for tldw_server
Product Requirements Document (PRD)

Status: Draft • Owner: Core Maintainers • Target: v0.2.x

## 1. Summary
Add first-class Slack bot support so users can run tldw workflows directly from Slack (slash commands and @mentions) with secure webhook verification, asynchronous processing via Jobs, and policy-controlled posting back to channels/threads.

This PRD defines product scope and technical contracts for a v1 release that is useful in production while staying compatible with existing AuthNZ, Jobs, RAG, Chat, and media ingestion capabilities.

## 2. Problem Statement
Today, users must leave Slack to use tldw features. That creates friction for:
- Asking contextual questions during team discussions.
- Triggering quick RAG/search/summarization from links shared in chat.
- Receiving results where collaboration is already happening.

A Slack bot should reduce context switching while preserving existing security and tenancy constraints.

## 3. Goals and Non-Goals
### Goals
- Support Slack slash commands and app mentions.
- Return fast acknowledgement responses and handle long operations asynchronously.
- Reuse existing tldw endpoints/services (chat, rag, media ingest) rather than duplicating logic.
- Support both AuthNZ modes:
  - `single_user`: map all Slack traffic to single user context.
  - `multi_user`: map Slack workspace/user to org/user context.
- Provide admin visibility and control through Jobs + Slack admin endpoints.
- Enforce signature verification, replay protection, event deduplication, and least-privilege scopes.

### Non-Goals (v1)
- Full Slack UI surface (modals, workflow steps, canvases, app home customization).
- File upload import from Slack channels (`files:read`) in v1.
- Multi-workspace shared channels edge-case parity.
- Real-time streaming token-by-token message updates in Slack.

## 4. Personas and Primary Use Cases
- Analyst: runs `/tldw rag <query>` in a team thread and gets cited results.
- Research lead: uses `/tldw summarize <url>` to generate a quick briefing.
- Engineer: asks `@tldw what changed in this issue?` in incident channels.
- Admin: installs the app, sets channel policy, reviews job status/errors.

## 5. Scope (v1)
### In Scope
- Slack app installation (OAuth 2.0 for bot token).
- Event ingestion endpoint for Slack Events API.
- Slash command endpoint for `/tldw`.
- App mention handling (`app_mention`) in channels and threads.
- Core commands:
  - `help`
  - `ask <question>`
  - `rag <query>`
  - `summarize <url|text>`
- `status <job_id>`
- Asynchronous handoff for long jobs via unified Jobs module.
- Posting results back to Slack via Slack Web API (`chat.postMessage`/`chat.postEphemeral`) and `response_url` when applicable.

### Out of Scope
- Slack file ingestion from attachments.
- Interactive modals/buttons beyond basic response URLs.
- Cross-org shared Slack Connect policy handling.

## 6. Functional Requirements
1. Slack request verification
- Verify `X-Slack-Signature` + `X-Slack-Request-Timestamp` using HMAC-SHA256.
- Reject requests outside replay window (default 5 minutes).
- Do not process invalid signatures.

2. URL verification and event handling
- Respond to Slack `url_verification` challenge.
- Process `event_callback` payloads for `app_mention` (and optionally message events behind a flag).
- Ignore bot-originated/self-originated events (`subtype=bot_message`, `bot_id`, or sender equals installed bot user) to prevent reply loops.

3. Slash commands
- Support `/tldw` with subcommand parsing.
- Return acknowledgement in <=3 seconds for both `/commands` and `/events` request paths.
- Queue long tasks and all downstream processing asynchronously via Jobs.

4. Idempotency and retries
- Deduplicate by Slack `event_id` or command request fingerprint.
- Handle Slack retry headers without duplicate processing.

5. Command routing
- `ask`: call existing chat completion stack.
- `rag`: call unified RAG search.
- `summarize`: run ingestion + summarization path.
- `status`: check Jobs status and format result, scoped to same workspace/tenant with role-based authorization checks.

6. Response modes
- Default ephemeral acknowledgement for user safety.
- Async follow-up responses must support `ephemeral|thread|channel` in v1 (policy-controlled).
- Use `response_url` and/or `chat.postEphemeral` for ephemeral follow-ups; use `chat.postMessage` for thread/channel follow-ups.
- Preserve thread context when invoked inside a thread.

7. Installation and linkage
- Store workspace installation info and encrypted bot token.
- Link Slack workspace to tenant/org and optionally Slack user to tldw user.
- Require OAuth `state` CSRF protection: generate high-entropy one-time state, bind to install initiator context, enforce short TTL, validate on callback, and mark consumed after first use.

8. Admin controls
- Enable/disable Slack integration per org.
- Allowed channels and commands policy.
- Rate limit caps per workspace/user.

## 7. Non-Functional Requirements
- Reliability: at-least-once webhook handling with idempotent processing.
- Performance: acknowledge Slack `/events` and `/commands` requests in <=3 seconds; complete most short commands within 10s, long tasks via async updates.
- Security: encrypted secrets at rest; no token leakage in logs.
- Observability: structured logs, metrics, and job/audit linkage.

## 8. UX and Interaction Flows
1) Install flow
- Admin starts install (`/oauth/start`) -> server issues one-time expiring `state` -> Slack OAuth consent -> callback validates `state` and persists installation -> success screen.

2) Slash command flow
- User sends `/tldw rag battery storage trends`
- Server validates signature, parses command, acks quickly.
- Job runs and bot posts final result to thread or ephemeral response.

3) App mention flow
- User sends `@tldw summarize https://...` in thread.
- Server validates + dedupes event, enqueues job.
- Bot posts progress/final summary in same thread.

4) Failure flow
- Invalid auth/signature -> silent 401/403 style behavior (no processing).
- Downstream failure -> user-facing error message with retry guidance.

## 9. Proposed API Surface (v1)
Base prefix: `/api/v1/slack`

Public webhook endpoints (no Auth header; Slack signature required):
- `POST /events` - Slack Events API callback (`url_verification`, `event_callback`).
- `POST /commands` - Slash command receiver.
- `GET /oauth/start` - OAuth install start; issues redirect to Slack with one-time expiring `state`.
- `GET /oauth/callback` - OAuth completion callback.

Authenticated admin endpoints:
- `GET /admin/installations` - list workspace installs for current tenant.
- `DELETE /admin/installations/{workspace_id}` - revoke/disconnect install.
- `GET /admin/policy` - fetch Slack integration policy.
- `PUT /admin/policy` - update policy (allowed channels/commands/response mode).

## 10. Proposed Data Model
Use DB abstractions in `app/core/DB_Management/` (no raw SQL in endpoints).

Tables/entities (logical):
- `slack_installations`
  - `id`, `tenant_id`, `workspace_id`, `workspace_name`, `bot_user_id`, `bot_token_encrypted`, `scopes`, `installed_by_user_id`, `created_at`, `updated_at`, `enabled`
- `slack_user_links`
  - `id`, `tenant_id`, `workspace_id`, `slack_user_id`, `local_user_id`, `created_at`, `updated_at`
- `slack_event_receipts`
  - `id`, `workspace_id`, `event_id`, `event_type`, `received_at`, `dedupe_expires_at`, `status`
- `slack_channel_policies`
  - `id`, `tenant_id`, `workspace_id`, `allowed_channels_json`, `blocked_channels_json`, `default_response_mode`, `enabled_commands_json`
- `slack_oauth_states`
  - `id`, `tenant_id`, `state_hash`, `initiated_by_user_id`, `redirect_uri`, `created_at`, `expires_at`, `consumed_at`

Jobs integration:
- Use unified Jobs manager (`domain = "slack"`) for command execution and completion callbacks.

## 11. Command Contract (v1)
Slash command grammar:
- `/tldw help`
- `/tldw ask <question>`
- `/tldw rag <query>`
- `/tldw summarize <url_or_text>`
- `/tldw status <job_id>`
- `status` visibility contract: authorized users can query jobs within the same workspace/tenant, subject to role checks and policy.

Mention grammar:
- `@tldw <same subcommands>`
- If no subcommand is supplied, default to `ask`.

## 12. AuthNZ Mapping
Single-user mode:
- All Slack requests execute as the configured single user context.

Multi-user mode:
- Resolve tenant by workspace install.
- Resolve user by `slack_user_links`; if missing, use policy-defined fallback (deny by default in v1 for safety).
- Enforce role-based authorization for `status` lookups; never expose cross-tenant or cross-workspace job details.

## 13. Security and Compliance Requirements
- Verify Slack signatures for every webhook request.
- Enforce replay window and event dedupe.
- Enforce OAuth callback CSRF protection with one-time expiring `state` validation.
- Encrypt bot/user tokens at rest.
- Do not log raw tokens, signed secrets, or full payloads with sensitive fields.
- Apply route-level rate limits and per-workspace/job quotas.
- Record audit events for install/uninstall/policy changes.

## 14. Rate Limiting and Idempotency
- Request limits:
  - webhook ingress limits by workspace and IP.
  - command execution limits by workspace + user.
- Idempotency:
  - `event_id` dedupe for Events API.
  - command dedupe hash for repeated Slack retries.

## 15. Observability
Metrics (proposed):
- `slack_requests_total{type,status}`
- `slack_signature_failures_total`
- `slack_events_deduped_total`
- `slack_jobs_enqueued_total{command}`
- `slack_jobs_failed_total{command}`
- `slack_response_latency_ms{command}`

Logging:
- include `workspace_id`, `event_id`, `command`, `job_id`, `request_id`.
- redact secrets and PII as required.

## 16. Configuration
Environment/config keys (proposed):
- `SLACK_SIGNING_SECRET`
- `SLACK_CLIENT_ID`
- `SLACK_CLIENT_SECRET`
- `SLACK_REDIRECT_URI`
- `SLACK_BOT_SCOPES` (default minimal)
- `SLACK_REPLAY_WINDOW_SECONDS` (default: 300)
- `SLACK_ENABLE_MENTIONS` (default: true)
- `SLACK_ENABLE_COMMANDS` (default: true)
- `SLACK_DEFAULT_RESPONSE_MODE` (`ephemeral|thread|channel`)

Minimum Slack scopes (v1):
- `commands`
- `app_mentions:read`
- `chat:write`

## 17. Testing Strategy
Unit tests:
- signature verification and replay guard.
- command parser and routing behavior.
- idempotency logic for duplicate events.
- bot/self-event loop guard behavior.

Integration tests:
- `/api/v1/slack/events` URL verification and event callbacks.
- `/api/v1/slack/commands` slash command ingest and ack behavior.
- `/api/v1/slack/oauth/start` and `/api/v1/slack/oauth/callback` state issue/validate/consume flow.
- Jobs enqueue + completion post flow with mocked Slack API.

Security tests:
- invalid signature rejection.
- expired timestamp rejection.
- invalid/expired/replayed OAuth `state` rejection.
- token redaction in logs.

## 18. Rollout Plan
Phase 0 - Internal alpha
- Install + webhook validation + `help` command only.

Phase 1 - v1 launch
- `ask`, `rag`, `summarize`, `status`.
- Jobs-based async processing.
- Admin policy endpoints + basic observability.

Phase 2 - v1.1+
- richer interaction UX (buttons/modals), optional file-based ingest, expanded policies.

## 19. Acceptance Criteria (v1)
- Slack app can be installed and workspace persisted securely.
- Slash command `/tldw` works for defined command set.
- `@tldw` mention handling works in channels and threads.
- Bot/self-originated Slack events are ignored and do not create loops.
- Invalid signatures/timestamps are rejected with no processing.
- OAuth callback rejects invalid/expired/replayed `state`.
- Duplicate events are processed once.
- Long-running operations run through Jobs and report completion in Slack.
- Async follow-up responses support `ephemeral|thread|channel` modes in v1.
- `status` enforces same-workspace/tenant scope with role checks.
- `/events` and `/commands` acknowledge within <=3 seconds under normal load.
- Admin can list installations and manage policy.

## 20. Risks and Mitigations
- Slack API retries cause duplicates.
  - Mitigation: strict dedupe store + idempotent jobs.
- Tenant/user mapping mistakes in multi-user mode.
  - Mitigation: explicit workspace->tenant and Slack user->local user linkage; deny on unknown mapping.
- Scope creep (modals/files/workflow steps).
  - Mitigation: freeze v1 to commands + mentions + async callbacks.

## 21. Open Questions
- Should unknown Slack users in a mapped workspace be denied or mapped to org default service user?
- Should channel posting be opt-in per command or globally configured per workspace?
- Should summarization support only URLs in v1, or also raw pasted long text?
- Do we need per-command model/provider overrides for Slack workloads?

## 22. Dependencies
- AuthNZ mapping and policy enforcement.
- Jobs manager for async execution + status.
- Existing Chat/RAG/Ingestion services.
- DB abstractions for installation/token/event persistence.

## 23. Implementation Epics and Issue Checklist
Use this checklist to create and track implementation issues.

### Epic 1: Slack platform and webhook foundation
Suggested issue title: `Slack v1 - Webhook foundation (events, commands, signature verification)`
- [ ] Add `/api/v1/slack/events` endpoint for `url_verification` and `event_callback`.
- [ ] Add `/api/v1/slack/commands` endpoint for slash command intake.
- [ ] Implement Slack signature verification (`X-Slack-Signature`, timestamp window).
- [ ] Add replay-window enforcement and clock-skew-safe validation.
- [ ] Add event dedupe store keyed by `event_id` (and retry-safe command fingerprint).
- [ ] Add bot/self-event guard to ignore bot-originated events and prevent reply loops.
- [ ] Add route-level rate limiting for Slack ingress.
- [ ] Enforce <=3s ACK contract for `/events` and `/commands` with async-only heavy work.

### Epic 2: OAuth installation and workspace lifecycle
Suggested issue title: `Slack v1 - OAuth install and workspace token management`
- [ ] Implement OAuth install start/callback flow and workspace installation persistence.
- [ ] Implement one-time expiring OAuth `state` issuance/validation/consumption.
- [ ] Encrypt bot tokens at rest and redact sensitive values in logs.
- [ ] Add install revoke/disconnect path and workspace disable toggle.
- [ ] Add admin APIs: list installations, remove installation.
- [ ] Add audit logging for install/uninstall/update actions.

### Epic 3: Command parser and execution routing
Suggested issue title: `Slack v1 - Command parser and core action routing`
- [ ] Implement parser for `/tldw help|ask|rag|summarize|status`.
- [ ] Implement mention parser with default fallback to `ask`.
- [ ] Route `ask` to chat completions service.
- [ ] Route `rag` to unified RAG search.
- [ ] Route `summarize` to ingest + summarize flow.
- [ ] Route `status` to Jobs status lookup with workspace/tenant scoping and role checks.
- [ ] Enforce allowed commands policy per workspace/tenant.

### Epic 4: Jobs integration and Slack response delivery
Suggested issue title: `Slack v1 - Async Jobs handoff and Slack response posting`
- [ ] Add Jobs payload contract for Slack command execution (`domain=\"slack\"`).
- [ ] Return fast acknowledgement responses before async execution.
- [ ] Post completion and failure responses via Slack Web API.
- [ ] Preserve channel/thread context in replies.
- [ ] Support policy-driven response mode: `ephemeral|thread|channel`.
- [ ] Add retry/backoff handling for Slack post failures.

### Epic 5: AuthNZ mapping, policy, and governance
Suggested issue title: `Slack v1 - Tenant/user mapping and admin policy controls`
- [ ] Implement workspace-to-tenant mapping.
- [ ] Implement Slack user to local user linking model.
- [ ] Enforce safe default for unknown user mapping (deny by default).
- [ ] Add admin policy model and endpoints (`GET/PUT /api/v1/slack/admin/policy`).
- [ ] Add channel allow/deny controls and default response mode config.
- [ ] Add per-workspace and per-user quotas.

### Epic 6: Observability, hardening, and release readiness
Suggested issue title: `Slack v1 - Testing, metrics, and production hardening`
- [ ] Add unit tests for signature verification, replay checks, parser, and dedupe logic.
- [ ] Add integration tests for events endpoint, commands endpoint, and async completion flow.
- [ ] Add security tests for invalid signatures and expired timestamps.
- [ ] Add metrics (`slack_requests_total`, `slack_signature_failures_total`, `slack_jobs_failed_total`, etc.).
- [ ] Add structured logs with `workspace_id`, `event_id`, `command`, `job_id`, `request_id`.
- [ ] Add rollout checklist for alpha to v1 promotion with acceptance criteria sign-off.

### Milestone checklist
- [ ] Phase 0 complete: install + webhook validation + `help`.
- [ ] Phase 1 complete: `ask`, `rag`, `summarize`, `status` with Jobs integration.
- [ ] Acceptance criteria from Section 19 fully validated in staging.
