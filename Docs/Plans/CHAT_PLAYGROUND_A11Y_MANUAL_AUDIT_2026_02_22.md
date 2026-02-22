# Chat Playground Accessibility Audit Record (2026-02-22)

## Scope

- Desktop keyboard + screen-reader semantic path
- Mobile/touch parity path

## Desktop Path (Chat Core)

1. Open chat page and focus composer.
2. Send a message and verify focus returns to composer.
3. Open message actions, change variant, and verify focus remains in timeline context.
4. Trigger branch action and verify return control remains reachable.

Checks:

- [x] Live region/action info semantics remain present in component contract.
- [x] Message actions retain explicit ARIA labels and keyboard shortcuts.
- [x] Non-color status cues remain available for message and model state.

Evidence suites:

- `src/components/Common/Playground/__tests__/ActionInfo.accessibility.test.tsx`
- `src/components/Common/Playground/__tests__/Playground.accessibility-regression.test.tsx`
- `src/components/Common/Playground/__tests__/Message.non-color-signals.guard.test.ts`
- `src/components/Common/Playground/__tests__/Message.keyboard-shortcuts.guard.test.ts`

## Mobile Path (Compact Controls)

1. Open mobile composer layout scenario.
2. Verify keyboard-open layout keeps input/actions reachable.
3. Verify artifacts/source jump controls remain reachable via compact affordances.

Checks:

- [x] Mobile keyboard layout contract remains stable.
- [x] Touch target sizing safeguards remain in contract tests.
- [x] Accessibility smoke suite includes responsive chat coverage.

Evidence suites:

- `src/components/Option/Playground/__tests__/Playground.responsive-parity.guard.test.ts`
- `src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`
- `src/components/Sidepanel/Chat/__tests__/ArtifactsPanel.jump-source.guard.test.ts`

## Gate Command

```bash
bun run test:playground:a11y --reporter=dot
```

Result: `10 files / 17 tests passed`.

## Release Gate Integration

- CI workflow includes a dedicated accessibility step:
  - `.github/workflows/ui-playground-quality-gates.yml` -> `Run accessibility gate`
