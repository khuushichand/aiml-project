# Media Multi UX Batch 04 - Batch Operations, Metadata Management, and Lifecycle Actions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn Media Multi into a task-complete library surface by adding first-class batch tagging, delete/archive lifecycle actions, export, and reprocess workflows directly from multi-selection context.

**Architecture:** Introduce a dedicated batch-action toolbar that activates when `selectedIds.length > 0`, backed by typed API-client methods in `TldwApiClient`. Keep actions optimistic where safe (tag updates) and guarded with confirmations where destructive (trash/permanent delete), with consistent per-item outcome summaries.

**Tech Stack:** React, TypeScript, Ant Design Dropdown/Modal/Form, TldwApiClient, background proxy, Vitest + Testing Library, Playwright.

---

## Execution Status (2026-02-23)

- Task 1: Complete (batch/lifecycle API client tests added in `tldw-api-client.media-batch-actions.test.ts`).
- Task 2: Complete (`TldwApiClient` now exposes typed batch keyword, trash lifecycle, reprocess, and statistics helpers; OpenAPI guard path unions updated).
- Task 3: Complete (stage5 batch toolbar test suite added with selection visibility and bulk-tagging coverage).
- Task 4: Complete (Media Multi batch toolbar implemented with add-tags, trash, export, and reprocess actions).
- Task 5: Complete (stage5 export/trash-handoff tests added).
- Task 6: Complete (export format helpers + trash handoff CTA wiring implemented).
- Task 7: Complete (Playwright workflows added for literature triage + media audit batch actions).
- Task 8: Complete (2026-02-23 verification evidence):
  - `cd apps/packages/ui && bunx vitest run src/services/__tests__/tldw-api-client.media-batch-actions.test.ts src/components/Review/__tests__/MediaReviewPage.stage5.batch-toolbar.test.tsx src/components/Review/__tests__/MediaReviewPage.stage5.export-trash-handoff.test.tsx` (`11 passed`).
  - `cd apps/tldw-frontend && TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/workflows/media-review.spec.ts --grep "batch|trash|export|reprocess" --reporter=line` (`2 passed`).
  - `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Review apps/packages/ui/src/services/tldw apps/tldw-frontend/e2e -f json -o /tmp/bandit_media_multi_batch04.json` (`0 results`, `loc: 0`).

---

## Covered Findings

- UX-003, UX-015, UX-016, UX-022

---

### Task 1: Add Failing API Client Tests for Missing Batch/Lifecycle Methods

**Files:**
- Modify: `apps/packages/ui/src/services/__tests__/tldw-api-client.media-ingest.test.ts`
- Create: `apps/packages/ui/src/services/__tests__/tldw-api-client.media-batch-actions.test.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Step 1: Write failing tests**

```ts
it('calls bulk keyword update endpoint with mode and ids', async () => {
  await client.bulkUpdateMediaKeywords({ media_ids: [1, 2], keywords: ['ai'], mode: 'add' })
  expect(bgRequest).toHaveBeenCalledWith(expect.objectContaining({
    path: '/api/v1/media/bulk/keyword-update',
    method: 'POST'
  }))
})

it('calls reprocess endpoint for a media item', async () => {
  await client.reprocessMedia(7, { include_embeddings: true })
  expect(bgRequest).toHaveBeenCalledWith(expect.objectContaining({
    path: '/api/v1/media/7/reprocess',
    method: 'POST'
  }))
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/services/__tests__/tldw-api-client.media-batch-actions.test.ts
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/services/__tests__/tldw-api-client.media-batch-actions.test.ts apps/packages/ui/src/services/__tests__/tldw-api-client.media-ingest.test.ts
git commit -m "test(media-api): add failing tests for media batch and lifecycle methods"
```

---

### Task 2: Implement API Client Methods for Batch Operations

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/services/tldw/openapi-guard.ts`
- Test: `apps/packages/ui/src/services/__tests__/tldw-api-client.media-batch-actions.test.ts`

**Step 1: Add minimal methods**

```ts
async bulkUpdateMediaKeywords(payload: { media_ids: number[]; keywords: string[]; mode?: 'add' | 'remove' | 'set' }) { /* POST /bulk/keyword-update */ }
async deleteMedia(mediaId: string | number) { /* DELETE /api/v1/media/{id} */ }
async restoreMedia(mediaId: string | number) { /* POST /api/v1/media/{id}/restore */ }
async permanentlyDeleteMedia(mediaId: string | number) { /* DELETE /api/v1/media/{id}/permanently */ }
async reprocessMedia(mediaId: string | number, options?: Record<string, unknown>) { /* POST /reprocess */ }
async getMediaStatistics() { /* GET /api/v1/media/statistics */ }
```

**Step 2: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/services/__tests__/tldw-api-client.media-batch-actions.test.ts
```

Expected: PASS.

**Step 3: Commit**

```bash
git add apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/services/tldw/openapi-guard.ts apps/packages/ui/src/services/__tests__/tldw-api-client.media-batch-actions.test.ts
git commit -m "feat(media-api): add typed batch keyword/lifecycle/reprocess methods"
```

---

### Task 3: Add Failing UI Tests for Media Multi Batch Action Toolbar

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.batch-toolbar.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('shows batch toolbar when selection is non-empty', async () => {
  render(<MediaReviewPage />)
  selectN(3)
  expect(screen.getByTestId('media-multi-batch-toolbar')).toBeInTheDocument()
})

it('supports bulk add keywords and reports success summary', async () => {
  render(<MediaReviewPage />)
  selectN(2)
  await user.type(screen.getByRole('textbox', { name: /batch keywords/i }), 'urgent')
  await user.click(screen.getByRole('button', { name: /add tags/i }))
  expect(mockBulkKeywordUpdate).toHaveBeenCalled()
  expect(screen.getByText(/updated keywords for 2 item/i)).toBeInTheDocument()
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.batch-toolbar.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.batch-toolbar.test.tsx
git commit -m "test(media-multi): add failing tests for batch operations toolbar"
```

---

### Task 4: Implement Batch Toolbar in MediaReviewPage (Tag, Trash, Export, Reprocess)

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Create: `apps/packages/ui/src/components/Review/media-multi-batch-actions.ts`
- Modify: `apps/packages/ui/src/public/_locales/en/review.json`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.batch-toolbar.test.tsx`

**Step 1: Add toolbar UI and handlers**

- Actions:
  - `Add tags`
  - `Move to trash`
  - `Export`
  - `Reprocess`
- Show selected count and action-level loading states.

**Step 2: Use typed API methods for execution**

- Keyword update via bulk endpoint.
- Delete via soft delete endpoint.
- Reprocess via `/reprocess`.

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.batch-toolbar.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/media-multi-batch-actions.ts apps/packages/ui/src/public/_locales/en/review.json apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.batch-toolbar.test.tsx
git commit -m "feat(media-multi): add batch toolbar for tags, trash, export, and reprocess"
```

---

### Task 5: Add Failing Tests for Export and Trash Recovery Handoff

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.export-trash-handoff.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('exports selected items in json/markdown/text formats', async () => {
  render(<MediaReviewPage />)
  selectN(2)
  await user.selectOptions(screen.getByRole('combobox', { name: /export format/i }), 'markdown')
  await user.click(screen.getByRole('button', { name: /export selected/i }))
  expect(mockDownloadBlob).toHaveBeenCalled()
})

it('navigates to trash view after successful batch delete when user chooses review trash', async () => {
  render(<MediaReviewPage />)
  selectN(2)
  await user.click(screen.getByRole('button', { name: /move to trash/i }))
  await user.click(screen.getByRole('button', { name: /open trash/i }))
  expect(mockNavigate).toHaveBeenCalledWith('/media-trash')
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.export-trash-handoff.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.export-trash-handoff.test.tsx
git commit -m "test(media-multi): add failing tests for export and trash handoff"
```

---

### Task 6: Implement Export Flow and Trash Handoff/Recovery Messaging

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Modify: `apps/packages/ui/src/components/Review/mediaPermalink.ts`
- Modify: `apps/packages/ui/src/public/_locales/en/review.json`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.export-trash-handoff.test.tsx`

**Step 1: Implement export formats**

- JSON, Markdown, Text serializers for selected items.
- Use `downloadBlob` utility.

**Step 2: Add delete success actions**

- Toast with `Undo` where possible.
- Secondary CTA `Open trash`.

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.export-trash-handoff.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/mediaPermalink.ts apps/packages/ui/src/public/_locales/en/review.json apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.export-trash-handoff.test.tsx
git commit -m "feat(media-multi): add export formats and trash recovery handoff"
```

---

### Task 7: Add E2E Coverage for Literature Triage and Media Audit Completion Flows

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/media-review.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/MediaReviewPage.ts`

**Step 1: Add literature triage scenario**

- Filter by PDF.
- Select 10.
- Enter stack/review.
- Compare two.
- Start chat handoff.

**Step 2: Add media audit scenario**

- Sort by date.
- Select stale items.
- Batch move to trash.
- Open trash.

**Step 3: Run e2e subset**

Run:
```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "triage|audit|batch"
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/media-review.spec.ts apps/tldw-frontend/e2e/utils/page-objects/MediaReviewPage.ts
git commit -m "test(media-multi): add e2e workflows for triage and audit batch actions"
```

---

### Task 8: Final Verification for Batch 04

**Files:**
- Verify touched files only.

**Step 1: Run API + UI unit tests**

```bash
cd apps && bunx vitest run packages/ui/src/services/__tests__/tldw-api-client.media-batch-actions.test.ts packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.batch-toolbar.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.export-trash-handoff.test.tsx
```

Expected: PASS.

**Step 2: Run e2e subset**

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "batch|trash|export|reprocess"
```

Expected: PASS.

**Step 3: Final commit (if needed)**

```bash
git add <remaining files>
git commit -m "chore(media-multi): finalize batch 04 batch-operations verification"
```

---

## Implementation Notes

1. Keep destructive operations confirm-gated and summarize partial failures clearly.
2. Prefer existing typed client paths over ad hoc `bgRequest` calls in component handlers.
3. Use `@test-driven-development` and `@verification-before-completion` during execution.
