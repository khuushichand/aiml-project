# Last 25 Open Issues Closure Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Review the most recently opened 25 open issues and define a concrete, dependency-aware execution plan to close each issue.

**Architecture:** Organize work into four streams: ACP workflow follow-on tracks, Slack v1, Discord v1, and standalone enhancements. Execute foundation-first within each stream, then hardening/release gates last. Close epic issues only after linked child issues, docs, and acceptance checklists are complete.

**Tech Stack:** FastAPI, Workflows engine, Jobs manager, AuthNZ/RBAC, rate limiting, audit logging, pytest (unit/integration/security), existing Docs PRDs/design plans.

---

## Scope Reviewed (as of 2026-02-26)

Source query:
- `gh issue list --repo rmusser01/tldw_server --state open --limit 25 --json ...`

Issues covered:
- ACP Track 1/3: `#772`-`#781`
- Slack v1: `#739`-`#744`
- Discord v1: `#745`-`#750`
- Standalone enhancements: `#752`, `#757`, `#758`

## Portfolio Findings

1. 22/25 issues are already structured into epics/tracks with acceptance criteria; execution risk is mostly sequencing and integration, not unclear scope.
2. Slack and Discord streams are parallelizable, but each requires strict internal order:
   - ingress/security -> install/lifecycle -> parser/routing -> async jobs -> policy/governance -> hardening.
3. ACP Track 1 and Track 3 explicitly depend on Track 2 hardening follow-on work; avoid starting implementation until Track 2 gates are green.
4. `#757` and `#758` are intentionally broad; they need scope compression to avoid open-ended execution.

## Global Sequencing

### Stage 0: Pre-flight (1-2 days)
- Confirm Track 2 hardening status and open gaps before ACP Track 1/3 execution.
- Create a single project board for all 25 issues with dependency links.
- Add missing labels (`acp-track-1`, `acp-track-3`, `slack-v1`, `discord-v1`, `reading`, `workflow-nodes`, `image-gen`).
- Define shared Definition of Done template for issue closure:
  - implementation merged,
  - tests passing,
  - docs updated,
  - acceptance criteria checked in issue comment,
  - security checks completed.

### Stage 1: Foundation Implementation (2-4 weeks)
- Execute Slack `#739` then `#740` and Discord `#745` then `#746`.
- In parallel, execute ACP contract-first child issues `#774` and `#778`.

### Stage 2: Routing and Async Execution (2-3 weeks)
- Slack: `#741` -> `#742`; Discord: `#747` -> `#748`.
- ACP: `#775`, `#779`, `#780`.

### Stage 3: Governance and Hardening (2-3 weeks)
- Slack: `#743` -> `#744`; Discord: `#749` -> `#750`.
- ACP: `#776`, `#777`, `#781`.

### Stage 4: Epic and Enhancement Closeout (1-2 weeks)
- Close epics `#772` and `#773` after child closure evidence is posted.
- Close enhancements `#752`, `#757`, `#758` with scoped deliverables and follow-on links if needed.

## Issue-by-Issue Closure Plans

### #739 Slack v1 - Webhook foundation (events, commands, signature verification)
**Review:** Foundational ingress issue; no dedicated Slack endpoint module exists yet.
**Plan to close:**
1. Add `POST /api/v1/slack/events` and `POST /api/v1/slack/commands` endpoint module and route wiring in `main.py`.
2. Implement shared Slack signature and timestamp replay verification helper.
3. Add dedupe receipt store for `event_id` and command fingerprint; handle retry headers idempotently.
4. Add ingress rate limits and <=3s ACK behavior for heavy paths (handoff only).
5. Add unit/integration tests for valid, invalid, replayed, and duplicate requests.
**Close checklist:**
- URL verification challenge works.
- Invalid signatures and stale timestamps are rejected.
- Duplicate deliveries process once.

### #740 Slack v1 - OAuth install and workspace token management
**Review:** OAuth lifecycle and token security layer; prerequisite for multi-tenant production use.
**Plan to close:**
1. Add Slack installation and OAuth-state persistence schema (with expiry and single-use state).
2. Implement `/api/v1/slack/oauth/start` and `/api/v1/slack/oauth/callback`.
3. Encrypt bot tokens at rest using existing secret strategy; enforce redaction in logs/errors.
4. Implement admin installation endpoints (`GET/DELETE`) and disable/re-enable controls.
5. Add audit events and tests for success/failure/replay cases.
**Close checklist:**
- Install persists secure token.
- Replay/invalid OAuth state rejected.
- Admin install lifecycle actions functional.
**Dependencies:** `#739` recommended first.

### #741 Slack v1 - Command parser and core action routing
**Review:** Core user-facing command behavior for `/tldw` and mentions.
**Plan to close:**
1. Implement slash command parser for `help|ask|rag|summarize|status`.
2. Implement mention parser with default fallback to `ask`.
3. Route to existing chat, rag, summarize, and jobs-status services without duplicating business logic.
4. Add policy enforcement hook before execution.
5. Add parser and route integration tests for all supported commands and edge cases.
**Close checklist:**
- All supported commands parse and route correctly.
- Unknown commands return actionable usage guidance.
**Dependencies:** `#739`; policy hooks finalized by `#743`.

### #742 Slack v1 - Async Jobs handoff and Slack response posting
**Review:** Long-running command delivery path and completion messaging.
**Plan to close:**
1. Define `domain="slack"` Jobs payload with correlation metadata (`request_id`, workspace, channel/thread).
2. Return fast ACK and enqueue execution path.
3. Implement worker posting logic for completion/failure to Slack API.
4. Implement response-mode routing (`ephemeral|thread|channel`) and retry/backoff for posting failures.
5. Add integration tests for enqueue-success, posting-failure-retry, and mode selection.
**Close checklist:**
- ACK is under platform timeout.
- End-to-end async flow posts result in correct destination.
**Dependencies:** `#739`, `#741`.

### #743 Slack v1 - Tenant/user mapping and admin policy controls
**Review:** Multi-user safety and governance controls.
**Plan to close:**
1. Implement workspace->tenant resolution and Slack user->local user mapping model.
2. Enforce deny-by-default for unresolved users.
3. Implement `GET/PUT /api/v1/slack/admin/policy`.
4. Add command/channel allow-deny and response mode policy controls.
5. Add per-workspace/per-user quota checks and tests.
**Close checklist:**
- Unknown mappings are blocked.
- Policy changes are persisted and enforced.
- Quota errors are explicit and predictable.
**Dependencies:** `#740` and enforcement points in `#741/#742`.

### #744 Slack v1 - Testing, metrics, and production hardening
**Review:** Quality gate issue; should close last in Slack stream.
**Plan to close:**
1. Add missing unit/integration/security tests covering signatures, replay, parser, dedupe, policy, async posting.
2. Add Slack metrics and latency instrumentation.
3. Add structured logging fields and verify secret redaction.
4. Execute staging validation against PRD Section 19 acceptance criteria.
5. Publish rollout checklist and sign-off artifact.
**Close checklist:**
- Test suites pass reliably.
- Metrics/logs visible in staging.
- Rollout checklist completed with sign-off.
**Dependencies:** `#739`-`#743`.

### #745 Discord v1 - Interaction endpoint and signature verification
**Review:** Foundation issue for Discord integration ingress.
**Plan to close:**
1. Add `/api/v1/discord/interactions` endpoint and route wiring.
2. Implement Discord signature verification and replay-window checks.
3. Add dedupe store keyed by `application_id + interaction_id`.
4. Add ingress rate limits and scheduled pruning of OAuth state/receipts.
5. Add unit/integration/security tests for valid, invalid, replayed, and duplicated events.
**Close checklist:**
- Invalid signatures/replays rejected.
- Duplicate interactions are idempotent.

### #746 Discord v1 - Tenant app credentials and install lifecycle
**Review:** Tenant-owned credential and install lifecycle control plane.
**Plan to close:**
1. Add tenant app credential schema/APIs with encrypted secret storage.
2. Implement install URL generation with signed, expiring OAuth state.
3. Implement callback validation and installation persistence.
4. Add disconnect/revoke and guild disable toggles; list/remove installation admin APIs.
5. Add audit events and full callback/install tests.
**Close checklist:**
- Credential changes audited and encrypted.
- OAuth state single-use + expiry enforced.
- Install/uninstall flows are reliable.
**Dependencies:** `#745` recommended first.

### #747 Discord v1 - Command parser and core action routing
**Review:** Slash command registration + routing to platform services.
**Plan to close:**
1. Implement `/tldw` command registration/upsert contract.
2. Implement parser for `help|ask|rag|summarize|status`.
3. Route each command to existing services (chat/rag/summarize/jobs status).
4. Enforce guild/tenant command policy gate.
5. Add parser and route integration tests.
**Close checklist:**
- Registration schema matches runtime parser behavior.
- Disallowed commands are blocked with clear messaging.
**Dependencies:** `#745`; policy finalization in `#749`.

### #748 Discord v1 - Async Jobs execution and follow-up messaging
**Review:** Async path with Discord follow-up token expiry fallback.
**Plan to close:**
1. Define `domain="discord"` Jobs payload and `request_id` correlation contract.
2. Implement immediate deferred ack and job enqueue.
3. Implement follow-up completion/failure posting via interaction API.
4. Add bot API fallback path when follow-up token expires.
5. Add retry/backoff logic and integration tests for fallback behavior.
**Close checklist:**
- End-to-end async behavior works with fallback.
- Response mode and context preservation verified.
**Dependencies:** `#745`, `#747`.

### #749 Discord v1 - Tenant mapping and admin policy controls
**Review:** Multi-tenant policy/governance for Discord requests.
**Plan to close:**
1. Implement app+guild->tenant resolution and service-user execution model.
2. Add optional strict explicit user-link policy gate.
3. Implement `GET/PUT /api/v1/discord/admin/policy`.
4. Add channel controls and per-guild/per-tenant quotas.
5. Add policy, mapping, and quota enforcement tests.
**Close checklist:**
- Requests execute only in resolved tenant scope.
- Unknown mapping behavior is safe by default.
**Dependencies:** `#746`, enforcement hooks in `#747/#748`.

### #750 Discord v1 - Testing, metrics, and production hardening
**Review:** Final quality and observability gate for Discord v1.
**Plan to close:**
1. Add missing unit/integration/security test matrix.
2. Add metrics counters/histograms and structured log fields.
3. Verify redaction and status-auth protections.
4. Run staging acceptance validation against Discord PRD Section 19.
5. Publish rollout checklist and sign-off.
**Close checklist:**
- Tests pass; metrics/logging complete; rollout evidence posted.
**Dependencies:** `#745`-`#749`.

### #752 [Enhancement] Improve image generation prompt
**Review:** Scope is underspecified; references OpenAI imagegen skill guidance.
**Plan to close:**
1. Define explicit quality rubric and test prompt set (style fidelity, safety, prompt clarity).
2. Implement prompt refinement helper (opt-in/opt-out) for image generation requests.
3. Integrate helper into image generation entrypoints (file artifacts/workflow adapter) with guardrails.
4. Add unit tests for deterministic prompt transformations and safety constraints.
5. Document behavior and provide before/after examples in docs.
**Close checklist:**
- Prompt refinement is test-covered and documented.
- Quality rubric shows measurable improvement on sample set.

### #757 [Feature-add] Workflows: More Nodes
**Review:** Backlog-dump issue with open-ended node list; needs scoped delivery plan.
**Plan to close:**
1. Triage requested node ideas into `v1-now` and `later` buckets with explicit acceptance criteria.
2. Create child issues per node pack (e.g., chat integrations, OCR, scheduling, import/export) and link all.
3. Implement one prioritized node pack end-to-end (adapter + registry + docs + tests).
4. Publish support matrix documenting implemented vs deferred nodes.
5. Close this umbrella issue as superseded by scoped child issues and delivered first pack.
**Close checklist:**
- Unbounded scope converted into tractable child backlog.
- At least one node pack shipped with tests/docs.

### #758 [Enhancement] Read-it-Later improvements
**Review:** High-level request with Omnivore reference; needs concrete v1 scope.
**Plan to close:**
1. Perform gap analysis of current `reading` endpoints/service vs target Omnivore-like capabilities.
2. Define v1 improvement slice (capture quality, item triage UX/API, archive/export, metadata quality).
3. Implement prioritized backend changes in `reading_service` and reading endpoints.
4. Add integration tests for improved ingest, status transitions, and import/export behavior.
5. Update docs and migration notes for new reading features.
**Close checklist:**
- Agreed v1 feature slice shipped and documented.
- Reading workflow tests cover new behavior.

### #772 Epic: ACP sandbox/workspace lifecycle integration for pipeline stages
**Review:** Epic issue; should close only after children `#774-#777` are complete.
**Plan to close:**
1. Confirm Track 2 dependency completion and link evidence.
2. Execute child issues in dependency order: `#774` -> `#775` -> (`#776`, `#777` in parallel).
3. Run workflow integration tests for bootstrap, branch/retry/cancel, teardown, and diagnostics.
4. Update design/operations docs with final lifecycle contract.
5. Mark child checklist complete and close epic with summary comment.
**Close checklist:**
- All child issues closed with merged code/tests/docs.
- Epic checklist and dependencies updated.

### #773 Epic: Pipeline control/status API expansion for ACP-centric runs
**Review:** API-surface expansion epic; depends on stable workflow contracts.
**Plan to close:**
1. Confirm Track 2 and Track 1 prerequisites relevant to status/control data consistency.
2. Execute child issues in order: `#778` -> `#779` -> `#780` -> `#781`.
3. Validate OpenAPI contracts and consumer-safe payload examples.
4. Run authz/rate-limit/audit integration validation.
5. Close epic after child checklist and docs are complete.
**Close checklist:**
- All child issues closed and acceptance criteria met.

### #774 Track 1: Workspace/session provisioning contract for workflow-run bootstrap
**Review:** Contract-first issue and starting point for Track 1.
**Plan to close:**
1. Define required provisioning fields/invariants and failure reasons in design doc.
2. Implement bootstrap validation in workflow run creation path.
3. Add explicit mapping to normalized reason codes.
4. Identify and wire integration touchpoints in ACP/workflow bootstrap path.
5. Add unit/integration tests for valid/invalid contract payloads.
**Close checklist:**
- Contract and invariants documented.
- Validation/failure behavior implemented and tested.
**Dependencies:** Track 2 hardening complete.

### #775 Track 1: Stage-level workspace binding and metadata propagation
**Review:** Ensures deterministic workspace metadata continuity across transitions.
**Plan to close:**
1. Define deterministic propagation rules for `workspace_id`, `workspace_group_id`, and session IDs.
2. Implement propagation enforcement across normal, branch, retry, and cancel paths.
3. Add integrity checks to prevent metadata drift.
4. Update artifact/event payloads to include required binding metadata.
5. Add integration tests for branch/retry/cancel integrity.
**Close checklist:**
- Binding integrity preserved across all transition paths.
**Dependencies:** `#774`.

### #776 Track 1: Workspace lifecycle teardown and reconciliation behavior
**Review:** Cleanup and orphan handling for partial failures.
**Plan to close:**
1. Define teardown triggers for success, cancel, and failure paths.
2. Implement teardown workflow and ownership validation checks.
3. Implement reconciliation worker for orphan resources and partial-failure recovery.
4. Add deterministic behavior for unrecoverable orphan scenarios.
5. Add tests for teardown idempotency and reconciliation outcomes.
**Close checklist:**
- Teardown policy and reconciliation rules are explicit and validated.
**Dependencies:** `#774`; interacts with `#775`.

### #777 Track 1: Sandbox diagnostic linkage and failure-mode normalization
**Review:** Operability and reason-code normalization issue.
**Plan to close:**
1. Create taxonomy mapping from sandbox failures to workflow reason codes.
2. Standardize diagnostic artifact fields/links in run/step outputs.
3. Ensure failure outputs are safe and non-sensitive.
4. Add observability fields for debugging correlation.
5. Add unit/integration tests for taxonomy mapping and diagnostic link presence.
**Close checklist:**
- Failure taxonomy and diagnostics are consistent across failure classes.
**Dependencies:** `#774`; uses metadata from `#775`.

### #778 Track 3: Run control endpoint contract review (pause/resume/cancel/retry)
**Review:** Contract-design issue for control semantics and idempotency.
**Plan to close:**
1. Publish action-by-state contract matrix for pause/resume/cancel/retry.
2. Define idempotency behavior (`applied` vs `already_applied`) per action.
3. Define explicit error and reason-code responses for terminal and invalid states.
4. Implement/adjust endpoint contracts and OpenAPI docs.
5. Add contract and API behavior tests.
**Close checklist:**
- Contract matrix published and implemented.
- Error and reason-code behavior explicit and tested.
**Dependencies:** Track 2 hardening complete.

### #779 Track 3: Stage-level status and reason-code response schema
**Review:** Consumer-facing status contract for timeline rendering.
**Plan to close:**
1. Define versioned schema for run/stage status payloads.
2. Define compatibility policy and migration handling for schema evolution.
3. Implement serializer normalization and reason-code enumerations.
4. Document edge-case payloads (timeouts, retries, cancels, blocked, invariant failures).
5. Add schema validation and compatibility tests.
**Close checklist:**
- Versioned schema and compatibility policy documented and enforced.
**Dependencies:** `#778`.

### #780 Track 3: Artifact/event query APIs for run timeline consumers
**Review:** Query surfaces needed by timeline/debug consumers.
**Plan to close:**
1. Define query filters, pagination, and sorting contract.
2. Implement artifact/event query endpoints with tenant-scoped access control.
3. Add response schema docs and timeline usage examples.
4. Add indexes/perf tuning for expected query paths.
5. Add integration tests for filters, paging, and authorization.
**Close checklist:**
- Query contract explicit, documented, and validated in tests.
**Dependencies:** `#779`.

### #781 Track 3: API authz/rate-limit/audit hardening for expanded control surface
**Review:** Security/operability hardening for new control and query APIs.
**Plan to close:**
1. Build permission matrix for all new control/status/query endpoints.
2. Apply route-level rate limits and quota alignment.
3. Add audit event coverage for all control actions and privileged queries.
4. Add authz/rate-limit/audit test suite.
5. Complete security review and document controls.
**Close checklist:**
- Authz, rate-limit strategy, and audit coverage are complete and tested.
**Dependencies:** `#778`, `#779`, `#780`.

## Parallelization Matrix

- Can run in parallel:
  - Slack stream (`#739`-`#744`) and Discord stream (`#745`-`#750`) after shared infra decisions.
  - ACP Track 1 (`#774`-`#777`) and Track 3 (`#778`-`#781`) once Track 2 gate is met.
- Must remain sequential:
  - Slack foundation -> hardening (`#739` -> `#744`).
  - Discord foundation -> hardening (`#745` -> `#750`).
  - ACP contracts -> schemas -> query/hardening (`#778` -> `#781`).

## Verification and Closure Evidence Template (for every issue)

1. Linked PR(s) merged.
2. Test commands/results pasted (unit/integration/security).
3. Docs updated with exact paths.
4. Acceptance criteria checklist fully checked in issue comment.
5. If epic: all child links closed and summarized.

