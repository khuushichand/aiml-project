# Chat Playground Composer Usability Checklist (2026-02-22)

## Ownership

- Feature owner: WebUI Chat UX
- Verification owner: Frontend QA

## Checklist

- [x] Primary row keeps send/stop, input, attachments, voice, and model selector.
- [x] Context modifiers remain visible as chips before send.
- [x] `@` mentions remain keyboard navigable with clear zero-result guidance.
- [x] `/` commands retain concise descriptions and syntax examples.
- [x] JSON mode + preset + cost/context notices remain visible and actionable.
- [x] Attachment preview/remove interactions remain available without layout regressions.

## Verification Commands

```bash
bun run test:playground:composer --reporter=dot
```

## Evidence

- Run result: `6 files / 24 tests passed`
- Key suites:
  - `src/components/Option/Playground/__tests__/MentionsDropdown.integration.test.tsx`
  - `src/hooks/playground/__tests__/useSlashCommands.test.tsx`
  - `src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`
