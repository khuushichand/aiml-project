## Stage 1: Backend Control Surface Hardening
**Goal**: Enforce correct ACP control-channel auth scopes and unify prompt handling across REST and WebSocket entrypoints.
**Success Criteria**: ACP stream/SSH sockets require write-scoped API keys, shadow governance denies do not block at the endpoint layer, and REST/WS prompt paths share the same persistence/audit logic.
**Tests**: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_websocket.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py -q`
**Status**: Complete

## Stage 2: Session Store and Resumable Forks
**Goal**: Make the ACP session store authoritative for runtime config, transcript bootstrap state, lineage, and fork recreation.
**Success Criteria**: Session records persist enough data to recreate runtime-backed forks, non-bootstrappable legacy sessions fail with `409 fork_not_resumable`, and workflow-created ACP sessions register through the same store.
**Tests**: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_status_schema.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_websocket.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py -q`
**Status**: Complete

## Stage 3: Frontend ACP Parity
**Goal**: Align ACP frontend types/store behavior with the hardened backend contracts for reconnects, session metadata, and fork behavior.
**Success Criteria**: ACP UI types include the backend fields they use, server-backed fork failures no longer silently fall back to local forks, and both ACP clients suppress reconnect on fatal close codes.
**Tests**: `bunx vitest run -c vitest.config.ts src/services/acp/__tests__/client.test.ts src/hooks/__tests__/useACPSession.test.tsx src/store/__tests__/acp-sessions.test.ts src/components/Option/ACPPlayground/__tests__/ACPChatPanel.test.tsx src/components/Option/ACPPlayground/__tests__/ACPSessionPanel.test.tsx`
**Status**: Complete

## Stage 4: Admin ACP Coverage and Verification
**Goal**: Cover the ACP admin policies/agents surface and run final security/verification checks on the touched scope.
**Success Criteria**: ACP admin agents/policies page has dedicated tests, touched ACP tests pass, and Bandit is clean on touched backend paths.
**Tests**: `bunx vitest run app/acp-sessions/__tests__/page.test.tsx app/acp-agents/__tests__/page.test.tsx`, `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py tldw_Server_API/app/services/admin_acp_sessions_service.py tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py tldw_Server_API/app/core/Agent_Client_Protocol/permission_tiers.py tldw_Server_API/app/core/Workflows/adapters/integration/acp.py -f json -o /tmp/bandit_acp_remediation_exact.json`
**Status**: Complete

## Post-Implementation Follow-Up
**Goal**: Close the remaining ACP REST API-key scope gap discovered during self-review and keep the startup privilege map valid.
**Success Criteria**: ACP REST endpoints enforce method-appropriate API-key scopes through `require_token_scope`, ACP privilege catalog entries exist for the new route metadata, and read/write regression tests cover the REST surface.
**Tests**: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py::test_acp_session_new_success -q`, `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_hardening_controls.py -q`, `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_endpoints.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_websocket.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_status_schema.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_hardening_controls.py tldw_Server_API/tests/Workflows/adapters/test_integration_adapters.py -q`, `bunx vitest run -c vitest.config.ts src/services/acp/__tests__/client.test.ts src/hooks/__tests__/useACPSession.test.tsx src/store/__tests__/acp-sessions.test.ts src/components/Option/ACPPlayground/__tests__/ACPChatPanel.test.tsx src/components/Option/ACPPlayground/__tests__/ACPSessionPanel.test.tsx`, `bunx vitest run app/acp-sessions/__tests__/page.test.tsx app/acp-agents/__tests__/page.test.tsx`, `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py tldw_Server_API/app/services/admin_acp_sessions_service.py tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py tldw_Server_API/app/core/Agent_Client_Protocol/permission_tiers.py tldw_Server_API/app/core/Workflows/adapters/integration/acp.py -f json -o /tmp/bandit_acp_remediation_exact.json`
**Status**: Complete
