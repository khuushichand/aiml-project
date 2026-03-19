# Deep Research Chat Pinned-Only Fallback Design

## Summary

Refine the composer’s no-active-attachment fallback when a pinned deep-research attachment exists.

Today, the pinned slot is functionally correct but visually reads like a mixed row of buttons. This slice gives pinned state a clearer role: a small dedicated mini-card that explains it is the thread’s default research context, while recent history remains a separate recall surface underneath.

## Goals

- Make pinned-only fallback state easy to understand at a glance.
- Clarify that the pinned attachment is the thread’s durable default research context.
- Keep pinned and recent-history roles visually separate.
- Preserve the existing active chip behavior unchanged.

## Non-Goals

- No persistence or schema changes.
- No backend changes.
- No transcript changes.
- No expanded attachment management panel.
- No changes to active attachment chip behavior.

## Approaches Considered

### 1. Dedicated pinned mini-card

When no active attachment exists but a pinned one does, render a compact card with:

- `Pinned research`
- query snippet
- a one-line explanation
- `Use now`
- `Open in Research`
- `Unpin`

Pros:

- clearest mental model
- small scope
- keeps recent history separate

Cons:

- adds a slightly larger fallback surface than the current inline row

### 2. Keep inline row, add explanatory text

Keep the current flat fallback layout and just add copy.

Pros:

- cheapest visual change

Cons:

- still muddled when pinned and recent history appear together

### 3. Full attachment management panel

Create a richer composer-side panel for active, pinned, and recent items.

Pros:

- most structured

Cons:

- too much UI for this slice

## Recommended Approach

Use a dedicated pinned mini-card for the pinned-only fallback.

This is the smallest change that actually clarifies the pinned slot’s purpose. It avoids reworking the active chip or attachment model, but gives users a clear default-context surface when no active attachment is currently applied.

## Architecture

This slice is frontend-only and lives in the no-active fallback path in:

- [PlaygroundForm.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx)

State model remains unchanged:

- `attachedResearchContext`
- `attachedResearchContextPinned`
- `attachedResearchContextHistory`

### Render rules

#### Active attachment exists

- keep the existing active chip flow unchanged

#### No active attachment, pinned exists

- render a dedicated pinned mini-card
- render recent history as a separate block below it if history exists

#### No active attachment, no pinned, history exists

- keep the current recent-history fallback behavior

## UI Contract

### Pinned-only mini-card contents

- title: `Pinned research`
- query snippet
- short explanation:
  - `This thread keeps this research as its default context.`
- actions:
  - `Use now`
  - `Open in Research`
  - `Unpin`

### Interaction rules

- `Use now` restores the pinned attachment into the active slot immediately
- `Open in Research` uses the existing run URL
- `Unpin` clears only the pinned slot
- none of these actions change recent-history ordering

### Pinned + history state

If recent history also exists:

- show the pinned mini-card first
- show a separate `Recent research` block underneath
- keep existing recent entry actions there:
  - use/restore
  - pin

The main improvement is visual separation:

- pinned default first
- recent recall second

## Error Handling

- if pinned restore/unpin actions fail, degrade the same way current attachment actions do
- the fallback should remain usable even if recent history is empty
- no extra error banners or toasts in this slice

## Testing

### Frontend

- pinned-only fallback renders a dedicated mini-card
- `Use now` restores pinned into the active slot
- `Open in Research` points to the pinned run URL
- `Unpin` clears only the pinned slot
- pinned mini-card and recent-history block render separately when both exist
- active attachment flow remains unchanged

### Backend

- no new backend tests; behavior is presentational only

## Risks

- overexplaining the pinned slot and making the composer noisier than necessary
- duplicating interaction logic between active chip and pinned-only fallback
- accidentally regressing current no-active history pin/use behavior while restructuring fallback layout

## Success Criteria

- pinned-only state clearly reads as the thread’s default research context
- no-active fallback is easier to scan
- recent history remains a separate, secondary recall surface
- active attachment UX is unchanged
