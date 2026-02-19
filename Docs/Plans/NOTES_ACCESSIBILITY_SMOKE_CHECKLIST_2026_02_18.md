# Notes Accessibility Smoke Checklist (Release Gate)

Date: 2026-02-18  
Scope: `/notes` page, keyword picker modal, graph modal, floating notes dock unsaved modal

## 1. Keyboard-Only Navigation

- Load `/notes` and press `Tab` from top of page:
  - `Skip to notes list` and `Skip to editor` links appear on focus.
- Activate `Skip to notes list`:
  - focus lands on notes list region.
- Activate `Skip to editor`:
  - focus lands on editor region.
- Open keyboard shortcuts help via `?`:
  - help dialog opens, `Escape` closes it, and focus returns to trigger.
- Open keyword picker (`Browse keywords`), press `Escape`:
  - modal closes and focus returns to `Browse keywords`.
- Open graph modal, press `Escape`:
  - modal closes and focus returns to `Open graph view`.
- Open dock, click close while dirty, choose `Cancel`:
  - unsaved modal closes and focus returns to dock close trigger.

## 2. Screen Reader Semantics (NVDA or VoiceOver)

- Selected note in list announces selected/current state.
- Editor textarea announces label `Note content`.
- Skip links announce meaningful destination names.
- Graph zoom controls announce:
  - `Zoom in`
  - `Zoom out`
  - `Fit graph to view`
- Modal titles are announced:
  - `Browse keywords`
  - `Notes graph view`
  - `Unsaved notes` (dock close flow)

## 3. Contrast and Visual Legibility

- Validate body text on surface in light and dark themes:
  - meets at least WCAG AA (4.5:1) for primary text.
- Verify focus indicator remains visible in light and dark themes for:
  - skip links
  - primary toolbar buttons
  - modal close/cancel actions

## 4. Regression Commands

Run from `apps/packages/ui` after activating project venv:

```bash
source ../../../.venv/bin/activate
bunx vitest run \
  src/components/Notes/__tests__/NotesManagerPage.stage19.accessibility-skip-links.test.tsx \
  src/components/Notes/__tests__/NotesManagerPage.stage20.accessibility-shortcuts.test.tsx \
  src/components/Notes/__tests__/NotesManagerPage.stage21.accessibility-modal-focus.test.tsx \
  src/components/Notes/__tests__/NotesManagerPage.stage22.accessibility-regression.test.tsx \
  src/components/Notes/__tests__/NotesGraphModal.stage2.graph-view.test.tsx \
  src/components/Common/NotesDock/__tests__/NotesDockPanel.stage1.accessibility.test.tsx \
  src/components/Common/NotesDock/__tests__/NotesDockPanel.stage2.accessibility-regression.test.tsx
```

Expected: all tests pass.
