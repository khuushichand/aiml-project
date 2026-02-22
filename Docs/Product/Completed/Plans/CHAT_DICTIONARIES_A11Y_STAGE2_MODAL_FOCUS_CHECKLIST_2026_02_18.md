# Chat Dictionaries A11y Stage 2 Modal Focus Checklist

## Scope

- Component: `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`
- Stage: Accessibility Plan 10, Stage 2
- Focus: Modal/drawer focus trap and focus-return behavior across keyboard-only flows

## Keyboard + Screen Reader Verification

1. Open `Create Dictionary` from `New Dictionary` and close via `Esc` and close button.
Expected: focus returns to `New Dictionary` trigger.

2. Open `Import Dictionary` from `Import` and close via `Esc` and close button.
Expected: focus returns to `Import` trigger.

3. Open `Manage Entries` drawer from row action and close via close button and `Esc`.
Expected: focus returns to the row’s `Manage entries` trigger.

4. In `Manage Entries`, open `Edit Entry` modal from an entry row and close it.
Expected: focus returns to the same `Edit entry` trigger inside the drawer; drawer remains open.

5. Open `Quick assign` modal from row action and close without saving.
Expected: focus returns to the `Quick assign` trigger.

6. Open `Dictionary Statistics` modal from row action and close.
Expected: focus returns to the `Stats` trigger.

7. While each modal is open, press `Tab` repeatedly.
Expected: focus remains trapped within the active modal/drawer controls.

8. With a screen reader enabled (NVDA/VoiceOver), verify title announcement order for:
- `Quick assign`
- `Import Dictionary`
- `Edit Entry`
Expected: dialog title announced first, then first interactive control.

## Regression Gate

- Keep this checklist paired with:
  - `apps/packages/ui/src/components/Option/Dictionaries/__tests__/Manager.accessibilityStage2.test.tsx`
