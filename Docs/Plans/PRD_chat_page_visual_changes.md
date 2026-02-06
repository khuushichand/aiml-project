# PRD: Chat Page Visual & Design Changes

## Objective

Improve the visual quality, spacing, typography, and responsiveness of the fullscreen chat page. These changes are purely cosmetic -- CSS classes, spacing values, border styles, and font sizes. No component restructuring.

---

## Background

The chat page has accumulated visual debt:
- Typography uses 5 different font size scales including sub-12px sizes that hurt readability
- Toolbar controls all use bordered pill badges that compete for attention
- Nested borders in the composer create visual heaviness
- Messages lack clear visual distinction between user and assistant
- Header buttons use bordered styles that create a "grid of boxes" feel
- Empty state is content-heavy and overwhelming

---

## Deliverables

### V1: Typography Scale Normalization

**Files**: All chat-related components

Establish minimum font size of `text-xs` (12px) across the chat UI:

| Current | Occurrences | Replace with | Exception |
|---------|-------------|-------------|-----------|
| `text-[10px]` | ~8 (MessageActionsBar, Message, PlaygroundForm) | `text-xs` | None |
| `text-[11px]` | ~20+ (toolbar badges, timestamps, hints) | `text-xs` | Variant pager counter can stay `text-[11px]` |

This creates a clean 3-level type scale: `text-xs` (12px), `text-sm` (14px), `text-base` (16px).

**Acceptance criteria**:
- No text smaller than 12px in the chat page
- Visual hierarchy maintained through weight and color, not sub-pixel size differences

---

### V2: Toolbar Badge Restyling

**Files**: ComposerToolbar (or PlaygroundForm if not yet extracted)

Replace bordered pill badge pattern:
```diff
- rounded-full border px-2 py-0.5 text-[11px] border-border text-text-muted
+ rounded-md px-2 py-1 text-xs text-text-subtle hover:bg-surface2 hover:text-text
```

Active toggle state:
```diff
- border-primary/50 bg-primary/10 text-primaryStrong
+ bg-primary/10 text-primaryStrong  (no border)
```

Follows existing `Button` ghost variant pattern from `apps/packages/ui/src/components/Common/Button.tsx`.

**Acceptance criteria**:
- Toolbar toggles look flat and calm when inactive
- Active state communicated through color, not border
- Touch targets remain adequate (min 36px height)

---

### V3: Message Spacing & Accent

**File**: `apps/packages/ui/src/components/Common/Playground/Message.tsx`

**Changes**:
1. Increase vertical spacing between messages:
   - Pro: `pb-2` -> `pb-3`, `md:px-4` -> `md:px-5`
   - Normal: `pb-1` -> `pb-2`, `md:px-3` -> `md:px-4`

2. Add left accent to bot messages:
   ```text
   border-l-2 border-l-primary/20
   ```

3. Soften card borders:
   ```diff
   - border border-border bg-surface/70
   + border border-border/50 bg-surface/60
   ```

4. Improve name/timestamp row spacing: add explicit `gap-1.5`

**Acceptance criteria**:
- More breathing room between messages
- Bot messages visually distinguishable at a glance via left accent
- Overall feel is lighter and more spacious

---

### V4: Header Button Styling

**File**: `apps/packages/ui/src/components/Layouts/ChatHeader.tsx`

Remove borders from header action buttons:
```diff
- rounded-md border border-border p-2 text-text-muted hover:bg-surface2 hover:text-text
+ rounded-md p-2 text-text-muted hover:bg-surface2 hover:text-text
```

This matches the sidebar toggle button style (line 83) which already has no border.

**Acceptance criteria**:
- Header buttons feel lighter and more integrated
- Hover state still provides clear affordance
- Consistent with sidebar toggle button style

---

### V5: Composer Border Reduction

**Files**: `PlaygroundForm.tsx`, `Playground.tsx`

1. **Remove outer composer card border in sticky mode**: When `stickyChatInput` is true, the `border-t border-border` at Playground.tsx line 554 provides sufficient separation. Remove the outer `border-border/80` from the composer card div (line 4569).

2. **Knowledge panel**: Replace `border border-border` with `bg-surface2/50` at line 4713. Use background color difference instead of border for visual separation.

3. **Reduce double-border effect**: The textarea has its own `border border-border/70` (line 4791) inside the composer card's `border border-border/80` (line 4569). Change composer card border to `border-transparent` and let the textarea border be the primary border.

**Acceptance criteria**:
- No more than one visible border level in the composer area
- Visual separation achieved through background color and spacing

---

### V6: Empty State Simplification

**File**: `apps/packages/ui/src/components/Option/Playground/PlaygroundEmpty.tsx`

1. Remove `FeatureDiscoveryHints` component (lines 37-79) -- the Voice Chat, Knowledge Search, and Compare Mode descriptions are better served by the tour and command palette

2. Remove the `examples` prop from `FeatureEmptyState` usage (lines 128-141) -- these bullet points duplicate the clickable example prompts below

3. Style example prompt chips as slightly larger cards:
   ```diff
   - rounded-full border border-border/80 bg-surface2/50 px-3 py-1.5 text-xs
   + rounded-xl border border-border/60 bg-surface2/40 px-4 py-2.5 text-sm
   ```

4. Remove the wrapping bordered card around the bottom section (lines 152-172). Let the example prompts float freely below the FeatureEmptyState.

**Acceptance criteria**:
- Empty state has ~50% less content
- Example prompts are more prominent and inviting
- Tour link remains accessible

---

### V7: Scroll-to-Bottom Button Polish

**File**: `apps/packages/ui/src/components/Option/Playground/Playground.tsx` (lines 558-567)

1. Increase button size: `p-2` -> `p-2.5`
2. Add subtle shadow: `shadow-md`
3. Add appear animation: `transition-all duration-200 animate-in fade-in zoom-in-95` (using Tailwind animate utilities or inline transition)
4. Add unread message count badge when user has scrolled up and new messages arrive

**Acceptance criteria**:
- Button is slightly larger and more prominent
- Appears with a subtle animation
- Shows count of new messages since scrolling away

---

### V8: Mobile Responsive Tweaks

**Files**: Multiple components

1. **Textarea min-height**: Reduce from `60px`/`44px` to `40px` on mobile
   ```diff
   - style={{ minHeight: isProMode ? "60px" : "44px" }}
   + style={{ minHeight: isMobile ? "40px" : isProMode ? "60px" : "44px" }}
   ```

2. **Message action buttons**: Replace `sm:min-w-0 sm:min-h-0` with explicit `sm:h-8 sm:w-8` for predictable desktop sizing

3. **Chat title in header**: Remove `hidden sm:block` to show on mobile with truncation

**Acceptance criteria**:
- Mobile composer takes less vertical space
- Desktop action buttons have consistent 32px sizing
- Chat title visible on all viewports

---

## Implementation Order

```text
V1 (Typography) -- independent, low risk, sweep
V4 (Header buttons) -- independent, small change
V6 (Empty state) -- independent, component-scoped
V3 (Message spacing) -- independent, component-scoped
V2 (Toolbar badges) -- depends on Structural PRD S2 if toolbar extracted, otherwise modify inline
V5 (Composer borders) -- independent but easier after Structural PRD extraction
V7 (Scroll button) -- independent, small scope
V8 (Mobile) -- independent, sweep
```

## Critical Files Reference

| File | Path | Lines | Role |
|------|------|-------|------|
| Message | `apps/packages/ui/src/components/Common/Playground/Message.tsx` | 1296 | Message bubble |
| MessageActionsBar | `apps/packages/ui/src/components/Common/Playground/MessageActionsBar.tsx` | 450 | Message actions |
| PlaygroundForm | `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx` | 5500+ | Composer |
| ChatHeader | `apps/packages/ui/src/components/Layouts/ChatHeader.tsx` | 234 | Header |
| PlaygroundEmpty | `apps/packages/ui/src/components/Option/Playground/PlaygroundEmpty.tsx` | 175 | Empty state |
| Playground | `apps/packages/ui/src/components/Option/Playground/Playground.tsx` | 595 | Root container |
| Button (reference) | `apps/packages/ui/src/components/Common/Button.tsx` | - | Ghost variant pattern |

## Verification

1. Start dev server: `cd apps/tldw-frontend && npm run dev`, open `/chat`
2. Test both Pro and Normal UI modes (toggle in settings)
3. Verify empty state displays correctly before any messages
4. Send messages, verify spacing and left accent on bot messages
5. Hover over messages, verify action bar layout
6. Test mobile viewport (Chrome DevTools at 375px and 768px)
7. Verify no text below 12px on the chat page
8. Run existing frontend tests if available
