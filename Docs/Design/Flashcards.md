# Flashcards

## UI Conventions (H4 Consistency Standards)

This note defines Flashcards UI consistency rules for tabs, create-entry routing, and drawer behavior.

### Navigation Labels

- Use `Study`, `Manage`, `Transfer` for Flashcards top-level tabs.
- Keep tab keys stable (`review`, `cards`, `importExport`) to avoid breaking keyboard-shortcut routing and deep state references.

Reference: `apps/packages/ui/src/components/Flashcards/FlashcardsManager.tsx`

### Primary Create Entry Point

- All secondary create actions (for example, Study empty state or top CTA) should route through the shared manager-level create entry point.
- The manager emits `openCreateSignal` to `ManageTab`, which opens `FlashcardCreateDrawer`.
- Avoid adding isolated create flows that bypass this routed path.

Reference:
- `apps/packages/ui/src/components/Flashcards/FlashcardsManager.tsx`
- `apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx`

### Drawer Standards

- Use shared drawer width token `FLASHCARDS_DRAWER_WIDTH_PX` for Create/Edit/Move drawers.
- Keep action order aligned as: `Cancel` -> secondary action -> primary action.
- Use consistent section rhythm (`mb-6`) and section headers for Organization/Content blocks.

Reference:
- `apps/packages/ui/src/components/Flashcards/constants/drawer-tokens.ts`
- `apps/packages/ui/src/components/Flashcards/components/FlashcardCreateDrawer.tsx`
- `apps/packages/ui/src/components/Flashcards/components/FlashcardEditDrawer.tsx`
- `apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx`

### Guardrails

- Tab naming and create-entry routing:  
  `apps/packages/ui/src/components/Flashcards/__tests__/FlashcardsManager.consistency.test.tsx`
- Shared drawer width token usage:  
  `apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.cloze-help.test.tsx`  
  `apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardEditDrawer.scheduling-metadata.test.tsx`  
  `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx`

## Background References

- https://www.kaggle.com/code/thomasanderson1962/public-synthetic-dataset-generation-w-internvl2
- https://www.youtube.com/watch?v=8zaKVFC9Eu4
- https://github.com/kerrickstaley/genanki
- https://darigovresearch.github.io/genanki/build/html/index.html
- https://github.com/patarapolw/anki-export
