# ACP Review Design

Date: 2026-03-07
Status: Approved
Owner: Codex + user

## 1. Context and Goal

The goal is to perform a full review of the ACP module across backend runtime/protocol behavior, session/admin state handling, and the ACP playground/admin UI. The review should identify concrete bugs, security or ownership gaps, cross-layer contract mismatches, and broader maintainability or architectural risks that are likely to produce future regressions.

This is a review-first effort rather than a feature build. The deliverable is a prioritized findings report, not an implementation changelog.

## 2. Selected Review Approach

Selected direction:
- Use a layered lifecycle audit rather than a file-by-file scan.
- Review ACP as one system spanning runner, sandbox runner, REST endpoints, WebSocket endpoints, admin/session state, and the UI clients.
- Prioritize correctness, auth/authz, lifecycle consistency, and contract integrity first.
- Include broader maintainability and architecture improvements after concrete findings.

Why this approach:
- ACP behavior is split across multiple duplicated code paths.
- Several important outcomes depend on how backend and UI assumptions line up.
- Lifecycle review is the most efficient way to catch both current bugs and their structural causes.

## 3. Review Surface

### 3.1 Backend Protocol and Runtime
- `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`
- `tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py`
- `tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
- `tldw_Server_API/app/core/Agent_Client_Protocol/stream_client.py`

### 3.2 Session and Admin State
- `tldw_Server_API/app/services/admin_acp_sessions_service.py`
- `tldw_Server_API/app/api/v1/endpoints/admin/admin_acp_agents.py`
- `apps/packages/ui/src/store/acp-sessions.ts`
- `apps/packages/ui/src/services/acp/types.ts`

### 3.3 UI Clients and ACP Playground
- `apps/packages/ui/src/services/acp/client.ts`
- `apps/packages/ui/src/services/acp/index.ts`
- `apps/packages/ui/src/hooks/useACPSession.tsx`
- ACP playground/admin components under `apps/packages/ui/src/components/Option/ACPPlayground/`
- `admin-ui/app/acp-sessions/page.tsx`
- `admin-ui/app/acp-agents/page.tsx`
- `admin-ui/app/acp-sessions/__tests__/page.test.tsx`

### 3.4 Related Integrations
- `tldw_Server_API/app/core/Workflows/adapters/integration/acp.py`
- Existing ACP docs and relevant test coverage under `Docs/`, `tldw_Server_API/tests/Agent_Client_Protocol/`, `tldw_Server_API/tests/sandbox/`, `tldw_Server_API/tests/AuthNZ_Unit/`, and admin/UI ACP test directories

## 4. Review Method

The review will proceed in four passes.

### 4.1 Contract Pass
- Compare schemas, REST behavior, WebSocket behavior, runner behavior, sandbox behavior, admin behavior, and UI assumptions.
- Verify agreement on payload shapes, error contracts, access control expectations, and lifecycle semantics.

### 4.2 Failure-Mode Pass
- Inspect edge cases around:
  - session creation and ownership
  - prompt execution and governance outcomes
  - permission request handling
  - WebSocket and SSH auth
  - polling versus streaming behavior
  - teardown and reconciliation
  - session forking
  - runtime-specific behavior differences

### 4.3 Maintainability Pass
- Identify duplicated logic, split ownership, hidden coupling, and state model weaknesses.
- Highlight structural cleanup opportunities that would reduce ACP churn and policy drift.

### 4.4 Coverage Pass
- Compare risky paths against current unit and integration tests.
- Call out missing regression coverage for the most failure-prone behavior.

## 5. Expected Deliverable

The review output should contain three sections:

1. Findings
   - Concrete bugs, security/authz issues, broken contracts, and behavioral regressions.
   - Ordered by severity with file and line references.

2. Architecture and Maintainability
   - Broader structural issues that increase change risk or produce inconsistent behavior.
   - Clear recommendations, but no speculative redesign without evidence.

3. Test Gaps
   - Missing regression tests for the highest-risk ACP paths.

The final response should follow the repository review convention:
- findings first
- severity-ordered
- file and line references for each concrete issue
- open questions or assumptions only after findings

## 6. Success Criteria

The review is successful if it produces:
- A prioritized list of real ACP issues with defensible evidence.
- Clear cross-layer reasoning for each major issue.
- A short set of structural recommendations that would reduce repeat defects.
- Concrete follow-up targets for fixes and regression tests.

## 7. Non-Goals

- Exhaustive style-only commentary.
- Low-signal nitpicks without reliability, security, or maintainability impact.
- Rewriting ACP architecture during the review itself.

## 8. Practical Constraints

- The current repository state is not clean and contains unrelated unresolved files, so documentation can be added safely but a clean commit may not be possible from this workspace state.
- ACP session/admin metadata is currently designed around in-memory coordination paths, so special attention is required when evaluating persistence, ownership, and reuse semantics.
