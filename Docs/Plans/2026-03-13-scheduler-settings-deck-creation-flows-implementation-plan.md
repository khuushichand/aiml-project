# Scheduler Settings In Deck Creation Flows Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend scheduler configuration into deck-creation flows across flashcards and quiz remediation, including explicit inline deck creation, selector-driven `Create new deck` flows, and quiz-owned remediation deck creation.

**Architecture:** Extract a shared scheduler draft/editor for creation surfaces, tighten the create-deck mutation to submit full scheduler settings, add `__new__` deck-selector support to import/generate/image-occlusion flows, and extend quiz remediation deck creation to accept scheduler settings when creating a new deck.

**Tech Stack:** React, TanStack Query, Ant Design, TypeScript, FastAPI, Pydantic, SQLite/PostgreSQL via `CharactersRAGDB`, Vitest, pytest, Bandit.

---

### Task 1: Extract Shared Scheduler Draft And Creation Editor Primitives

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/utils/scheduler-settings.ts`
- Create: `apps/packages/ui/src/components/Flashcards/hooks/useDeckSchedulerDraft.ts`
- Create: `apps/packages/ui/src/components/Flashcards/components/DeckSchedulerSettingsEditor.tsx`
- Create: `apps/packages/ui/src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx`

**Step 1: Write the failing tests**

Add UI tests for:

- preset selection updating the scheduler summary
- advanced field edits producing validated full settings
- reset-to-defaults restoring baseline settings
- validation errors staying local to the editor

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx
```

Expected: FAIL because the shared editor and hook do not exist.

**Step 3: Write minimal implementation**

Implement:

- `useDeckSchedulerDraft`
- `DeckSchedulerSettingsEditor`

Requirements:

- compact creation-mode layout
- preset selector
- summary preview
- optional advanced section
- full-settings validation output

Keep the implementation free of deck version/conflict logic from `SchedulerTab`.

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx
```

Expected: PASS.

### Task 2: Tighten Deck-Creation Mutation Contract And Reuse It In Flashcards Create Drawer

**Files:**
- Modify: `apps/packages/ui/src/services/flashcards.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/components/FlashcardCreateDrawer.tsx`
- Create: `apps/packages/ui/src/components/Flashcards/hooks/__tests__/useCreateDeckMutation.test.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.image-insert.test.tsx`

**Step 1: Write the failing tests**

Add tests for:

- `useCreateDeckMutation` forwarding full `scheduler_settings`
- inline create-deck flow submitting deck name plus scheduler settings
- cancel clearing inline scheduler draft state
- existing deck selection remaining unchanged until successful create

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run \
  src/components/Flashcards/hooks/__tests__/useCreateDeckMutation.test.tsx \
  src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.image-insert.test.tsx
```

Expected: FAIL because the mutation does not forward scheduler settings and the drawer has no scheduler editor.

**Step 3: Write minimal implementation**

Implement:

- `createDeck()` type tightened to full `DeckSchedulerSettings` when present
- `useCreateDeckMutation()` accepting `scheduler_settings`
- `FlashcardCreateDrawer` inline new-deck flow using the shared scheduler editor

Also add a read-only scheduler summary when an existing deck is selected.

**Step 4: Run test to verify it passes**

Run the same command from Step 2.

Expected: PASS.

### Task 3: Add `Create New Deck` Selector Flows To Structured Import, Generated Cards, And Image Occlusion

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ImageOcclusionTransferPanel.tsx`
- Create: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.deck-creation.test.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx`

**Step 1: Write the failing tests**

Add tests for:

- structured import selector supports `__new__`
- generated cards selector supports `__new__`
- image occlusion selector supports `__new__`
- selecting `__new__` shows deck-name plus scheduler editor
- the default-first-deck effect does not overwrite the `__new__` sentinel
- save/import creates a deck with scheduler settings and then saves cards into it

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run \
  src/components/Flashcards/tabs/__tests__/ImportExportTab.deck-creation.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx
```

Expected: FAIL because those selectors do not yet support `__new__`.

**Step 3: Write minimal implementation**

In each flow:

- add `__new__` selector option
- add local new-deck config state
- add deck name plus shared scheduler editor block
- make the auto-default effects sentinel-aware
- pass validated scheduler settings into `useCreateDeckMutation()`

Also show a read-only scheduler summary for existing selected decks.

**Step 4: Run test to verify it passes**

Run the same command from Step 2.

Expected: PASS.

### Task 4: Extend Quiz Remediation Deck Creation To Accept Scheduler Settings

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py`
- Modify: `apps/packages/ui/src/services/quizzes.ts`
- Modify: `apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts`
- Modify: `apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx`

**Step 1: Write the failing tests**

Add backend and frontend tests for:

- remediation convert request accepting `create_deck_scheduler_settings`
- remediation-created deck storing those scheduler settings
- remediation UI showing the shared scheduler editor when `Create new deck` is selected
- remediation UI forwarding scheduler settings with `create_deck_name`
- existing selected remediation deck showing a scheduler summary

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py \
  -k "remediation_conversion" -v
```

And:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: FAIL because the remediation request and UI do not yet carry scheduler settings.

**Step 3: Write minimal implementation**

Backend:

- add `create_deck_scheduler_settings` to the remediation convert request schema
- validate it only with `create_deck_name`
- pass it into the remediation conversion helper
- use it when calling deck creation

Frontend:

- extend quiz service/hook types
- render the shared scheduler editor when `Create new deck` is selected
- submit full validated scheduler settings with remediation conversion
- show read-only scheduler summary for existing selected decks

**Step 4: Run test to verify it passes**

Run the same commands from Step 2.

Expected: PASS.

### Task 5: Update Docs And Run End-To-End Verification

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`

**Step 1: Update docs**

Document:

- choosing scheduler settings during deck creation
- `Create new deck` in import/generate/image-occlusion flows
- remediation deck creation with scheduler settings
- using the `Scheduler` tab for later edits

**Step 2: Run frontend verification matrix**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/apps/packages/ui
bunx vitest run \
  src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx \
  src/components/Flashcards/hooks/__tests__/useCreateDeckMutation.test.tsx \
  src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.image-insert.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImportExportTab.deck-creation.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx \
  src/components/Flashcards/tabs/__tests__/SchedulerTab.editor.test.tsx
```

Expected: PASS.

**Step 3: Run backend verification**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py \
  -k "remediation_conversion" -v
```

Expected: PASS.

**Step 4: Run Bandit on touched Python scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m bandit -r \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/tldw_Server_API/app/api/v1/endpoints/quizzes.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/tldw_Server_API/app/api/v1/schemas/quizzes.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  -f json -o /tmp/bandit_scheduler_creation_flows.json
```

Expected: either no new findings or only pre-existing findings outside the new slice.

**Step 5: Run diff hygiene**

Run:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux diff --check
```

Expected: clean.

### Task 6: Final Review And Commit

**Step 1: Review the diff**

Check for:

- any selector-state regressions from `__new__`
- duplicated scheduler validation logic
- any path still creating decks without explicit scheduler handling
- any remediation path drift between deck create and conversion request

**Step 2: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux add \
  Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md \
  Docs/Plans/2026-03-13-scheduler-settings-deck-creation-flows-design.md \
  Docs/Plans/2026-03-13-scheduler-settings-deck-creation-flows-implementation-plan.md \
  apps/packages/ui/src/components/Flashcards/components/DeckSchedulerSettingsEditor.tsx \
  apps/packages/ui/src/components/Flashcards/components/FlashcardCreateDrawer.tsx \
  apps/packages/ui/src/components/Flashcards/components/__tests__/DeckSchedulerSettingsEditor.test.tsx \
  apps/packages/ui/src/components/Flashcards/hooks/useDeckSchedulerDraft.ts \
  apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts \
  apps/packages/ui/src/components/Flashcards/hooks/__tests__/useCreateDeckMutation.test.tsx \
  apps/packages/ui/src/components/Flashcards/tabs/ImageOcclusionTransferPanel.tsx \
  apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx \
  apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx \
  apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.deck-creation.test.tsx \
  apps/packages/ui/src/components/Flashcards/utils/scheduler-settings.ts \
  apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx \
  apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx \
  apps/packages/ui/src/services/flashcards.ts \
  apps/packages/ui/src/services/quizzes.ts \
  apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts \
  tldw_Server_API/app/api/v1/endpoints/quizzes.py \
  tldw_Server_API/app/api/v1/schemas/quizzes.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/assistant-conflict-recovery-ux commit -m "feat(flashcards): add scheduler settings to deck creation flows"
```

Success means the branch has one consistent scheduler-creation experience across flashcards and quiz remediation.
