## Stage 1: Endpoint Survey & Test Controls
**Goal**: Confirm API paths, required payloads, and env toggles for the new workflows.
**Success Criteria**: Each workflow has identified endpoints + gating env vars and cleanup paths.
**Tests**: N/A (planning/inspection only).
**Status**: Complete

## Stage 2: Prompt Studio, Notes, Chatbooks Workflows
**Goal**: Add API-only Playwright E2E tests for Prompt Studio, Notes tagging/soft-delete, and Chatbooks roundtrip import.
**Success Criteria**: Tests cover multi-step flows with assertions and cleanup.
**Tests**: `pytest -m e2e tldw_Server_API/tests/server_e2e_tests/test_prompt_studio_workflow.py`, `.../test_notes_tags_restore_workflow.py`, `.../test_chatbooks_roundtrip_workflow.py`
**Status**: Complete

## Stage 3: AuthNZ Multi-User + LLM Provider Workflows
**Goal**: Add multi-user RBAC/audit workflow and LLM provider workflows (local + external, gated).
**Success Criteria**: Tests validate permission enforcement/audit access; LLM flows validate provider config, completions, streaming, metrics.
**Tests**: `pytest -m e2e tldw_Server_API/tests/server_e2e_tests/test_authnz_multi_user_workflow.py`, `.../test_llm_provider_workflow.py`
**Status**: Complete

## Stage 4: Finalize & Document Toggles
**Goal**: Update plan status, summarize env gates/assumptions, and note any intentional skips.
**Success Criteria**: Plan file updated to Complete; next-step run commands noted in summary.
**Tests**: N/A (documentation only).
**Status**: Complete
