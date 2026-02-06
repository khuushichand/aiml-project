## Stage 1: API Docs Alignment for New Character Chat Fields
**Goal**: Document `prompt_preset`, `chatPresetOverrideId`, `chatGenerationOverride`, and legacy `generationOverrides` behavior in Character Chat API docs.
**Success Criteria**: Main Character Chat docs describe request fields, precedence, and compatibility notes for settings payloads.
**Tests**: Documentation review for consistency with endpoint schema and behavior.
**Status**: Complete

## Stage 2: Remove Deprecated Client Prompt Preview Heuristic Utility
**Goal**: Remove `apps/packages/ui/src/utils/prompt-preview.ts` and stale tests now that server-backed preview is the source of truth.
**Success Criteria**: No imports remain and extension test suite passes without the removed utility.
**Tests**: Frontend extension tests for prompt preview component and related suites.
**Status**: Complete

## Stage 3: Triage and Fix ChaCha Executor Thread Teardown Warning
**Goal**: Eliminate recurring `chacha-db_0` lingering thread warnings in test teardown.
**Success Criteria**: Test teardown performs explicit ChaCha executor shutdown with no recurring warning in targeted test runs.
**Tests**: Character chat unit/integration test runs with teardown logs checked.
**Status**: Complete

## Stage 4: Implement Next PRD Fix Batch (Generation Overrides Quick Access)
**Goal**: Add chat settings UI controls for `chatGenerationOverride` so users can override character generation per chat.
**Success Criteria**: Conversation settings can persist/clear enabled flag and generation values (`temperature`, `top_p`, `repetition_penalty`, `stop`) in server-backed chat settings.
**Tests**: Frontend test coverage for new controls and targeted backend integration regression run.
**Status**: Complete

## Stage 5: Final Verification and Summary
**Goal**: Run targeted backend/frontend tests and confirm scoped diffs.
**Success Criteria**: New/updated tests pass and implementation is summarized with file references.
**Tests**: Targeted pytest + vitest extension test commands.
**Status**: Complete
