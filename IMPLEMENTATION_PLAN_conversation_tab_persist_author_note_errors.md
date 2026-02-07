## Stage 1: Inspect Current Error Handling
**Goal**: Identify how `ConversationTab` currently reports async failures and where `persistAuthorNote`/`persistAuthorNotePosition` are used.
**Success Criteria**: Confirmed existing notification pattern and exact functions to update.
**Tests**: N/A (inspection stage).
**Status**: Complete

## Stage 2: Implement Consistent Error Surfacing
**Goal**: Ensure failures from `updateSettings` in `persistAuthorNote` and `persistAuthorNotePosition` are surfaced through the same notification routine as other handlers.
**Success Criteria**: Both functions catch update failures and notify users via shared logic.
**Tests**: TypeScript compile check for edited file.
**Status**: In Progress

## Stage 3: Verify and Finalize
**Goal**: Validate the change, summarize outcomes, and clean up task plan file.
**Success Criteria**: Diff reviewed; no unintended changes; plan file removed after completion.
**Tests**: Targeted lint/type check if available.
**Status**: Not Started
