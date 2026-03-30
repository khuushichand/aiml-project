# Workspace Study Materials Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make workspace-generated quizzes and flashcards persist as real module records with canonical workspace ownership, one persisted quiz per workspace run, deck-level flashcard ownership, hidden-by-default main-page visibility, and stable cross-page access from both the workspace and native Quiz/Flashcards pages.

**Architecture:** Put canonical ownership in backend persistence first so scope rules are enforceable rather than UI-only. Add `workspace_id` as the stable ownership field for quizzes and decks, keep `workspace_tag` only as a compatibility/display layer while migrating, then update workspace generation to write one quiz per bundle and one scoped deck per flashcard run. Finally, wire the shared React Query service layer, workspace artifact state, and Quiz/Flashcards pages to honor ownership filters, move-scope actions, and direct-link force-show behavior.

**Tech Stack:** FastAPI, Pydantic, ChaChaNotes SQLite/PostgreSQL DB layer, React, TypeScript, TanStack Query, Vitest, React Testing Library, Playwright, pytest

---

## File Structure

- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
  Purpose: canonical persistence, schema migration, list/update helpers, and ownership-aware filtering for quizzes, decks, flashcards, analytics, and review queue selection.
- `tldw_Server_API/app/api/v1/schemas/quizzes.py`
  Purpose: quiz request/response contract for `workspace_id`, compatibility `workspace_tag`, and mixed-source single-quiz generation.
- `tldw_Server_API/app/api/v1/schemas/flashcards.py`
  Purpose: deck request/response contract for `workspace_id` ownership and deck-scoped visibility filters.
- `tldw_Server_API/app/api/v1/schemas/workspace_schemas.py`
  Purpose: add workspace-level `study_materials_policy` to workspace CRUD.
- `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
  Purpose: expose ownership-aware quiz list/create/update/generate behavior and direct quiz fetches.
- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
  Purpose: expose ownership-aware deck listing, deck updates, card/review/document filter parameters, and stable direct fetch behavior.
- `tldw_Server_API/app/api/v1/endpoints/workspaces.py`
  Purpose: save/load the workspace default study-materials policy.
- `tldw_Server_API/tests/ChaChaNotesDB/test_quizzes_basic.py`
  Purpose: DB-level quiz ownership, migration, and single-record multi-source invariants.
- `tldw_Server_API/tests/ChaChaNotesDB/test_flashcards_basic.py`
  Purpose: DB-level deck ownership, scope transitions, and ownership-aware card/review filtering.
- `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py`
  Purpose: API-level quiz filtering, update, direct fetch, and generation contract.
- `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`
  Purpose: API-level deck/card/review/document visibility and move-scope contract.
- `tldw_Server_API/tests/Workspaces/test_workspaces_api.py`
  Purpose: workspace CRUD contract for `study_materials_policy`.
- `apps/packages/ui/src/services/quizzes.ts`
  Purpose: client-side quiz types and HTTP params for `workspace_id`, optional compatibility `workspace_tag`, and single-bundle generation.
- `apps/packages/ui/src/services/flashcards.ts`
  Purpose: client-side deck/card/review query params and deck ownership metadata.
- `apps/packages/ui/src/types/workspace.ts`
  Purpose: workspace settings and generated-artifact metadata for persisted quiz/deck identifiers and ownership-aware handoff data.
- `apps/packages/ui/src/store/workspace.ts`
  Purpose: persist workspace-level study-materials policy and artifact metadata in workspace snapshots.
- `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/hooks/useArtifactGeneration.tsx`
  Purpose: generate one persisted quiz for the selected source bundle, create scoped flashcard decks with bulk saves, and attach stable quiz/deck identifiers to artifacts.
- `apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts`
  Purpose: query keys and optimistic updates for the new ownership fields and visibility filters.
- `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
  Purpose: propagate ownership-aware filters through decks, card lists, due counts, analytics, cram queues, and review-next selection.
- `apps/packages/ui/src/components/Quiz/QuizPlayground.tsx`
  Purpose: read route/query handoff state and force-show a directly referenced quiz even when workspace-owned items are hidden by default.
- `apps/packages/ui/src/components/Quiz/tabs/ManageTab.tsx`
  Purpose: add `Show workspace quizzes`, workspace filtering, and move-scope actions.
- `apps/packages/ui/src/components/Quiz/tabs/TakeQuizTab.tsx`
  Purpose: ensure direct-start `quizId` flows can open a workspace-owned quiz without requiring global filter changes.
- `apps/packages/ui/src/components/Flashcards/FlashcardsManager.tsx`
  Purpose: honor handoff `deckId` and keep direct deck navigation visible even when workspace decks are hidden by default.
- `apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx`
  Purpose: add `Show workspace decks`, workspace filtering, and move-scope actions.
- `apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx`
  Purpose: preserve review access for direct `deckId` handoffs while default workspace visibility remains off.
- `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardDocumentQuery.ts`
  Purpose: keep document/query views aligned with deck ownership visibility rules.
- `apps/packages/ui/src/services/tldw/quiz-flashcards-handoff.ts`
  Purpose: maintain stable direct-link handoff semantics for `quizId` and `deckId`.
- `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
  Purpose: lock one-quiz-per-run and scoped flashcard deck generation behavior.
- `apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx`
  Purpose: extend existing quiz management tests for workspace filter and move-scope behavior.
- `apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx`
  Purpose: verify direct `quizId` navigation force-shows workspace-owned quizzes.
- `apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardQueries.review-next.test.tsx`
  Purpose: verify ownership-aware review-next and card visibility behavior.
- `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx`
  Purpose: extend deck management coverage for workspace filters and move-scope actions.
- `apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.ts`
  Purpose: verify document/query views do not leak workspace-owned cards when workspace visibility is off.
- `apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts`
  Purpose: keep workspace generation producing valid quiz/flashcard artifacts while also asserting persisted cross-page handoffs.
- `apps/tldw-frontend/tests/e2e/workspace-playground.parity.spec.ts`
  Purpose: extension/shared UI parity for workspace generation and cross-page handoff.

## Task 1: Add Canonical Workspace Ownership To Backend Persistence And API Contracts

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/workspace_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/workspaces.py`
- Test: `tldw_Server_API/tests/ChaChaNotesDB/test_quizzes_basic.py`
- Test: `tldw_Server_API/tests/ChaChaNotesDB/test_flashcards_basic.py`
- Test: `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py`
- Test: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`
- Test: `tldw_Server_API/tests/Workspaces/test_workspaces_api.py`

- [ ] **Step 1: Write the failing backend tests for workspace ownership**

Add or extend backend tests to prove:

1. quizzes accept and return `workspace_id`
2. decks accept and return `workspace_id`
3. `workspace_id = null` means general scope
4. workspace CRUD accepts `study_materials_policy`
5. quiz and deck update APIs can move items between general scope and one workspace without cloning

Use focused assertions like:

```python
quiz_id = db.create_quiz(name="Scoped quiz", workspace_id="ws-1")
quiz = db.get_quiz(quiz_id)
assert quiz["workspace_id"] == "ws-1"
assert quiz["workspace_tag"] in (None, "workspace:ws-1")
```

```python
deck_id = db.create_deck(name="Scoped deck", workspace_id="ws-1")
deck = db.get_deck(deck_id)
assert deck["workspace_id"] == "ws-1"
```

- [ ] **Step 2: Run the targeted backend tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/ChaChaNotesDB/test_quizzes_basic.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_flashcards_basic.py \
  tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py \
  tldw_Server_API/tests/Workspaces/test_workspaces_api.py \
  -v
```

Expected: FAIL because the current backend still exposes `workspace_tag` only for quizzes, has no deck ownership field, and has no `study_materials_policy` on workspaces.

- [ ] **Step 3: Add the minimal schema and persistence support**

Implement the smallest backend changes that make the new contract real:

- add `workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL` to `quizzes` and `decks`
- add indexes for quiz and deck `workspace_id`
- add `study_materials_policy TEXT` to `workspaces` with a conservative default like `"general"`
- extend DB create/get/list/update helpers for quizzes and decks to read and write `workspace_id`
- keep `workspace_tag` optional for quiz compatibility, but never use it as the canonical filter or update field
- extend deck serialization to include `workspace_id`
- extend workspace serialization to include `study_materials_policy`

Keep the DB API boring and explicit:

```python
def list_quizzes(..., workspace_id: str | None = None, include_workspace_items: bool = False):
    ...

def list_decks(..., workspace_id: str | None = None, include_workspace_items: bool = False):
    ...
```

- [ ] **Step 4: Re-run the targeted backend tests**

Run the same pytest command from Step 2.

Expected: PASS for ownership fields, workspace policy persistence, and in-place scope updates.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/app/api/v1/schemas/quizzes.py \
  tldw_Server_API/app/api/v1/schemas/flashcards.py \
  tldw_Server_API/app/api/v1/schemas/workspace_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/quizzes.py \
  tldw_Server_API/app/api/v1/endpoints/flashcards.py \
  tldw_Server_API/app/api/v1/endpoints/workspaces.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_quizzes_basic.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_flashcards_basic.py \
  tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py \
  tldw_Server_API/tests/Workspaces/test_workspaces_api.py
git commit -m "feat: add workspace ownership to quizzes and decks"
```

## Task 2: Enforce Ownership Across Flashcard Review, Card, And Analytics Flows

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- Test: `tldw_Server_API/tests/ChaChaNotesDB/test_flashcards_basic.py`
- Test: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`

- [ ] **Step 1: Write the failing flashcard visibility tests**

Add tests that prove hiding workspace-owned decks is not enough:

1. `list_flashcards()` with default filters does not leak cards from workspace-owned decks
2. `get_next_review_card()` with no deck and default filters does not return cards from workspace-owned decks
3. analytics and document/query flows respect the same visibility rule
4. directly fetching a concrete deck still works even if workspace items are hidden by default

Example DB-level expectation:

```python
general_deck = db.create_deck(name="General")
workspace_deck = db.create_deck(name="Workspace", workspace_id="ws-1")
db.add_flashcard({"deck_id": workspace_deck, "front": "Q", "back": "A"})
items = db.list_flashcards()
assert all(item["deck_id"] != workspace_deck for item in items)
```

- [ ] **Step 2: Run the flashcard-focused backend tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/ChaChaNotesDB/test_flashcards_basic.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py \
  -v
```

Expected: FAIL because current card listing, review-next, and analytics APIs only filter by deck/tag/due state.

- [ ] **Step 3: Add ownership-aware flashcard filters**

Update the DB and endpoint layer so any flashcard read path can enforce ownership:

- add shared ownership filter inputs such as `workspace_id` and `include_workspace_items`
- join `decks d` when needed so flashcard rows can be filtered by deck ownership
- make default behavior `general only`
- support explicit workspace filtering when `include_workspace_items=true`
- keep direct card/deck fetches independent from list visibility so force-show UI flows can still resolve a concrete target

Prefer one ownership predicate helper rather than re-implementing SQL fragments in every method.

- [ ] **Step 4: Re-run the flashcard-focused backend tests**

Run the pytest command from Step 2.

Expected: PASS for card listing, review-next, analytics, and document/query visibility invariants.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/app/api/v1/endpoints/flashcards.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_flashcards_basic.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py
git commit -m "feat: enforce workspace ownership in flashcard queries"
```

## Task 3: Rework Workspace Generation To Produce One Quiz And One Scoped Deck Per Run

**Files:**
- Modify: `apps/packages/ui/src/services/quizzes.ts`
- Modify: `apps/packages/ui/src/services/flashcards.ts`
- Modify: `apps/packages/ui/src/types/workspace.ts`
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/hooks/useArtifactGeneration.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx`

- [ ] **Step 1: Write the failing workspace-generation tests**

Extend the StudioPane tests to prove:

1. multi-source quiz generation calls `generateQuiz(...)` once with a mixed-source `sources` bundle instead of per-media fan-out
2. quiz artifacts store the real persisted `quiz.id`
3. flashcard generation creates or selects one scoped deck, then bulk-saves cards into it
4. flashcard artifacts store the real persisted `deck.id`
5. workspace policy determines whether ownership metadata is attached

Use explicit mocks:

```tsx
expect(mockGenerateQuiz).toHaveBeenCalledTimes(1)
expect(mockGenerateQuiz).toHaveBeenCalledWith(
  expect.objectContaining({
    sources: [
      { source_type: "media", source_id: "101" },
      { source_type: "media", source_id: "202" }
    ],
    workspace_id: "workspace-a"
  }),
  expect.anything()
)
```

- [ ] **Step 2: Run the targeted StudioPane tests to verify they fail**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run \
  ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx \
  ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx \
  --reporter=verbose
```

Expected: FAIL because the current quiz path still fans out per media item and current flashcard artifact metadata is not designed around canonical deck ownership and persisted handoff IDs.

- [ ] **Step 3: Implement the minimal workspace-generation rewrite**

Update the shared client layer and workspace artifact model to:

- add `workspace_id` to quiz and deck service types
- add `studyMaterialsPolicy` to workspace state/types
- add persisted handoff metadata to `GeneratedArtifact`, for example:

```ts
data?: {
  quizId?: number
  deckId?: number
  workspaceId?: string | null
  sourceMediaIds?: number[]
}
```

- rewrite quiz generation so it uses one request with `sources`
- rewrite flashcard persistence to create a fresh workspace-owned deck by default when policy is workspace-owned
- prefer `createFlashcardsBulk(...)` for generated cards
- generate a readable default deck name using workspace name and source bundle context

- [ ] **Step 4: Re-run the targeted StudioPane tests**

Run the vitest command from Step 2.

Expected: PASS, with one quiz request per run and one persisted deck per flashcard run.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/services/quizzes.ts \
  apps/packages/ui/src/services/flashcards.ts \
  apps/packages/ui/src/types/workspace.ts \
  apps/packages/ui/src/store/workspace.ts \
  apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/hooks/useArtifactGeneration.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx
git commit -m "feat: persist workspace study generation into scoped records"
```

## Task 4: Add Quiz And Flashcards Page Filters, Move-Scope Actions, And Direct-Link Force-Show

**Files:**
- Modify: `apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts`
- Modify: `apps/packages/ui/src/components/Quiz/QuizPlayground.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/tabs/ManageTab.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/tabs/TakeQuizTab.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardDocumentQuery.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/FlashcardsManager.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx`
- Modify: `apps/packages/ui/src/services/tldw/quiz-flashcards-handoff.ts`
- Test: `apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx`
- Test: `apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardQueries.review-next.test.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.ts`
- Test: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx`

- [ ] **Step 1: Write the failing UI tests for visibility and force-show behavior**

Cover these cases:

1. Quiz Manage hides workspace-owned quizzes by default and shows them when the toggle is enabled
2. Flashcards Manage hides workspace-owned decks by default and shows them when the toggle is enabled
3. move-scope actions update the item in place
4. direct `quizId` navigation opens a workspace-owned quiz even if the toggle is off
5. direct `deckId` navigation opens a workspace-owned deck even if the toggle is off
6. review-next and document-query hooks do not surface workspace-owned cards when visibility is off

- [ ] **Step 2: Run the targeted UI tests to verify they fail**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run \
  ../packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx \
  ../packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx \
  ../packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardQueries.review-next.test.tsx \
  ../packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.ts \
  ../packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx \
  --reporter=verbose
```

Expected: FAIL because the current UI does not have workspace ownership filters or force-show logic on direct handoff IDs.

- [ ] **Step 3: Implement the minimal UI behavior**

Make the smallest changes that satisfy the product contract:

- add default `general-only` params to quiz and flashcard list hooks
- add `Show workspace quizzes` and `Show workspace decks` toggles plus workspace pickers
- add move-scope actions that patch `workspace_id` in place
- when a concrete `quizId` or `deckId` is present in handoff/query state, fetch that item directly and inject it into the visible selection even if list filters would exclude it
- keep the surrounding collection default unchanged so force-show does not silently flip global filters

Keep the handoff behavior explicit:

```ts
if (startQuizId) {
  forceVisibleQuizIds.add(startQuizId)
}
```

- [ ] **Step 4: Re-run the targeted UI tests**

Run the vitest command from Step 2.

Expected: PASS for hidden-by-default behavior, move-scope updates, and direct-link force-show.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts \
  apps/packages/ui/src/components/Quiz/QuizPlayground.tsx \
  apps/packages/ui/src/components/Quiz/tabs/ManageTab.tsx \
  apps/packages/ui/src/components/Quiz/tabs/TakeQuizTab.tsx \
  apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts \
  apps/packages/ui/src/components/Flashcards/hooks/useFlashcardDocumentQuery.ts \
  apps/packages/ui/src/components/Flashcards/FlashcardsManager.tsx \
  apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx \
  apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx \
  apps/packages/ui/src/services/tldw/quiz-flashcards-handoff.ts \
  apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx \
  apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx \
  apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardQueries.review-next.test.tsx \
  apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.ts \
  apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx
git commit -m "feat: add workspace ownership controls to study pages"
```

## Task 5: Verify End-To-End Behavior, Security, And Shared-UI Parity

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts`
- Modify: `apps/tldw-frontend/tests/e2e/workspace-playground.parity.spec.ts`
- Optional Test Additions: `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`

- [ ] **Step 1: Extend the failing E2E tests**

Add coverage for:

1. generating a quiz in a workspace stores one persisted quiz and opening it from the Quiz page still works
2. generating flashcards in a workspace stores one persisted deck and opening it from the Flashcards page still works
3. workspace-owned items stay hidden by default in native pages until filters or direct-link force-show are used
4. moving scope from workspace to general keeps the same record IDs
5. downloaded artifacts still do not contain `failed to generate`

- [ ] **Step 2: Run the failing E2E tests**

Run:

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false \
TLDW_WEB_URL=http://localhost:3000 \
TLDW_SERVER_URL=http://127.0.0.1:8000 \
TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY \
bunx playwright test \
  e2e/workflows/workspace-playground.output-matrix.probe.spec.ts \
  tests/e2e/workspace-playground.parity.spec.ts \
  --reporter=line
```

Expected: FAIL until workspace artifact handoffs, native-page filters, and scope-move flows are fully wired.

- [ ] **Step 3: Run the full verification set after implementation**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run \
  ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx \
  ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx \
  ../packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx \
  ../packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx \
  ../packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardQueries.review-next.test.tsx \
  ../packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.ts \
  ../packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx \
  --reporter=verbose
```

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/ChaChaNotesDB/test_quizzes_basic.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_flashcards_basic.py \
  tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py \
  tldw_Server_API/tests/Workspaces/test_workspaces_api.py \
  -v
```

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false \
TLDW_WEB_URL=http://localhost:3000 \
TLDW_SERVER_URL=http://127.0.0.1:8000 \
TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY \
bunx playwright test \
  e2e/workflows/workspace-playground.output-matrix.probe.spec.ts \
  tests/e2e/workspace-playground.parity.spec.ts \
  --reporter=line
```

- [ ] **Step 4: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/quizzes.py \
  tldw_Server_API/app/api/v1/endpoints/flashcards.py \
  tldw_Server_API/app/api/v1/endpoints/workspaces.py \
  tldw_Server_API/app/api/v1/schemas/quizzes.py \
  tldw_Server_API/app/api/v1/schemas/flashcards.py \
  tldw_Server_API/app/api/v1/schemas/workspace_schemas.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  -f json -o /tmp/bandit_workspace_study_materials.json
```

Expected: no new security findings in touched code.

- [ ] **Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts \
  apps/tldw-frontend/tests/e2e/workspace-playground.parity.spec.ts
git commit -m "test: cover workspace study materials scope end to end"
```

## Notes For The Implementer

- Keep `workspace_id` canonical and treat `workspace_tag` as compatibility-only until all callers are migrated.
- Do not reintroduce per-media quiz fan-out in the workspace generation path.
- Do not rely on front-end filtering alone for flashcard visibility. Backend list, review-next, analytics, and document/query paths must all agree.
- Preserve direct fetch semantics for concrete `quizId` and `deckId` routes so workspace artifacts always open the intended record.
- Prefer appending new focused tests to existing high-signal files before creating brand-new test files unless those files become unwieldy.
- Keep commits small and reviewable. Each task above should land cleanly on its own.

## Manual Review

I performed the plan review inline rather than dispatching a separate reviewer subagent because this session was not explicitly authorized for sub-agent delegation.
