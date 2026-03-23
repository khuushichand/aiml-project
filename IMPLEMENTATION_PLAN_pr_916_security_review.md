## Stage 1: Reproduce Remaining Security Findings
**Goal**: Confirm the live PR security alerts map to current code paths and define intended hardened behavior.
**Success Criteria**: Remaining CodeQL findings are traced to specific helpers and response paths in the worktree.
**Tests**: `gh api` alert inspection, targeted file reads
**Status**: Complete

## Stage 2: Add Regression Tests
**Goal**: Capture the desired safe behavior for ACP workspace path validation and shared-chat response sanitization.
**Success Criteria**: New or updated tests fail against the current implementation before code changes.
**Tests**: `pytest tldw_Server_API/tests/Agent_Orchestration/test_workspace_api_helpers.py -q`, `pytest tldw_Server_API/tests/Sharing/test_shared_workspace_chat_security.py -q`
**Status**: Complete

## Stage 3: Harden Backend Paths And Responses
**Goal**: Restrict ACP workspace roots and dispatch CWD handling, and redact internal RAG error details from shared-chat responses.
**Success Criteria**: The updated helpers enforce safe roots, dispatch blocks absolute workspace overrides, and shared chat never returns raw internal error strings.
**Tests**: Targeted pytest, Bandit on touched backend files
**Status**: Complete

## Stage 4: Verify And Close GitHub Review
**Goal**: Re-run local verification, push the fix if needed, and reply to or dismiss the remaining GitHub security review items.
**Success Criteria**: Local verification passes and the PR no longer shows remaining unresolved security findings related to this change set.
**Tests**: Targeted pytest, Bandit, `gh pr view 916 --repo rmusser01/tldw_server --json statusCheckRollup`
**Status**: In Progress
