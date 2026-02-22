# PRD: Discord Bot Integration for tldw_server
Product Requirements Document (PRD)

Status: Draft • Owner: Core Maintainers • Target: v0.2.x

## 1. Summary
Add first-class Discord bot support so users can run tldw workflows directly from Discord slash commands with secure interaction handling, asynchronous processing via Jobs, and policy-controlled responses in channels/threads.

This PRD defines scope and technical contracts for a v1 release that is production-usable while reusing existing AuthNZ, Jobs, RAG, Chat, and media ingestion capabilities.

v1 decisions captured in this document:
- Slash-command invocation only.
- Tenant-owned Discord bot apps (per-tenant credentials and install lifecycle).

## 2. Problem Statement
Today, users must leave Discord to use tldw features. That creates friction for:
- Asking contextual questions during active community/team conversations.
- Running quick RAG/search/summarization against links and pasted text.
- Sharing AI-assisted outputs in the same channel where collaboration happens.

A Discord bot should reduce context switching while preserving existing security and tenancy constraints.

## 3. Goals and Non-Goals
### Goals
- Support Discord slash command invocation.
- Return fast acknowledgement responses and handle long operations asynchronously.
- Reuse existing tldw endpoints/services (chat, rag, media ingest) rather than duplicating logic.
- Support both AuthNZ modes:
  - `single_user`: map all Discord traffic to single user context.
  - `multi_user`: map Discord guild to org/tenant context with a safe default execution model.
- Provide admin visibility and control through Jobs + Discord admin endpoints.
- Enforce request verification, event deduplication, rate limits, and least-privilege bot permissions.
- Support tenant-owned Discord app credential management and installation lifecycle.

### Non-Goals (v1)
- Mention-based invocation (`@tldw`) in v1.
- Full feature parity with every Discord surface (buttons/modals/select menus everywhere, forum auto-workflows).
- Voice-channel transcription relay in v1.
- Attachment ingestion from every file type and size in v1.
- Streaming token-by-token edits for all responses.
- Self-service Discord-to-local account linking flow in v1.

## 4. Personas and Primary Use Cases
- Analyst: runs `/tldw rag <query>` in a thread and gets cited results.
- Research lead: uses `/tldw summarize <url>` to generate a briefing in channel.
- Engineer: runs `/tldw ask what changed in this issue?` during incident response.
- Admin: configures tenant app credentials, installs bot, configures allowed channels/commands, reviews job status/errors.

## 5. Scope (v1)
### In Scope
- Tenant-owned Discord app/bot setup and guild installation lifecycle.
- Interaction endpoint for slash command handling and interaction callbacks.
- Core commands:
  - `help`
  - `ask <question>`
  - `rag <query>`
  - `summarize <url|text>`
  - `status <request_id>`
- Asynchronous handoff for long jobs via unified Jobs module.
- Posting results back to Discord channel/thread context.
- Basic guild/channel policy and command allowlist controls.
- Admin credential management + OAuth install URL generation + callback/state validation.

### Out of Scope
- Mention-based invocation in v1.
- Full voice/Stage channel support.
- Complex interactive workflows (multi-step forms/modals beyond basic v1 needs).
- Large-scale attachment ingestion pipeline for all Discord file scenarios.

## 6. Functional Requirements
1. Request verification
- Verify Discord interaction signatures on every inbound interaction request.
- Resolve tenant app config by `application_id` and verify with the corresponding stored public key.
- Reject invalid signatures or malformed payloads without processing.

2. Interaction handling
- Support slash command invocation for `/tldw`.
- Acknowledge interactions within Discord timing limits (target <3s).
- For operations expected to exceed acknowledgement windows, send deferred acknowledgement and continue asynchronously.
- For late completions where interaction follow-up token is no longer usable, fallback to bot API post in allowed channel/thread.

3. Command parsing and routing
- Parse `help|ask|rag|summarize|status`.
- `ask`: route to existing chat completions stack.
- `rag`: route to unified RAG search.
- `summarize`: route to ingestion + summarization path.
- `status`: route to Jobs status lookup by external `request_id` (not raw internal job id).

4. Async processing and updates
- Queue long-running requests in Jobs (`domain = "discord"`).
- Include correlation fields (`interaction_id`, `request_id`, `job_id`) in job payload/result metadata.
- Send immediate acknowledgement, then follow up with completion/failure messages.

5. Idempotency and retries
- Deduplicate retries by (`application_id`, `interaction_id`) and replay-window policy.
- Ensure repeated delivery does not enqueue duplicate work.

6. Context handling
- Preserve channel/thread context when replying.
- Support policy-driven response mode (`channel|thread|ephemeral` where supported by interaction type).
- Define fallback behavior when requested response mode is unavailable (for example thread create denied -> channel response).

7. Installation and mapping
- Store tenant-owned app credentials and guild installation metadata with encrypted secrets.
- Store and validate OAuth install callback state (single-use, expiring).
- Link Discord guild installation to tenant.
- In multi-user mode v1, execute Discord jobs under tenant service-user context by default.

8. Admin controls
- Enable/disable integration per tenant/org.
- Configure allowed guild channels and enabled commands.
- Configure default model/provider override for Discord traffic (optional, policy-based).
- Rotate tenant app credentials and expose health diagnostics for install/config issues.

## 7. Non-Functional Requirements
- Reliability: at-least-once event handling with idempotent processing.
- Performance: acknowledge command quickly; short commands typically complete within 10s; long tasks complete asynchronously.
- Security: encrypted secrets at rest; OAuth state validation; no token leakage in logs.
- Observability: structured logs, metrics, and job/audit linkage.

## 8. UX and Interaction Flows
1) Tenant app setup + install flow
- Admin stores tenant Discord app credentials in tldw admin.
- Admin opens generated OAuth install URL and authorizes the bot in a guild.
- Callback validates state and persists installation metadata.

2) Slash command flow
- User sends `/tldw rag battery storage trends`.
- Service verifies signature, parses command, acknowledges quickly.
- Job runs and bot posts result in the same thread/channel context.

3) Deferred response fallback flow
- User sends a long-running command (`/tldw summarize ...`).
- Service sends deferred acknowledgement and enqueues job.
- Job completion posts via interaction follow-up when possible; if token is expired, service posts via bot API in allowed context and records fallback.

4) Failure flow
- Invalid signature/auth/state -> request rejected with no processing.
- Downstream failure -> user-facing error with retry guidance.

## 9. Proposed API Surface (v1)
Base prefix: `/api/v1/discord`

Public endpoint (no Auth header; Discord signature required):
- `POST /interactions` - Discord interaction receiver (slash commands + callbacks).

Public endpoint (OAuth callback; state required):
- `GET /oauth/callback` - complete guild install flow and persist installation metadata.

Authenticated admin endpoints:
- `GET /admin/app` - fetch tenant Discord app config metadata (no secret plaintext).
- `PUT /admin/app` - create/update tenant Discord app credentials (encrypted at rest).
- `POST /admin/install-url` - generate OAuth install URL with signed state.
- `GET /admin/installations` - list guild installs for current tenant.
- `DELETE /admin/installations/{guild_id}` - revoke/disconnect install.
- `GET /admin/policy` - fetch Discord integration policy.
- `PUT /admin/policy` - update policy (allowed channels/commands/default response mode).

## 10. Proposed Data Model
Use DB abstractions in `app/core/DB_Management/` (no raw SQL in endpoints).

Tables/entities (logical):
- `discord_tenant_apps`
  - `id`, `tenant_id`, `application_id`, `client_id`, `client_secret_encrypted`, `bot_token_encrypted`, `public_key`, `created_at`, `updated_at`, `enabled`
- `discord_installations`
  - `id`, `tenant_id`, `tenant_app_id`, `guild_id`, `guild_name`, `bot_user_id`, `permissions_json`, `installed_by_user_id`, `created_at`, `updated_at`, `enabled`
- `discord_oauth_states`
  - `id`, `tenant_id`, `state_hash`, `expires_at`, `consumed_at`, `created_at`
- `discord_event_receipts`
  - `id`, `tenant_id`, `application_id`, `interaction_id`, `event_type`, `received_at`, `dedupe_expires_at`, `status`
- `discord_channel_policies`
  - `id`, `tenant_id`, `guild_id`, `allowed_channels_json`, `blocked_channels_json`, `default_response_mode`, `enabled_commands_json`, `default_model`
- `discord_job_messages`
  - `id`, `tenant_id`, `guild_id`, `channel_id`, `thread_id`, `message_id`, `request_id`, `job_id`, `created_at`, `updated_at`

Recommended constraints/indexes:
- unique `(tenant_id, application_id)` on `discord_tenant_apps`.
- unique `(tenant_id, guild_id)` on `discord_installations`.
- unique `(application_id, interaction_id)` on `discord_event_receipts`.

Data retention/pruning policy (v1):
- `discord_oauth_states`: purge consumed/expired rows older than 24 hours.
- `discord_event_receipts`: retain 30 days for forensics/duplicate-delivery analysis, then prune.
- `discord_job_messages`: retain 90 days for status traceability, then prune.
- Pruning runs daily via existing maintenance/scheduler services and must be idempotent.

Jobs integration:
- Use unified Jobs manager (`domain = "discord"`) for command execution and completion callbacks.

## 11. Command Contract (v1)
Slash command grammar:
- `/tldw help`
- `/tldw ask <question>`
- `/tldw rag <query>`
- `/tldw summarize <url_or_text>`
- `/tldw status <request_id>`

Slash command registration schema (Discord application command contract):
- Root command:
  - name: `tldw`
  - description: `Run tldw assistant actions`
- Subcommands:
  - `help` (no options)
  - `ask`
    - required option: `question` (`string`, min 1, max 2000)
  - `rag`
    - required option: `query` (`string`, min 1, max 1000)
  - `summarize`
    - required option: `input` (`string`, min 1, max 4000)
  - `status`
    - required option: `request_id` (`string`, min 1, max 128)
- Registration/update behavior:
  - Command registration is managed by server-side upsert at startup (and admin-triggered refresh).
  - Parser behavior must remain schema-compatible with registered subcommands/options.

Status semantics:
- `request_id` is an external opaque identifier returned to the caller.
- Status lookup must be authorized for the same tenant/guild context; cross-tenant or unknown request lookups are denied.

## 12. AuthNZ Mapping
Single-user mode:
- All Discord requests execute as configured single-user context.

Multi-user mode (v1):
- Resolve tenant by `application_id` + guild installation mapping.
- Execute commands as tenant service-user context by default.
- Optional stricter policy may deny execution unless explicit per-user mapping exists (future expansion).

## 13. Security and Compliance Requirements
- Verify Discord signatures for every interaction request.
- Enforce replay protection and request dedupe.
- Validate OAuth callback state and consume state tokens only once.
- Encrypt bot tokens and related secrets at rest.
- Do not log raw tokens/secrets or full sensitive payloads.
- Apply route-level rate limits and per-guild/per-tenant quotas.
- Authorize `status` lookups by tenant/guild/request ownership.
- Record audit events for app credential changes, install/uninstall, and policy updates.

## 14. Rate Limiting and Idempotency
- Request limits:
  - interaction ingress limits by `application_id` and guild.
  - command execution limits by guild + tenant context.
- Idempotency:
  - dedupe by (`application_id`, `interaction_id`).
  - deterministic `request_id` propagation to prevent duplicate async completion handling.

## 15. Observability
Metrics (proposed):
- `discord_requests_total{type,status}`
- `discord_signature_failures_total`
- `discord_oauth_state_failures_total`
- `discord_events_deduped_total`
- `discord_jobs_enqueued_total{command}`
- `discord_jobs_failed_total{command}`
- `discord_response_latency_ms{command}`
- `discord_followup_fallback_total{reason}`

Logging:
- include `tenant_id`, `application_id`, `guild_id`, `channel_id`, `interaction_id`, `command`, `job_id`, `request_id`.
- redact secrets and sensitive user content as required.

## 16. Configuration
Environment/config keys (proposed):
- `DISCORD_ENABLE_COMMANDS` (default: true)
- `DISCORD_DEFAULT_RESPONSE_MODE` (`channel|thread|ephemeral`)
- `DISCORD_REPLAY_WINDOW_SECONDS` (default: 300)
- `DISCORD_INTERACTION_TOKEN_TTL_SECONDS` (default: 900)
- `DISCORD_OAUTH_REDIRECT_URI`
- `DISCORD_OAUTH_STATE_RETENTION_HOURS` (default: 24)
- `DISCORD_EVENT_RECEIPT_RETENTION_DAYS` (default: 30)
- `DISCORD_JOB_MESSAGE_RETENTION_DAYS` (default: 90)

Tenant-specific Discord credentials:
- `application_id`, `client_id`, `client_secret`, `bot_token`, and `public_key` are stored per tenant through authenticated admin APIs and encrypted at rest.
- v1 does not rely on a single global deployment-wide bot token.

Minimum Discord bot scopes/intents (v1):
- `bot`
- `applications.commands`
- Permissions: send messages, read message history, create public/private threads (if thread replies enabled)
- Intents: minimal; no privileged intents required for slash-only v1.

## 17. Testing Strategy
Unit tests:
- signature verification and replay guard.
- OAuth state issue/validate/consume behavior.
- command parser and routing behavior.
- command registration schema validation (subcommands/options/limits).
- idempotency logic for duplicate interaction deliveries.
- status authorization checks (cross-tenant/cross-guild denial).

Integration tests:
- `/api/v1/discord/interactions` for ping/verification and command callbacks.
- `/api/v1/discord/oauth/callback` state validation + installation persistence.
- slash command registration upsert and refresh flow.
- Jobs enqueue + completion post flow with mocked Discord API client.
- follow-up fallback path when interaction token expires.
- policy enforcement for channel allow/deny and command allowlist.

Security tests:
- invalid signature rejection.
- expired/replayed request rejection.
- invalid/expired/reused OAuth state rejection.
- unauthorized status lookup rejection.
- token redaction in logs.

## 18. Rollout Plan
Phase 0 - Internal alpha
- tenant app config + OAuth install + interaction verification + `help` command only.

Phase 1 - v1 launch
- `ask`, `rag`, `summarize`, `status`.
- Jobs-based async processing with deferred/follow-up fallback.
- Admin policy endpoints + basic observability.

Phase 2 - v1.1+
- optional mention invocation, attachment ingestion expansion, richer interaction UX, optional voice integrations.

## 19. Acceptance Criteria (v1)
- Tenant admin can configure tenant-owned Discord app credentials and complete guild installation securely.
- Slash command `/tldw` works for defined command set.
- Invalid signatures/replayed requests are rejected with no processing.
- Duplicate requests are processed once.
- Long-running operations run through Jobs and report completion in Discord.
- Deferred response flow works, including fallback when interaction follow-up token is no longer usable.
- `status` only returns authorized request state within tenant/guild boundaries.
- Slash command registration schema is consistent with parser and deployed command metadata.
- Admin can list installations and manage policy.

## 20. Risks and Mitigations
- Discord retry/delivery duplication causes duplicate execution.
  - Mitigation: strict dedupe store + idempotent Jobs payloads.
- Tenant/guild mapping mistakes in multi-user mode.
  - Mitigation: explicit app+guild->tenant mapping and deny on unknown mapping.
- Tenant-owned app credential misconfiguration breaks command UX.
  - Mitigation: startup/config health checks and actionable admin diagnostics.
- Long async jobs exceed interaction follow-up token lifetime.
  - Mitigation: deferred response + controlled fallback to bot API posting.
- Scope creep (mentions, voice, deep interactive UI, broad attachment support).
  - Mitigation: freeze v1 to slash commands + async callbacks.

## 21. Open Questions
- Should channel posting defaults be global per guild or configurable per command?
- Should summarization support raw pasted long text by default in v1, or URL-first?
- Do we need per-command model/provider overrides for Discord workloads?
- For v1.1+, should we add a self-service Discord-to-local account linking flow?

## 22. Dependencies
- AuthNZ mapping and policy enforcement.
- Jobs manager for async execution + status.
- Existing Chat/RAG/Ingestion services.
- DB abstractions for app/install/token/event persistence.

## 23. Implementation Epics and Issue Checklist
Use this checklist to create and track implementation issues.

### Epic 1: Discord interaction foundation
Suggested issue title: `Discord v1 - Interaction endpoint and signature verification`
- [ ] Add `/api/v1/discord/interactions` endpoint for interaction handling.
- [ ] Implement Discord signature verification and replay-window checks.
- [ ] Add dedupe store for interaction retries keyed by `application_id + interaction_id`.
- [ ] Add ingress rate limiting by application/guild.
- [ ] Add daily pruning for `discord_oauth_states` and `discord_event_receipts` retention windows.

### Epic 2: Tenant app lifecycle and guild installation
Suggested issue title: `Discord v1 - Tenant app credentials and install lifecycle`
- [ ] Implement tenant app credential APIs and encrypted secret storage.
- [ ] Implement install URL generation with signed OAuth state.
- [ ] Implement OAuth callback state validation and installation persistence.
- [ ] Add disconnect/revoke path and guild disable toggle.
- [ ] Add admin APIs to list and remove installations.
- [ ] Add audit events for app credential updates, install/uninstall, and policy changes.

### Epic 3: Command parser and routing
Suggested issue title: `Discord v1 - Command parser and core action routing`
- [ ] Add `/tldw` slash command registration/upsert with subcommands/options defined in Section 11.
- [ ] Implement parser for `/tldw help|ask|rag|summarize|status`.
- [ ] Route `ask` to chat completions service.
- [ ] Route `rag` to unified RAG search.
- [ ] Route `summarize` to ingestion + summarize flow.
- [ ] Route `status` to authorized Jobs status lookup by `request_id`.
- [ ] Enforce allowed commands policy per guild/tenant.

### Epic 4: Jobs handoff and Discord response delivery
Suggested issue title: `Discord v1 - Async Jobs execution and follow-up messaging`
- [ ] Add Jobs payload contract for Discord command execution (`domain="discord"`) with `request_id` correlation.
- [ ] Return fast interaction acknowledgement before async execution (deferred when needed).
- [ ] Post completion/failure responses via interaction follow-up API.
- [ ] Add fallback to bot API posting when follow-up token is expired.
- [ ] Preserve channel/thread context in replies.
- [ ] Support policy-driven response mode (`channel|thread|ephemeral`).
- [ ] Add retry/backoff handling for Discord post failures.

### Epic 5: AuthNZ mapping and policy controls
Suggested issue title: `Discord v1 - Tenant mapping and admin policy controls`
- [ ] Implement app+guild-to-tenant mapping.
- [ ] Implement tenant service-user execution model for multi-user v1.
- [ ] Add optional strict policy gate for explicit user-link requirement (future-compatible).
- [ ] Add admin policy model and endpoints (`GET/PUT /api/v1/discord/admin/policy`).
- [ ] Add channel allow/deny controls and default response mode config.
- [ ] Add per-guild and per-tenant quotas.

### Epic 6: Observability, hardening, and release readiness
Suggested issue title: `Discord v1 - Testing, metrics, and production hardening`
- [ ] Add unit tests for signature/replay/parser/dedupe/OAuth-state/status-auth logic.
- [ ] Add integration tests for interactions endpoint, OAuth callback, and async completion flow.
- [ ] Add security tests for invalid signatures, replayed requests, invalid OAuth state, and unauthorized status lookups.
- [ ] Add metrics (`discord_requests_total`, `discord_signature_failures_total`, `discord_oauth_state_failures_total`, etc.).
- [ ] Add structured logs with `tenant_id`, `application_id`, `guild_id`, `interaction_id`, `command`, `job_id`, `request_id`.
- [ ] Add rollout checklist for alpha to v1 promotion with acceptance criteria sign-off.

### Milestone checklist
- [ ] Phase 0 complete: tenant app config + OAuth install + interaction verification + `help`.
- [ ] Phase 1 complete: `ask`, `rag`, `summarize`, `status` with Jobs integration.
- [ ] Acceptance criteria from Section 19 fully validated in staging.
