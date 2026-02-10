## Stage 1: Add Auth DB Lock Retry and 503 Mapping
**Goal**: Add bounded retry/backoff for SQLite lock contention in AuthNZ DB transaction dependency and return a user-facing 503 with Retry-After when retries are exhausted.
**Success Criteria**: Auth dependency retries lock errors; exhausted retries produce HTTP 503 instead of generic 500.
**Tests**: Existing auth dependency tests pass; add/adjust tests for lock retry + 503 behavior.
**Status**: In Progress

## Stage 2: Throttle API Key Usage Writes
**Goal**: Reduce per-request write contention by throttling `api_keys` usage updates (`usage_count`/`last_used_at`) to a configurable interval.
**Success Criteria**: API key validation still authenticates correctly; usage writes occur at most once per interval per key/process.
**Tests**: Existing API key/auth tests pass; add tests covering throttle behavior and default behavior.
**Status**: Not Started

## Stage 3: Validate and Finalize
**Goal**: Run targeted tests, update plan statuses, and clean up temporary planning artifact.
**Success Criteria**: Targeted tests green, no regressions observed in touched auth paths, plan completed and removed.
**Tests**: `pytest` focused on AuthNZ auth deps and API key manager tests.
**Status**: Not Started
