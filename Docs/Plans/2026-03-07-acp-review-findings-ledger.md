# ACP Review Findings Ledger

Date: 2026-03-07
Status: In Progress
Owner: Codex

## Scope Notes

- Full ACP surface: backend runtime/protocol, session/admin state, ACP playground UI, and dedicated admin UI ACP pages.
- Use this ledger to capture evidence before promoting anything into the final review.

## Severity Rubric

- `P1`: security/authz expansion, broken common-path behavior, or contract breaks that invalidate user-visible ACP flows
- `P2`: runtime-specific regressions, admin/runtime drift, or UX failures with real operational impact
- `P3`: maintainability problems or test gaps that materially raise future ACP risk

## Candidate Findings

- `P1` Read-scoped API keys can access ACP control WebSockets and SSH surfaces.
- `P1` WebSocket-driven prompts do not persist ACP session history or usage in the session store.
- `P1` Endpoint-layer governance handling can block shadow-mode denies despite runner rollout semantics.
- `P1` Forked ACP session IDs are persisted in store only and are not resumable by the runtime contract.
- `P2` Sandbox runner permission-tier behavior can diverge from admin policy configuration.
- `P2` UI WebSocket clients reconnect on fatal `4404` and `4429` close codes.
- `P3` Backend fork lineage is stored but not exposed via normal session list/detail schemas, so fork ancestry is not reconstructible from server state alone.
- `P3` TypeScript ACP create-session request/response types lag the backend schema for tenancy metadata, increasing drift risk between UI and API contracts.

## Coverage Gaps

- Missing endpoint-level tests for shadow rollout behavior on prompt paths.
- Missing tests for WebSocket prompt persistence into session history and usage.
- Missing tests for control-scope enforcement on ACP WebSocket and SSH auth.
- Missing tests for sandbox permission-policy parity.
- Missing tests for fatal close-code reconnect suppression in UI clients.
- Missing dedicated tests for the ACP admin agents/policies page flows.

## Open Questions

- Whether forking is intended to remain a local/UI-only affordance or become a true resumable server-side ACP feature.
