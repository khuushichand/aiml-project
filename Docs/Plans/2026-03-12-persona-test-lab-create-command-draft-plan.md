## Stage 1: Capture No-Match Hand-Off
**Goal**: Define the Test Lab to Commands handoff for unmatched spoken phrases.
**Success Criteria**: Test Lab exposes a create-command action when no direct command matches.
**Tests**: `TestLabPanel.test.tsx`
**Status**: Complete

## Stage 2: Prefill Command Drafts
**Goal**: Open the Commands editor with the heard phrase prefilled as a new draft.
**Success Criteria**: Route state carries the phrase into Commands and the editor applies it once.
**Tests**: `CommandsPanel.test.tsx`, `sidepanel-persona.command-handoff.test.tsx`
**Status**: Complete

## Stage 3: Verify Persona Garden Flow
**Goal**: Prove the new guided-create path works with the existing repair loop.
**Success Criteria**: Targeted Persona Garden tests pass without regressions.
**Tests**: targeted `vitest` Persona Garden suite
**Status**: Complete
