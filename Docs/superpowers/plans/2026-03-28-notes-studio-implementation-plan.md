# Notes Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a V1 `Notes Studio` flow that turns a selected Markdown excerpt into a derived study note with canonical Studio sidecar storage, notebook-style rendering, optional follow-up diagrams, and print-optimized export.

**Architecture:** Keep ordinary notes as the searchable/editable container and add a `note_studio_documents` sidecar in the same Notes DB as the canonical Studio record. Use a backend Studio service to generate a structured payload plus Markdown companion content, then expose Notes Studio endpoints the React Notes UI can call to launch a dedicated Studio view and print/export path. Reuse the existing Notes page, query state, and print/export utilities where possible, but isolate Studio-specific rendering and stale-state logic in focused modules instead of overloading the generic Markdown/WYSIWYG editor.

**Tech Stack:** FastAPI, Pydantic, ChaChaNotes SQLite DB layer, existing Workflows/LLM adapters, React, TypeScript, TanStack Query, Ant Design, Vitest, React Testing Library, Playwright, pytest, Bandit

---

## File Structure

- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
  Purpose: add the `note_studio_documents` schema, transactional create/update helpers, soft-delete/restore behavior, stale/hash metadata, and note-to-sidecar fetch methods.
- `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
  Purpose: keep the base Note contract aligned with Studio-aware note responses where plain note fetches need a lightweight Studio summary.
- `tldw_Server_API/app/api/v1/schemas/notes_studio.py`
  Purpose: define Studio request/response models, payload section models, diagram manifest types, template enums, handwriting enums, and stale-state response envelopes.
- `tldw_Server_API/app/core/Notes/studio_markdown.py`
  Purpose: generate Markdown companion bodies from canonical Studio payloads and compute companion hashes deterministically.
- `tldw_Server_API/app/core/Notes/studio_service.py`
  Purpose: validate excerpt selections, call the generation adapter, normalize Studio payloads, persist derived notes atomically, compute stale state, and orchestrate diagram generation/retry flows.
- `tldw_Server_API/app/core/Workflows/adapters/content/_config.py`
  Purpose: add a typed config model for Notes Studio structured generation and diagram follow-up generation.
- `tldw_Server_API/app/core/Workflows/adapters/content/generation.py`
  Purpose: register the `notes_studio_generate` adapter and, if needed, harden the existing diagram adapter for notebook-friendly outputs.
- `tldw_Server_API/app/core/Workflows/adapters/content/__init__.py`
  Purpose: export the new Notes Studio generation adapter so endpoint/service code can reuse the shared workflow registry.
- `tldw_Server_API/app/api/v1/endpoints/notes.py`
  Purpose: expose Studio derive/fetch/regenerate/diagram routes alongside the existing Notes CRUD routes without introducing a second top-level Notes surface.
- `tldw_Server_API/tests/ChaChaNotesDB/test_note_studio_db.py`
  Purpose: lock down sidecar schema creation, transactional note-plus-sidecar persistence, soft-delete/restore behavior, and stale/hash invariants.
- `tldw_Server_API/tests/Notes_NEW/unit/test_notes_studio_service.py`
  Purpose: verify payload normalization, companion Markdown generation, stale detection, and diagram manifest handling without hitting HTTP.
- `tldw_Server_API/tests/Notes_NEW/integration/test_notes_studio_api.py`
  Purpose: verify derive-note, fetch-studio, regenerate, and diagram flows through the real Notes API and temp DB.
- `apps/packages/ui/src/services/notes-studio.ts`
  Purpose: define typed client helpers for Notes Studio derive/fetch/regenerate/diagram/export actions using the existing background proxy.
- `apps/packages/ui/src/services/__tests__/notes-studio.test.ts`
  Purpose: verify Notes Studio client requests and payload serialization.
- `apps/packages/ui/src/components/Notes/notes-studio-types.ts`
  Purpose: centralize frontend Studio types so Notes UI, export, and tests share one Studio contract.
- `apps/packages/ui/src/components/Notes/NotesStudioCreateModal.tsx`
  Purpose: collect template and handwriting choices after excerpt selection and block WYSIWYG-only entry in V1.
- `apps/packages/ui/src/components/Notes/NotesStudioView.tsx`
  Purpose: render lined/grid/Cornell notebook chrome, handwriting accents, stale-warning banners, diagram cards, and print/export controls.
- `apps/packages/ui/src/components/Notes/NotesStudioDiagramCard.tsx`
  Purpose: render diagram suggestion state, retry affordances, and SVG output separate from the main Studio layout component.
- `apps/packages/ui/src/components/Notes/notes-manager-utils.ts`
  Purpose: add selection helpers, Studio-specific utility types/constants, locale-driven paper defaults, and notebook template metadata.
- `apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
  Purpose: add the `Notes Studio` action to the Notes header overflow/AI actions menu.
- `apps/packages/ui/src/components/Notes/NotesEditorPane.tsx`
  Purpose: surface Studio entry affordances, render the Studio view when a selected note has Studio data, and preserve the Markdown/WYSIWYG split.
- `apps/packages/ui/src/components/Notes/hooks/useNotesEditorState.tsx`
  Purpose: track Studio document state, excerpt selection, stale warnings, and regenerate actions alongside existing editor state.
- `apps/packages/ui/src/components/Notes/hooks/useNotesExport.tsx`
  Purpose: route Studio notes through Studio print/export while keeping plain note export behavior unchanged.
- `apps/packages/ui/src/components/Notes/export-utils.ts`
  Purpose: add print-optimized Studio HTML builders, paper-size handling, template backgrounds, and plain-export fallback behavior.
- `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  Purpose: wire the modal, backend calls, note selection handoff, and derived-note navigation into the existing Notes page.
- `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.notes-studio-entry.test.tsx`
  Purpose: verify Markdown-only entry, selection requirements, and derived-note creation handoff.
- `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage44.notes-studio-view.test.tsx`
  Purpose: verify Studio note loading, stale banners, template switching rules, handwriting mode, and diagram suggestion affordances.
- `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage45.notes-studio-export.test.tsx`
  Purpose: verify Studio print/export and fallback behavior from the real Notes page surface.
- `apps/packages/ui/src/components/Notes/__tests__/export-utils.test.ts`
  Purpose: extend print/export unit coverage for Studio HTML generation, page sizing, and notebook backgrounds.
- `apps/packages/ui/src/public/_locales/en/option.json`
  Purpose: add English strings for Notes Studio entry, modal choices, stale warnings, diagram actions, and print/export labels.
- `apps/packages/ui/src/assets/locale/en/option.json`
  Purpose: keep the source English locale bundle aligned with the public locale output used by tests/runtime.
- `apps/tldw-frontend/e2e/utils/page-objects/NotesPage.ts`
  Purpose: add helpers for selection, opening Notes Studio, and asserting the derived Studio note shell.
- `apps/tldw-frontend/e2e/workflows/notes-studio-derived-note.spec.ts`
  Purpose: cover the end-to-end happy path from excerpt selection to derived Studio note and print dialog launch.

## Stages

### Stage 1: Backend Studio Persistence

**Goal:** Land the sidecar table, DB helpers, and schema models needed to persist Studio notes safely.

**Success Criteria:** A note can store and retrieve a Studio sidecar with payload, hashes, template metadata, and delete/restore semantics.

**Tests:** `python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_note_studio_db.py -v`

**Status:** Complete

### Stage 2: Backend Studio Generation API

**Goal:** Add derive/fetch/regenerate/diagram endpoints backed by a focused Studio service and structured generation adapter.

**Success Criteria:** The API can create a derived Studio note from a source excerpt, expose Studio data on fetch, regenerate after Markdown drift, and store notebook diagram manifests.

**Tests:** `python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_notes_studio_service.py tldw_Server_API/tests/Notes_NEW/integration/test_notes_studio_api.py -v`

**Status:** Not Started

### Stage 3: Notes UI Entry And State

**Goal:** Add the Markdown-only `Notes Studio` launch flow and derived-note navigation to the existing Notes page.

**Success Criteria:** Users can select Markdown text, choose template/handwriting options, create a Studio note, and reopen it from the Notes page without breaking existing Notes editing flows.

**Tests:** `bunx vitest run apps/packages/ui/src/services/__tests__/notes-studio.test.ts apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.notes-studio-entry.test.tsx`

**Status:** Not Started

### Stage 4: Studio Rendering And Export

**Goal:** Add a Studio-specific note surface with stale warnings, diagram cards, and print-optimized export.

**Success Criteria:** Studio notes render lined/grid/Cornell layouts, accented handwriting, diagram state, and paper-size-aware print HTML while plain export still works.

**Tests:** `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage44.notes-studio-view.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage45.notes-studio-export.test.tsx apps/packages/ui/src/components/Notes/__tests__/export-utils.test.ts`

**Status:** Not Started

### Stage 5: End-To-End And Security Verification

**Goal:** Prove the feature works across API + UI boundaries and does not introduce backend security regressions in touched code.

**Success Criteria:** The targeted Playwright workflow passes and Bandit reports no new findings in the touched backend scope.

**Tests:** `bunx playwright test apps/tldw-frontend/e2e/workflows/notes-studio-derived-note.spec.ts --reporter=line`, `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/notes.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/core/Notes/studio_markdown.py tldw_Server_API/app/core/Notes/studio_service.py -f json -o /tmp/bandit_notes_studio.json`

**Status:** Not Started

## Task 1: Add Studio Sidecar Storage And Shared Backend Models

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/notes_studio.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/ChaChaNotesDB/test_note_studio_db.py`

- [ ] **Step 1: Write the failing DB and schema tests**

Add tests that prove:

1. the Notes DB creates `note_studio_documents`
2. a Studio sidecar can be inserted and fetched by `note_id`
3. soft-deleting a note keeps the sidecar available for restore and restore reuses the same sidecar instead of regenerating it
4. hard-delete cleanup removes the sidecar
5. stale-state hashes are persisted and compared explicitly

Use concrete assertions like:

```python
note_id = db.add_note(title="Source", content="Alpha beta gamma")
db.create_note_studio_document(
    note_id=note_id,
    payload_json={"meta": {"source_note_id": note_id}, "sections": []},
    template_type="lined",
    handwriting_mode="accented",
    source_note_id=note_id,
    excerpt_snapshot="beta",
    excerpt_hash="sha256:demo",
    companion_content_hash="sha256:markdown",
    render_version=1,
)

studio = db.get_note_studio_document(note_id)
assert studio is not None
assert studio["template_type"] == "lined"
assert studio["handwriting_mode"] == "accented"
```

- [ ] **Step 2: Run the targeted backend tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_note_studio_db.py -v
```

Expected: FAIL because the Studio sidecar table and helpers do not exist yet.

- [ ] **Step 3: Add the minimal storage and schema support**

Implement the boring persistence layer first:

- add `note_studio_documents` with `note_id`, `payload_json`, `template_type`, `handwriting_mode`, `source_note_id`, `excerpt_snapshot`, `excerpt_hash`, `diagram_manifest_json`, `companion_content_hash`, `render_version`, `created_at`, `last_modified`
- keep it in the same DB and wrap note-plus-sidecar writes in one transaction helper
- add read helpers such as:

```python
def get_note_studio_document(self, note_id: str) -> dict[str, Any] | None:
    ...

def create_note_studio_document(..., conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    ...

def upsert_note_studio_document(..., conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    ...
```

- expose lightweight Studio summary fields on note fetch only where needed, not by embedding the whole payload into every list response
- define request/response models in `notes_studio.py` instead of overloading `notes_schemas.py` with large nested payloads

- [ ] **Step 4: Re-run the targeted backend tests**

Run the pytest command from Step 2.

Expected: PASS for sidecar creation, retrieval, soft-delete persistence, and hard-delete cleanup.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/notes_studio.py \
  tldw_Server_API/app/api/v1/schemas/notes_schemas.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_note_studio_db.py
git commit -m "feat: add notes studio sidecar storage"
```

## Task 2: Add Studio Generation, Regeneration, And Diagram APIs

**Files:**
- Create: `tldw_Server_API/app/core/Notes/studio_markdown.py`
- Create: `tldw_Server_API/app/core/Notes/studio_service.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/content/_config.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/content/generation.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/content/__init__.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/notes.py`
- Test: `tldw_Server_API/tests/Notes_NEW/unit/test_notes_studio_service.py`
- Test: `tldw_Server_API/tests/Notes_NEW/integration/test_notes_studio_api.py`

- [ ] **Step 1: Write the failing Studio service and API tests**

Add tests that prove:

1. `POST /api/v1/notes/studio/derive` creates a new derived note plus sidecar
2. the derived sidecar stores `source_note_id`, `excerpt_snapshot`, and `excerpt_hash` from the selected excerpt end to end
3. the derived note title follows a deterministic source-title rule such as `"{source title} Study Notes"` with an `Untitled Study Notes` fallback
4. the companion Markdown contains semantically useful headings and summary text, not notebook chrome tokens
5. Cornell generation includes at least one explicit recall prompt or fill-in blank so the output remains a hybrid notebook, not a fully polished summary
6. `GET /api/v1/notes/{note_id}/studio` returns the canonical payload and stale flag
7. `POST /api/v1/notes/{note_id}/studio/regenerate` rebuilds payload + companion content from current Markdown
8. `POST /api/v1/notes/{note_id}/studio/diagrams` stores a manifest containing diagram type, source section ids, canonical source graph/intermediate representation, cached SVG, render hash, and generation status
9. empty, whitespace-only, or otherwise invalid excerpt requests are rejected server-side even if a client bypasses UI gating

Use service-level assertions like:

```python
result = await derive_note_studio_document(
    db=db,
    source_note_id=source_id,
    excerpt_text="The mitochondrion is the powerhouse...",
    template_type="cornell",
    handwriting_mode="accented",
)
assert result.note["id"] != source_id
assert result.note["title"] == "Source Note Study Notes"
assert result.studio["source_note_id"] == source_id
assert result.studio["excerpt_snapshot"] == "The mitochondrion is the powerhouse..."
assert result.studio["excerpt_hash"].startswith("sha256:")
assert result.studio["payload_json"]["layout"]["template_type"] == "cornell"
assert "# Key Ideas" in result.note["content"]
assert "Fill this in:" in result.note["content"]
```

- [ ] **Step 2: Run the targeted service/API tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Notes_NEW/unit/test_notes_studio_service.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_notes_studio_api.py \
  -v
```

Expected: FAIL because no Studio service or routes exist yet.

- [ ] **Step 3: Implement the Studio service and routes**

Build the smallest end-to-end backend path that matches the spec:

- create a `notes_studio_generate` workflow adapter or equivalent helper that returns structured JSON validated against a Studio payload schema
- keep prompt/adapter output scoped to:
  - `meta`
  - `sections`
  - `layout`
  - optional `summary`
  - optional `prompts`
  - optional `diagrams`
- require hybrid notebook output in the generation contract:
  - main notes are AI-filled
  - at least one recall prompt, cue question, or fill-in blank is left for the user
  - Cornell output must include a cue/prompt area, not only complete prose
- generate Markdown companion content in `studio_markdown.py` using deterministic rules such as:

```python
markdown = "\n\n".join(
    [
        f"# {title}",
        "## Cue Questions",
        cue_markdown,
        "## Main Notes",
        notes_markdown,
        "## Summary",
        summary_markdown,
        "## Fill This In",
        prompt_markdown,
    ]
)
```

- add focused routes in `notes.py`:
  - `POST /api/v1/notes/studio/derive`
  - `GET /api/v1/notes/{note_id}/studio`
  - `POST /api/v1/notes/{note_id}/studio/regenerate`
  - `POST /api/v1/notes/{note_id}/studio/diagrams`
- reject invalid derive input server-side:
  - reject empty or whitespace-only excerpts
  - reject requests with no `source_note_id`
  - reject selection metadata that is obviously malformed when offsets are provided
- preserve the same note-access and ownership checks as the existing Notes routes for derive, fetch, regenerate, and diagram calls
- derive note titles deterministically from the source title:
  - `"${source_title} Study Notes"` when the source title is non-empty
  - `"Untitled Study Notes"` when the source title is missing
- default new Studio notes to `handwriting_mode="accented"` unless the user explicitly chooses `off`
- mark Studio documents stale only when the Markdown companion content drifts:
  - do not mark stale for title-only edits
  - do not mark stale for keyword-only edits
  - do not mark stale for backlink-only edits
  - do mark stale when the current note body content hash no longer matches `companion_content_hash`
- persist diagram manifests with explicit fields:
  - `diagram_type`
  - `source_section_ids`
  - `source_graph`
  - `cached_svg`
  - `render_hash`
  - `generation_status`
- keep diagram suggestions heuristic and bounded in V1:
  - suggest `concept_map` when there are multiple concept-heavy sections
  - suggest `flowchart` when sections contain ordered steps
  - suggest `comparison_diagram` when the payload includes compare/contrast sections
  - otherwise show no suggestion until the user explicitly asks for a diagram
- keep `replace selection` out of scope; the derive endpoint always creates a new note in V1

- [ ] **Step 4: Re-run the targeted service/API tests**

Run the pytest command from Step 2.

Expected: PASS for derive, fetch, regenerate, and diagram manifest behavior.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Notes/studio_markdown.py \
  tldw_Server_API/app/core/Notes/studio_service.py \
  tldw_Server_API/app/core/Workflows/adapters/content/_config.py \
  tldw_Server_API/app/core/Workflows/adapters/content/generation.py \
  tldw_Server_API/app/core/Workflows/adapters/content/__init__.py \
  tldw_Server_API/app/api/v1/endpoints/notes.py \
  tldw_Server_API/tests/Notes_NEW/unit/test_notes_studio_service.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_notes_studio_api.py
git commit -m "feat: add notes studio derive and diagram APIs"
```

## Task 3: Add The Markdown-Only Notes Studio Launch Flow

**Files:**
- Create: `apps/packages/ui/src/services/notes-studio.ts`
- Create: `apps/packages/ui/src/services/__tests__/notes-studio.test.ts`
- Create: `apps/packages/ui/src/components/Notes/notes-studio-types.ts`
- Create: `apps/packages/ui/src/components/Notes/NotesStudioCreateModal.tsx`
- Modify: `apps/packages/ui/src/components/Notes/notes-manager-utils.ts`
- Modify: `apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
- Modify: `apps/packages/ui/src/components/Notes/NotesEditorPane.tsx`
- Modify: `apps/packages/ui/src/components/Notes/hooks/useNotesEditorState.tsx`
- Modify: `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
- Modify: `apps/packages/ui/src/public/_locales/en/option.json`
- Modify: `apps/packages/ui/src/assets/locale/en/option.json`
- Test: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.notes-studio-entry.test.tsx`

- [ ] **Step 1: Write the failing frontend tests for entry gating and derive-note handoff**

Add tests that prove:

1. the `Notes Studio` action appears in the Notes header AI actions
2. it is disabled or blocked when there is no Markdown selection
3. the `Notes Studio` action is only available in Markdown mode, while WYSIWYG mode shows a separate prompt that offers `Switch to Markdown`
4. the modal captures `template_type` and `handwriting_mode`
5. a successful derive response selects the new note and opens Studio view

Use assertions like:

```tsx
fireEvent.mouseDown(screen.getByRole("button", { name: /more actions/i }))
fireEvent.click(await screen.findByText("Notes Studio"))
expect(screen.getByText("Choose notebook template")).toBeInTheDocument()
```

- [ ] **Step 2: Run the targeted frontend tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/notes-studio.test.ts \
  apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.notes-studio-entry.test.tsx
```

Expected: FAIL because the Studio client, modal, and Notes action do not exist yet.

- [ ] **Step 3: Implement the launch flow with the smallest safe UI changes**

Keep V1 strict and explicit:

- add a typed `notes-studio.ts` client with functions like:

```ts
export async function deriveNoteStudio(request: DeriveNoteStudioRequest) {
  return bgRequest<DeriveNoteStudioResponse>({
    path: "/api/v1/notes/studio/derive",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: request
  })
}
```

- add `Notes Studio` to `NotesEditorHeader.tsx` under the AI group
- keep the `Notes Studio` action available only when:
  - a note is selected
  - the editor input mode is `markdown`
- when the editor is in `wysiwyg`, show a separate inline or modal prompt near the input-mode controls that offers:
  - `Switch to Markdown`
  - `Cancel`
- only open the template modal once the editor is in Markdown mode and the current Markdown selection is non-empty
- when already in Markdown mode, block empty selections with an explicit warning instead of a silent no-op
- add a focused modal for:
  - `lined`
  - `grid`
  - `cornell`
  - `off`
  - `accented`
- on success, refetch notes, select the returned note id, fetch `GET /api/v1/notes/{note_id}/studio`, and switch the Notes page into Studio view for that note
- do not add `replace selection`

- [ ] **Step 4: Re-run the targeted frontend tests**

Run the Vitest command from Step 2.

Expected: PASS for action visibility, Markdown-only gating, modal behavior, and derived-note handoff.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/services/notes-studio.ts \
  apps/packages/ui/src/services/__tests__/notes-studio.test.ts \
  apps/packages/ui/src/components/Notes/notes-studio-types.ts \
  apps/packages/ui/src/components/Notes/NotesStudioCreateModal.tsx \
  apps/packages/ui/src/components/Notes/notes-manager-utils.ts \
  apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx \
  apps/packages/ui/src/components/Notes/NotesEditorPane.tsx \
  apps/packages/ui/src/components/Notes/hooks/useNotesEditorState.tsx \
  apps/packages/ui/src/components/Notes/NotesManagerPage.tsx \
  apps/packages/ui/src/public/_locales/en/option.json \
  apps/packages/ui/src/assets/locale/en/option.json \
  apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.notes-studio-entry.test.tsx
git commit -m "feat: add notes studio launch flow"
```

## Task 4: Add Studio Rendering, Stale Warnings, And Print Export

**Files:**
- Create: `apps/packages/ui/src/components/Notes/NotesStudioView.tsx`
- Create: `apps/packages/ui/src/components/Notes/NotesStudioDiagramCard.tsx`
- Modify: `apps/packages/ui/src/components/Notes/notes-studio-types.ts`
- Modify: `apps/packages/ui/src/components/Notes/NotesEditorPane.tsx`
- Modify: `apps/packages/ui/src/components/Notes/hooks/useNotesEditorState.tsx`
- Modify: `apps/packages/ui/src/components/Notes/hooks/useNotesExport.tsx`
- Modify: `apps/packages/ui/src/components/Notes/export-utils.ts`
- Test: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage44.notes-studio-view.test.tsx`
- Test: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage45.notes-studio-export.test.tsx`
- Test: `apps/packages/ui/src/components/Notes/__tests__/export-utils.test.ts`

- [ ] **Step 1: Write the failing rendering and export tests**

Add tests that prove:

1. lined, grid, and Cornell templates render distinct notebook chrome
2. new Studio notes default to `accented` handwriting unless the user chooses `off`
3. `accented` handwriting changes headings/cues only, not dense body text
4. a stale banner appears only when note body content diverges from `companion_content_hash`, not for title/keyword/backlink-only edits
5. regenerate-from-Markdown calls the backend and clears stale state
6. Studio print export supports `US Letter`, `A4`, and `A5`
7. the default paper size is locale-driven: `US Letter` for US locale and `A4` otherwise
8. Studio print export includes page margins, page breaks, Cornell side-column layout, template background classes, and SVG diagrams
9. Studio print export embeds notebook font fallbacks explicitly so layout remains readable when custom handwriting fonts are unavailable
10. plain single-note export still works for Studio notes when Studio print fails

Use export assertions like:

```ts
const html = buildStudioPrintableHtml(studioDoc, note, { paperSize: "A4" })
expect(html).toContain("data-paper-size=\"A4\"")
expect(html).toContain("studio-template-cornell")
expect(html).toContain("<svg")
```

- [ ] **Step 2: Run the targeted rendering/export tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage44.notes-studio-view.test.tsx \
  apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage45.notes-studio-export.test.tsx \
  apps/packages/ui/src/components/Notes/__tests__/export-utils.test.ts
```

Expected: FAIL because the Studio renderer and print builder do not exist yet.

- [ ] **Step 3: Implement the Studio view and export path**

Keep the rendering contract shared between screen and print:

- add `NotesStudioView.tsx` that accepts `{ note, studioDocument, paperSize, onRegenerate, onGenerateDiagram }`
- render template chrome with explicit classes like:

```tsx
<section className={cn("studio-sheet", `studio-template-${templateType}`)}>
  <header className={cn("studio-heading", handwritingMode === "accented" && "studio-handwritten")}>
    {title}
  </header>
</section>
```

- show stale-state banner actions:
  - `Regenerate Studio view from current Markdown`
  - `Continue editing plain note`
- render diagrams through `NotesStudioDiagramCard.tsx` from canonical source + cached SVG, not raw Mermaid fences
- add a Studio-specific print builder to `export-utils.ts`
- support `US Letter`, `A4`, and `A5` plus locale-driven default paper-size selection
- include explicit print CSS for page margins, page breaks, Cornell cue column layout, and notebook/handwriting font fallbacks
- have `useNotesExport.tsx` choose Studio print HTML when the selected note has Studio data and fall back to plain note print on failure

- [ ] **Step 4: Re-run the targeted rendering/export tests**

Run the Vitest command from Step 2.

Expected: PASS for template rendering, stale handling, diagram cards, and Studio print/export.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Notes/NotesStudioView.tsx \
  apps/packages/ui/src/components/Notes/NotesStudioDiagramCard.tsx \
  apps/packages/ui/src/components/Notes/notes-studio-types.ts \
  apps/packages/ui/src/components/Notes/NotesEditorPane.tsx \
  apps/packages/ui/src/components/Notes/hooks/useNotesEditorState.tsx \
  apps/packages/ui/src/components/Notes/hooks/useNotesExport.tsx \
  apps/packages/ui/src/components/Notes/export-utils.ts \
  apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage44.notes-studio-view.test.tsx \
  apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage45.notes-studio-export.test.tsx \
  apps/packages/ui/src/components/Notes/__tests__/export-utils.test.ts
git commit -m "feat: add notes studio view and export"
```

## Task 5: Verify End-To-End Behavior And Run Security Checks

**Files:**
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/NotesPage.ts`
- Create: `apps/tldw-frontend/e2e/workflows/notes-studio-derived-note.spec.ts`
- Modify: `tldw_Server_API/app/api/v1/endpoints/notes.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/core/Notes/studio_markdown.py`
- Modify: `tldw_Server_API/app/core/Notes/studio_service.py`

- [ ] **Step 1: Write the failing end-to-end workflow test**

Add one focused Playwright workflow that proves:

1. a user selects Markdown text in Notes
2. opens `Notes Studio`
3. creates a derived note with `Cornell` + `accented`
4. sees the Studio view shell
5. can trigger print export without a frontend crash

Use helpers in `NotesPage.ts` so the test body stays readable:

```ts
await notesPage.selectEditorRange("mitochondrion")
await notesPage.openNotesStudio()
await notesPage.completeNotesStudioSetup({ template: "cornell", handwriting: "accented" })
await expect(page.getByTestId("notes-studio-view")).toBeVisible()
```

- [ ] **Step 2: Run the E2E test to verify it fails**

Run:

```bash
bunx playwright test apps/tldw-frontend/e2e/workflows/notes-studio-derived-note.spec.ts --reporter=line
```

Expected: FAIL because the Notes page E2E helpers and workflow do not exist yet.

- [ ] **Step 3: Add the minimal E2E helpers and fix any final gaps**

Keep the last-mile changes small:

- add page-object helpers instead of direct selector duplication
- only patch implementation gaps discovered by the E2E test
- avoid broad refactors at this stage; fix the concrete issue the test exposes

- [ ] **Step 4: Re-run the targeted verification commands**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/notes-studio.test.ts \
  apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.notes-studio-entry.test.tsx \
  apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage44.notes-studio-view.test.tsx \
  apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage45.notes-studio-export.test.tsx \
  apps/packages/ui/src/components/Notes/__tests__/export-utils.test.ts
```

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/ChaChaNotesDB/test_note_studio_db.py \
  tldw_Server_API/tests/Notes_NEW/unit/test_notes_studio_service.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_notes_studio_api.py \
  -v
```

```bash
bunx playwright test apps/tldw-frontend/e2e/workflows/notes-studio-derived-note.spec.ts --reporter=line
```

```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/notes.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/app/core/Notes/studio_markdown.py \
  tldw_Server_API/app/core/Notes/studio_service.py \
  -f json -o /tmp/bandit_notes_studio.json
```

Expected: targeted Vitest, pytest, Playwright, and Bandit all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/page-objects/NotesPage.ts \
  apps/tldw-frontend/e2e/workflows/notes-studio-derived-note.spec.ts \
  tldw_Server_API/app/api/v1/endpoints/notes.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/app/core/Notes/studio_markdown.py \
  tldw_Server_API/app/core/Notes/studio_service.py
git commit -m "test: verify notes studio end to end"
```

## Implementation Notes

- Do not add `replace selection` in this plan. If you discover UI affordances that imply it, remove or defer them.
- Keep Studio payload canonical and Markdown companion deterministic. Never attempt full reverse-parsing of arbitrary Markdown into Studio payload in V1.
- Store both canonical diagram source and cached SVG in the sidecar. Rendering should prefer cached SVG and regenerate only through the explicit diagram endpoint.
- Keep plain note list/search/export behavior intact. Studio-aware behavior should activate only when a Studio sidecar exists for the selected note.
- If you split any of the new files further during implementation, update this plan before continuing so the task/file mapping stays truthful.
