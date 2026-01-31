## Stage 1: Code fixes + feature wiring
**Goal**: Wire quizzes generation to unified chat, upgrade slides export (PDF) + RAG pipeline, add APKG export, fix template list/get mismatch, handle ConflictError gracefully.
**Success Criteria**: New code paths compile, tools definitions updated, ConflictError mapped to user-facing validation errors.
**Tests**: Unit tests added/updated for modules; existing MCP tests still pass.
**Status**: Complete

## Stage 2: MCP module tests
**Goal**: Add MCP unified tests for quizzes/flashcards/slides covering CRUD and export/generation entrypoints.
**Success Criteria**: New tests pass without external services; LLM and PDF/APKG paths mocked.
**Tests**: pytest tldw_Server_API/app/core/MCP_unified/tests/test_*_module.py -v
**Status**: Complete

## Stage 3: Verification + cleanup
**Goal**: Ensure plan items completed, update plan status, summarize changes.
**Success Criteria**: All stages marked complete; no open issues.
**Tests**: Optional full MCP_unified tests if requested.
**Status**: Complete
