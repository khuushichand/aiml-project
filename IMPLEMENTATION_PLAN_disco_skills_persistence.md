## Stage 1: Data model + persistence plumbing
**Goal**: Extend message types/storage to include disco skill comments and provide update helper.
**Success Criteria**: Message types include `discoSkillComment`; DB helpers can update this field by message id; formatters map it through.
**Tests**: N/A (type-level + storage helpers)
**Status**: Complete

## Stage 2: Message component integration
**Goal**: Read persisted comments, avoid double generation, and persist new comments.
**Success Criteria**: Stored comments render on reload when enabled; new comments save to message data; comments clear on message content change.
**Tests**: Manual: toggle persist on/off, reload, edit/regenerate message.
**Status**: Complete

## Stage 3: Logic/UI mismatches
**Goal**: Clamp stats for pass/fail, align prompt length, and update annotation badge per plan.
**Success Criteria**: Pass/fail uses clamped stats; prompt says 1–3 sentences; badge shows Passive.
**Tests**: Manual spot-check.
**Status**: Complete
