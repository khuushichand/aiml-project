## Stage 1: Add Regression Tests
**Goal**: Capture current failure-prone behavior with focused tests before code changes.
**Success Criteria**: New tests fail before implementation and encode expected guard logic.
**Tests**: `useServerChatLoader.test.ts`, `background-proxy.test.ts`.
**Status**: Complete

## Stage 2: Harden Server Chat Loader Against Stream Overwrite Races
**Goal**: Prevent server-load snapshots from replacing in-flight/unsynced local chat state and allow reload when local list is empty.
**Success Criteria**: Loader does not short-circuit when same chat is "loaded" but local messages are empty; latest refs are used at commit time.
**Tests**: `useServerChatLoader.test.ts`.
**Status**: Complete

## Stage 3: Handle Mid-Stream Transport Interruptions + Persist Recovery
**Goal**: Avoid frozen UI/missing tail turns by handling port transport interruption safely and persisting recoverable assistant content.
**Success Criteria**: Stream with partial data + transport error no longer hard-fails; character flow attempts safe persistence on interrupted stream errors.
**Tests**: `background-proxy.test.ts`, targeted `useChatActions` guard test.
**Status**: Complete

## Stage 4: Verify
**Goal**: Validate behavior and security checks for touched scope.
**Success Criteria**: Targeted tests pass and Bandit reports no new findings in touched frontend files.
**Tests**: `bunx vitest ...`, `python -m bandit -r apps/packages/ui/src/services apps/packages/ui/src/hooks/chat -f json ...`.
**Status**: Complete
