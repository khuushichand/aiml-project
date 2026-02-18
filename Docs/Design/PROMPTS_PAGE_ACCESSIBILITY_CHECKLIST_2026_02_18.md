# Prompts Page Accessibility Checklist

Date: 2026-02-18  
Scope: `/prompts` and Studio sub-tabs

## Critical Controls

- [x] Screen reader live region exists with `role="status"` and `aria-live="polite"`.
- [x] Custom prompt rows are keyboard focusable and open edit drawer on `Enter`/`Space`.
- [x] Favorite toggle exposes state with `aria-pressed`.
- [x] Prompt type icon cluster exposes semantic label via `role="group"` and `aria-label`.
- [x] Copilot action controls include visible focus styling and minimum target-size utility classes.
- [x] Disabled Studio tabs expose prerequisite guidance through accessible labels/tooltips.
- [x] Mobile Studio navigation exposes text labels (no icon-only ambiguity).
- [x] Keyboard shortcuts help is discoverable by button and `?` shortcut.

## Shortcut Inventory

- `N`: Create new prompt
- `/`: Focus search
- `Esc`: Close drawer/modal
- `?`: Open keyboard shortcut help
