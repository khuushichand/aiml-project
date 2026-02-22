# PR / Release Notes: P1 Tutorials Rollout (WebUI + Extension)

Date: 2026-02-22  
Scope: Per-page tutorial expansion + Quick Chat tutorials section hardening

## PR Summary

This change completes the P1 tutorial rollout by adding guided "Basics" tutorials for the remaining core workspace routes and hardening selector/test contracts to reduce regressions.

## New P1 Tutorial Routes

The following routes now have page tutorials available in both:
- `?` Help modal (`Tutorials` tab)
- Quick Chat helper -> `Browse Guides` -> `Tutorials for this page`

Canonical routes:
- `/prompts` -> `prompts-basics`
- `/evaluations` -> `evaluations-basics`
- `/notes` -> `notes-basics`
- `/flashcards` -> `flashcards-basics`
- `/world-books` -> `world-books-basics`

Legacy alias coverage:
- `/options/prompts` -> `/prompts`
- `/options/evaluations` -> `/evaluations`
- `/options/notes` -> `/notes`
- `/options/flashcards` -> `/flashcards`
- `/options/world-books` -> `/world-books`

## New Selector / Test Contracts

### Selector contracts

Added explicit `data-testid` anchors for tutorial stability on pages where selectors were missing or not stable enough:
- Evaluations:
  - `evaluations-page-title`
  - `evaluations-tabs`
  - `evaluations-create-button`
  - `evaluations-list-card`
  - `evaluations-detail-card`
- World Books:
  - `world-books-tutorial-shell`
  - `world-books-search-input`
  - `world-books-enabled-filter`
  - `world-books-attachment-filter`
  - `world-books-table`
  - `world-books-new-button`
  - `world-books-import-button`

### Automated contracts and behavior tests

Added/expanded tests:
- Route/tutorial coverage:
  - `apps/packages/ui/src/tutorials/__tests__/registry.test.ts`
  - `apps/packages/ui/src/components/Common/QuickChatHelper/__tests__/quick-chat-tutorials.test.ts`
- P1 selector contracts:
  - `apps/packages/ui/src/tutorials/__tests__/p1-target-contracts.test.ts`
  - Verifies P1 tutorial targets use stable selectors and expected anchors remain in source.
- Quick Chat Tutorials section behavior:
  - `apps/packages/ui/src/components/Common/QuickChatHelper/__tests__/QuickChatGuidesPanel.tutorials-section.test.tsx`
  - Verifies ordering, start/replay/locked behavior, and empty-state behavior.
- Locale mirror parity:
  - `apps/packages/ui/src/tutorials/__tests__/locale-mirror.test.ts`
  - Verifies `src/assets/locale/en/tutorials.json` and `src/public/_locales/en/tutorials.json` stay in sync.

## Validation Evidence

Primary test slice run:

```bash
bunx vitest run \
  src/components/Common/QuickChatHelper/__tests__/*.test.ts \
  src/components/Common/QuickChatHelper/__tests__/*.test.tsx \
  src/tutorials/__tests__/*.test.ts
```

Result: 8 files passed, 50 tests passed.

## User-Facing Release Notes Snippet

### Guided Tutorials Expanded Across More Pages

You can now launch guided page tutorials from both the Help modal (`?`) and Quick Chat `Browse Guides` on:
- Prompts
- Evaluations
- Notes
- Flashcards
- World Books

Tutorials are page-specific, show completion state, and support replay after completion.

## Known Limitations

1. P1 currently ships one "Basics" tutorial per new route; deeper advanced/tutorial tracks are not yet added for these pages.
2. Tutorial steps depend on page state (for example offline/unsupported modes can hide certain controls); the runner retries and skips missing targets, but some steps may be skipped in constrained states.
3. Locale parity enforcement currently covers English tutorial locales; non-English mirrors are not yet covered by parity tests.
4. This rollout is validated by unit/component tests; dedicated Playwright end-to-end tutorial flows for P1 routes are not included in this patch.

