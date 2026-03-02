# Collections Pinboard Utility Parity (Strict Notes Boundary) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute this plan task-by-task in this session.

**Goal:** Add Pinboard-style utility improvements to Collections (saved searches, archive-on-save controls, dead-link resilience, and Notes linking) while keeping Notes as the only standalone note system.

**Architecture:** Extend Reading/Collections APIs and DB tables with additive models (`saved_searches`, `content_item_note_links`) and enrich existing reading save/detail contracts. Reuse `/api/v1/notes` for note creation/content ownership and enforce note existence/ownership checks before creating links. Gate new surfaces behind focused feature flags (`collections_reading_saved_searches_enabled`, `collections_reading_note_links_enabled`, `collections_reading_archive_controls_enabled`) while preserving existing reading and notes flows.

**Tech Stack:** FastAPI, Pydantic, CollectionsDatabase (SQLite/PG backend abstraction), React + Zustand + Ant Design, Vitest, Pytest.

**Execution Guardrails:**
- Run all frontend Vitest commands from `apps/packages/ui` (or set equivalent Vitest root/config) to avoid path-alias resolution failures and accidental `.worktrees` test discovery.
- Verify in staged checkpoints: backend scope first, frontend API contracts second, UI flows last.

---

### Task 1: Add Reading API Schemas for Archive Mode, Saved Searches, and Link Responses

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/reading_schemas.py`
- Test: `tldw_Server_API/tests/Collections/test_reading_api.py`

**Step 1: Write the failing test**

```python
def test_reading_save_returns_archive_requested_field(reading_app):
    async def override_user():
        return User(id=9001, username="reader", email=None, is_active=True)

    reading_app.dependency_overrides[get_request_user] = override_user
    with TestClient(reading_app) as client:
        r = client.post(
            "/api/v1/reading/save",
            json={
                "url": "https://example.org/archive-test",
                "title": "Archive Test",
                "content": "Archive content",
                "archive_mode": "always",
            },
        )
        assert r.status_code == 200, r.text
        assert "archive_requested" in r.json()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_api.py -k archive_requested -v`
Expected: FAIL because response lacks `archive_requested`.

**Step 3: Write minimal implementation**

```python
class ReadingSaveRequest(BaseModel):
    archive_mode: Literal["use_default", "always", "never"] = "use_default"

class ReadingItem(BaseModel):
    archive_requested: bool = False
    has_archive_copy: bool = False
    last_fetch_error: str | None = None

class ReadingSavedSearchCreateRequest(BaseModel): ...
class ReadingSavedSearchUpdateRequest(BaseModel): ...
class ReadingSavedSearchResponse(BaseModel): ...
class ReadingNoteLinkResponse(BaseModel): ...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_api.py -k archive_requested -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/reading_schemas.py tldw_Server_API/tests/Collections/test_reading_api.py
git commit -m "feat(reading-schema): add archive mode and saved-search/note-link schemas"
```

### Task 2: Add Collections DB Tables and Accessors (`saved_searches`, `content_item_note_links`)

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Collections_DB.py`
- Create: `tldw_Server_API/tests/Collections/test_reading_saved_searches_db.py`
- Create: `tldw_Server_API/tests/Collections/test_reading_note_links_db.py`

**Step 1: Write the failing test**

```python
def test_saved_search_crud_roundtrip(collections_db):
    created = collections_db.create_saved_search(name="Morning", query_json='{"q":"ai"}', sort="updated_desc")
    rows, total = collections_db.list_saved_searches(limit=10, offset=0)
    assert total == 1
    assert rows[0].id == created.id
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_saved_searches_db.py -v`
Expected: FAIL with missing table or missing method errors.

**Step 3: Write minimal implementation**

```python
CREATE TABLE IF NOT EXISTS saved_searches (...);
CREATE TABLE IF NOT EXISTS content_item_note_links (...);

def create_saved_search(...): ...
def list_saved_searches(...): ...
def update_saved_search(...): ...
def delete_saved_search(...): ...
def link_note_to_content_item(...): ...
def list_note_links_for_content_item(...): ...
def unlink_note_from_content_item(...): ...
```

**Step 4: Run test to verify it passes**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_saved_searches_db.py -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_note_links_db.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Collections_DB.py tldw_Server_API/tests/Collections/test_reading_saved_searches_db.py tldw_Server_API/tests/Collections/test_reading_note_links_db.py
git commit -m "feat(collections-db): add saved searches and content-item note links"
```

### Task 3: Add Reading Endpoints for Saved Searches and Note Link CRUD (POST/GET/DELETE)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/reading.py`
- Test: `tldw_Server_API/tests/Collections/test_reading_api.py`

**Step 1: Write the failing test**

```python
def test_note_link_endpoints_cover_post_get_delete(reading_app):
    async def override_user():
        return User(id=9002, username="reader2", email=None, is_active=True)
    reading_app.dependency_overrides[get_request_user] = override_user
    with TestClient(reading_app) as client:
        # setup reading item...
        # POST link -> 200
        # GET links -> contains note_id
        # DELETE link -> success
        ...
```

Add an explicit boundary regression test in this task:

```python
def test_note_link_rejects_foreign_note(reading_app):
    # User A creates a note; user B attempts to link it.
    # Expected strict-boundary behavior: 404 (preferred) or 403.
    ...
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_api.py -k "saved_searches or note_link or foreign_note" -v`
Expected: FAIL with `404` route not found.

**Step 3: Write minimal implementation**

```python
@router.post("/saved-searches", status_code=201) ...
@router.get("/saved-searches") ...
@router.patch("/saved-searches/{search_id}") ...
@router.delete("/saved-searches/{search_id}") ...

@router.post("/items/{item_id}/links/note") ...
@router.get("/items/{item_id}/links") ...
@router.delete("/items/{item_id}/links/note/{note_id}") ...
```

Add strict boundary enforcement:
- validate note exists via Notes DB lookup for current user before linking
- reject foreign/missing note IDs with `404` or `403` as appropriate

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_api.py -k "saved_searches or note_link or foreign_note" -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/reading.py tldw_Server_API/tests/Collections/test_reading_api.py
git commit -m "feat(reading-api): add saved-search CRUD and note-link CRUD endpoints"
```

### Task 4: Implement Archive Policy Resolution with Real Auto-Archive + Resilience Metadata

**Files:**
- Modify: `tldw_Server_API/app/core/Collections/reading_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/reading.py`
- Test: `tldw_Server_API/tests/Collections/test_reading_service.py`
- Test: `tldw_Server_API/tests/Collections/test_reading_api.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_archive_mode_always_creates_archive_artifact(...):
    result = await service.save_url(url="https://example.org/a", archive_mode="always", content_override="hello")
    assert result.archive_requested is True
    assert result.archive_output_id is not None
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_service.py -k "archive_mode or archive_artifact" -v`
Expected: FAIL with missing argument/attribute/artifact.

**Step 3: Write minimal implementation**

```python
def _resolve_archive_mode(requested: str, default_enabled: bool) -> bool: ...

async def save_url(..., archive_mode: str = "use_default") -> ReadingSaveResult:
    archive_requested = _resolve_archive_mode(archive_mode, default_enabled)
    if archive_requested:
        archive_output_id = await maybe_create_archive_artifact(...)
    return ReadingSaveResult(..., archive_requested=archive_requested, archive_output_id=archive_output_id)
```

Expose in reading item/detail response:
- `archive_requested`
- `has_archive_copy`
- `last_fetch_error`

**Step 4: Run test to verify it passes**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_service.py -k "archive_mode or archive_artifact" -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_api.py -k "archive_requested or has_archive_copy" -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Collections/reading_service.py tldw_Server_API/app/api/v1/endpoints/reading.py tldw_Server_API/tests/Collections/test_reading_service.py tldw_Server_API/tests/Collections/test_reading_api.py
git commit -m "feat(reading): implement archive policy and resilience metadata"
```

### Task 5: Extend Frontend Types and API Client Contracts (with mocked transport tests)

**Files:**
- Modify: `apps/packages/ui/src/types/collections.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Create: `apps/packages/ui/src/services/tldw/__tests__/reading-saved-searches.test.ts`

**Step 1: Write the failing test**

```ts
import { vi } from "vitest"
vi.mock("@/services/background-proxy", () => ({ bgRequest: vi.fn() }))

it("posts create saved-search payload", async () => {
  const api = new TldwApiClient()
  await api.createReadingSavedSearch({ name: "Daily", query: { q: "ai" } })
  expect(bgRequest).toHaveBeenCalledWith(expect.objectContaining({
    path: "/api/v1/reading/saved-searches",
    method: "POST"
  }))
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/reading-saved-searches.test.ts`
Expected: FAIL with missing method/type errors.

**Step 3: Write minimal implementation**

```ts
export interface ReadingSavedSearch { ... }

async createReadingSavedSearch(...) { ... }
async listReadingSavedSearches(...) { ... }
async updateReadingSavedSearch(...) { ... }
async deleteReadingSavedSearch(...) { ... }
async linkReadingItemToNote(...) { ... }
async listReadingItemNoteLinks(...) { ... }
async unlinkReadingItemNote(...) { ... }
```

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/reading-saved-searches.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/types/collections.ts apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/services/tldw/__tests__/reading-saved-searches.test.ts
git commit -m "feat(frontend-api): add saved-search and note-link client contracts"
```

### Task 5A: Add Feature Flags for New Collections Surfaces

**Files:**
- Modify: `tldw_Server_API/app/core/config.py` (or equivalent runtime config surface)
- Modify: `tldw_Server_API/app/api/v1/endpoints/reading.py` (flag-aware route/UI-contract gating where applicable)
- Modify: `apps/packages/ui/src/store/collections.tsx` (or equivalent capability/feature-flag integration point)
- Test: `tldw_Server_API/tests/Collections/test_reading_api.py`
- Test: `apps/packages/ui/src/services/tldw/__tests__/reading-saved-searches.test.ts`

**Step 1: Write failing tests**

Add tests that prove:
- New collections surfaces are disabled when the relevant flags are off.
- Existing Reading + Notes flows remain unaffected when flags are off.
- New surfaces are enabled when flags are on.

**Step 2: Run tests to verify failures**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_api.py -k "feature_flag or note_link or saved_searches" -v`
- `cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/reading-saved-searches.test.ts`

Expected: FAIL until flags are wired.

**Step 3: Write minimal implementation**

Implement the three flags and wire them into backend/frontend capability checks:
- `collections_reading_saved_searches_enabled`
- `collections_reading_note_links_enabled`
- `collections_reading_archive_controls_enabled`

**Step 4: Run tests to verify pass**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_api.py -k "feature_flag or note_link or saved_searches" -v`
- `cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/reading-saved-searches.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/config.py tldw_Server_API/app/api/v1/endpoints/reading.py apps/packages/ui/src/store/collections.tsx tldw_Server_API/tests/Collections/test_reading_api.py apps/packages/ui/src/services/tldw/__tests__/reading-saved-searches.test.ts
git commit -m "feat(collections-flags): gate saved-searches note-links and archive-controls"
```

### Task 6: Add Saved Searches and Archive Controls to Reading List UI

**Files:**
- Modify: `apps/packages/ui/src/store/collections.tsx`
- Modify: `apps/packages/ui/src/components/Option/Collections/ReadingList/AddUrlModal.tsx`
- Modify: `apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemsList.tsx`
- Create: `apps/packages/ui/src/components/Option/Collections/ReadingList/SavedSearchesMenu.tsx`
- Create: `apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/saved-searches-menu.test.tsx`

**Step 1: Write the failing test**

```tsx
it("applies a saved search to reading filters", async () => {
  render(<SavedSearchesMenu ... />)
  await user.click(screen.getByText("Daily AI"))
  expect(onApply).toHaveBeenCalled()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Collections/ReadingList/__tests__/saved-searches-menu.test.tsx`
Expected: FAIL with missing component/state wiring.

**Step 3: Write minimal implementation**

```tsx
<SavedSearchesMenu
  searches={savedSearches}
  onApply={applySavedSearch}
  onCreateFromCurrent={createSavedSearchFromFilters}
/>
```

Add Add-URL control for `archive_mode`.

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Collections/ReadingList/__tests__/saved-searches-menu.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/collections.tsx apps/packages/ui/src/components/Option/Collections/ReadingList/AddUrlModal.tsx apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemsList.tsx apps/packages/ui/src/components/Option/Collections/ReadingList/SavedSearchesMenu.tsx apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/saved-searches-menu.test.tsx
git commit -m "feat(collections-ui): add saved searches and archive controls"
```

### Task 7: Add Linked Notes Panel to Reading Item Detail

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemDetail.tsx`
- Modify: `apps/packages/ui/src/types/collections.ts`
- Create: `apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/reading-item-detail-note-links.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders linked notes and supports unlink", async () => {
  render(<ReadingItemDetail ... />)
  expect(await screen.findByText("Linked Notes")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: /unlink/i }))
  expect(api.unlinkReadingItemNote).toHaveBeenCalled()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Collections/ReadingList/__tests__/reading-item-detail-note-links.test.tsx`
Expected: FAIL with missing linked-notes UI/actions.

**Step 3: Write minimal implementation**

```tsx
<Card title={t("collections:reading.linkedNotes", "Linked Notes")}>
  {linkedNotes.map((note) => (
    <Button onClick={() => unlink(note.note_id)}>Unlink</Button>
  ))}
</Card>
```

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Collections/ReadingList/__tests__/reading-item-detail-note-links.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemDetail.tsx apps/packages/ui/src/types/collections.ts apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/reading-item-detail-note-links.test.tsx
git commit -m "feat(collections-ui): add linked notes panel in reading detail"
```

### Task 8: Full Verification, Security Scan, and Docs Sync (Staged Checkpoints)

**Files:**
- Modify: `Docs/Product/Completed/Content_Collections_UX_Backlog_PRD.md`
- Verify: touched backend/frontend test files

**Step 1: Write final verification checklist**

```text
Checklist:
- Reading API tests pass
- Collections DB tests pass
- New frontend tests pass
- Bandit clean on touched backend paths
```

**Step 2: Run verification commands**

Run Stage A (Backend):
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_api.py tldw_Server_API/tests/Collections/test_reading_service.py tldw_Server_API/tests/Collections/test_reading_saved_searches_db.py tldw_Server_API/tests/Collections/test_reading_note_links_db.py -v`
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/reading.py tldw_Server_API/app/core/Collections/reading_service.py tldw_Server_API/app/core/DB_Management/Collections_DB.py -f json -o /tmp/bandit_collections_pinboard.json`

Run Stage B (Frontend API Contracts):
- `cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/reading-saved-searches.test.ts src/services/__tests__/tldw-api-client.reading-import-export.test.ts`

Run Stage C (Frontend UI, only after Tasks 6/7 complete):
- `cd apps/packages/ui && bunx vitest run src/components/Option/Collections/ReadingList/__tests__/saved-searches-menu.test.tsx src/components/Option/Collections/ReadingList/__tests__/reading-item-detail-note-links.test.tsx`

Expected: each stage PASS; Bandit reports no new high-confidence issues in touched code.

**Step 3: Update docs minimally**

```markdown
- Add saved searches and item-note linking to Collections capabilities.
- Document strict Notes boundary explicitly.
```

**Step 4: Re-run narrow sanity checks**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reading_api.py -k "saved_searches or note_link or archive_requested" -v`
- `cd apps/packages/ui && bunx vitest run src/components/Option/Collections/ReadingList/__tests__/saved-searches-menu.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/Product/Completed/Content_Collections_UX_Backlog_PRD.md
git add tldw_Server_API/app/api/v1/schemas/reading_schemas.py
git add tldw_Server_API/app/api/v1/endpoints/reading.py
git add tldw_Server_API/app/core/Collections/reading_service.py
git add tldw_Server_API/app/core/DB_Management/Collections_DB.py
git add tldw_Server_API/tests/Collections/test_reading_api.py
git add tldw_Server_API/tests/Collections/test_reading_service.py
git add tldw_Server_API/tests/Collections/test_reading_saved_searches_db.py
git add tldw_Server_API/tests/Collections/test_reading_note_links_db.py
git add apps/packages/ui/src/types/collections.ts
git add apps/packages/ui/src/services/tldw/TldwApiClient.ts
git add apps/packages/ui/src/services/tldw/__tests__/reading-saved-searches.test.ts
git add apps/packages/ui/src/store/collections.tsx
git add apps/packages/ui/src/components/Option/Collections/ReadingList/AddUrlModal.tsx
git add apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemsList.tsx
git add apps/packages/ui/src/components/Option/Collections/ReadingList/SavedSearchesMenu.tsx
git add apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/saved-searches-menu.test.tsx
git add apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemDetail.tsx
git add apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/reading-item-detail-note-links.test.tsx
git commit -m "feat(collections): deliver pinboard utility parity with strict notes boundary"
```
