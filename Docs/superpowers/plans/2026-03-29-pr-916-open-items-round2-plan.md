## Stage 1: Audit Remaining PR Feedback
**Goal**: Verify which PR #916 comments and CI failures are still valid on the current `origin/dev` head.
**Success Criteria**: A concrete list of still-actionable items exists, separated from already-fixed or outdated bot findings.
**Tests**: Live GitHub PR comment fetch; local code inspection of referenced files.
**Status**: Complete

## Stage 2: Add Regression Tests First
**Goal**: Capture the remaining live issues with failing tests before implementation.
**Success Criteria**: New or updated tests fail against the unfixed behavior for users repo commit handling, frontend chat sanitization, in-process LLM provider probing, and in-process HuggingFace embeddings fallback.
**Tests**: Targeted pytest/vitest cases for `users_repo.py`, `llm_providers.py`, `Embeddings_Create.py`, and frontend chat client sanitization.
**Status**: Complete

## Stage 3: Implement Focused Fixes
**Goal**: Fix the verified live PR issues without widening scope.
**Success Criteria**: `users_repo.py` no longer suppresses SQLite commit failures in the affected paths; frontend chat response sanitization redacts stack-bearing strings recursively; `/llm/providers` avoids unsafe runtime tokenizer probing in in-process smoke mode; in-process HuggingFace embeddings fall back to deterministic synthetic vectors instead of importing `torch`.
**Tests**: Stage 2 tests pass after implementation.
**Status**: Complete

## Stage 4: Verify and Prepare PR Follow-Up
**Goal**: Run focused verification and summarize which PR comments are fixed versus already outdated.
**Success Criteria**: Targeted tests pass, the full in-process critical E2E suite passes, changed files are clean, and the remaining PR feedback is documented accurately.
**Tests**: Targeted pytest, vitest, full in-process critical E2E, `git diff --check`, and Bandit on touched Python paths.
**Status**: Complete
