# Unified Governance Plane for MCP Unified + ACP

Date: 2026-02-24
Status: Approved for implementation planning
Owner: Codex + user collaboration

## 1. Goal

Design a strategic governance layer that can be applied consistently across:

- MCP Unified tool execution.
- ACP prompt and permission flows.

The governance layer should provide:

- Queryable team knowledge/policies.
- Validation before risky actions.
- Explicit gap detection and resolution workflows.
- Deterministic, auditable policy enforcement.

## 2. Confirmed Scope Decisions

Validated with user:

1. Scope includes both MCP Unified and ACP.
2. Planning horizon is strategic (2+ week architecture-level changes).
3. ACP has no existing external clients, so ACP contracts can be designed cleanly.
4. MCP wire compatibility must be preserved for now, with additive deprecation guidance for legacy behavior.

## 3. Approaches Considered

## Approach A: Policy/Packaging improvements only

- Port only lightweight concepts (manifesting, tool metadata standardization, logging improvements).

Pros:
- Lowest implementation risk.

Cons:
- Does not deliver governance memory/enforcement value.

## Approach B: ACP-first governance interceptor

- Apply governance in ACP only (prompt + permission paths), defer MCP integration.

Pros:
- Faster path to visible behavior change in agent workflows.

Cons:
- Creates policy gaps for direct MCP callers.
- Requires later duplication or refactor.

## Approach C (Recommended): Unified governance plane across MCP + ACP

- Introduce one shared governance domain with reusable enforcement and policy resolution.
- Integrate into both MCP and ACP runtime paths.

Pros:
- Single source of truth for policy decisions.
- Deterministic behavior and better auditability.
- Avoids MCP/ACP divergence.

Cons:
- Highest implementation complexity.

Decision: Approach C.

## 4. Target Architecture

## 4.1 Governance Domain Layer

Add a new shared core package:

- `tldw_Server_API/app/core/Governance/`

Responsibilities:

- Rule retrieval (`query_knowledge`).
- Change/action validation (`validate_change`).
- Gap lifecycle (`resolve_gap`).
- Shared policy conflict resolution and fallback behavior.
- Deterministic decision traces for audits/replay.

## 4.2 MCP Surface

Add MCP tools via a new module:

- `tldw_Server_API/app/core/MCP_unified/modules/implementations/governance_module.py`

Tools:

- `governance.query_knowledge`
- `governance.validate_change`
- `governance.resolve_gap`

All tools remain first-class MCP tools so they inherit existing auth/RBAC/catalog/rate-limit patterns.

## 4.3 Enforcement Hook Points

MCP Unified:

- Pre-execution governance preflight in `MCPProtocol._handle_tools_call` before underlying module execution.

ACP:

- Preflight on `POST /api/v1/acp/sessions/prompt`.
- Preflight in WS prompt handling.
- Preflight/decision escalation in `session/request_permission` handling in runner clients.

## 4.4 Approval Decision Coordination

Use one ACP decision coordinator (single state machine) to unify:

- ACP tier-based approval needs.
- Governance `require_approval` actions.

Precedence:

- `deny > require_approval > warn > allow`

## 5. Revised Data Model and Schemas

## 5.1 Persistence Tables

`governance_rules`

- `id`, `org_id`, `team_id`, `persona_id`, `workspace_id` (nullable scope columns)
- `category`, `title`, `body_markdown`, `status`, `priority`
- `effective_from`, `expires_at`, `created_by`, timestamps

`governance_rule_revisions` (append-only)

- `rule_id`, `revision`, `content_hash`, `body_markdown`, `change_note`, `created_by`, `created_at`

`governance_policies`

- scope columns (`org_id`, `team_id`, `persona_id`, `workspace_id`)
- `default_mode` (`ask_user|agent_decide|auto_resolve`)
- `failure_mode` (`fail_open|fail_closed|warn_only`)
- timestamps

`governance_policy_rules`

- `policy_id`, `surface` (`mcp_tool_call|acp_prompt|acp_permission`)
- `category`, `severity` (`info|warn|error`)
- `action` (`allow|warn|require_approval|deny`)
- optional patterns (`tool_pattern`, `agent_type_pattern`)

`governance_gaps`

- scope columns, `question`, `question_fingerprint`, `category`
- `status` (`open|resolved|dismissed`)
- `resolution_mode`, `resolution_text`
- `owner_user_id`, `review_due_at`, `resolved_by`, timestamps

`governance_validations` (immutable audit log)

- scope columns, `surface`, `subject_type`, `subject_id`
- `status` (`pass|fail|warn`), `category`, `violations_json`, `suggested_fix`
- `content_hash`, `redacted_excerpt`, `secret_scan_flags_json`
- `policy_id`, `policy_revision`, `matched_policy_rule_ids_json`
- `matched_rule_revision_ids_json`, `resolver_version`, `engine_version`
- `effective_action`, `fallback_reason`, `latency_ms`, timestamps

`governance_validation_sources`

- `validation_id`, `rule_id`, `rule_revision`

## 5.2 Constraints and Indexes

- Unique open-gap dedupe via partial uniqueness on fingerprint+scope+category where `status='open'`.
- Composite indexes on scope/category/status for rules/policies/gaps/validations.
- FTS5 index for rule content and title search.

## 5.3 Runtime Schemas

`governance.query_knowledge`

- Inputs: `query`, `category`, optional `scope_context`

`governance.validate_change`

- Inputs: `task`, `category`, `surface`, and one of:
  - `code`
  - `tool_name + arguments`
  - `prompt/messages`

`governance.resolve_gap`

- Inputs: `question`, `category`, optional `candidate_resolution`

Outputs include:

- `status`, `sources`, `gap_detected`, `resolution_mode`, `decision_id`

## 5.4 Category Canonicalization

Use one canonical category enum:

- `architecture`, `stack`, `testing`, `deployment`, `security`, `style`,
  `dependencies`, `error_handling`, `business_logic`, `general`

Category mapping service returns:

- canonical category
- source (`explicit|metadata|pattern|default`)
- confidence

## 6. End-to-End Request Flow

## 6.1 MCP `tools/call`

1. Request enters `_handle_tools_call`.
2. Governance preflight executes with scope, surface, category, tool, args.
3. Governance action resolved:
   - `allow` -> execute
   - `warn` -> execute + warning metadata
   - `require_approval` -> structured approval-required response
   - `deny` -> structured deny response
4. Audit row persisted with traceable policy/rule revision references.

## 6.2 ACP Prompt Flow

1. Prompt request (REST or WS) is preflighted via governance.
2. Actions:
   - `allow/warn` -> continue
   - `require_approval` -> queued through unified ACP approval coordinator
   - `deny` -> block with structured reason
3. Validation/audit record persisted.

## 6.3 ACP Permission Flow

1. `session/request_permission` receives tool request.
2. Governance preflight runs before tier auto-approval logic.
3. ACP tier + governance requirement are normalized into one approval decision.
4. Single pending approval record per action fingerprint.

## 6.4 Gap Lifecycle

1. If no rule coverage is found, compute deterministic question fingerprint.
2. Transactional upsert/fetch of open gap.
3. Apply resolution mode:
   - `ask_user` -> block or approval queue
   - `agent_decide` -> proceed with warning + tracked gap
   - `auto_resolve` -> proceed with stored resolution
4. Persist decision trace and identifiers.

## 7. Risk Controls (Resolved)

## 7.1 Recursion Guard

- Bypass governance checks for `governance.*` tools and internal calls via metadata marker.
- Add depth guard (`governance_depth`) to prevent recursive loops.
- Keep RBAC active even with governance bypass.

## 7.2 Dual Approval Pipeline Avoidance

- One ACP decision coordinator with deterministic precedence:
  - `deny > require_approval > warn > allow`
- One pending approval record per action fingerprint.

## 7.3 Policy Conflict Determinism

- Scope precedence:
  - `workspace/persona > team > org > global`
- Same-scope tie-breakers:
  - `priority`, then latest `updated_at`
- Store winning and losing candidates in decision trace.

## 7.4 Latency Controls

- Per-surface timeout budgets.
- Read-through caches for policy/rule snapshots.
- Circuit breaker around governance backend operations.

## 7.5 Fallback Consistency

- One shared fallback resolver for MCP + ACP.
- Default global fallback if no scoped override exists.
- Full fallback trace persisted per event.

## 7.6 Gap Dedupe Race Safety

- DB-enforced uniqueness for open gaps.
- Transactional insert-or-fetch pattern with retry-safe handling.

## 7.7 Multi-Tenant Isolation

- Scope filter applied before ranking/FTS results.
- Shared scope predicate builder for all queries.
- Cross-scope access requires explicit elevated permission.

## 7.8 Metrics Cardinality Safety

- Low-cardinality labels only for Prometheus dimensions.
- High-cardinality detail stays in logs and audit rows.

## 7.9 Audit Replay Completeness

- Persist policy/rule revision references and decision trace inputs.
- Add replay capability based on stored revisions.

## 7.10 Rollout Safety

- Surface-level modes: `off`, `shadow`, `enforce`.
- Scoped canaries by org/team/persona/workspace.
- Clear rollback controls and SLO gates per phase.

## 7.11 Compatibility and Deprecation Strategy

ACP:

- No backward-compatibility shim required; define clean governance contracts.

MCP:

- Maintain wire compatibility.
- Add governance metadata additively (`error.data.governance`, optional result metadata).
- Emit deprecation notices for legacy interpretation paths and phase toward major-version cleanup.

## 8. Error Model and Observability

Structured governance outcomes:

- `governance_denied`
- `governance_approval_required`
- `governance_gap_open`
- `governance_unavailable_fallback`

Core metrics:

- `governance_checks_total{surface,category,status}`
- `governance_policy_action_total{surface,action}`
- `governance_gaps_open_total{category}`
- `governance_fallback_total{failure_mode}`
- governance latency histograms by surface

Logs/audit fields:

- `request_id`, `session_id`, `surface`, `category`
- decision/action, policy/rule revision refs, fallback reason
- fully redacted payload handling before persistence/logging

## 9. Test Strategy

Unit:

- scope precedence and conflict resolution
- category mapping consistency
- recursion and bypass guards
- fallback resolver determinism

Integration:

- MCP governance preflight outcomes (`allow/warn/require_approval/deny`)
- ACP prompt/permission coordinator behavior
- shared fallback parity across MCP + ACP

Property-based:

- precedence invariants under random scope/policy combinations
- idempotent gap dedupe behavior under concurrency

Security:

- tenant isolation negative tests
- secret redaction persistence/logging tests

Performance:

- latency SLO checks for cache-hit and cache-miss paths
- fallback/circuit-breaker behavior under induced faults

## 10. Rollout Plan

1. Phase 1:
   - `mcp_tool_call=shadow`, ACP surfaces `off`
2. Phase 2:
   - `mcp_tool_call=enforce`, `acp_permission=shadow`
3. Phase 3:
   - `acp_permission=enforce`, `acp_prompt=shadow`
4. Phase 4:
   - all targeted surfaces enforce

Go/no-go gates:

- governance latency budget adherence
- fallback event rate thresholds
- false-positive deny/approval rates
- no tenant-isolation regressions

## 11. Implementation Boundary

Included in this design:

- Unified governance domain model and enforcement hooks.
- Shared policy conflict/fallback resolver.
- Gap lifecycle and immutable audit traces.
- Strategic MCP compatibility with additive deprecation path.

Deferred:

- Any broad API shape break for MCP (reserved for future major version).

