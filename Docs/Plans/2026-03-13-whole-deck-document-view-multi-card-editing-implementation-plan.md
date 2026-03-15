# Whole-Deck Document View And Multi-Card Editing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a `document` presentation mode inside Flashcards `Manage` that supports continuous-scroll deck maintenance, inline multi-card editing, and row-safe immediate saves.

**Architecture:** Extend the existing `Manage` surface instead of creating a new workspace. Add a mixed-result flashcard bulk-update endpoint, a document-mode infinite query plus truncation metadata, and a dedicated document row editor with per-row save queues, conditional cache updates, row-local undo, and conflict recovery. Keep advanced edit/preview flows in the existing drawer.

**Tech Stack:** FastAPI, Pydantic, React, TypeScript, TanStack Query, Ant Design, pytest, Vitest

---

Follow `@superpowers/test-driven-development` throughout. Before declaring the work complete, run the commands in the verification section and follow `@superpowers/verification-before-completion`.

## Scope Guardrails

- Implement `document` as a third presentation mode inside Flashcards `Manage`.
- Reuse existing `Manage` filters, selection, bulk actions, and the detailed edit drawer.
- Document-mode v1 sort options are limited to `due` and `created`.
- Inline row editing supports:
  - `front`
  - `back`
  - `deck`
  - `tags`
  - `notes`
  - `template/model_type`
- Row saves are immediate, per-row, and use optimistic locking.
- Use mixed-result bulk-update responses; do not make the batch all-or-nothing.
- Add row-local conflict recovery and undo.
- Do not add image support, image occlusion, scheduler changes, or a new standalone editor workspace in this plan.

## Relevant Existing Code

- `apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx`
- `apps/packages/ui/src/components/Flashcards/components/FlashcardEditDrawer.tsx`
- `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- `apps/packages/ui/src/components/Flashcards/utils/error-taxonomy.ts`
- `apps/packages/ui/src/services/flashcards.ts`
- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`
- `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`

## Implementation Notes

- Prefer creating focused frontend helpers/components instead of adding all document-mode logic directly inside `ManageTab.tsx`.
- Reuse the drawer’s template normalization logic rather than duplicating `model_type` behavior.
- Use the new bulk-update endpoint for all document-mode saves, including single-row saves.
- Serialize in-flight saves per row and coalesce queued edits into the next request payload.
- Only patch the infinite-query cache in place when row membership and order remain valid; otherwise invalidate just the active document query.

### Task 1: Add Bulk-Update API Contract Tests

**Files:**
- Modify: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`
- Reference: `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- Reference: `tldw_Server_API/app/api/v1/schemas/flashcards.py`

**Step 1: Write the failing test**

```python
def test_flashcards_bulk_patch_returns_mixed_results(client_with_flashcards_db):
    deck = create_test_deck(client_with_flashcards_db)
    first = create_test_flashcard(client_with_flashcards_db, deck_id=deck["id"])
    second = create_test_flashcard(client_with_flashcards_db, deck_id=deck["id"])

    response = client_with_flashcards_db.patch(
        "/api/v1/flashcards/bulk",
        json=[
            {
                "uuid": first["uuid"],
                "front": "Updated front",
                "expected_version": first["version"],
            },
            {
                "uuid": second["uuid"],
                "model_type": "cloze",
                "front": "Not a cloze",
                "expected_version": second["version"],
            },
        ],
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["status"] == "updated"
    assert data["results"][0]["flashcard"]["front"] == "Updated front"
    assert data["results"][1]["status"] == "validation_error"
    assert data["results"][1]["error"]["invalid_fields"] == ["front"]


def test_flashcards_bulk_patch_reports_conflict_without_rolling_back_siblings(client_with_flashcards_db):
    card_a = create_test_flashcard(client_with_flashcards_db)
    card_b = create_test_flashcard(client_with_flashcards_db)

    client_with_flashcards_db.patch(
        f"/api/v1/flashcards/{card_b['uuid']}",
        json={"front": "Other update", "expected_version": card_b["version"]},
        headers=AUTH_HEADERS,
    )

    response = client_with_flashcards_db.patch(
        "/api/v1/flashcards/bulk",
        json=[
            {
                "uuid": card_a["uuid"],
                "back": "Saved sibling",
                "expected_version": card_a["version"],
            },
            {
                "uuid": card_b["uuid"],
                "back": "Conflicted edit",
                "expected_version": card_b["version"],
            },
        ],
        headers=AUTH_HEADERS,
    )

    data = response.json()
    assert data["results"][0]["status"] == "updated"
    assert data["results"][1]["status"] == "conflict"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "bulk_patch" -v
```

Expected: FAIL with `405`/`404` because `PATCH /api/v1/flashcards/bulk` does not exist yet.

**Step 3: Write minimal implementation**

- Add request/response schemas for bulk-update rows and per-item results in `tldw_Server_API/app/api/v1/schemas/flashcards.py`.
- Add a `PATCH /bulk` handler in `tldw_Server_API/app/api/v1/endpoints/flashcards.py`.
- Reuse current validation rules from single-card updates for each item.
- Process each item independently and collect mixed results in one response.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "bulk_patch" -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py
git commit -m "feat(flashcards): add bulk update api contract"
```

### Task 2: Harden Backend Validation And Result Shapes

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- Modify: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`

**Step 1: Write the failing test**

```python
def test_flashcards_bulk_patch_rejects_deleted_deck_and_not_found_rows(client_with_flashcards_db):
    deleted_deck = create_deleted_test_deck(client_with_flashcards_db)
    live_card = create_test_flashcard(client_with_flashcards_db)

    response = client_with_flashcards_db.patch(
        "/api/v1/flashcards/bulk",
        json=[
            {
                "uuid": live_card["uuid"],
                "deck_id": deleted_deck["id"],
                "expected_version": live_card["version"],
            },
            {
                "uuid": "missing-card-uuid",
                "front": "No card",
                "expected_version": 1,
            },
        ],
        headers=AUTH_HEADERS,
    )

    data = response.json()
    assert data["results"][0]["status"] == "validation_error"
    assert data["results"][1]["status"] == "not_found"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "deleted_deck_and_not_found_rows" -v
```

Expected: FAIL because result classification is incomplete.

**Step 3: Write minimal implementation**

- Normalize per-item errors into stable response shapes:
  - `status`
  - `error.code`
  - `error.message`
  - optional structured details like `invalid_fields`
- Return `not_found` instead of generic server failures for missing cards.
- Preserve the single-card deck/cloze/template validation rules exactly.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "deleted_deck_and_not_found_rows" -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py
git commit -m "feat(flashcards): classify bulk update row failures"
```

### Task 3: Add Frontend Service Types And Document Query Hook

**Files:**
- Modify: `apps/packages/ui/src/services/flashcards.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- Create: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardDocumentQuery.ts`
- Test: `apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.tsx`

**Step 1: Write the failing test**

```tsx
it("limits document-mode sorts to due and created and reports truncation for capped multi-tag scans", async () => {
  vi.mocked(listFlashcards)
    .mockResolvedValueOnce({
      items: [makeFlashcard({ uuid: "a", tags: ["one", "two"] })],
      count: 1,
      total: 20000,
    })

  const { result } = renderHook(() =>
    useFlashcardDocumentQuery({
      deckId: null,
      tags: ["one", "two"],
      dueStatus: "all",
      sortBy: "due",
    })
  )

  await waitFor(() => expect(result.current.data?.pages.length).toBe(1))
  expect(result.current.supportedSorts).toEqual(["due", "created"])
  expect(result.current.isTruncated).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.tsx
```

Expected: FAIL because the document query hook does not exist.

**Step 3: Write minimal implementation**

- Add new service types for bulk-update request/response rows in `apps/packages/ui/src/services/flashcards.ts`.
- Add `patchFlashcardsBulk(...)` service function.
- Add `useFlashcardDocumentQuery(...)` built on `useInfiniteQuery`.
- Expose:
  - loaded pages
  - `fetchNextPage`
  - `hasNextPage`
  - `isTruncated`
  - `supportedSorts`
- For multi-tag document queries, scan source pages incrementally and flag truncation if the scan limit is reached.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/flashcards.ts apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts apps/packages/ui/src/components/Flashcards/hooks/useFlashcardDocumentQuery.ts apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.tsx
git commit -m "feat(flashcards): add document query hook"
```

### Task 4: Add Document-Mode Mutation Hook And Cache Policy Helpers

**Files:**
- Modify: `apps/packages/ui/src/services/flashcards.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- Create: `apps/packages/ui/src/components/Flashcards/utils/document-cache-policy.ts`
- Test: `apps/packages/ui/src/components/Flashcards/utils/__tests__/document-cache-policy.test.ts`

**Step 1: Write the failing test**

```ts
it("forces document query refresh when a row edit changes filter membership", () => {
  const previous = makeFlashcard({ uuid: "row-1", deck_id: 5, tags: ["bio"] })
  const next = makeFlashcard({ uuid: "row-1", deck_id: 7, tags: ["chem"] })

  expect(
    shouldRefetchDocumentQueryAfterRowSave(previous, next, {
      deckId: 5,
      tags: ["bio"],
      sortBy: "due",
      dueStatus: "all",
    })
  ).toBe(true)
})

it("allows in-place patching when row membership and sort position remain stable", () => {
  const previous = makeFlashcard({ uuid: "row-1", notes: "old" })
  const next = makeFlashcard({ uuid: "row-1", notes: "new" })

  expect(
    shouldRefetchDocumentQueryAfterRowSave(previous, next, {
      deckId: null,
      tags: [],
      sortBy: "due",
      dueStatus: "all",
    })
  ).toBe(false)
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/utils/__tests__/document-cache-policy.test.ts
```

Expected: FAIL because the helper does not exist.

**Step 3: Write minimal implementation**

- Add a dedicated bulk-update mutation hook for document mode.
- Add helper(s) that decide whether to:
  - patch the updated row into the infinite-query cache
  - or invalidate only the active document query
- Keep the legacy single-card mutation unchanged for drawer/review flows.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/utils/__tests__/document-cache-policy.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/flashcards.ts apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts apps/packages/ui/src/components/Flashcards/utils/document-cache-policy.ts apps/packages/ui/src/components/Flashcards/utils/__tests__/document-cache-policy.test.ts
git commit -m "feat(flashcards): add document mode cache policy"
```

### Task 5: Add Document View Shell To Manage

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx`
- Create: `apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentView.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-mode.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders a document presentation mode and hides unsupported sorts", async () => {
  renderManageTab()

  fireEvent.click(screen.getByTestId("flashcards-density-toggle-document"))

  expect(screen.getByTestId("flashcards-document-view")).toBeInTheDocument()
  expect(screen.queryByText("Ease")).not.toBeInTheDocument()
  expect(screen.queryByText("Last reviewed")).not.toBeInTheDocument()
})

it("shows a truncation banner and disables select-all-across when document results are capped", async () => {
  mockDocumentQuery({ isTruncated: true })
  renderManageTab({ initialMode: "document" })

  expect(screen.getByTestId("flashcards-document-truncation-banner")).toBeInTheDocument()
  expect(screen.getByTestId("flashcards-select-all-across")).toBeDisabled()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-mode.test.tsx
```

Expected: FAIL because document mode does not exist.

**Step 3: Write minimal implementation**

- Extend the presentation toggle logic in `ManageTab.tsx` to support `document`.
- Keep top-level `cards | trash` mode semantics unchanged.
- Render a `FlashcardDocumentView` component when `document` is active.
- Restrict sort options in document mode to `due` and `created`.
- Surface truncation UI and disable select-all-across when truncation is active.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-mode.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentView.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-mode.test.tsx
git commit -m "feat(flashcards): add manage document mode shell"
```

### Task 6: Add Editable Document Rows With Per-Row Save Queues

**Files:**
- Create: `apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentRow.tsx`
- Create: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardDocumentRowState.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentView.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx`

**Step 1: Write the failing test**

```tsx
it("queues overlapping row edits and sends the second patch after the first succeeds", async () => {
  const mutateAsync = vi.fn()
    .mockResolvedValueOnce({
      results: [{ uuid: "row-1", status: "updated", flashcard: makeFlashcard({ uuid: "row-1", version: 2, front: "one" }) }],
    })
    .mockResolvedValueOnce({
      results: [{ uuid: "row-1", status: "updated", flashcard: makeFlashcard({ uuid: "row-1", version: 3, front: "two" }) }],
    })

  render(<FlashcardDocumentRow card={makeFlashcard({ uuid: "row-1", version: 1 })} bulkUpdate={mutateAsync} />)

  await editFrontTwiceBeforeFirstRequestResolves()

  expect(mutateAsync).toHaveBeenCalledTimes(2)
  expect(mutateAsync.mock.calls[1][0][0].expected_version).toBe(2)
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx
```

Expected: FAIL because the row component and save-queue hook do not exist.

**Step 3: Write minimal implementation**

- Build row-level local state:
  - current row snapshot
  - dirty patch
  - queued patch
  - save status
  - validation/conflict/stale markers
- Serialize one in-flight save per row.
- Coalesce later edits into the next queued patch.
- Reuse template normalization rules from the drawer before saving.
- Start rows in read mode and enter edit mode on focus.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentRow.tsx apps/packages/ui/src/components/Flashcards/hooks/useFlashcardDocumentRowState.ts apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentView.tsx apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx
git commit -m "feat(flashcards): add inline document row editor"
```

### Task 7: Add Conflict Recovery, Row Undo, And Keyboard Support

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentView.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentRow.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-editing.test.tsx`

**Step 1: Write the failing test**

```tsx
it("offers reload and reapply actions when a row save conflicts", async () => {
  mockDocumentBulkUpdateConflict("row-1")
  renderManageTab({ initialMode: "document" })

  await triggerRowSaveConflict("row-1")

  expect(screen.getByTestId("flashcards-document-row-conflict-row-1")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: /reload row/i })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: /reapply my edit/i })).toBeInTheDocument()
})

it("restores a previous row snapshot when undo is triggered after inline save", async () => {
  renderManageTab({ initialMode: "document" })

  await saveDocumentRowEdit("row-1", { front: "Updated front" })
  fireEvent.click(screen.getByRole("button", { name: /undo/i }))

  await waitFor(() =>
    expect(mockDocumentBulkUpdate).toHaveBeenLastCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ uuid: "row-1", front: "Original front" }),
      ])
    )
  )
})

it("supports keyboard save and cancel in document mode", async () => {
  renderManageTab({ initialMode: "document" })

  focusDocumentRowField("row-1", "front")
  await user.keyboard("Edited text")
  await user.keyboard("{Meta>}{Enter}{/Meta}")

  expect(mockDocumentBulkUpdate).toHaveBeenCalled()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-editing.test.tsx
```

Expected: FAIL because document-mode recovery and keyboard behavior are not implemented.

**Step 3: Write minimal implementation**

- Add row-local conflict UI with:
  - reload row
  - reapply edit
- Reuse previous-row snapshots to implement inline undo.
- Add document-mode keyboard support for:
  - focus movement
  - selection toggle
  - edit activation
  - save
  - cancel
  - open drawer
- Ensure the drawer still opens correctly from document rows.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-editing.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentView.tsx apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentRow.tsx apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-editing.test.tsx
git commit -m "feat(flashcards): add document mode recovery and keyboard support"
```

### Task 8: Update User Guide And Final Regression Coverage

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx`
- Modify: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`

**Step 1: Write the failing test**

```tsx
it("still opens the edit drawer from manage after document mode is introduced", async () => {
  renderManageTab()
  fireEvent.click(screen.getByRole("button", { name: /edit/i }))
  expect(screen.getByText("Edit Flashcard")).toBeInTheDocument()
})
```

```python
def test_flashcards_single_patch_still_returns_updated_card(client_with_flashcards_db):
    card = create_test_flashcard(client_with_flashcards_db)

    response = client_with_flashcards_db.patch(
        f"/api/v1/flashcards/{card['uuid']}",
        json={"front": "Still works", "expected_version": card["version"]},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["front"] == "Still works"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "single_patch_still_returns_updated_card" -v
bunx vitest run apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx
```

Expected: If the new work introduced regressions, one or more tests fail and must be fixed before close-out.

**Step 3: Write minimal implementation**

- Update docs to describe:
  - `document` mode purpose
  - supported inline-edit fields
  - sort restrictions
  - truncation behavior
- Fix any regressions uncovered by existing `Manage` tests.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "single_patch_still_returns_updated_card" -v
bunx vitest run apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py
git commit -m "docs(flashcards): document manage document mode"
```

## Verification

Run all of the following from `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import`:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "bulk_patch or single_patch_still_returns_updated_card" -v
```

Expected: PASS for the new bulk-update coverage and existing single-card update regression coverage.

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards -v
```

Expected: PASS for the touched flashcards backend scope.

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.tsx apps/packages/ui/src/components/Flashcards/utils/__tests__/document-cache-policy.test.ts apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-mode.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.document-editing.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx
```

Expected: PASS for document-mode query, row, keyboard, undo, and regression coverage.

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -f json -o /tmp/bandit_flashcards_document_mode.json
```

Expected: no new high-signal findings in touched backend files.

```bash
git status --short
```

Expected: clean working tree after commits.
