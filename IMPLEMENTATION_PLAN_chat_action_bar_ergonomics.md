## Stage 1: Map current action bar + state model
**Goal**: Document the current full-screen chat action bar structure and state sources (PlaygroundForm + tools popover) and pin the target layout spec (MCP on top row, Ephemeral toggle in action row).
**Success Criteria**: A short mapping of current elements to new positions and a final action-bar spec (desktop + narrow) is captured in this plan.
**Tests**: N/A (design + mapping only).
**Status**: Complete

## Stage 2: Restructure action bar layout (visual + hierarchy)
**Goal**: Implement the new 2-row layout in the full-screen chat (PlaygroundForm) with MCP moved to top row, Ephemeral toggle in the action row, and high-frequency actions visible without opening +Tools.
**Success Criteria**: 
- MCP control rendered on the top row alongside Prompt/Model/Character.
- Ephemeral (temporary chat) toggle appears in the action row with visible state.
- Web Search and Knowledge are first-class pills in the action row.
- Attach is a split affordance (primary = image picker, secondary = menu).
- Send menu only contains send behavior (Enter-to-send).
**Tests**: Update or add component tests for action bar rendering and states in `apps/tldw-frontend/__tests__/pages/chat-feedback.test.tsx` (or add a new test module under `apps/tldw-frontend/__tests__/pages/chat-action-bar.test.tsx`).
**Status**: Not Started

## Stage 3: Simplify +Tools and move advanced MCP config
**Goal**: Reduce +Tools popover to low-frequency items and move MCP catalog/module filters to a dedicated settings surface.
**Success Criteria**:
- +Tools popover contains only low-frequency actions (compare models, clear conversation, OCR, etc.).
- MCP advanced configuration opens in a dedicated panel/drawer (link from MCP control or settings).
- MCP tool choice remains in the action bar (Auto/Required/None + tool count).
**Tests**: Add a UI test verifying the MCP settings entrypoint and that catalog/module filters are no longer in the +Tools popover.
**Status**: Not Started

## Stage 4: Accessibility + responsive polish
**Goal**: Ensure keyboard access, aria states, and responsive behavior match the new layout.
**Success Criteria**:
- All toggles expose aria-pressed/expanded as appropriate.
- Badge counts and ON states are visible in both wide and narrow layouts.
- Tab order is logical and stable.
**Tests**: Run existing UI test suite; add an a11y check if applicable.
**Status**: Not Started
