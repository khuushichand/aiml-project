# Characters Form Rollout Parity Checklist (Plan 04 Stage 4)

## Scope

This checklist verifies post-refactor parity for the shared `CharacterForm` used by both create and edit modals in:

- `apps/packages/ui/src/components/Option/Characters/Manager.tsx`

## Field-Level Parity (Create vs Edit)

- [x] Name
- [x] System prompt (required + helper + example toggle)
- [x] Greeting
- [x] Description
- [x] Tags
- [x] Avatar field
- [x] Prompt preset (elevated)
- [x] Advanced section toggles (Prompt control / Generation settings / Metadata)
- [x] Alternate greetings dynamic list (add/remove/reorder)
- [x] Extensions JSON
- [x] Mood images placeholder

## Behavioral Parity

- [x] AI field-generation buttons present in both modes
- [x] Keyboard shortcut hook remains wired for new/create/focus/escape actions
- [x] Preview toggle and preview card render in both modes
- [x] Submit button loading and labels differ only by mode-specific text

## Migration Cleanup

- [x] Create/edit duplicate form blocks removed in favor of `renderSharedCharacterForm`
- [x] Dead optimistic cache write path removed for stale key (`["tldw:listCharacters", "all"]`)

## Verification Artifacts

- Component tests: `apps/packages/ui/src/components/Option/Characters/__tests__/Manager.first-use.test.tsx`
- Utility tests: `apps/packages/ui/src/components/Option/Characters/__tests__/search-utils.test.ts`
- E2E critical-path spec: `apps/extension/tests/e2e/characters-create-edit-import-export.spec.ts`
