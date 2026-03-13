# Structured Q&A Import With Approval Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a deterministic structured Q&A import flow in Flashcards `Transfer` so users can paste labeled Q&A notes, preview editable candidate cards, and save only approved cards to a deck without LLM rewriting.

**Architecture:** Add a server-side structured Q&A preview parser and a preview endpoint at `/api/v1/flashcards/import/structured/preview`. Extend the shared UI service layer and `Transfer` import surface to call that preview endpoint, render editable drafts, and persist approved drafts via the existing flashcard bulk-create path plus existing undo-notification patterns. Keep v1 text/Markdown-only and explicitly exclude live capture, OCR, OneNote integration, and image extraction.

**Tech Stack:** FastAPI, Pydantic, Python regex/text parsing, React, TypeScript, TanStack Query, Ant Design, pytest, Vitest

---

Follow `@superpowers/test-driven-development` throughout. Before declaring the work complete, run the commands in the verification section and follow `@superpowers/verification-before-completion`.

## Scope Guardrails

- Support deterministic `Q:` / `A:` and `Question:` / `Answer:` labeled text only in v1, including the same labels copied from Markdown or note exports.
- Preserve user-authored text and Markdown; do not call an LLM to rewrite card content.
- Preview is non-destructive. Saving approved drafts uses the existing flashcard bulk-create path.
- Do not change CSV/JSON/APKG behavior except to add the new structured import mode alongside them.
- Do not infer unlabeled question/answer pairs in v1.
- Do not add card image extraction, live app scanning, screenshare capture, or remote integrations in this plan.

## Relevant Existing Code

- `apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx`
- `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- `apps/packages/ui/src/components/Flashcards/constants/help-links.ts`
- `apps/packages/ui/src/services/flashcards.ts`
- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`
- `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`

### Task 1: Add Deterministic Structured Q&A Parser Core

**Files:**
- Create: `tldw_Server_API/app/core/Flashcards/structured_qa_import.py`
- Test: `tldw_Server_API/tests/Flashcards/test_structured_qa_import.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Flashcards.structured_qa_import import (
    parse_structured_qa_preview,
)


def test_parse_structured_qa_preview_builds_multiline_pairs():
    result = parse_structured_qa_preview(
        """Q: What is ATP?
A: Primary cellular energy currency.
Still part of the answer.

Question: What is glycolysis?
Answer: Cytosolic glucose breakdown.
"""
    )

    assert [draft.front for draft in result.drafts] == [
        "What is ATP?",
        "What is glycolysis?",
    ]
    assert result.drafts[0].back == (
        "Primary cellular energy currency.\nStill part of the answer."
    )
    assert result.errors == []


def test_parse_structured_qa_preview_reports_incomplete_blocks():
    result = parse_structured_qa_preview(
        """Q: Complete pair
A: Complete answer

Q: Missing answer
"""
    )

    assert len(result.drafts) == 1
    assert result.errors[0].line == 4
    assert "Missing answer" in result.errors[0].error
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_structured_qa_import.py -v
```

Expected: FAIL because `structured_qa_import.py` and `parse_structured_qa_preview` do not exist yet.

**Step 3: Write minimal implementation**

```python
import re
from dataclasses import dataclass, field

QUESTION_RE = re.compile(r"^\s*(?:Q|Question)\s*[:.-]\s*(.+?)\s*$", re.IGNORECASE)
ANSWER_RE = re.compile(r"^\s*(?:A|Answer)\s*[:.-]\s*(.*)\s*$", re.IGNORECASE)


@dataclass
class StructuredQaDraft:
    front: str
    back: str
    line_start: int
    line_end: int
    notes: str | None = None
    extra: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class StructuredQaParseError:
    line: int | None
    error: str


@dataclass
class StructuredQaPreviewResult:
    drafts: list[StructuredQaDraft] = field(default_factory=list)
    errors: list[StructuredQaParseError] = field(default_factory=list)
    detected_format: str = "qa_labels"
    skipped_blocks: int = 0


def parse_structured_qa_preview(content: str) -> StructuredQaPreviewResult:
    # Scan line-by-line, open a question block when a Q label is found,
    # switch to answer mode on the first A label, preserve continuation lines,
    # and emit non-fatal errors for incomplete blocks instead of raising.
    ...
```

Implementation notes:

- Keep parsing deterministic and side-effect free.
- Preserve Markdown and line breaks inside answers.
- Treat blank lines as separators, not errors.
- Emit draft `line_start` / `line_end` metadata for UI diagnostics.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_structured_qa_import.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Flashcards/structured_qa_import.py tldw_Server_API/tests/Flashcards/test_structured_qa_import.py
git commit -m "feat(flashcards): add structured q and a preview parser"
```

### Task 2: Add Preview API Contract And Endpoint

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- Modify: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`
- Reference: `tldw_Server_API/app/core/Flashcards/structured_qa_import.py`

**Step 1: Write the failing test**

```python
def test_structured_preview_endpoint_returns_drafts(client_with_flashcards_db):
    payload = {
        "content": "Q: What is ATP?\nA: Primary energy currency.\n"
    }

    response = client_with_flashcards_db.post(
        "/api/v1/flashcards/import/structured/preview",
        json=payload,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["detected_format"] == "qa_labels"
    assert data["drafts"][0]["front"] == "What is ATP?"
    assert data["drafts"][0]["back"] == "Primary energy currency."
    assert data["errors"] == []


def test_structured_preview_respects_line_caps(client_with_flashcards_db, monkeypatch):
    monkeypatch.setenv("FLASHCARDS_IMPORT_MAX_LINES", "2")

    payload = {
        "content": "Q: One\nA: First\nQ: Two\nA: Second\n"
    }

    response = client_with_flashcards_db.post(
        "/api/v1/flashcards/import/structured/preview",
        json=payload,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["drafts"]) == 1
    assert any("Maximum preview line limit" in error["error"] for error in data["errors"])
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k structured_preview -v
```

Expected: FAIL with `404` because the preview endpoint does not exist yet.

**Step 3: Write minimal implementation**

```python
class StructuredQaImportPreviewRequest(BaseModel):
    content: str = Field(..., min_length=1)


class StructuredQaImportPreviewDraft(BaseModel):
    front: str
    back: str
    line_start: int
    line_end: int
    notes: Optional[str] = None
    extra: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class StructuredQaImportPreviewError(BaseModel):
    line: Optional[int] = None
    error: str


class StructuredQaImportPreviewResponse(BaseModel):
    drafts: list[StructuredQaImportPreviewDraft] = Field(default_factory=list)
    errors: list[StructuredQaImportPreviewError] = Field(default_factory=list)
    detected_format: Literal["qa_labels"] = "qa_labels"
    skipped_blocks: int = 0


@router.post(
    "/import/structured/preview",
    response_model=StructuredQaImportPreviewResponse,
)
def preview_structured_qa_import(
    payload: StructuredQaImportPreviewRequest,
    max_lines: Optional[int] = Query(None, ge=1),
    max_line_length: Optional[int] = Query(None, ge=1),
    max_field_length: Optional[int] = Query(None, ge=1),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    if any(p is not None for p in (max_lines, max_line_length, max_field_length)):
        _require_flashcards_admin(principal)

    result = parse_structured_qa_preview(
        payload.content,
        max_lines=...,
        max_line_length=...,
        max_field_length=...,
    )
    return {
        "drafts": [draft.__dict__ for draft in result.drafts],
        "errors": [error.__dict__ for error in result.errors],
        "detected_format": result.detected_format,
        "skipped_blocks": result.skipped_blocks,
    }
```

Implementation notes:

- Keep the endpoint preview-only. Do not write to the DB here.
- Return non-fatal parse errors in the response body instead of throwing `400` for incomplete blocks.
- Reuse the existing flashcards import env caps (`FLASHCARDS_IMPORT_MAX_LINES`, `FLASHCARDS_IMPORT_MAX_LINE_LENGTH`, `FLASHCARDS_IMPORT_MAX_FIELD_LENGTH`) so preview cannot bypass current abuse limits.
- Only throw request-level errors for malformed/empty payloads.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k structured_preview -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py
git commit -m "feat(api): add structured q and a preview endpoint"
```

### Task 3: Expose Preview API In Shared UI Services And Hooks

**Files:**
- Modify: `apps/packages/ui/src/services/flashcards.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- Create: `apps/packages/ui/src/services/__tests__/flashcards-structured-import.test.ts`

**Step 1: Write the failing test**

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest"

const mockBgRequest = vi.hoisted(() => vi.fn())

vi.mock("@/services/background-proxy", () => ({
  bgRequest: mockBgRequest
}))

vi.mock("@/services/resource-client", () => ({
  createResourceClient: vi.fn(() => ({
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn()
  }))
}))

import {
  createFlashcardsBulk,
  previewStructuredQaImport
} from "@/services/flashcards"

describe("flashcards structured import service", () => {
  beforeEach(() => {
    mockBgRequest.mockReset()
    mockBgRequest.mockResolvedValue({ drafts: [], errors: [], detected_format: "qa_labels", skipped_blocks: 0 })
  })

  it("calls the structured preview endpoint", async () => {
    await previewStructuredQaImport({ content: "Q: ATP\\nA: Energy" })

    expect(mockBgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/flashcards/import/structured/preview",
        method: "POST",
        body: { content: "Q: ATP\\nA: Energy" }
      })
    )
  })

  it("calls the bulk create endpoint for approved structured drafts", async () => {
    await createFlashcardsBulk([
      {
        front: "What is ATP?",
        back: "Primary energy currency.",
        model_type: "basic",
        is_cloze: false,
        reverse: false
      }
    ])

    expect(mockBgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/flashcards/bulk",
        method: "POST",
      })
    )
  })
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/flashcards-structured-import.test.ts
```

Expected: FAIL because `previewStructuredQaImport` does not exist yet.

**Step 3: Write minimal implementation**

```typescript
export type StructuredQaImportPreviewRequest = {
  content: string
}

export type StructuredQaImportPreviewDraft = {
  front: string
  back: string
  line_start: number
  line_end: number
  notes?: string | null
  extra?: string | null
  tags?: string[] | null
}

export type StructuredQaImportPreviewResponse = {
  drafts: StructuredQaImportPreviewDraft[]
  errors: Array<{ line?: number | null; error: string }>
  detected_format: "qa_labels"
  skipped_blocks: number
}

export async function previewStructuredQaImport(
  input: StructuredQaImportPreviewRequest
): Promise<StructuredQaImportPreviewResponse> {
  return await bgRequest({
    path: "/api/v1/flashcards/import/structured/preview" as AllowedPath,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: input
  })
}

export async function createFlashcardsBulk(
  input: FlashcardCreate[]
): Promise<FlashcardListResponse> {
  return await bgRequest({
    path: "/api/v1/flashcards/bulk" as AllowedPath,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: input
  })
}
```

Implementation notes:

- Keep this layer thin. No parsing logic belongs in the service.
- Do not add a new persistence endpoint; approved drafts will save through the existing bulk-create mutation.
- Export the types so `ImportExportTab` can strongly type draft state.
- Add `usePreviewStructuredQaImportMutation()` and `useCreateFlashcardsBulkMutation()` in `useFlashcardQueries.ts`, and ensure the bulk mutation invalidates flashcard queries once after the batch succeeds.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/flashcards-structured-import.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/flashcards.ts apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts apps/packages/ui/src/services/__tests__/flashcards-structured-import.test.ts
git commit -m "feat(ui): add structured q and a preview service contract"
```

### Task 4: Add Structured Import Preview And Approval UI In `Transfer`

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx`
- Reference: `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- Reference: `apps/packages/ui/src/services/flashcards.ts`

**Step 1: Write the failing test**

```typescript
it("previews structured q and a drafts and saves only selected cards", async () => {
  vi.mocked(usePreviewStructuredQaImportMutation).mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue({
      detected_format: "qa_labels",
      skipped_blocks: 0,
      errors: [],
      drafts: [
        { front: "What is ATP?", back: "Primary energy currency.", line_start: 1, line_end: 2, tags: [] },
        { front: "What is glycolysis?", back: "Cytosolic glucose breakdown.", line_start: 4, line_end: 5, tags: [] }
      ]
    }),
    isPending: false
  } as any)

  const createBulkMutateAsync = vi
    .fn()
    .mockResolvedValueOnce({
      items: [{ uuid: "card-1", version: 1 }],
      count: 1
    })
  vi.mocked(useCreateFlashcardsBulkMutation).mockReturnValue({
    mutateAsync: createBulkMutateAsync,
    isPending: false
  } as any)

  render(<ImportExportTab />)

  fireEvent.change(screen.getByTestId("flashcards-import-format"), {
    target: { value: "structured" }
  })
  fireEvent.change(screen.getByTestId("flashcards-import-textarea"), {
    target: { value: "Q: What is ATP?\\nA: Primary energy currency." }
  })
  fireEvent.click(screen.getByTestId("flashcards-structured-preview-button"))

  await waitFor(() => {
    expect(screen.getByDisplayValue("What is ATP?")).toBeInTheDocument()
  })

  fireEvent.click(screen.getByTestId("flashcards-structured-save-button"))

  await waitFor(() => {
    expect(createBulkMutateAsync).toHaveBeenCalledTimes(1)
  })
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx -t "previews structured q and a drafts and saves only selected cards"
```

Expected: FAIL because the `structured` import mode and preview/save controls do not exist yet.

**Step 3: Write minimal implementation**

```typescript
type ImportMode = "delimited" | "json" | "apkg" | "structured"

const previewStructuredMutation = usePreviewStructuredQaImportMutation()
const [structuredDrafts, setStructuredDrafts] = React.useState<StructuredQaImportPreviewDraft[]>([])
const [selectedStructuredDraftIds, setSelectedStructuredDraftIds] = React.useState<string[]>([])
const [structuredPreviewErrors, setStructuredPreviewErrors] = React.useState<FlashcardsImportError[]>([])
const [structuredTargetDeckId, setStructuredTargetDeckId] = React.useState<number | null | undefined>(undefined)

const handleStructuredPreview = async () => {
  const preview = await previewStructuredMutation.mutateAsync({ content })
  const drafts = preview.drafts.map((draft, index) => ({
    ...draft,
    id: `structured-${index}-${draft.line_start}`
  }))
  setStructuredDrafts(drafts)
  setSelectedStructuredDraftIds(drafts.map((draft) => draft.id))
  setStructuredPreviewErrors(preview.errors)
}

const handleSaveStructuredDrafts = async () => {
  const selectedDrafts = structuredDrafts.filter((draft) =>
    selectedStructuredDraftIds.includes(draft.id)
  )
  const deckId = await resolveTargetDeckId()
  const payload = selectedDrafts.map((draft) => ({
    deck_id: deckId,
    front: draft.front,
    back: draft.back,
    notes: draft.notes || undefined,
    extra: draft.extra || undefined,
    tags: draft.tags || undefined,
    model_type: "basic",
    is_cloze: false,
    reverse: false,
    source_ref_type: "manual"
  }))
  const createdCards = await createBulkMutation.mutateAsync(payload)
  // Reuse existing undo notification pattern with createdCards.items[].uuid/version.
}
```

Implementation notes:

- Add `structured` as a fourth import format beside delimited, JSON, and APKG.
- Reuse `FileDropZone` and textarea for `.txt` / `.md` content instead of building a new uploader.
- Show a preview button first, then render editable drafts with:
  - checkbox per draft
  - editable `Front`
  - editable `Back`
  - source line metadata
  - remove draft action
- Save only checked drafts.
- Preserve the existing success/warning/error summary and undo-notification behavior.
- Prefer extracting a small shared draft-editor renderer/state helper from the existing generated-card draft UI instead of building a second divergent draft editor.
- If some saves fail, keep failed drafts in place and remove only successfully saved drafts, mirroring the generated-card save flow.
- Do not save selected drafts through repeated single-card create calls; use the bulk-create path to avoid one invalidate per card.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx
```

Expected: PASS, including the new structured-preview tests plus the pre-existing import/generate regression coverage.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx
git commit -m "feat(flashcards): add structured q and a transfer preview flow"
```

### Task 5: Sync Help Docs And In-App Help Links

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`
- Modify: `apps/packages/ui/src/components/Flashcards/constants/help-links.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/constants/__tests__/help-links.test.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx`

**Step 1: Write the failing test**

```typescript
it("includes a structured import guide anchor", () => {
  expect(FLASHCARDS_HELP_LINKS.structuredImport).toContain(
    "#structured-q-and-a-preview"
  )
})
```

Also extend the existing anchor-integrity test so it fails until the new guide heading exists.

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/constants/__tests__/help-links.test.ts
```

Expected: FAIL because the new anchor and guide section do not exist yet.

**Step 3: Write minimal implementation**

```typescript
export const FLASHCARDS_HELP_DOC_BASE_URL =
  "https://github.com/rmusser01/tldw_server/blob/HEAD/Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md"

export const FLASHCARDS_HELP_LINKS = {
  overview: withAnchor("daily-study-workflow"),
  ratings: withAnchor("ratings-and-scheduling-basics"),
  cloze: withAnchor("cloze-syntax"),
  importFormats: withAnchor("import-and-export-formats"),
  structuredImport: withAnchor("structured-q-and-a-preview"),
  troubleshooting: withAnchor("troubleshooting")
} as const
```

```typescript
const DOC_PATH = path.resolve(
  process.cwd(),
  "../../../Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md"
)
```

```markdown
## Structured Q&A Preview

Use this mode when your notes already contain labeled question/answer pairs.

Supported labels in v1:

- `Q:` / `A:`
- `Question:` / `Answer:`

Workflow:

1. Paste labeled Q&A text or drop a `.txt` / `.md` file.
2. Preview candidate cards.
3. Edit, deselect, or remove drafts.
4. Save approved drafts to a deck.
```

Implementation notes:

- Add a structured-mode help link in `ImportExportTab`.
- Keep the docs explicit that v1 is preview-only plus manual approval.
- Do not claim OneNote scanning, OCR, or image extraction support.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Flashcards/constants/__tests__/help-links.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md apps/packages/ui/src/components/Flashcards/constants/help-links.ts apps/packages/ui/src/components/Flashcards/constants/__tests__/help-links.test.ts apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx
git commit -m "docs(flashcards): document structured q and a preview import"
```

## Final Verification

Run all targeted checks before calling the feature complete:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_structured_qa_import.py -v
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "structured_preview" -v
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "import and not structured_preview" -v
bunx vitest run apps/packages/ui/src/services/__tests__/flashcards-structured-import.test.ts apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx apps/packages/ui/src/components/Flashcards/constants/__tests__/help-links.test.ts
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/app/core/Flashcards/structured_qa_import.py -f json -o /tmp/bandit_structured_qa_import.json
```

Expected:

- All targeted pytest and Vitest suites pass.
- Bandit reports no new issues in the touched backend files.
- Existing delimited/JSON/APKG import tests still pass after adding the new mode.

## Manual Smoke Checklist

- Delimited import still works.
- JSON/JSONL import still works.
- APKG import still works.
- Structured preview does not save cards until explicit approval.
- Saving structured drafts shows the same undo affordance as other import flows.
- Incomplete Q&A blocks appear as preview diagnostics, not server errors.
