# First-Class Card Image Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-class flashcard image support with authenticated inline rendering, managed asset storage, APKG import/export round-trip, and search-safe indexing.

**Architecture:** Flashcard text fields will store inline markdown with internal `flashcard-asset://` references while image bytes live in a dedicated `flashcard_assets` table. The WebUI markdown renderer will resolve those refs through authenticated blob fetches, and the APKG pipeline will translate between app-native refs and Anki media HTML so image-backed cards round-trip cleanly.

**Tech Stack:** FastAPI, Pydantic, SQLite via `CharactersRAGDB`, React, TanStack Query, Ant Design, Vitest, pytest, Bandit.

---

### Task 1: Add Internal Asset Reference Helpers

**Files:**
- Create: `tldw_Server_API/app/core/Flashcards/asset_refs.py`
- Test: `tldw_Server_API/tests/Flashcards/test_flashcard_asset_refs.py`

**Step 1: Write the failing tests**

Add tests for:
- parsing `flashcard-asset://<uuid>` refs from markdown image syntax
- building markdown snippets from UUID + alt text
- sanitizing markdown image refs into search-safe text that preserves alt text
- rewriting markdown refs to temporary export HTML `<img>` placeholders

Example test shape:

```python
def test_sanitize_flashcard_asset_markdown_preserves_alt_text():
    text = "Start ![Histology slide](flashcard-asset://1234) end"
    assert sanitize_flashcard_text_for_search(text) == "Start Histology slide end"
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_flashcard_asset_refs.py -v
```

Expected: FAIL because the helper module does not exist yet.

**Step 3: Write the minimal implementation**

Implement helpers in `asset_refs.py`:
- `build_flashcard_asset_reference`
- `build_flashcard_asset_markdown`
- `extract_flashcard_asset_uuids`
- `sanitize_flashcard_text_for_search`
- `replace_markdown_asset_refs_for_export`

Use a single canonical scheme:

```python
FLASHCARD_ASSET_SCHEME = "flashcard-asset://"
```

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_flashcard_asset_refs.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add tldw_Server_API/app/core/Flashcards/asset_refs.py tldw_Server_API/tests/Flashcards/test_flashcard_asset_refs.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): add asset reference helpers"
```

### Task 2: Add Flashcard Asset Storage And Search-Safe Columns

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/Flashcards/test_flashcards_db_assets.py`

**Step 1: Write the failing tests**

Add DB tests for:
- creating a `flashcard_assets` record
- fetching asset metadata/content
- attaching referenced assets to a saved card
- detaching removed assets from a card
- backfilling `front_search`, `back_search`, and `notes_search`

Example test shape:

```python
def test_add_flashcard_asset_and_attach_to_card(chacha_db):
    asset_uuid = chacha_db.add_flashcard_asset(...)
    card_uuid = chacha_db.add_flashcard({...})
    chacha_db.reconcile_flashcard_asset_refs(card_uuid, front="![alt](flashcard-asset://%s)" % asset_uuid, back="", extra="", notes="")
    asset = chacha_db.get_flashcard_asset(asset_uuid)
    assert asset["card_uuid"] == card_uuid
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_db_assets.py -v
```

Expected: FAIL because the table/helpers do not exist.

**Step 3: Write the minimal implementation**

In `ChaChaNotes_DB.py`:
- add `flashcard_assets` schema bootstrap
- add migration/auto-heal logic for:
  - `flashcard_assets`
  - `front_search`, `back_search`, `notes_search`
- update flashcard FTS triggers to index sanitized search columns
- implement helpers:
  - `add_flashcard_asset`
  - `get_flashcard_asset`
  - `get_flashcard_asset_content`
  - `reconcile_flashcard_asset_refs`
  - `cleanup_stale_flashcard_assets`

Use the Task 1 sanitizer to populate the search columns on create/update/import.

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_db_assets.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/Flashcards/test_flashcards_db_assets.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): add asset storage and search fields"
```

### Task 3: Add Asset Upload And Content Endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- Possibly modify: `tldw_Server_API/app/core/Utils/image_validation.py`
- Test: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`

**Step 1: Write the failing tests**

Add endpoint integration tests for:
- `POST /api/v1/flashcards/assets` accepts valid image upload and returns `reference` + `markdown_snippet`
- invalid MIME or oversized upload is rejected
- `GET /api/v1/flashcards/assets/{uuid}/content` returns bytes + MIME
- create/update/bulk update reject missing or detached foreign refs

Example test shape:

```python
def test_upload_flashcard_asset_returns_markdown_snippet(client, auth_headers, png_bytes):
    response = client.post("/api/v1/flashcards/assets", files={"file": ("slide.png", png_bytes, "image/png")}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["markdown_snippet"].startswith("![")
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "flashcard_asset" -v
```

Expected: FAIL because the endpoints/schema do not exist.

**Step 3: Write the minimal implementation**

In `schemas/flashcards.py` add models for:
- upload response
- asset metadata response

In `endpoints/flashcards.py` add:
- `POST /assets`
- `GET /assets/{asset_uuid}/content`

Use DB helpers from Task 2 and image validation utilities to enforce:
- supported raster MIME types
- per-image byte cap
- deterministic markdown snippet generation

Extend create/update/bulk update endpoint flows to call asset reconciliation after the card mutation succeeds.

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "flashcard_asset" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add tldw_Server_API/app/api/v1/schemas/flashcards.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/app/core/Utils/image_validation.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): add asset upload and fetch endpoints"
```

### Task 4: Add APKG Import/Export Translation For Managed Assets

**Files:**
- Modify: `tldw_Server_API/app/core/Flashcards/apkg_exporter.py`
- Modify: `tldw_Server_API/app/core/Flashcards/apkg_importer.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- Modify: `tldw_Server_API/tests/Flashcards/test_apkg_exporter.py`
- Modify: `tldw_Server_API/tests/Flashcards/test_apkg_importer.py`
- Modify: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`

**Step 1: Write the failing tests**

Add tests for:
- exporting `flashcard-asset://` refs packages media into APKG
- exported `tldw` APKG models include hidden `Notes` field
- importing APKG media creates asset records and rewrites fields to markdown refs
- notes images round-trip for `tldw` APKG exports/imports
- total media byte cap rejects oversized APKG media payloads

Example test shape:

```python
def test_apkg_export_translates_internal_asset_refs_to_packaged_media():
    rows = [{"front": "![alt](flashcard-asset://asset-1)", ...}]
    apkg = export_apkg_from_rows(rows, asset_loader=...)
    ...
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_apkg_exporter.py tldw_Server_API/tests/Flashcards/test_apkg_importer.py -v
```

Expected: FAIL because the APKG pipeline does not understand internal refs or `Notes`.

**Step 3: Write the minimal implementation**

In `apkg_exporter.py`:
- translate managed markdown refs to HTML `<img>` tags before media extraction
- support an asset loader callback or pre-expanded row assets
- extend `tldw` export models with hidden `Notes`

In `apkg_importer.py`:
- parse model field names when available
- load the APKG `media` manifest and numbered media members
- rewrite imported image-bearing HTML/markdown into `flashcard-asset://` markdown refs
- preserve `notes` for `tldw`-exported models and explicit `Notes` fields

In `endpoints/flashcards.py`:
- enforce total APKG media byte caps on import/export

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Flashcards/test_apkg_exporter.py tldw_Server_API/tests/Flashcards/test_apkg_importer.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add tldw_Server_API/app/core/Flashcards/apkg_exporter.py tldw_Server_API/app/core/Flashcards/apkg_importer.py tldw_Server_API/app/api/v1/endpoints/flashcards.py tldw_Server_API/tests/Flashcards/test_apkg_exporter.py tldw_Server_API/tests/Flashcards/test_apkg_importer.py tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): add apkg image round trip"
```

### Task 5: Add Authenticated Managed Image Rendering In Markdown

**Files:**
- Modify: `apps/packages/ui/src/components/Common/Markdown.tsx`
- Create: `apps/packages/ui/src/components/Common/ManagedMarkdownImage.tsx`
- Create: `apps/packages/ui/src/services/flashcard-assets.ts`
- Test: `apps/packages/ui/src/components/Common/__tests__/Markdown.flashcard-asset-image.test.tsx`
- Test: `apps/packages/ui/src/services/__tests__/flashcard-assets.test.ts`

**Step 1: Write the failing tests**

Add tests for:
- `flashcard-asset://` refs resolve through authenticated fetch and render an `<img>`
- regular `http` and `data:` images keep existing behavior
- object URL caching prevents duplicate fetches for the same asset ref
- failure renders a small inline fallback instead of crashing markdown

Example test shape:

```tsx
it("resolves flashcard asset refs through the managed image component", async () => {
  render(<Markdown message="![alt](flashcard-asset://asset-1)" />)
  expect(await screen.findByRole("img", { name: "alt" })).toBeInTheDocument()
})
```

**Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run --config vitest.config.ts src/components/Common/__tests__/Markdown.flashcard-asset-image.test.tsx src/services/__tests__/flashcard-assets.test.ts
```

Expected: FAIL because the resolver/component does not exist.

**Step 3: Write the minimal implementation**

Implement:
- `flashcard-assets.ts`
  - parse asset UUID from `flashcard-asset://`
  - fetch arrayBuffer through authenticated request helpers
  - create/reuse blob URLs
- `ManagedMarkdownImage.tsx`
  - detect the custom scheme
  - lazy-resolve near viewport
  - render fallback on error
- wire `Markdown.tsx` image renderer to delegate custom-scheme refs to `ManagedMarkdownImage`

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run --config vitest.config.ts src/components/Common/__tests__/Markdown.flashcard-asset-image.test.tsx src/services/__tests__/flashcard-assets.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add apps/packages/ui/src/components/Common/Markdown.tsx apps/packages/ui/src/components/Common/ManagedMarkdownImage.tsx apps/packages/ui/src/services/flashcard-assets.ts apps/packages/ui/src/components/Common/__tests__/Markdown.flashcard-asset-image.test.tsx apps/packages/ui/src/services/__tests__/flashcard-assets.test.ts
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): resolve managed asset images in markdown"
```

### Task 6: Add Inline Image Insert Actions To Flashcard Editors

**Files:**
- Modify: `apps/packages/ui/src/services/flashcards.ts`
- Modify: `apps/packages/ui/src/components/Flashcards/components/FlashcardCreateDrawer.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/components/FlashcardEditDrawer.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentRow.tsx`
- Create: `apps/packages/ui/src/components/Flashcards/utils/insert-flashcard-asset-markdown.ts`
- Test: `apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.image-insert.test.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardEditDrawer.image-insert.test.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx`

**Step 1: Write the failing tests**

Add tests for:
- create drawer inserts returned markdown snippet into `front`, `back`, `extra`, and `notes`
- edit drawer does the same
- document-mode row editing inserts the snippet into the active field
- previews render the inserted image reference through markdown

Example test shape:

```tsx
it("inserts uploaded image markdown into the focused front field", async () => {
  render(<FlashcardCreateDrawer ... />)
  ...
  expect(textarea).toHaveValue("Before\n![alt](flashcard-asset://asset-1)")
})
```

**Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run --config vitest.config.ts src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.image-insert.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.image-insert.test.tsx src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx
```

Expected: FAIL because the upload helper and insert actions do not exist.

**Step 3: Write the minimal implementation**

In `services/flashcards.ts` add:
- upload asset request types
- `uploadFlashcardAsset`

In the flashcard editors:
- add `Insert image` actions for `front`, `back`, `extra`, `notes`
- wire to a hidden file input + upload helper
- insert returned markdown at cursor position or append with newline fallback

Use one shared helper in `insert-flashcard-asset-markdown.ts`.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run --config vitest.config.ts src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.image-insert.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.image-insert.test.tsx src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add apps/packages/ui/src/services/flashcards.ts apps/packages/ui/src/components/Flashcards/components/FlashcardCreateDrawer.tsx apps/packages/ui/src/components/Flashcards/components/FlashcardEditDrawer.tsx apps/packages/ui/src/components/Flashcards/components/FlashcardDocumentRow.tsx apps/packages/ui/src/components/Flashcards/utils/insert-flashcard-asset-markdown.ts apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.image-insert.test.tsx apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardEditDrawer.image-insert.test.tsx apps/packages/ui/src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "feat(flashcards): add inline image insert actions"
```

### Task 7: Update Docs And Run Verification

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`
- Modify: `Docs/Plans/2026-03-13-first-class-card-image-support-design.md` if implementation decisions need final wording sync

**Step 1: Update the user guide**

Document:
- supported fields
- insert-image flow
- asset reference behavior
- APKG notes round-trip caveat for `tldw` exports

**Step 2: Run backend verification**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Flashcards/test_flashcard_asset_refs.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_db_assets.py \
  tldw_Server_API/tests/Flashcards/test_apkg_exporter.py \
  tldw_Server_API/tests/Flashcards/test_apkg_importer.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py -k "flashcard_asset or apkg" -v
```

Expected: PASS.

**Step 3: Run frontend verification**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run --config vitest.config.ts \
  src/components/Common/__tests__/Markdown.flashcard-asset-image.test.tsx \
  src/services/__tests__/flashcard-assets.test.ts \
  src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.image-insert.test.tsx \
  src/components/Flashcards/components/__tests__/FlashcardEditDrawer.image-insert.test.tsx \
  src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx
```

Expected: PASS.

**Step 4: Run Bandit on touched backend scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/flashcards.py \
  tldw_Server_API/app/api/v1/schemas/flashcards.py \
  tldw_Server_API/app/core/Flashcards/asset_refs.py \
  tldw_Server_API/app/core/Flashcards/apkg_exporter.py \
  tldw_Server_API/app/core/Flashcards/apkg_importer.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  -f json -o /tmp/bandit_flashcards_image_support.json
```

Expected: JSON output with no new findings in touched code.

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "docs(flashcards): document inline image support"
```
