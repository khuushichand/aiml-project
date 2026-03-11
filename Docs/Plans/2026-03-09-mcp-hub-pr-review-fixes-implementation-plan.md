## Stage 1: Reproduce Review Findings
**Goal**: Lock the open PR review comments into executable failing tests.
**Success Criteria**: New or updated tests fail for the current gaps in approval validation, policy enforcement, approval scoping, and approval payload sanitization.
**Tests**: `python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py -q`
**Status**: Complete

## Stage 2: Fix Security And Correctness Gaps
**Goal**: Close the remaining security/control-plane issues in MCP Hub and MCP protocol enforcement.
**Success Criteria**: Grant authority cannot be bypassed via tool lists; approval decisions are constrained server-side; policy enforcement no longer silently fails open when enabled; approval scope hashing and summaries are safe.
**Tests**: `python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_approval_service.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py -q`
**Status**: Complete

## Stage 3: Fix Maintainability And Compliance Findings
**Goal**: Address the remaining review comments around docstrings, rate limiting, exception consistency, and persona retry duplication.
**Success Criteria**: New helpers are documented, MCP Hub routes are rate limited, endpoint error handling follows project patterns where appropriate, and duplicated persona retry execution logic is extracted.
**Tests**: `python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/Persona/test_persona_ws.py -q`
**Status**: Complete

## Stage 4: Verify And Update PR
**Goal**: Prove the fixes, run security checks, and update the PR branch and review threads.
**Success Criteria**: Focused test suites pass, Bandit reports no new findings in touched code, branch is pushed, and open review threads receive replies/resolution updates.
**Tests**: `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/services/mcp_hub_approval_service.py tldw_Server_API/app/services/mcp_hub_policy_resolver.py tldw_Server_API/app/core/MCP_unified/protocol.py -f json -o /tmp/bandit_mcp_hub_review_fixes.json`
**Status**: Complete
