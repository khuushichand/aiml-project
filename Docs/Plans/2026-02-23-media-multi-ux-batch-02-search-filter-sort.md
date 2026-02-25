# Media Multi UX Batch 02 - Search, Filter, and Sort Clarity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make search/filter behavior predictable and complete by surfacing sort/date controls, clarifying full-content search cost, and improving filter-state visibility and control.

**Architecture:** Reuse existing search payload patterns from `mediaSearchRequest.ts` and add equivalent controls in `MediaReviewPage` without changing endpoint contracts. Treat content-search as an explicit expensive mode with cancellable progress and transparent status messaging.

**Tech Stack:** React, TypeScript, Ant Design Select/DatePicker, TanStack Query, i18n, Vitest + Testing Library, Playwright.

---

## Execution Status (2026-02-23)

- Task 1: Complete (stage3 harness now validates sort control and date-range group rendering).
- Task 2: Complete (sort/date state and payload wiring added through `buildMediaSearchPayload` with search/list endpoint parity).
- Task 3: Complete (full-content search relabeled as explicit slow mode with scope copy).
- Task 4: Complete (content filtering progress state, live status copy, and cancellation action implemented).
- Task 5: Complete (collapsed-state filter chips are now removable with keyboard-accessible controls).
- Task 6: Complete (keyword suggestion ranking helper implemented and unit-tested).
- Task 7: Complete (Playwright scenarios added for sort/date payload wiring and content-search progress visibility).
- Task 8: Complete (targeted Vitest + Playwright slices and Bandit run are green).

---

## Covered Findings

- UX-002, UX-009, UX-010, UX-011

---

### Task 1: Add Failing Tests for Sort and Date Range Controls

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.sort-date-controls.test.tsx`
- Reference: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('renders sort control and date range filter in media multi header', async () => {
  render(<MediaReviewPage />)
  expect(screen.getByRole('combobox', { name: /sort/i })).toBeInTheDocument()
  expect(screen.getByLabelText(/date range/i)).toBeInTheDocument()
})

it('sends selected sort/date filters in list/search requests', async () => {
  render(<MediaReviewPage />)
  await user.selectOptions(screen.getByRole('combobox', { name: /sort/i }), 'date_desc')
  await setDateRange('2025-01-01', '2025-01-31')
  await user.click(screen.getByRole('button', { name: /search/i }))

  expect(lastSearchPayload()).toMatchObject({ sort_by: 'date_desc' })
  expect(lastSearchPayload().date_range).toBeTruthy()
})
```

**Step 2: Run tests to verify failure**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.sort-date-controls.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.sort-date-controls.test.tsx
git commit -m "test(media-multi): add failing tests for sort and date range controls"
```

---

### Task 2: Implement Sort + Date Range Controls and Payload Wiring

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Reference: `apps/packages/ui/src/components/Review/mediaSearchRequest.ts`
- Modify: `apps/packages/ui/src/public/_locales/en/review.json`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.sort-date-controls.test.tsx`

**Step 1: Add minimal implementation**

```ts
const [sortBy, setSortBy] = React.useState<MediaSortBy>('relevance')
const [dateRange, setDateRange] = React.useState<MediaDateRange>({ startDate: null, endDate: null })

// in search payload
if (sortBy !== 'relevance') body.sort_by = sortBy
if (dateRange.startDate || dateRange.endDate) body.date_range = { start: dateRange.startDate, end: dateRange.endDate }
```

**Step 2: Add UI controls in filter section**

- Sort dropdown with `relevance`, `date_desc`, `date_asc`, `title_asc`, `title_desc`.
- Date range picker with clear support.
- Include these fields in active filter count.

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.sort-date-controls.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/public/_locales/en/review.json apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.sort-date-controls.test.tsx
git commit -m "feat(media-multi): add sort and date-range filtering controls"
```

---

### Task 3: Add Failing Tests for Full-Content Search Status and Cost Transparency

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.content-search-status.test.tsx`
- Reference: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('labels content search as slower and scoped to currently loaded results', async () => {
  render(<MediaReviewPage />)
  expect(screen.getByText(/search full content \(slower\)/i)).toBeInTheDocument()
  expect(screen.getByText(/current page results/i)).toBeInTheDocument()
})

it('shows progress while content fetch filtering runs', async () => {
  render(<MediaReviewPage />)
  await user.click(screen.getByRole('checkbox', { name: /search full content/i }))
  expect(screen.getByRole('status', { name: /content filtering progress/i })).toBeInTheDocument()
})
```

**Step 2: Run tests to verify failure**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.content-search-status.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.content-search-status.test.tsx
git commit -m "test(media-multi): add failing tests for content-search transparency"
```

---

### Task 4: Implement Content-Search Progress, Scope Copy, and Cancellation

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Create: `apps/packages/ui/src/components/Review/content-filtering-progress.ts`
- Modify: `apps/packages/ui/src/public/_locales/en/review.json`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.content-search-status.test.tsx`

**Step 1: Add progress state helper**

```ts
export type ContentFilterProgress = { completed: number; total: number; running: boolean }
export const toProgressLabel = ({ completed, total }: ContentFilterProgress) => `${completed}/${total}`
```

**Step 2: Wire progress + cancellation in page logic**

- Track per-run request token.
- Update progress as detail requests complete.
- Ignore stale run results.
- Render explicit status copy near toggle.

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.content-search-status.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/content-filtering-progress.ts apps/packages/ui/src/public/_locales/en/review.json apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.content-search-status.test.tsx
git commit -m "feat(media-multi): add explicit full-content search progress and scoped copy"
```

---

### Task 5: Add Failing Tests for Collapsed Filter Chip Removal

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.collapsed-filter-chips.test.tsx`
- Reference: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('shows removable filter chips when filters are collapsed', async () => {
  render(<MediaReviewPage />)
  applyFilters({ types: ['pdf'], keywords: ['research'] })
  collapseFilters()

  expect(screen.getByRole('button', { name: /remove filter pdf/i })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /remove filter pdf/i }))
  expect(activeTypeFilters()).toEqual([])
})
```

**Step 2: Run test (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.collapsed-filter-chips.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing test**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.collapsed-filter-chips.test.tsx
git commit -m "test(media-multi): add failing tests for collapsed filter chip removal"
```

---

### Task 6: Implement Collapsed Filter Chips and Keyword Suggestion Prioritization

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Create: `apps/packages/ui/src/components/Review/filter-chip-priority.ts`
- Create: `apps/packages/ui/src/components/Review/__tests__/filter-chip-priority.test.ts`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.collapsed-filter-chips.test.tsx`

**Step 1: Implement chip UI actions in collapsed state**

- Render chips for active media-type and keyword filters.
- Each chip must have keyboard-accessible remove button.
- Keep existing badge count.

**Step 2: Add keyword prioritization helper**

```ts
export function rankKeywordSuggestions(keywords: string[], query: string): string[] {
  // startsWith > contains > alphabetical
}
```

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.collapsed-filter-chips.test.tsx packages/ui/src/components/Review/__tests__/filter-chip-priority.test.ts
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/filter-chip-priority.ts apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.collapsed-filter-chips.test.tsx apps/packages/ui/src/components/Review/__tests__/filter-chip-priority.test.ts
git commit -m "feat(media-multi): add collapsed filter chips and ranked keyword suggestions"
```

---

### Task 7: E2E Coverage for Sort/Date and Content Search Progress

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/media-review.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/MediaReviewPage.ts`

**Step 1: Add two e2e scenarios**

- Sort/date controls change result order deterministically (using mocked fixture ordering).
- Content-search mode displays progress state and returns filtered items.

**Step 2: Run e2e subset**

Run:
```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "sort|date|content search"
```

Expected: PASS.

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/media-review.spec.ts apps/tldw-frontend/e2e/utils/page-objects/MediaReviewPage.ts
git commit -m "test(media-multi): add e2e coverage for sort/date and content-search status"
```

---

### Task 8: Final Verification for Batch 02

**Files:**
- Verify touched files only.

**Step 1: Run targeted unit tests**

```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.sort-date-controls.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.content-search-status.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.collapsed-filter-chips.test.tsx packages/ui/src/components/Review/__tests__/filter-chip-priority.test.ts
```

Expected: PASS.

**Step 2: Run relevant e2e subset**

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "sort|filter|search"
```

Expected: PASS.

**Step 3: Final commit (if needed)**

```bash
git add <remaining files>
git commit -m "chore(media-multi): finalize batch 02 search/filter/sort verification"
```

---

## Implementation Notes

1. Keep server contracts unchanged; only extend request payload usage for fields already supported by backend.
2. Maintain fast default path; expensive content search must remain opt-in and clearly communicated.
3. Use `@test-driven-development` and `@verification-before-completion` during execution.
