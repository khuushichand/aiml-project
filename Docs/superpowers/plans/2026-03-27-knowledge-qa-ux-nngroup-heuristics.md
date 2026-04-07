# Knowledge QA UX Improvements (NN/g Heuristics) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the Knowledge QA page UX by replacing ML jargon with research-literate language, adding progressive disclosure to the evidence panel, providing recovery guidance for low-quality results, and simplifying source card actions.

**Architecture:** All changes are within existing React components — no new state management, no routing changes, no API changes. The work touches label strings, conditional rendering, one new banner component, and source card action restructuring.

**Tech Stack:** React, TypeScript, TailwindCSS, Ant Design 6.2, Lucide React icons, Vitest

---

## Task 1: Jargon — Relevance Descriptor Labels

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/sourceListUtils.ts:250-277`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/sourceListUtils.ts:279-303`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/sourceListUtils.test.ts`

**Step 1: Update test expectations for relevance labels**

In `sourceListUtils.test.ts`, find assertions for `getRelevanceDescriptor` and update expected labels:
- `"High match"` → `"Strong relevance"`
- `"Moderate match"` → `"Moderate relevance"`
- `"Low match"` → `"Weak relevance"`

If no label assertions exist, add them:

```ts
it("returns Strong relevance for high scores", () => {
  const result = getRelevanceDescriptor(0.85)
  expect(result?.label).toBe("Strong relevance")
  expect(result?.level).toBe("high")
})

it("returns Moderate relevance for mid scores", () => {
  const result = getRelevanceDescriptor(0.6)
  expect(result?.label).toBe("Moderate relevance")
  expect(result?.level).toBe("moderate")
})

it("returns Weak relevance for low scores", () => {
  const result = getRelevanceDescriptor(0.2)
  expect(result?.label).toBe("Weak relevance")
  expect(result?.level).toBe("low")
})
```

**Step 2: Update test expectations for chunk position labels**

In the same test file, update `formatChunkPosition` assertions:
- `"Chunk 3 of 12"` → `"Section 3 of 12"`
- `"Chunk 4 of 20"` → `"Section 4 of 20"`
- `"Chunk 7"` → `"Section 7"`
- `"Chunk 128"` → `"Section 128"`

**Step 3: Run tests to verify they fail**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/sourceListUtils.test.ts`
Expected: FAIL — old labels still in source

**Step 4: Update `getRelevanceDescriptor` labels in source**

In `sourceListUtils.ts` lines 250-277, change:
- Line 259: `label: "High match"` → `label: "Strong relevance"`
- Line 267: `label: "Moderate match"` → `label: "Moderate relevance"`
- Line 274: `label: "Low match"` → `label: "Weak relevance"`

**Step 5: Update `formatChunkPosition` labels in source**

In `sourceListUtils.ts` lines 279-303, change all occurrences of `"Chunk"` to `"Section"`:
- Line 285: `` return `Chunk ${slashPattern[1]} of ${slashPattern[2]}` `` → `` return `Section ${slashPattern[1]} of ${slashPattern[2]}` ``
- Line 293: `` return `Chunk ${chunkPattern[1]} of ${chunkPattern[2]}` `` → `` return `Section ${chunkPattern[1]} of ${chunkPattern[2]}` ``
- Line 295: `` return `Chunk ${chunkPattern[1]}` `` → `` return `Section ${chunkPattern[1]}` ``
- Line 299: `` return `Chunk ${normalized}` `` → `` return `Section ${normalized}` ``

**Step 6: Run tests to verify they pass**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/sourceListUtils.test.ts`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/sourceListUtils.ts apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/sourceListUtils.test.ts
git commit -m "feat(knowledge-qa): replace ML jargon in relevance and chunk labels

Replace 'High/Moderate/Low match' with 'Strong/Moderate/Weak relevance'
and 'Chunk N' with 'Section N' for research-literate audience."
```

---

## Task 2: Jargon — AnswerPanel Badges (Grounding, Verified, Verification Report)

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx:108-126, 194-197, 559, 566-594`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`

**Step 1: Update test expectations**

In `AnswerPanel.states.test.tsx`:
- Line 187: `"Grounding: 50% cited"` → `"50% of answer cites sources"`
- Line 205: `"Verified: High"` → `"Source support: Strong"`
- Line 206 (the verification report test): `"Verification report (3 claims)"` → `"Claim check (3 claims)"`
- Line 220-221: `"Verified: Medium"` → `"Source support: Partial"` and `"Verification report"` → `"Claim check"`

**Step 2: Run tests to verify they fail**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`
Expected: FAIL

**Step 3: Update `describeFaithfulness` labels**

In `AnswerPanel.tsx` lines 108-126, change the return objects:
```ts
function describeFaithfulness(score: number | null): TrustDescriptor | null {
  if (score == null || Number.isNaN(score)) return null
  if (score >= 0.85) {
    return {
      label: "Strong",
      className: "border-success/40 bg-success/15 text-success",
    }
  }
  if (score >= 0.6) {
    return {
      label: "Partial",
      className: "border-warn/40 bg-warn/15 text-warn",
    }
  }
  return {
    label: "Weak",
    className: "border-danger/40 bg-danger/15 text-danger",
  }
}
```

**Step 4: Update trust score label**

In `AnswerPanel.tsx` lines 195-197, change:
```ts
const trustScoreLabel = searchDetails?.faithfulnessScore != null
  ? "How well claims are backed by sources"
  : "How well claims are backed by sources"
```

**Step 5: Update the "Open in Workspace" button text**

In `AnswerPanel.tsx` line 559, change:
```ts
{workspaceHandoffPending ? "Opening..." : "Continue in editor"}
```

**Step 6: Update grounding badge rendering**

In `AnswerPanel.tsx` lines 566-573, replace the grounding badge block:

```tsx
{groundingCoverage ? (
  groundingCoverage.percent === 0 && normalizedAnswer ? (
    <span
      className="inline-flex items-center rounded-md border border-warn/30 bg-warn/10 px-2 py-0.5 text-xs text-warn"
      title="The generated answer does not include inline source citations."
    >
      Answer may not be based on your sources
    </span>
  ) : groundingCoverage.percent > 0 ? (
    <span
      className="inline-flex items-center rounded-md border border-border bg-surface px-2 py-0.5 text-xs text-text-muted"
      title={`${groundingCoverage.citedSentences}/${groundingCoverage.totalSentences} answer sentences include citations.`}
    >
      {groundingCoverage.percent}% of answer cites sources
    </span>
  ) : null
) : null}
```

**Step 7: Update "Verified" badge text**

In `AnswerPanel.tsx` line 582, change:
```tsx
Verified: {faithfulnessDescriptor.label}
```
to:
```tsx
Source support: {faithfulnessDescriptor.label}
```

**Step 8: Update verification report badge**

In `AnswerPanel.tsx` lines 590-593, change:
```tsx
Verification report
{searchDetails.verificationTotalClaims != null
  ? ` (${searchDetails.verificationTotalClaims} claims)`
  : ""}
```
to:
```tsx
Claim check
{searchDetails.verificationTotalClaims != null
  ? ` (${searchDetails.verificationTotalClaims} claims)`
  : ""}
```

Also update the title attribute on line 588:
```tsx
title="Structured claim check report is available for this answer."
```

**Step 9: Run tests to verify they pass**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`
Expected: PASS

**Step 10: Update workspace-handoff test**

In `AnswerPanel.workspace-handoff.test.tsx` line 74, change:
```ts
fireEvent.click(screen.getByRole("button", { name: "Continue in editor" }))
```

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.workspace-handoff.test.tsx`
Expected: PASS

**Step 11: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.workspace-handoff.test.tsx
git commit -m "feat(knowledge-qa): replace jargon in answer panel badges

- 'Grounding: N% cited' → contextual: shows warning at 0%, neutral at >0%
- 'Verified: High/Medium/Low' → 'Source support: Strong/Partial/Weak'
- 'Verification report' → 'Claim check'
- 'Open in Workspace' → 'Continue in editor'
- 'Faithfulness' tooltip → plain language"
```

---

## Task 3: Jargon — AnswerWorkspace Stage Copy

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/panels/AnswerWorkspace.tsx:15-30`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerWorkspace.a11y.test.tsx`

**Step 1: Check existing test expectations for stage copy**

Read `AnswerWorkspace.a11y.test.tsx` and look for assertions on `"Verifying"` or `"Ranking"` stage text.

**Step 2: Update stage copy strings**

In `AnswerWorkspace.tsx` lines 15-30:

```ts
const STAGE_COPY: Record<QueryStage, string> = {
  idle: "Ready to search",
  searching: "Searching selected sources",
  ranking: "Ranking best evidence",
  generating: "Generating answer",
  verifying: "Checking source citations",
  complete: "Answer complete",
  error: "Search needs attention",
}

const LIVE_STAGE_COPY: Partial<Record<QueryStage, string>> = {
  searching: "Searching your selected sources.",
  ranking: "Ranking retrieved sources.",
  generating: "Generating answer.",
  verifying: "Checking source citations.",
}
```

Changes: `verifying` stage text in both maps.

**Step 3: Run tests**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerWorkspace.a11y.test.tsx`
Expected: PASS (or update any assertions that match old text)

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/panels/AnswerWorkspace.tsx
git commit -m "feat(knowledge-qa): replace 'Verifying answer grounding' with plain language"
```

---

## Task 4: Conversation Thread Cleanup — Hide on First Question

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/ConversationThread.tsx:450-452, 503, 526`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/panels/AnswerWorkspace.tsx:100`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/ConversationThread.test.tsx`

**Step 1: Check ConversationThread test expectations**

Read `ConversationThread.test.tsx` to understand what guards and rendering behavior the tests assert on. Pay attention to tests that check the component renders with `hasComparisonWorkspace` but zero historical turns.

**Step 2: Update ConversationThread guard**

In `ConversationThread.tsx` line 450-452, change:
```ts
if (!hasComparisonWorkspace && historicalTurns.length === 0) {
  return null
}
```
to:
```ts
if (historicalTurns.length === 0) {
  return null
}
```

**Step 3: Update ConversationThread labels**

In `ConversationThread.tsx`:
- Line 503: Change `"Start Branch"` to `"Ask a different follow-up"` (and the `"Creating branch..."` fallback stays)
- Line 526: Change `"Comparison workspace"` to `"Compare answers"`

**Step 4: Update AnswerWorkspace context box guard**

In `AnswerWorkspace.tsx` line 100, change:
```ts
const hasThreadContext = Boolean(currentThreadId) || displayedTurnCount > 0
```
to:
```ts
const hasThreadContext = displayedTurnCount > 1
```

**Step 5: Update ConversationThread tests**

In `ConversationThread.test.tsx`:
- Line 176: `{ name: "Start Branch" }` → `{ name: "Ask a different follow-up" }`
- Line 225: `{ name: "Start Branch" }` → `{ name: "Ask a different follow-up" }`
- Update any tests that assert the component renders with 0 historical turns

**Step 6: Run tests**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/ConversationThread.test.tsx`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/ConversationThread.tsx apps/packages/ui/src/components/Option/KnowledgeQA/panels/AnswerWorkspace.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/ConversationThread.test.tsx
git commit -m "feat(knowledge-qa): hide conversation thread on first question

- Don't render ConversationThread when historicalTurns is empty
- Hide 'Conversation - 1 turn' context box on first question
- Rename 'Start Branch' → 'Ask a different follow-up'
- Rename 'Comparison workspace' → 'Compare answers'"
```

---

## Task 5: Evidence Panel — Adaptive Source List Density

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SourceList.tsx:724-846`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx`

**Step 1: Add density tests**

In `SourceList.behavior.test.tsx`, add tests:

```tsx
it("hides filter controls when 1-3 sources (compact density)", () => {
  // Render with provider mocked to return 2 results
  // Assert date filter select is NOT in the document
  // Assert keyword filter input is NOT in the document
  // Assert source type filter buttons are NOT in the document
  // Assert "Show filters" button IS in the document
})

it("shows filters after clicking Show filters in compact mode", () => {
  // Render with 2 results
  // Click "Show filters"
  // Assert filter controls now visible
})

it("shows sort and keyword filter for 4-9 sources (default density)", () => {
  // Render with 6 results
  // Assert sort select IS visible
  // Assert keyword filter IS visible
  // Assert date filter IS hidden (behind "More filters")
})

it("shows all filters for 10+ sources (full density)", () => {
  // Render with 12 results
  // Assert all filter controls visible
})
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx`
Expected: FAIL

**Step 3: Implement density logic in SourceList**

In `SourceList.tsx`, after the `results.length === 0` guard at line 724-726, add:

```tsx
const [showFiltersOverride, setShowFiltersOverride] = useState(false)
const density = results.length <= 3 ? "compact" : results.length <= 9 ? "default" : "full"
const showFilters = density === "full" || showFiltersOverride
const showExtendedFilters = density === "full" || (showFiltersOverride && density !== "full")
```

Then wrap the filter sections:

**Header filters (lines 742-804):** Wrap in `{(density !== "compact" || showFilters) && (...)}`

Inside the header, for the date filter specifically (lines 746-756): Wrap in `{(density === "full" || showExtendedFilters) && (...)}`

**Source type filters (lines 808-826):** Wrap in `{showExtendedFilters && (...)}`

**Content facet filters (lines 828-846):** Wrap in `{showExtendedFilters && (...)}`

After the header `</div>` at line 805, add a compact/default filter toggle:

```tsx
{density !== "full" && !showFilters && (
  <button
    type="button"
    onClick={() => setShowFiltersOverride(true)}
    className="text-xs font-medium text-primary hover:text-primaryStrong transition-colors"
  >
    Show filters
  </button>
)}
{density !== "full" && showFilters && (
  <button
    type="button"
    onClick={() => setShowFiltersOverride(false)}
    className="text-xs font-medium text-text-muted hover:text-text transition-colors"
  >
    Hide filters
  </button>
)}
```

**Step 4: Run tests to verify they pass**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx`
Expected: PASS

**Step 5: Run full SourceList test suite**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.accessibility.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.feedback.test.tsx`
Expected: PASS (may need to update tests that assume filters always visible)

**Step 6: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/SourceList.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx
git commit -m "feat(knowledge-qa): adaptive source list density by result count

Compact (1-3): hide all filters, show toggle
Default (4-9): sort + keyword only, rest behind toggle
Full (10+): all filters as before"
```

---

## Task 6: Evidence Rail — Auto-Open Threshold + Source Count Badge

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx:226-246`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/evidence/EvidenceRail.tsx:119-140`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQALayout.behavior.test.tsx`

**Step 1: Read existing layout behavior tests**

Read `KnowledgeQALayout.behavior.test.tsx` to understand how the auto-open behavior is currently tested.

**Step 2: Add auto-open threshold test**

```tsx
it("does not auto-open evidence rail for 1-2 sources", () => {
  // Render with provider mocked: results = [oneSource], queryStage = "complete"
  // Assert evidence rail is NOT open (or collapsed state visible)
})

it("auto-opens evidence rail for 3+ sources", () => {
  // Render with 3+ results, queryStage = "complete"
  // Assert evidence rail is open
})
```

**Step 3: Run tests to verify they fail**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQALayout.behavior.test.tsx`

**Step 4: Update auto-open logic**

In `KnowledgeQALayout.tsx` lines 226-235, change the effect:

```tsx
useEffect(() => {
  const resultsCount = results?.length ?? 0
  if (
    hasResults &&
    resultsCount >= 3 &&
    queryStage !== "searching" &&
    !settingsPanelOpen &&
    !evidenceRailOpen &&
    !userClosedRailRef.current
  ) {
    setEvidenceRailOpen(true)
  }
  if (!hasResults) {
    userClosedRailRef.current = false
    return
  }
}, [
  evidenceRailOpen,
  hasResults,
  queryStage,
  results?.length,
  setEvidenceRailOpen,
  settingsPanelOpen,
])
```

**Step 5: Add source count badge to collapsed rail button**

In `EvidenceRail.tsx` lines 129-138, add a `resultsCount` badge when collapsed:

```tsx
<button
  type="button"
  onClick={() => onOpenChange(true)}
  className="relative rounded-md border border-border bg-surface p-2 text-text-subtle hover:bg-hover hover:text-text transition-colors"
  aria-label={`Open evidence panel (${resultsCount} sources)`}
  aria-expanded={false}
  aria-controls="knowledge-evidence-panel"
>
  <PanelRightOpen className="h-4 w-4" />
  {resultsCount > 0 && (
    <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-white">
      {resultsCount}
    </span>
  )}
</button>
```

**Step 6: Run tests**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQALayout.behavior.test.tsx`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx apps/packages/ui/src/components/Option/KnowledgeQA/evidence/EvidenceRail.tsx
git commit -m "feat(knowledge-qa): progressive evidence rail — collapse for few sources

- Auto-open only when 3+ sources (was: any results)
- Show source count badge on collapsed rail button"
```

---

## Task 7: Low-Quality Recovery Banner

**Files:**
- Create: `apps/packages/ui/src/components/Option/KnowledgeQA/panels/LowQualityRecoveryBanner.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/panels/AnswerWorkspace.tsx`
- Create: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/LowQualityRecoveryBanner.test.tsx`

**Step 1: Write the banner test**

Create `__tests__/LowQualityRecoveryBanner.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react"
import { LowQualityRecoveryBanner } from "../panels/LowQualityRecoveryBanner"

describe("LowQualityRecoveryBanner", () => {
  const defaultProps = {
    onRefine: vi.fn(),
    onEnableWeb: vi.fn(),
    onSelectSources: vi.fn(),
    onDismiss: vi.fn(),
  }

  it("renders the recovery message", () => {
    render(<LowQualityRecoveryBanner {...defaultProps} />)
    expect(
      screen.getByText(/sources may not closely match/i)
    ).toBeInTheDocument()
  })

  it("calls onEnableWeb when web button clicked", () => {
    render(<LowQualityRecoveryBanner {...defaultProps} />)
    fireEvent.click(screen.getByRole("button", { name: /include web/i }))
    expect(defaultProps.onEnableWeb).toHaveBeenCalled()
  })

  it("calls onDismiss when close button clicked", () => {
    render(<LowQualityRecoveryBanner {...defaultProps} />)
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }))
    expect(defaultProps.onDismiss).toHaveBeenCalled()
  })

  it("calls onSelectSources when link clicked", () => {
    render(<LowQualityRecoveryBanner {...defaultProps} />)
    fireEvent.click(screen.getByRole("button", { name: /select different/i }))
    expect(defaultProps.onSelectSources).toHaveBeenCalled()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/LowQualityRecoveryBanner.test.tsx`
Expected: FAIL (module not found)

**Step 3: Implement the banner component**

Create `panels/LowQualityRecoveryBanner.tsx`:

```tsx
import React from "react"
import { Lightbulb, X, Globe, Search, Layers } from "lucide-react"

type LowQualityRecoveryBannerProps = {
  onRefine: () => void
  onEnableWeb: () => void
  onSelectSources: () => void
  onDismiss: () => void
}

export function LowQualityRecoveryBanner({
  onRefine,
  onEnableWeb,
  onSelectSources,
  onDismiss,
}: LowQualityRecoveryBannerProps) {
  return (
    <div
      className="rounded-lg border border-warn/20 bg-warn/5 p-3"
      role="status"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
          <div className="space-y-2">
            <p className="text-sm text-text">
              These sources may not closely match your question.
            </p>
            <p className="text-xs text-text-muted">Try refining your search:</p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onRefine}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text-subtle hover:bg-hover hover:text-text transition-colors"
                aria-label="Use more specific terms"
              >
                <Search className="h-3 w-3" />
                Use more specific terms
              </button>
              <button
                type="button"
                onClick={onEnableWeb}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text-subtle hover:bg-hover hover:text-text transition-colors"
                aria-label="Include web sources"
              >
                <Globe className="h-3 w-3" />
                Include web sources
              </button>
              <button
                type="button"
                onClick={onSelectSources}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text-subtle hover:bg-hover hover:text-text transition-colors"
                aria-label="Select different sources"
              >
                <Layers className="h-3 w-3" />
                Select different sources
              </button>
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-md p-1 text-text-muted hover:bg-hover hover:text-text transition-colors"
          aria-label="Dismiss recovery suggestions"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/LowQualityRecoveryBanner.test.tsx`
Expected: PASS

**Step 5: Integrate banner into AnswerWorkspace**

In `AnswerWorkspace.tsx`, add imports and integration:

Add imports at top:
```ts
import { LowQualityRecoveryBanner } from "./LowQualityRecoveryBanner"
```

Add state and computed value inside the component function (after line 100):
```ts
const [recoveryDismissed, setRecoveryDismissed] = useState(false)

const isLowQualityResult = useMemo(() => {
  if (queryStage !== "complete") return false
  if (results.length === 0) return false
  const allLowRelevance = results.every(
    (r: { score?: number }) => (r.score ?? 0) < (settings?.strip_min_relevance ?? 0.3)
  )
  const noCitations = (citations?.length ?? 0) === 0
  return allLowRelevance || (noCitations && results.length > 0)
}, [queryStage, results, citations, settings?.strip_min_relevance])
```

Note: `settings` and `citations` must be destructured from `useKnowledgeQA()` at line 45-46. Add them:
```ts
const { results = [], error = null, messages = [], currentThreadId = null, citations = [], settings } =
  useKnowledgeQA()
```

Reset `recoveryDismissed` when a new search happens (add effect):
```ts
useEffect(() => {
  if (queryStage === "searching") {
    setRecoveryDismissed(false)
  }
}, [queryStage])
```

Then in the JSX between `<AnswerPanel />` and `<FollowUpInput />` (lines 197-198):

```tsx
<AnswerPanel />
{isLowQualityResult && !recoveryDismissed && (
  <LowQualityRecoveryBanner
    onRefine={() => {
      // Focus the search/follow-up input
      const input = document.getElementById("knowledge-search-input")
      input?.focus()
    }}
    onEnableWeb={() => {
      // Toggle web fallback via context
      // This requires access to updateSetting from useKnowledgeQA
    }}
    onSelectSources={() => {
      // Open settings panel to sources section
      setSettingsPanelOpen?.(true)
    }}
    onDismiss={() => setRecoveryDismissed(true)}
  />
)}
<FollowUpInput />
```

Note: `setSettingsPanelOpen` is available from `useKnowledgeQA()`. The `onEnableWeb` handler needs `updateSetting` which should also be destructured from context. Check the provider for the correct function name and wire it up.

**Step 6: Run full workspace tests**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerWorkspace.a11y.test.tsx`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/panels/LowQualityRecoveryBanner.tsx apps/packages/ui/src/components/Option/KnowledgeQA/panels/AnswerWorkspace.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/LowQualityRecoveryBanner.test.tsx
git commit -m "feat(knowledge-qa): low-quality result recovery banner

Shows suggestions (refine query, enable web, change sources)
when all sources score below strip_min_relevance threshold or
answer has zero citations. Dismissable per search session."
```

---

## Task 8: Source Card Action Simplification

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SourceCard.tsx:395-540`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SourceCard.behavior.test.tsx`

**Step 1: Read existing SourceCard tests**

Read `SourceCard.behavior.test.tsx` to understand which actions are tested by button name.

**Step 2: Update test expectations**

Tests that click buttons by name will need updating:
- `"View full"` → `"View"`
- `"Copy citation"` → `"Cite"`
- Actions now behind overflow menu need different test approach (open menu first, then click)

Add new tests:
```tsx
it("shows overflow menu with secondary actions", () => {
  render(<SourceCard {...defaultProps} />)
  fireEvent.click(screen.getByRole("button", { name: /more actions/i }))
  expect(screen.getByText("Pin")).toBeInTheDocument()
  expect(screen.getByText("Copy text")).toBeInTheDocument()
})

it("shows feedback on hover", () => {
  render(<SourceCard {...defaultProps} />)
  // Feedback section should have opacity-0 by default
  // and become visible on group-hover (tested via class check)
})
```

**Step 3: Restructure SourceCard actions**

In `SourceCard.tsx` lines 395-540, replace with primary/secondary split.

Add import at top: `import { Dropdown } from "antd"` and `import { MoreHorizontal } from "lucide-react"`

Replace the action section (lines 396-495) with:

```tsx
{/* Actions — primary/secondary split */}
<div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/50 bg-bg-subtle px-3 py-2 sm:px-4">
  <div className="flex items-center gap-1">
    <button
      type="button"
      onClick={() => onViewFull(result, index)}
      className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md border border-border bg-surface text-text-subtle hover:bg-hover hover:text-text transition-colors"
      title="View the full source content"
      aria-label={`View source ${index}`}
    >
      <FileText className="w-3.5 h-3.5" />
      View
    </button>

    <button
      type="button"
      onClick={handleCopyCitation}
      className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md border border-border bg-surface text-text-subtle hover:bg-hover hover:text-text transition-colors"
      title="Copy citation"
    >
      {copiedState === "citation" ? "Copied!" : "Cite"}
    </button>

    <Dropdown
      menu={{
        items: [
          {
            key: "pin",
            label: isPinned ? "Unpin" : "Pin",
            onClick: () => onTogglePin(result, index),
          },
          {
            key: "ask-detail",
            label: "Ask: Tell me more",
            onClick: () => onAskAbout(result, "detail"),
          },
          {
            key: "ask-summary",
            label: "Ask: Summarize",
            onClick: () => onAskAbout(result, "summary"),
          },
          {
            key: "ask-quotes",
            label: "Ask: Key quotes",
            onClick: () => onAskAbout(result, "quotes"),
          },
          {
            key: "copy-text",
            label: copiedState === "text" ? "Copied text" : "Copy text",
            onClick: handleCopyText,
          },
          ...(url
            ? [
                {
                  key: "open",
                  label: "Open original",
                  onClick: handleOpenExternal,
                },
              ]
            : []),
        ],
      }}
      trigger={["click"]}
      placement="bottomRight"
    >
      <button
        type="button"
        className="flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium rounded-md border border-border bg-surface text-text-subtle hover:bg-hover hover:text-text transition-colors"
        aria-label={`More actions for source ${index}`}
      >
        <MoreHorizontal className="w-3.5 h-3.5" />
      </button>
    </Dropdown>
  </div>
</div>
```

Replace the feedback section (lines 497-540) to add group-hover visibility:

```tsx
<div className="flex flex-wrap items-center gap-2 px-4 py-2 border-t border-border/50 text-xs opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
  <span className="text-text-muted">Relevant?</span>
  {/* ... existing thumbs up/down buttons unchanged ... */}
</div>
```

Ensure the root `<div>` of SourceCard has `className="group ..."` (add `group` to existing classes).

**Step 4: Remove the `askTemplate` state**

The `askTemplate` state and its `<select>` are no longer needed since templates are now in the overflow menu. Remove:
```ts
const [askTemplate, setAskTemplate] = useState<SourceAskTemplate>("detail")
```

**Step 5: Run tests**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/SourceCard.behavior.test.tsx`
Expected: PASS (after test updates from Step 2)

**Step 6: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/SourceCard.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SourceCard.behavior.test.tsx
git commit -m "feat(knowledge-qa): simplify source card actions

Primary actions: View + Cite (always visible)
Secondary actions: Pin, Ask variants, Copy text, Open (in overflow menu)
Feedback row: visible on hover/focus only"
```

---

## Task 9: Final Integration Test + Settings Threshold

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SettingsPanel/ExpertSettings.tsx`

**Step 1: Add relevance threshold control to Expert Settings**

In `ExpertSettings.tsx`, find the section for `strip_min_relevance` (search for `"strip_min_relevance"`). It should already exist. If there is no clear user-facing label for it, update the label:

```tsx
label: "Min source relevance for suggestions"
description: "Sources below this score trigger the recovery suggestion banner"
```

This reuses the existing `strip_min_relevance` setting (default 0.3) rather than creating a new field.

**Step 2: Run the full KnowledgeQA test suite**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/KnowledgeQA/__tests__/`
Expected: All PASS

**Step 3: Final commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/SettingsPanel/ExpertSettings.tsx
git commit -m "feat(knowledge-qa): label strip_min_relevance for recovery banner threshold"
```

---

## Verification Checklist

After all tasks are complete:

1. **Visual check**: Open Knowledge QA page
   - [ ] No "Conversation Thread (0 prior turns)" on first question
   - [ ] Grounding badge shows "Answer may not be based on your sources" when 0%
   - [ ] Labels: "Source support: Strong", "Weak relevance", "Section 3 of 12"
2. **Evidence panel**: Query with 1 source
   - [ ] Rail stays collapsed with count badge
   - [ ] Clicking badge opens rail
   - [ ] No filter controls visible (compact density)
3. **Evidence panel**: Query with 5+ sources
   - [ ] Rail auto-opens
   - [ ] Sort + keyword visible, date/facet behind toggle
4. **Recovery banner**: Query something not in sources
   - [ ] Banner appears between answer and follow-up
   - [ ] Buttons functional (refine, web, sources)
   - [ ] X dismisses, new search resets
5. **Source card**: Check any source card
   - [ ] Only View + Cite + ... visible
   - [ ] Overflow menu has Pin, Ask variants, Copy, Open
   - [ ] Feedback row appears on hover
6. **Accessibility**: Tab through all controls
   - [ ] Focus rings present
   - [ ] Aria labels correct
   - [ ] Overflow menu keyboard-navigable
7. **Responsive**: Check mobile
   - [ ] Recovery banner stacks vertically
   - [ ] Evidence modal still works
