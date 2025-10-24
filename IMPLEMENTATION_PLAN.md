## Stage 1: Analysis & Fix Design
**Goal**: Confirm existing gaps for gpt-5 async handling, session cleanup, and provider config fallbacks. Define precise code changes.
**Success Criteria**: Documented issues verified in code; desired adjustments outlined for each bug.
**Tests**: None (analysis only).
**Status**: Complete

## Stage 2: Core Fixes
**Goal**: Implement code updates for OpenAI async payload formation, ensure sessions close after non-streaming requests, and apply config fallbacks for Cohere and Google handlers.
**Success Criteria**: Updated functions compile; logic aligns with design; no linting regressions detected.
**Tests**: `python -m compileall tldw_Server_API/app/core/LLM_Calls`
**Status**: Complete

## Stage 3: Test Coverage
**Goal**: Add regression tests that fail on the original bugs and pass after fixes.
**Success Criteria**: New tests cover async gpt-5 payload behavior, session cleanup (mocked), and config fallbacks for Cohere/Google; test suite passes locally.
**Tests**: `python -m pytest tldw_Server_API/tests/core/llm_calls`
**Status**: Complete

## Stage 4: Review & Wrap-Up
**Goal**: Verify no outstanding work, update plan statuses, and summarize changes for the user.
**Success Criteria**: Plan reflects completion; final message sent with summary and next steps.
**Tests**: None.
**Status**: Complete

## Stage 5: Session Lifecycle Audit
**Goal**: Identify all remaining LLM provider calls lacking proper session cleanup or consistent error handling (including Z.AI).
**Success Criteria**: Checklist of affected functions ready for implementation.
**Tests**: None.
**Status**: Complete

## Stage 6: Session & Error Fixes
**Goal**: Apply try/finally session closures, adjust streaming generator cleanup, and route Z.AI HTTP errors through `_raise_chat_error_from_http`.
**Success Criteria**: Updated code passes compilation and matches design notes.
**Tests**: `python -m compileall tldw_Server_API/app/core/LLM_Calls`
**Status**: Complete

## Stage 7: Regression Tests
**Goal**: Extend automated coverage to catch session leaks and Z.AI error normalization regressions.
**Success Criteria**: New/updated tests fail on old code and pass after fixes; targeted pytest run green.
**Tests**: `python -m pytest tldw_Server_API/tests/LLM_Calls/test_llm_providers.py -k "session" && python -m pytest tldw_Server_API/tests/LLM_Calls/test_llm_providers.py -k "zai"`
**Status**: Complete

## Stage 8: Final Review
**Goal**: Double-check diffs, update plan statuses, and prepare final summary for user.
**Success Criteria**: Plan completed; final response delivered.
**Tests**: None.
**Status**: Complete
