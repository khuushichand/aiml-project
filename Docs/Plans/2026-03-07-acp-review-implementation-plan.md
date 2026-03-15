# ACP Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce a full ACP review across backend runtime/protocol behavior, admin/session state handling, and playground/admin UI, with prioritized findings, maintainability risks, and regression-test gaps.

**Architecture:** Execute the review as a lifecycle audit instead of a file-by-file read. Trace the ACP contract across REST, WebSocket, runner, sandbox runner, state store, admin endpoints, and UI clients so cross-layer mismatches are surfaced with evidence instead of isolated observations.

**Tech Stack:** FastAPI, Pydantic, asyncio, WebSocket, Python runner/sandbox modules, React, TypeScript, Vitest, pytest

---

**Execution Note:** If this plan is executed in the current session instead of a separate one, use `superpowers:subagent-driven-development` while keeping the same task order and quality gates.

**Working Artifact:** Record evidence and candidate findings in `docs/plans/2026-03-07-acp-review-findings-ledger.md` before drafting the final review.

**Severity Rubric:**
- `P1`: security/authz expansion, broken common-path behavior, or contract breaks that invalidate user-visible ACP flows
- `P2`: runtime-specific regressions, admin/runtime drift, or UX failures with real operational impact
- `P3`: maintainability problems or test gaps that are not immediately user-breaking but materially raise future ACP risk

### Task 1: Build the ACP Lifecycle Map

**Files:**
- Read: `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`
- Read: `tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py`
- Read: `tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py`
- Read: `tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
- Read: `apps/packages/ui/src/store/acp-sessions.ts`
- Read: `apps/packages/ui/src/services/acp/types.ts`
- Read: `admin-ui/app/acp-sessions/page.tsx`
- Read: `admin-ui/app/acp-agents/page.tsx`
- Reference: `Docs/Design/ACP_runner.md`
- Reference: `Docs/User_Guides/Integrations_Experiments/Getting_Started_with_ACP.md`

**Step 1: Inspect ACP public contracts**

Run: `rg -n "session/new|session/prompt|session/cancel|stream|ssh|fork|reconcile" tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py`
Expected: A compact map of ACP lifecycle routes and related schemas.

**Step 2: Inspect runner and sandbox lifecycle methods**

Run: `rg -n "def (create_session|prompt|cancel|close_session|verify_session_access|register_websocket|respond_to_permission)" tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
Expected: Matching lifecycle entry points for both runtime modes.

**Step 3: Capture contract assumptions**

Write down:
- which layer owns session identity
- which layer owns session history and usage
- where governance is enforced
- which paths depend on WebSocket presence

**Step 4: Record lifecycle mismatches**

Output: Create a short working list of mismatches before assigning severity.

### Task 2: Audit Ownership, Auth, and Governance Paths

**Files:**
- Read: `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`
- Read: `tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py`
- Read: `tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
- Read: `tldw_Server_API/app/core/AuthNZ/api_key_manager.py`
- Read: `tldw_Server_API/app/core/AuthNZ/User_DB_Handling.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_websocket.py`

**Step 1: Trace prompt governance handling**

Run: `rg -n "_check_prompt_governance|governance_blocked|is_denied_with_enforcement|rollout_mode" tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
Expected: One clear map of where governance denies are interpreted.

**Step 2: Trace WebSocket and SSH auth scope requirements**

Run: `rg -n "required_scope=|_authenticate_ws|websocket\\(|validate_api_key\\(" tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py tldw_Server_API/app/core/AuthNZ/api_key_manager.py tldw_Server_API/app/core/AuthNZ/User_DB_Handling.py`
Expected: Evidence showing the effective scope required for ACP streaming and SSH control.

**Step 3: Compare intended versus actual enforcement**

Write down:
- whether shadow-mode governance can accidentally block
- whether read-scoped credentials can perform ACP control actions
- whether runtime-specific auth paths diverge

**Step 4: Assign severity**

Promote any issue that can block legitimate traffic or widen privileged access.

### Task 3: Audit Session State, History, Forking, and Reconciliation

**Files:**
- Read: `tldw_Server_API/app/services/admin_acp_sessions_service.py`
- Read: `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`
- Read: `tldw_Server_API/app/core/Workflows/adapters/integration/acp.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_hardening_controls.py`

**Step 1: Trace state ownership**

Run: `rg -n "register_session|record_prompt|fork_session|close_session|get_session|list_sessions" tldw_Server_API/app/services/admin_acp_sessions_service.py tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py tldw_Server_API/app/core/Workflows/adapters/integration/acp.py`
Expected: Evidence of which call paths populate or skip ACP session state.

**Step 2: Trace fork semantics end to end**

Run: `rg -n "fork|session_id" tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py apps/packages/ui/src/components/Option/ACPPlayground/ACPSessionPanel.tsx`
Expected: Evidence showing whether forked sessions can actually be resumed or queried.

**Step 3: Compare REST prompt recording with WebSocket prompt handling**

Run: `rg -n "record_prompt|prompt_complete|type == \"prompt\"|sendPrompt" tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py apps/packages/ui/src/hooks/useACPSession.tsx apps/packages/ui/src/components/Option/ACPPlayground/ACPChatPanel.tsx`
Expected: Evidence of whether the primary UI path persists prompt history and usage.

**Step 4: Capture persistence and visibility blind spots**

Write down:
- which sessions appear in list/detail/admin views
- which sessions can be audited, forked, or reconciled
- which sessions are invisible because they bypass the store

### Task 4: Audit UI Client and Playground/Admin Parity

**Files:**
- Read: `apps/packages/ui/src/services/acp/client.ts`
- Read: `apps/packages/ui/src/hooks/useACPSession.tsx`
- Read: `apps/packages/ui/src/store/acp-sessions.ts`
- Read: `apps/packages/ui/src/services/acp/types.ts`
- Read: `apps/packages/ui/src/components/Option/ACPPlayground/ACPChatPanel.tsx`
- Read: `apps/packages/ui/src/components/Option/ACPPlayground/ACPSessionPanel.tsx`
- Read: `admin-ui/app/acp-sessions/page.tsx`
- Read: `admin-ui/app/acp-agents/page.tsx`
- Read: `tldw_Server_API/app/api/v1/endpoints/admin/admin_acp_agents.py`
- Test: `apps/packages/ui/src/services/acp/__tests__/client.test.ts`
- Test: `apps/packages/ui/src/components/Option/ACPPlayground/__tests__/ACPSessionPanel.test.tsx`
- Test: `admin-ui/app/acp-sessions/__tests__/page.test.tsx`

**Step 1: Trace reconnect behavior**

Run: `rg -n "4401|4404|4429|onclose|reconnect" apps/packages/ui/src/services/acp/client.ts apps/packages/ui/src/hooks/useACPSession.tsx`
Expected: A precise map of which close codes stop reconnects and which codes loop.

**Step 2: Trace how the UI uses forked sessions**

Run: `rg -n "forkSession|getSessionUsage|getSessionDetail|replaceSessionId" apps/packages/ui/src/components/Option/ACPPlayground/ACPSessionPanel.tsx apps/packages/ui/src/services/acp/client.ts`
Expected: Evidence of any UI assumptions that do not hold against backend behavior.

**Step 3: Compare admin/runtime behavior**

Run: `rg -n "permission policy|resolve_permission_tier|has_websocket_connections|close_session" tldw_Server_API/app/api/v1/endpoints/admin/admin_acp_agents.py tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
Expected: Evidence of runtime-specific policy drift or admin blind spots.

**Step 4: Record UI-facing regressions**

Promote any issue that traps users in reconnect loops, hides state, or makes actions appear successful when the backend cannot honor them.

### Task 5: Compare Findings Against Test Coverage

**Files:**
- Read: `tldw_Server_API/tests/Agent_Client_Protocol/`
- Read: `tldw_Server_API/tests/sandbox/`
- Read: `tldw_Server_API/tests/AuthNZ_Unit/`
- Read: `apps/packages/ui/src/services/acp/__tests__/`
- Read: `apps/packages/ui/src/components/Option/ACPPlayground/__tests__/`
- Read: `admin-ui/app/acp-sessions/__tests__/`

**Step 1: Map each high-risk finding to current tests**

Run: `rg -n "fork|governance|shadow|websocket|permission|reconcile|diagnostics|usage|scope|ssh|acp" tldw_Server_API/tests/Agent_Client_Protocol tldw_Server_API/tests/sandbox tldw_Server_API/tests/AuthNZ_Unit apps/packages/ui/src/services/acp/__tests__ apps/packages/ui/src/components/Option/ACPPlayground/__tests__ admin-ui/app/acp-sessions/__tests__`
Expected: A coverage map showing what is tested and what is missing.

**Step 2: Identify missing regression tests**

Write down missing coverage for:
- endpoint-level governance rollout behavior
- WebSocket/API key control-scope enforcement
- fork usability across runtime/store/UI boundaries
- WebSocket prompt history and usage persistence
- sandbox permission-policy parity
- fatal close-code reconnect behavior in UI clients

**Step 3: Prioritize gaps**

Order gaps by how likely they are to hide production regressions.

### Task 6: Draft the Final Review

**Files:**
- Reference all files above
- Output: final review response in this session

**Step 1: Write findings first**

Structure:
- severity-ordered
- one finding per point
- include exact file references and why it matters

**Step 2: Add open questions or assumptions**

Keep this short and only include items that affect interpretation of a finding.

**Step 3: Add architecture and test-gap summary**

Keep it secondary to the findings list.

**Step 4: Note repository-state blocker**

Call out that docs were added but a clean commit was not attempted because the workspace already has unrelated unresolved files.
