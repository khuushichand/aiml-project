# Notes Moodboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-class moodboards to Notes so users can build hybrid boards (manual pins + smart rules), browse a masonry wall with image covers, and open notes in the existing detail experience.

**Architecture:** Add dedicated `moodboards` and `moodboard_note_links` tables in ChaChaNotes, expose `/api/v1/notes/moodboards/*` endpoints, and integrate a third Notes view mode (`moodboard`) in `NotesManagerPage`. Reuse existing note detail and relation panels; only board management and board-content retrieval are new.

**Tech Stack:** FastAPI, Pydantic v2, ChaChaNotes_DB (SQLite/Postgres-compatible patterns), React + TanStack Query + Ant Design, Vitest, Pytest.

---

### Task 1: Add backend schema contracts for moodboards

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/notes_moodboards.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/__init__.py` (only if exports are used)
- Test: `tldw_Server_API/tests/Notes_NEW/unit/test_notes_moodboard_schemas.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.api.v1.schemas.notes_moodboards import MoodboardCreate


def test_moodboard_create_allows_hybrid_rule_payload():
    payload = MoodboardCreate(
        name="Research visuals",
        description="Design and writing references",
        smart_rule={
            "query": "design system",
            "keyword_tokens": ["ux", "ui"],
            "notebook_collection_ids": [1, 2],
            "sources": ["source:web:example.com"],
            "updated_after": None,
            "updated_before": None,
        },
    )
    assert payload.name == "Research visuals"
    assert payload.smart_rule["keyword_tokens"] == ["ux", "ui"]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_notes_moodboard_schemas.py::test_moodboard_create_allows_hybrid_rule_payload -v`
Expected: FAIL with import error for `notes_moodboards`.

**Step 3: Write minimal implementation**

```python
class MoodboardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    smart_rule: dict[str, Any] | None = None
```

Add full request/response models needed by API now to avoid piecemeal churn.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_notes_moodboard_schemas.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/notes_moodboards.py tldw_Server_API/tests/Notes_NEW/unit/test_notes_moodboard_schemas.py
git commit -m "test(notes): add moodboard schema contracts"
```

### Task 2: Add ChaChaNotes DB migration and moodboard CRUD

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py`

**Step 1: Write the failing test**

```python
def test_create_and_get_moodboard(db):
    moodboard_id = db.create_moodboard(name="Inspo", description="refs", smart_rule_json=None)
    row = db.get_moodboard_by_id(moodboard_id)
    assert row["name"] == "Inspo"
    assert row["deleted"] in (0, False)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py::test_create_and_get_moodboard -v`
Expected: FAIL with missing `create_moodboard`.

**Step 3: Write minimal implementation**

```python
CREATE TABLE IF NOT EXISTS moodboards(...);


def create_moodboard(...):
    ...

def get_moodboard_by_id(...):
    ...

def list_moodboards(...):
    ...

def update_moodboard(...):
    ...

def soft_delete_moodboard(...):
    ...
```

Implement via the same optimistic-lock and soft-delete patterns used by notes/keyword_collections.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py -k "create_and_get_moodboard" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py
git commit -m "feat(notes-db): add moodboard tables and CRUD"
```

### Task 3: Add moodboard membership methods (manual pin/unpin)

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py`

**Step 1: Write the failing test**

```python
def test_pin_unpin_note_idempotent(db):
    note_id = db.add_note("Title", "Body")
    moodboard_id = db.create_moodboard(name="Pins", description=None, smart_rule_json=None)

    assert db.add_note_to_moodboard(moodboard_id, note_id) is True
    assert db.add_note_to_moodboard(moodboard_id, note_id) is True

    links = db.list_moodboard_note_links(moodboard_id)
    assert len([l for l in links if l["note_id"] == note_id]) == 1

    assert db.remove_note_from_moodboard(moodboard_id, note_id) is True
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py::test_pin_unpin_note_idempotent -v`
Expected: FAIL with missing membership methods.

**Step 3: Write minimal implementation**

```python
CREATE TABLE IF NOT EXISTS moodboard_note_links(..., PRIMARY KEY(moodboard_id, note_id));


def add_note_to_moodboard(...):
    # INSERT OR IGNORE / ON CONFLICT DO NOTHING


def remove_note_from_moodboard(...):
    # DELETE ...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py -k "pin_unpin" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py
git commit -m "feat(notes-db): add moodboard manual membership links"
```

### Task 4: Add hybrid board content query (manual ∪ smart, dedup, cover image)

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/notes.py` (reuse attachment helpers if needed)
- Test: `tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py`

**Step 1: Write the failing test**

```python
def test_list_moodboard_notes_union_and_membership_source(db):
    # seed notes, keywords, manual pin, and smart-rule match overlap
    rows = db.list_moodboard_notes(moodboard_id=mid, limit=50, offset=0)
    by_id = {row["id"]: row for row in rows}
    assert by_id[manual_only_id]["membership_source"] == "manual"
    assert by_id[smart_only_id]["membership_source"] == "smart"
    assert by_id[both_id]["membership_source"] == "both"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py::test_list_moodboard_notes_union_and_membership_source -v`
Expected: FAIL with missing `list_moodboard_notes`.

**Step 3: Write minimal implementation**

```python
def list_moodboard_notes(self, moodboard_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
    # 1) load board + smart_rule_json
    # 2) collect manual IDs
    # 3) collect smart IDs via existing note search/filter methods
    # 4) union + annotate membership_source
    # 5) return note summaries newest-first
```

Populate `cover_image_url` by resolving first image attachment from note attachment metadata directory.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py -k "membership_source" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py
git commit -m "feat(notes-db): add hybrid moodboard content query"
```

### Task 5: Add FastAPI moodboard endpoints

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/notes_moodboards.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Notes_NEW/integration/test_notes_moodboards_api.py`

**Step 1: Write the failing test**

```python
def test_create_list_get_moodboard(client_with_notes_db):
    create = client_with_notes_db.post("/api/v1/notes/moodboards", json={"name": "Board A"})
    assert create.status_code == 201
    mid = create.json()["id"]

    lst = client_with_notes_db.get("/api/v1/notes/moodboards")
    assert lst.status_code == 200
    assert any(item["id"] == mid for item in lst.json().get("items", []))
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/integration/test_notes_moodboards_api.py::test_create_list_get_moodboard -v`
Expected: FAIL with 404 route not found.

**Step 3: Write minimal implementation**

```python
router = APIRouter()

@router.post("/moodboards", response_model=MoodboardResponse, status_code=201)
async def create_moodboard(...): ...

@router.get("/moodboards", response_model=MoodboardListResponse)
async def list_moodboards(...): ...
```

Wire router in `main.py` with `/api/v1/notes` prefix (same scope/tag family as Notes).

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/integration/test_notes_moodboards_api.py -k "create_list_get" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/notes_moodboards.py tldw_Server_API/app/main.py tldw_Server_API/tests/Notes_NEW/integration/test_notes_moodboards_api.py
git commit -m "feat(notes-api): add moodboard CRUD endpoints"
```

### Task 6: Add membership + content endpoints (`/notes/{id}` + `/moodboards/{id}/notes`)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/notes_moodboards.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/notes_moodboards.py`
- Test: `tldw_Server_API/tests/Notes_NEW/integration/test_notes_moodboards_api.py`

**Step 1: Write the failing test**

```python
def test_moodboard_note_membership_and_content_listing(client_with_notes_db):
    # create notes + board, pin one note
    pin = client.post(f"/api/v1/notes/moodboards/{mid}/notes/{note_id}")
    assert pin.status_code == 200

    content = client.get(f"/api/v1/notes/moodboards/{mid}/notes", params={"limit": 20, "offset": 0})
    assert content.status_code == 200
    assert any(row["id"] == note_id for row in content.json().get("items", []))
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/integration/test_notes_moodboards_api.py::test_moodboard_note_membership_and_content_listing -v`
Expected: FAIL with 404/501 for membership endpoints.

**Step 3: Write minimal implementation**

```python
@router.post("/moodboards/{moodboard_id}/notes/{note_id}")
async def pin_note(...): ...

@router.delete("/moodboards/{moodboard_id}/notes/{note_id}")
async def unpin_note(...): ...

@router.get("/moodboards/{moodboard_id}/notes", response_model=MoodboardNotesListResponse)
async def list_moodboard_notes(...): ...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/integration/test_notes_moodboards_api.py -k "membership_and_content" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/notes_moodboards.py tldw_Server_API/app/api/v1/schemas/notes_moodboards.py tldw_Server_API/tests/Notes_NEW/integration/test_notes_moodboards_api.py
git commit -m "feat(notes-api): add moodboard membership and content endpoints"
```

### Task 7: Add frontend API client support for moodboards

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Create: `apps/packages/ui/src/components/Notes/moodboards-api.ts` (optional wrapper helpers)
- Test: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx`

**Step 1: Write the failing test**

```tsx
it("loads moodboard list when moodboard mode is selected", async () => {
  // mock bgRequest for /api/v1/notes/moodboards
  // click Moodboard toggle
  // assert board entries render
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx`
Expected: FAIL because moodboard mode/UI client methods do not exist.

**Step 3: Write minimal implementation**

```ts
async listMoodboards(...) { ... }
async createMoodboard(...) { ... }
async listMoodboardNotes(...) { ... }
async pinMoodboardNote(...) { ... }
```

Use existing `bgRequest` patterns and query param builders from nearby Notes methods.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/components/Notes/moodboards-api.ts apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx
git commit -m "feat(notes-ui): add moodboard API client methods"
```

### Task 8: Add moodboard UI components and integrate third Notes view mode

**Files:**
- Create: `apps/packages/ui/src/components/Notes/MoodboardWall.tsx`
- Create: `apps/packages/ui/src/components/Notes/MoodboardSidebar.tsx`
- Modify: `apps/packages/ui/src/components/Notes/types.ts`
- Modify: `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
- Test: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx`
- Test: `apps/packages/ui/src/components/Notes/__tests__/MoodboardWall.stage1.cover-fallback.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("renders image card when cover_image_url exists and text fallback otherwise", () => {
  // render MoodboardWall with 2 cards
  // assert <img> for one and text fallback for second
})

it("opens note detail when moodboard card is clicked", async () => {
  // click card
  // assert existing selected note editor content loads
})
```

**Step 2: Run tests to verify they fail**

Run: `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/MoodboardWall.stage1.cover-fallback.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx`
Expected: FAIL due missing components and view mode.

**Step 3: Write minimal implementation**

```tsx
type NotesListViewMode = "list" | "timeline" | "moodboard"

{listViewMode === "moodboard" ? (
  <MoodboardWall items={moodboardItems} onOpenNote={handleSelectNote} />
) : ...}
```

Add masonry layout and keep note-open behavior wired to current selection/detail flow.

**Step 4: Run tests to verify they pass**

Run: `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/MoodboardWall.stage1.cover-fallback.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Notes/MoodboardWall.tsx apps/packages/ui/src/components/Notes/MoodboardSidebar.tsx apps/packages/ui/src/components/Notes/types.ts apps/packages/ui/src/components/Notes/NotesManagerPage.tsx apps/packages/ui/src/components/Notes/__tests__/MoodboardWall.stage1.cover-fallback.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx
git commit -m "feat(notes-ui): add moodboard mode and masonry wall"
```

### Task 9: Add compact associated-items strip behavior checks in moodboard flow

**Files:**
- Modify: `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
- Test: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.moodboard-associated-strip.test.tsx`

**Step 1: Write the failing test**

```tsx
it("shows compact related/backlinks/sources strip after opening note from moodboard", async () => {
  // open moodboard note
  // assert relation panel headings and chips are visible
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.moodboard-associated-strip.test.tsx`
Expected: FAIL because flow is not yet asserting/reaching relation strip after moodboard open.

**Step 3: Write minimal implementation**

```tsx
// Ensure moodboard card open path uses existing handleSelectNote + relation query triggers
```

No new relation system; reuse existing `noteRelations` panels.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.moodboard-associated-strip.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Notes/NotesManagerPage.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.moodboard-associated-strip.test.tsx
git commit -m "test(notes-ui): verify associated strip after moodboard open"
```

### Task 10: Add locale strings and docs updates

**Files:**
- Modify: `apps/packages/ui/src/assets/locale/en/option.json`
- Modify: `apps/packages/ui/src/public/_locales/en/option.json`
- Modify: `Docs/Design/Note_Taking.md`
- Test: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx`

**Step 1: Write/update a failing assertion for copy key usage**

```tsx
expect(screen.getByText("Moodboard")).toBeInTheDocument()
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx`
Expected: FAIL when translation key/default text is missing.

**Step 3: Write minimal implementation**

Add keys for:
- moodboard view mode button
- empty moodboard states
- create/edit/delete board actions
- membership source labels (`manual`, `smart`, `both`)

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/assets/locale/en/option.json apps/packages/ui/src/public/_locales/en/option.json Docs/Design/Note_Taking.md
git commit -m "docs/ui: add moodboard copy and notes design updates"
```

### Task 11: Full verification and security gate

**Files:**
- Verify touched backend/frontend files from prior tasks.

**Step 1: Run focused backend notes tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_moodboard_db.py tldw_Server_API/tests/Notes_NEW/unit/test_notes_moodboard_schemas.py tldw_Server_API/tests/Notes_NEW/integration/test_notes_moodboards_api.py -v`
Expected: PASS

**Step 2: Run focused frontend tests**

Run: `bunx vitest run apps/packages/ui/src/components/Notes/__tests__/MoodboardWall.stage1.cover-fallback.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage42.moodboard-mode.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage43.moodboard-associated-strip.test.tsx`
Expected: PASS

**Step 3: Run Bandit on touched backend scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/notes_moodboards.py tldw_Server_API/app/api/v1/schemas/notes_moodboards.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py -f json -o /tmp/bandit_notes_moodboard.json`
Expected: JSON report generated, no new high-confidence issues in touched code.

**Step 4: Sanity check git diff and commit final fixes**

Run: `git status --short && git diff --stat`
Expected: Only intended moodboard changes remain.

**Step 5: Commit**

```bash
git add <all moodboard-related files>
git commit -m "feat(notes): add hybrid moodboards with image-first board view"
```

### Task 12: Completion checks and handoff

**Files:**
- Modify: `Docs/Plans/2026-02-27-notes-moodboard-implementation-plan.md` (mark execution notes)
- Optional: `CHANGELOG.md`

**Step 1: Record what was executed vs deferred**

```markdown
## Execution Notes
- Completed tasks: ...
- Deferred tasks: ...
```

**Step 2: Run final smoke checks**

Run: `source .venv/bin/activate && python -m pytest -m "integration" -k "notes and moodboard" -v`
Expected: PASS or documented skip reasons.

**Step 3: Prepare reviewer summary**

Include:
- API endpoints added
- DB migration version
- UI entry points
- Test evidence commands run

**Step 4: Commit**

```bash
git add Docs/Plans/2026-02-27-notes-moodboard-implementation-plan.md CHANGELOG.md
git commit -m "docs: finalize moodboard implementation handoff notes"
```

**Step 5: Open PR with verification evidence**

```bash
git push
# open PR with test + bandit results in description
```
