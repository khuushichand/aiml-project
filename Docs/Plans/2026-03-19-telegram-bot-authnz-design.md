# Telegram Bot + AuthNZ/MCP Governance Design

Date: 2026-03-19
Status: Approved

## Summary

Add first-class Telegram bot support to `tldw_server` as a tenant-scoped integration that reuses existing Chat, Persona, Character Chat, Jobs, Workflows, Notifications, and MCP Hub governance primitives.

Telegram is a client surface, not a separate execution authority. All execution, including bot commands, freeform chat, persona sessions, character chat, workflow runs, and spawned agents, must be authorized through the existing AuthNZ + MCP Hub control plane with scoped, auditable execution identities.

## Goals

- Provide first-class Telegram support for end users.
- Support conversational interaction, not just utility commands.
- Allow Telegram to interact with:
  - assistant chat
  - personas
  - characters
  - workflows
  - Jobs-backed async actions
- Make MCP Hub and AuthNZ the single policy authority for bots, personas, workflows, and spawned agents.
- Enforce least-privilege execution for all child agents and workflow steps.
- Keep multi-user tenant isolation strong from day one.

## Non-Goals

- Building a Claude-style always-on live session bridge as the primary v1 model.
- Granting Telegram broad ambient tenant authority.
- Supporting every Telegram media/update type in v1.
- Creating a Telegram-only conversation store separate from existing chat/session systems.
- Adding generic filesystem/process access to Telegram principals by default.

## Product Decisions Captured

- Telegram v1 is a first-class bot surface, closer to the existing Discord direction than a notification-only delivery channel.
- Multi-user tenant-safe behavior is the primary optimization target.
- Approval and permission requests should surface in Telegram chat, not be forced back into the web UI.
- Chat, personas, and characters should all be interactable via Telegram.
- Unknown Telegram users are denied by default for data-bearing and tool-using actions.
- Service-principal fallback is allowed only for explicitly allowlisted low-risk workflows or utilities.
- Telegram v1 uses webhooks, not long polling.
- Telegram v1 is text-first:
  - text messages
  - bot commands
  - callback queries for approvals and mode switching

## Approaches Considered

### 1. Tenant-scoped Telegram bot integration with MCP/AuthNZ-governed execution (recommended)

Each tenant owns Telegram bot configuration and policy. Telegram updates are ingested by `tldw_server`, resolved to a tenant and actor, then executed through existing Jobs, Workflows, Chat, Persona, Character Chat, and MCP Hub policy enforcement.

Pros:

- Best fit for multi-user isolation.
- Matches the repository direction for first-class integrations.
- Keeps policy centralized.
- Naturally supports future expansion.

Cons:

- More up-front schema and admin work.

### 2. One deployment-wide Telegram bot with routing rules

One bot serves all tenants using allowlists and routing metadata.

Pros:

- Lower initial setup complexity.

Cons:

- Higher routing and isolation risk.
- Weaker audit story.
- Poorer hosted or shared deployment fit.

### 3. Live-session relay first

Treat Telegram primarily as a bridge into a running agent session.

Pros:

- Closest to the Claude channels concept.

Cons:

- Poor fit for end-user reliability.
- Weak fit for tenant-safe multi-user execution.
- Less aligned with existing Jobs/Workflows architecture.

## Recommendation

Use approach 1.

Telegram should be a first-class tenant integration domain with centralized policy enforcement, narrow execution identities, and tight reuse of the existing Jobs, Workflows, Chat, Persona, Character Chat, and MCP Hub subsystems.

## Existing Context

The current repo already contains critical primitives this design should reuse rather than replace:

- Core Scheduler:
  - `tldw_Server_API/app/core/Scheduler/scheduler.py`
- Workflows recurring scheduler:
  - `tldw_Server_API/app/services/workflows_scheduler.py`
- Reminders and notifications:
  - `tldw_Server_API/app/services/reminders_scheduler.py`
  - `tldw_Server_API/app/api/v1/endpoints/notifications.py`
  - `apps/tldw-frontend/pages/notifications.tsx`
- Discord integration precedent:
  - `tldw_Server_API/app/api/v1/endpoints/discord.py`
  - `tldw_Server_API/app/api/v1/endpoints/discord_oauth_admin.py`
  - `Docs/Product/Discord_Bot_PRD.md`
- MCP Hub governance and capability direction:
  - `Docs/Plans/2026-03-09-mcp-hub-tool-permissions-design.md`
  - `Docs/Plans/2026-02-24-mcp-acp-unified-governance-plane-design.md`
  - `Docs/Plans/2026-03-11-mcp-hub-multi-root-path-execution-design.md`

Telegram should be built as another integration domain on top of those systems.

## Architecture

### Telegram as an ingress and delivery surface

Telegram should be treated as an ingress surface plus a reply delivery surface.

It is not a separate authority system. It should not bypass:

- AuthNZ RBAC
- MCP Hub effective policy resolution
- workflow step scoping
- tool approval logic
- workspace/path enforcement

### Main components

- `Telegram Integration`
  - inbound webhook handling
  - update validation
  - dedupe and replay protection
  - outbound reply delivery
  - chat metadata tracking
- `Telegram Policy Resolver`
  - resolve tenant, chat policy, actor mapping, command allowlists, mode restrictions
- `Execution Identity Broker`
  - issue short-lived scoped execution identities for Telegram-originated runs
- `Telegram Jobs Adapter`
  - async handoff and reply correlation for long-running actions
- `Telegram Session Mapper`
  - map Telegram contexts onto existing assistant chat, persona session, and character chat records

### Core principle

All Telegram execution is downscoped.

A Telegram request may initiate a workflow or spawn a child agent, but every downstream execution context must receive only the exact permissions and capabilities declared for that unit of work. No child may inherit broad tenant authority by default.

## Execution and Data Flow

### Inbound update flow

1. Telegram sends an update to `POST /api/v1/telegram/webhook`.
2. The server validates webhook secret and bot identity.
3. The server records a dedupe receipt and rejects replayed or malformed updates.
4. The server resolves:
   - tenant bot record
   - chat binding
   - actor link
   - chat policy
   - target interaction mode
5. The MCP/AuthNZ layer issues a short-lived execution identity.
6. The request is routed to one of:
   - immediate execution for cheap read-only actions
   - Jobs for long-running actions
   - Workflows for multi-step orchestrated actions
   - chat/persona/character session handling
7. The result is delivered back to Telegram and optionally persisted to the in-app notifications system when policy requires it.

### Immediate vs async paths

Use immediate execution for:

- `help`
- cheap `status`
- lightweight mode selection
- cheap metadata lookups

Use Jobs for:

- `ask`
- `rag`
- `summarize`
- persona or character turns that may require model/tool activity
- long-running tool-backed actions
- outbound reply retries

Use Workflows for:

- composite or policy-governed actions
- scheduled or reusable automations
- actions requiring child agent orchestration

### Scheduled behavior

Scheduled actions may target Telegram, but scheduled runs do not inherit broad privileges.

Every scheduled execution receives a dedicated scoped identity, similar in spirit to the existing scheduler virtual-key minting path, but generalized so it can also represent Telegram-targeted or bot-originated actions.

## AuthNZ and MCP Hub Governance Model

### Single policy authority

MCP Hub remains the canonical editor and resolver for:

- tool permissions
- approval rules
- capability profiles
- overrides
- credential bindings
- effective policy evaluation

Telegram consumes this model. It does not define a second policy source of truth.

### Permission layers

Telegram should use three authorization layers:

1. Integration admin permissions
   - who may configure Telegram bot credentials, webhooks, and policies
2. Entry permissions
   - which chats and users may invoke which commands, personas, characters, and workflows
3. Execution capabilities
   - what a given Telegram-triggered session, workflow step, or child agent may actually do

### Suggested Telegram-specific permissions

- `telegram.admin`
- `telegram.receive`
- `telegram.reply`

These should complement, not replace, existing business permissions such as:

- `workflows.runs.control`
- `workflows.runs.read`
- `notifications.control`
- `notifications.read`
- `tasks.control`
- `tasks.read`
- domain-specific MCP capabilities such as `filesystem.read`, `filesystem.write`, `tool.invoke`, and future service-specific capability families

### Scoped execution identity

Every Telegram-originated run should bind:

- `tenant_id`
- `source = telegram`
- Telegram actor metadata
- linked user or service principal id
- allowed permissions
- allowed capabilities
- optional explicit scope ids:
  - `conversation_id`
  - `character_id`
  - `persona_id`
  - allowed workflow ids
  - allowed tool ids
  - allowed workspace ids
- TTL
- correlation ids

This execution identity should be claim-first and usable by:

- APIs
- Jobs workers
- Workflows
- MCP tool execution
- child agents

Implementation note:

- Telegram-originated Jobs should carry this brokered context in a top-level `execution_identity` payload field.
- Parent Telegram identities should include the transport permissions needed to receive and reply on Telegram, plus the linked actor's resolved permissions.
- Workspace, workflow, and tool allowlists should default to empty until an explicit policy or binding narrows them in.

### Downscoped child agents

If a Telegram request spawns a workflow or child agent, each child receives a narrower identity.

Example:

- parent intent: “check my email and summarize”
- child A: `email.read`
- child B: `llm.generate`
- child C: `telegram.reply`

Child A cannot send mail or delete mail.
Child B cannot access the mailbox.
Child C cannot read mail or mutate workspace state.

## Workspace and Tool Scope Rules

Telegram should start with no filesystem/process/workspace capability by default.

Path-bound or workspace-bound tools may only be used when:

- MCP Hub policy explicitly grants them
- the execution identity includes the allowed workspace binding
- the workspace/path resolver can unambiguously map the request into trusted scope

If Telegram-triggered execution lacks explicit workspace binding, those tools fail closed.

This is required to remain consistent with the existing MCP Hub path enforcement model.

## Tenant, Bot, Chat, and Actor Model

### Tenant-owned bots

Each tenant owns its Telegram bot configuration.

Telegram does not have a Discord-style install lifecycle, so the admin flow is:

- store tenant bot token securely
- discover or validate bot metadata
- register webhook and secret token
- enable/disable bot
- manage chat and actor policies

### Unknown users

Unknown Telegram users should be denied by default for:

- tenant data access
- chat/persona/character access
- workflows
- MCP tools
- anything approval-bearing

### Service-principal fallback

Service-principal fallback is allowed only for explicitly allowlisted low-risk utilities or workflows.

Those fallback executions must:

- be declared in policy
- use narrow predeclared capabilities
- never act as a broad tenant superuser
- remain auditable as service-principal executions

## Chat, Persona, and Character Interaction Model

Telegram v1 should support three conversation modes:

- `assistant`
- `persona`
- `character`

### Assistant chat

Default general-purpose tldw conversation over the existing chat stack.

### Persona chat

Conversation bound to an allowed persona and its effective MCP/tool policy.

### Character chat

Conversation bound to an allowed character or character-card session, using the existing character chat stack and storage rather than creating a Telegram-only clone.

### Interaction model

Support both explicit commands and sticky mode.

Examples:

- `/ask ...`
- `/rag ...`
- `/summarize ...`
- `/status ...`
- `/mode assistant`
- `/persona set <persona>`
- `/character set <character>`

After mode is selected, follow-up messages in an eligible context continue the active session.

### Session mapping contract

Telegram must not create a second-class conversation store.

Canonical session records remain the existing assistant chat, persona session, and character chat/session records. Telegram-specific metadata is attached to those canonical records for correlation, replay, and UI continuity.

### Session key rules

DM session key:

- `tenant + telegram_user`

Group/topic session key:

- `tenant + telegram_chat + topic_or_thread + telegram_user`

This avoids one group chat or one user mutating another user’s persona or character context.

### Group-chat safety

DMs may support sticky freeform mode.

Group chats should default to stricter interaction:

- explicit commands
- reply-to-bot flows
- stricter policy than DMs

Freeform sticky group behavior should be opt-in and policy-gated.

## Approval and Permission Requests

Approval-required actions should be surfaced in Telegram chat.

### Approval flow

1. Runtime detects `require_approval`.
2. Server creates a pending approval record.
3. Bot sends an approval message with:
   - short summary
   - requested capability/tool/action
   - expiry
   - `Approve`
   - `Deny`
4. User response is sent via callback query.
5. Server validates:
   - approval record exists
   - record is not expired
   - approver identity matches policy
   - requested scope exactly matches the pending request fingerprint
6. If approved, execution resumes.
7. If denied or expired, execution terminates with an auditable denial state.

### Approval safety rules

- Approval records are single-use.
- Approval records are short-lived.
- Approval scope is exact:
  - exact tool
  - exact normalized arguments
  - exact workspace bundle if relevant
  - exact identity context
- Any change to scope invalidates the approval and requires a new request.

### DM vs group approval

In DMs:

- the linked user may approve inline

In groups:

- only the initiating linked user may approve
- policy may force high-risk approvals into DM with the bot even if the request started in a group

This allows Telegram-native approval without making group chats ambient approval surfaces.

## API Surface

Base prefix: `/api/v1/telegram`

### Public endpoint

- `POST /webhook`
  - Telegram update receiver

### Authenticated admin endpoints

- `GET /admin/bot`
- `PUT /admin/bot`
- `POST /admin/webhook/sync`
- `GET /admin/policy`
- `PUT /admin/policy`
- `GET /admin/chats`
- `POST /admin/link/start`
- `GET /admin/links`
- `DELETE /admin/links/{telegram_user_id}`
- `GET /jobs/{request_id}`

### Optional future endpoints

- admin test-send
- chat reset
- session mode reset
- command catalog discovery

## Data Model

Use DB abstractions under `app/core/DB_Management/` and existing AuthNZ secret storage patterns.

### `telegram_tenant_bots`

- `id`
- `tenant_id`
- `bot_id`
- `bot_username`
- `bot_token_encrypted`
- `webhook_url`
- `webhook_secret`
- `enabled`
- `created_at`
- `updated_at`

### `telegram_chat_bindings`

- `id`
- `tenant_id`
- `chat_id`
- `chat_type`
- `chat_title`
- `chat_username`
- `enabled`
- `last_seen_at`
- `created_at`
- `updated_at`

### `telegram_actor_links`

- `id`
- `tenant_id`
- `telegram_user_id`
- `telegram_username`
- `auth_user_id`
- `service_principal_id` nullable
- `status`
- `created_at`
- `updated_at`
- `linked_by`

### `telegram_pairing_codes`

- `id`
- `tenant_id`
- `auth_user_id`
- `code_hash`
- `expires_at`
- `consumed_at`
- `created_at`

### `telegram_chat_policies`

- `id`
- `tenant_id`
- `chat_id` nullable for tenant default
- `allowed_commands_json`
- `allowed_persona_ids_json`
- `allowed_character_ids_json`
- `allowed_workflow_ids_json`
- `response_mode`
- `allow_service_principal_fallback`
- `quota_profile`
- `enabled`
- timestamps

### `telegram_update_receipts`

- `id`
- `tenant_id`
- `update_id`
- `chat_id`
- `message_id`
- `received_at`
- `dedupe_expires_at`

### `telegram_job_messages`

- `id`
- `tenant_id`
- `chat_id`
- `thread_or_topic_id`
- `telegram_user_id`
- `request_id`
- `job_id`
- `workflow_run_id`
- `conversation_id`
- `persona_session_id`
- `character_session_id`
- `created_at`
- `updated_at`

### `telegram_approvals`

- `id`
- `tenant_id`
- `approval_token`
- `initiating_auth_user_id`
- `chat_id`
- `approval_scope_fingerprint`
- `status`
- `expires_at`
- `approved_at`
- `approved_by_auth_user_id`
- `created_at`

## Security and Failure Handling

### Fail-closed conditions

Reject without execution on:

- unknown tenant bot
- secret token mismatch
- malformed payload
- replayed update
- expired or invalid pairing code
- missing actor link when policy requires linked-user execution
- unsupported update type
- missing workspace binding for workspace-scoped tools

### Safe user-facing errors

Return short non-leaky Telegram responses such as:

- `not allowed`
- `account linking required`
- `approval expired`
- `unsupported in this chat`

Detailed deny reasons go to audit logs, not the chat.

### Delivery guarantees

Outbound Telegram delivery should run through Jobs for retry-safe posting on async paths.

If delivery fails after execution succeeds:

- persist the successful result state
- surface it through in-app notifications or status retrieval
- do not lose the completed outcome

### Loop suppression

Ignore self-originated or unsupported update patterns that could create bot loops.

## Quotas and Cost Controls

Telegram chat surfaces can drive sustained model usage. V1 should define:

- per-tenant quotas
- per-chat quotas
- per-user quotas
- default low-cost model policy for Telegram interaction
- optional command-specific or mode-specific model overrides

These quotas should apply before expensive execution starts, not after.

## Testing Strategy

### Unit tests

- webhook validation
- tenant bot resolution
- dedupe and replay handling
- policy evaluation
- actor-link enforcement
- service-principal fallback gating
- execution identity minting
- approval record validation
- child-agent downscoping

### Integration tests

- webhook to Jobs flow
- webhook to Workflow run flow
- assistant chat via Telegram
- persona session via Telegram
- character chat via Telegram
- paired-user execution
- inline approval approve/deny flow
- Telegram reply correlation
- in-app notification fallback on delivery failure

### Security tests

- forged secret rejection
- replayed update rejection
- cross-tenant chat spoofing rejection
- expired pairing code rejection
- unauthorized approval attempt rejection
- unauthorized service-principal fallback rejection
- capability escalation rejection
- explicit regression:
  - child agent with `email.read` cannot invoke `email.delete`

## Observability

Emit structured logs and metrics with:

- `tenant_id`
- `bot_id`
- `chat_id`
- `telegram_user_id`
- `auth_user_id`
- `request_id`
- `job_id`
- `workflow_run_id`
- `conversation_id`
- `persona_id`
- `character_id`
- `approval_id`
- `policy_outcome`

Suggested metrics:

- `telegram_requests_total`
- `telegram_webhook_failures_total`
- `telegram_signature_failures_total`
- `telegram_updates_duplicate_total`
- `telegram_jobs_enqueued_total`
- `telegram_approval_requests_total`
- `telegram_approval_denied_total`
- `telegram_delivery_failures_total`

## Acceptance Criteria

- Tenant-owned Telegram bots are configurable and auditable.
- Telegram users can be linked to AuthNZ identities.
- Telegram supports:
  - assistant chat
  - persona chat
  - character chat
  - core commands
  - Jobs-backed async actions
- Telegram-triggered workflows and child agents execute under scoped identities.
- MCP Hub remains the single effective policy authority.
- Child agents and workflow steps are downscoped and auditable.
- Approval-required actions can be surfaced and resolved in Telegram under exact-scope approval rules.
- Unknown Telegram users are denied by default for privileged or data-bearing actions.
- Telegram does not create a separate second-class chat/session store.

## Recommended v1 Scope Boundary

Include:

- tenant bot config
- webhook intake
- actor linking
- assistant/persona/character chat
- `help`, `ask`, `rag`, `summarize`, `status`
- Jobs handoff
- workflow launch
- Telegram-native approval callbacks

Defer:

- voice note flows
- arbitrary file upload flows
- broader media and rich interaction surfaces
- always-on live-session relay mode
- any expansion that weakens central policy enforcement
