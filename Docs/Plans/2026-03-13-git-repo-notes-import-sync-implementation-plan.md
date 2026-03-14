# Git Repo Notes Import and Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `git_repository`-backed one-time import and ongoing sync for Notes, with dedicated Notes folder primitives and GitHub-only remote support in V1.

**Architecture:** Extend the existing `ingestion_sources` subsystem instead of adding a parallel Notes-only importer. Keep local and remote repo ingestion on the same snapshot and diff pipeline, add dedicated Notes folder tables and APIs instead of overloading smart collections, and explicitly keep V1 rename semantics as delete plus create.

**Tech Stack:** FastAPI, Pydantic v2, SQLite/PostgreSQL-backed `ChaChaNotes_DB`, existing `ingestion_sources` Jobs worker, React, TypeScript, Ant Design, Vitest, Pytest, Bandit.

---

### Task 1: Add `git_repository` source type contracts

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Sources/models.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/ingestion_sources.py`
- Modify: `tldw_Server_API/app/core/Ingestion_Sources/service.py`
- Modify: `apps/packages/ui/src/types/ingestion-sources.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Test: `apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts`
- Test: `apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_git_repository_source_contract.py`

**Step 1: Write the failing backend contract test**

```python
def test_normalize_source_payload_accepts_git_repository():
    from tldw_Server_API.app.core.Ingestion_Sources.service import normalize_source_payload

    payload = normalize_source_payload(
        {
            "source_type": "git_repository",
            "sink_type": "notes",
            "policy": "import_only",
        }
    )

    assert payload["source_type"] == "git_repository"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_git_repository_source_contract.py::test_normalize_source_payload_accepts_git_repository -v
```

Expected: FAIL because `git_repository` is not in allowed source types.

**Step 3: Write minimal implementation**

Add `git_repository` to:

- `SourceType`
- `SOURCE_TYPES`
- `IngestionSourceCreateRequest`
- `IngestionSourcePatchRequest`
- frontend `IngestionSourceType`
- Tldw API client normalization

Example target shape:

```python
SourceType = Literal["local_directory", "archive_snapshot", "git_repository"]
SOURCE_TYPES: frozenset[str] = frozenset({"local_directory", "archive_snapshot", "git_repository"})
```

**Step 4: Run backend and frontend contract tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_git_repository_source_contract.py -v
```

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx
```

Expected: PASS with `git_repository` recognized as a legal source type.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/models.py tldw_Server_API/app/api/v1/schemas/ingestion_sources.py tldw_Server_API/app/core/Ingestion_Sources/service.py apps/packages/ui/src/types/ingestion-sources.ts apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx tldw_Server_API/tests/Ingestion_Sources/test_git_repository_source_contract.py
git commit -m "feat(sources): add git repository source type contracts"
```

### Task 2: Add dedicated Notes folder database primitives

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Create: `tldw_Server_API/tests/Notes_NEW/unit/test_note_folders_db.py`

**Step 1: Write the failing database tests**

```python
def test_add_note_folder_creates_hierarchical_folder(tmp_notes_db):
    folder_id = tmp_notes_db.add_note_folder(name="api", parent_id=None)
    row = tmp_notes_db.get_note_folder_by_id(folder_id)
    assert row["name"] == "api"


def test_link_note_to_folder_round_trips_membership(tmp_notes_db):
    note_id = tmp_notes_db.add_note(title="A", content="B")
    folder_id = tmp_notes_db.add_note_folder(name="docs", parent_id=None)

    assert tmp_notes_db.link_note_to_folder(note_id, folder_id) is True
    folders = tmp_notes_db.get_folders_for_note(note_id)
    assert [row["id"] for row in folders] == [folder_id]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_note_folders_db.py -v
```

Expected: FAIL with missing DB methods and schema.

**Step 3: Write minimal implementation**

Add schema and helpers for:

- `note_folders`
- `note_folder_memberships`
- `add_note_folder`
- `get_note_folder_by_id`
- `list_note_folders`
- `update_note_folder`
- `soft_delete_note_folder`
- `link_note_to_folder`
- `unlink_note_from_folder`
- `get_folders_for_note`
- `get_notes_for_folder`

Keep folder provenance in a structured field such as `provenance_json`.

Example schema target:

```sql
CREATE TABLE IF NOT EXISTS note_folders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  parent_id INTEGER REFERENCES note_folders(id) ON DELETE SET NULL,
  provenance_json TEXT NOT NULL DEFAULT '{}',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  client_id TEXT NOT NULL DEFAULT 'unknown',
  version INTEGER NOT NULL DEFAULT 1
);
```

**Step 4: Run tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_note_folders_db.py -v
```

Expected: PASS for folder CRUD and note membership round-trips.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/Notes_NEW/unit/test_note_folders_db.py
git commit -m "feat(notes-db): add dedicated note folder primitives"
```

### Task 3: Add Notes folder API schemas and endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/notes.py`
- Create: `tldw_Server_API/tests/Notes_NEW/integration/test_note_folders_api.py`

**Step 1: Write the failing API tests**

```python
def test_create_note_folder_endpoint(client):
    response = client.post("/api/v1/notes/folders", json={"name": "docs"})
    assert response.status_code == 201
    assert response.json()["name"] == "docs"


def test_link_note_to_folder_endpoint(client):
    note = client.post("/api/v1/notes", json={"title": "A", "content": "B"}).json()
    folder = client.post("/api/v1/notes/folders", json={"name": "docs"}).json()

    response = client.post(f"/api/v1/notes/{note['id']}/folders/{folder['id']}")
    assert response.status_code == 200
```

**Step 2: Run tests to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/integration/test_note_folders_api.py -v
```

Expected: FAIL with missing routes and schema models.

**Step 3: Write minimal implementation**

Add API models for:

- `NoteFolderCreate`
- `NoteFolderUpdate`
- `NoteFolderResponse`
- `NoteFoldersListResponse`
- `NoteFolderMembershipResponse`

Add endpoints for:

- `POST /api/v1/notes/folders`
- `GET /api/v1/notes/folders`
- `PATCH /api/v1/notes/folders/{folder_id}`
- `DELETE /api/v1/notes/folders/{folder_id}`
- `POST /api/v1/notes/{note_id}/folders/{folder_id}`
- `DELETE /api/v1/notes/{note_id}/folders/{folder_id}`
- `GET /api/v1/notes/{note_id}/folders`

**Step 4: Run API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notes_NEW/integration/test_note_folders_api.py -v
```

Expected: PASS for folder CRUD and membership endpoints.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/notes_schemas.py tldw_Server_API/app/api/v1/endpoints/notes.py tldw_Server_API/tests/Notes_NEW/integration/test_note_folders_api.py
git commit -m "feat(notes-api): add note folder endpoints"
```

### Task 4: Implement local git repository snapshot building

**Files:**
- Create: `tldw_Server_API/app/core/Ingestion_Sources/git_repository.py`
- Modify: `tldw_Server_API/app/services/ingestion_sources_worker.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_git_repository_snapshot.py`

**Step 1: Write the failing snapshot tests**

```python
def test_build_git_repository_snapshot_filters_supported_note_files(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "docs.md").write_text("# Title", encoding="utf-8")
    (repo_root / "binary.pdf").write_text("ignored", encoding="utf-8")

    from tldw_Server_API.app.core.Ingestion_Sources.git_repository import build_git_repository_snapshot_with_failures

    items, failures = build_git_repository_snapshot_with_failures(
        {"mode": "local_repo", "path": str(repo_root)},
        sink_type="notes",
    )

    assert "docs.md" in items
    assert "binary.pdf" not in items
    assert failures == {}
```

**Step 2: Run test to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_git_repository_snapshot.py -v
```

Expected: FAIL because the snapshot builder module does not exist.

**Step 3: Write minimal implementation**

Implement:

- local repo validation
- `.git` exclusion
- supported suffix filtering for Notes
- optional `root_subpath`
- relative-path normalization
- `HEAD` and dirty-state diagnostics in snapshot metadata

Example entry shape:

```python
{
    "relative_path": "docs.md",
    "content_hash": "...",
    "source_format": "markdown",
    "text": "# Title",
    "raw_metadata": {"repo_head_sha": "...", "repo_dirty": False},
}
```

**Step 4: Run tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_git_repository_snapshot.py -v
```

Expected: PASS for local repo scanning and file filtering.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/git_repository.py tldw_Server_API/app/services/ingestion_sources_worker.py tldw_Server_API/tests/Ingestion_Sources/test_git_repository_snapshot.py
git commit -m "feat(sources): add local git repository snapshot builder"
```

### Task 5: Extend notes sync binding for repo-managed folders and split detach state

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Sources/sinks/notes_sink.py`
- Modify: `tldw_Server_API/app/services/ingestion_sources_worker.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_git_notes_sink.py`

**Step 1: Write the failing sink tests**

```python
def test_git_notes_sink_updates_repo_managed_folders_but_preserves_user_added_folders(fake_notes_db):
    from tldw_Server_API.app.core.Ingestion_Sources.sinks.notes_sink import apply_notes_change

    binding = {
        "note_id": "n-1",
        "current_version": 2,
        "sync_status": "sync_managed",
        "repo_folder_ids": [10, 11],
        "content_sync_state": "detached",
    }

    result = apply_notes_change(
        fake_notes_db,
        binding=binding,
        change={"event_type": "changed", "relative_path": "docs/api/a.md", "text": "# A\n\nbody"},
        policy="canonical",
    )

    assert result["sync_status"] == "content_detached"
    assert result["folders_reconciled"] is True
```

**Step 2: Run test to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_git_notes_sink.py -v
```

Expected: FAIL because the current notes sink only understands `sync_managed` and `conflict_detached`.

**Step 3: Write minimal implementation**

Extend binding/result handling to track:

- `content_sync_state`
- `repo_folder_ids`
- `folders_reconciled`

Implement split behavior:

- detached content is not overwritten
- repo-managed folder memberships are still reconciled
- user-added extra folders are preserved

Keep V1 rename semantics unchanged:

- delete old path
- create new path

**Step 4: Run tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_git_notes_sink.py tldw_Server_API/tests/Ingestion_Sources/test_notes_sink.py tldw_Server_API/tests/Ingestion_Sources/integration/test_notes_detached_integration.py -v
```

Expected: PASS for split detach and no regressions in existing notes sync.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/sinks/notes_sink.py tldw_Server_API/app/services/ingestion_sources_worker.py tldw_Server_API/tests/Ingestion_Sources/test_git_notes_sink.py tldw_Server_API/tests/Ingestion_Sources/test_notes_sink.py tldw_Server_API/tests/Ingestion_Sources/integration/test_notes_detached_integration.py
git commit -m "feat(notes-sync): add repo folder reconciliation and split detach state"
```

### Task 6: Add remote GitHub materialization for `git_repository`

**Files:**
- Create: `tldw_Server_API/app/core/Ingestion_Sources/github_repository.py`
- Modify: `tldw_Server_API/app/services/ingestion_sources_worker.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_github_repository_source.py`

**Step 1: Write the failing remote source tests**

```python
def test_materialize_github_repository_archive_builds_cache_tree(tmp_path, monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Sources.github_repository import materialize_github_repository

    result = materialize_github_repository(
        config={
            "mode": "remote_github_repo",
            "repo_url": "https://github.com/octo/example",
            "ref": "main",
            "account_id": "acct-1",
        },
        cache_root=tmp_path,
        account_token="token",
    )

    assert result.cache_path.exists()
    assert result.revision
```

**Step 2: Run test to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_github_repository_source.py -v
```

Expected: FAIL because the module does not exist.

**Step 3: Write minimal implementation**

Implement a GitHub-only remote materializer that:

- validates GitHub URL shape
- obtains a token from linked account context
- downloads the requested ref as an archive or equivalent file-tree payload
- extracts to a managed cache directory
- returns cache metadata such as revision SHA and cache path

Keep transport intentionally narrow in V1. Do not add generic `git clone`.

**Step 4: Run tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_github_repository_source.py -v
```

Expected: PASS for remote materialization happy path and validation failures.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/github_repository.py tldw_Server_API/app/services/ingestion_sources_worker.py tldw_Server_API/tests/Ingestion_Sources/test_github_repository_source.py
git commit -m "feat(sources): add github repository materialization for notes sync"
```

### Task 7: Wire `git_repository` execution into ingestion source worker and APIs

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/ingestion_sources.py`
- Modify: `tldw_Server_API/app/core/Ingestion_Sources/service.py`
- Modify: `tldw_Server_API/app/services/ingestion_sources_worker.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/integration/test_git_repository_ingestion_source.py`

**Step 1: Write the failing integration tests**

```python
def test_create_git_repository_source_and_trigger_sync(client):
    response = client.post(
        "/api/v1/ingestion-sources",
        json={
            "source_type": "git_repository",
            "sink_type": "notes",
            "policy": "import_only",
            "config": {"mode": "local_repo", "path": "/tmp/repo"},
        },
    )

    assert response.status_code == 201
```

**Step 2: Run test to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/integration/test_git_repository_ingestion_source.py -v
```

Expected: FAIL because the endpoint still only understands local directories and archive snapshots.

**Step 3: Write minimal implementation**

Wire `git_repository` through:

- create/update payload preparation
- worker snapshot loading
- source detail serialization
- sync trigger flow

Respect:

- one-time import vs ongoing sync
- GitHub remote cache path usage
- allowed-root enforcement for local repos

**Step 4: Run integration tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/integration/test_git_repository_ingestion_source.py -v
```

Expected: PASS for source creation, sync dispatch, and source detail retrieval.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/ingestion_sources.py tldw_Server_API/app/core/Ingestion_Sources/service.py tldw_Server_API/app/services/ingestion_sources_worker.py tldw_Server_API/tests/Ingestion_Sources/integration/test_git_repository_ingestion_source.py
git commit -m "feat(sources): wire git repository source through sync execution"
```

### Task 8: Extend Sources UI for git repositories

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Sources/SourceForm.tsx`
- Modify: `apps/packages/ui/src/components/Option/Sources/SourceDetailPage.tsx`
- Modify: `apps/packages/ui/src/components/Option/Sources/SourceStatusPanels.tsx`
- Modify: `apps/packages/ui/src/assets/locale/en/sources.json`
- Test: `apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx`
- Test: `apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx`

**Step 1: Write the failing UI tests**

```tsx
it("shows git repository configuration fields when git repository is selected", async () => {
  render(<SourceForm mode="create" />)
  fireEvent.click(screen.getByLabelText("Git repository"))
  expect(screen.getByLabelText("Repository mode")).toBeInTheDocument()
})
```

**Step 2: Run tests to verify failure**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx
```

Expected: FAIL because the git repository option and diagnostics are absent.

**Step 3: Write minimal implementation**

Add UI support for:

- `Git repository` source type
- local vs remote GitHub mode selector
- local path, repo URL, account, ref, root subpath
- one-time import vs keep synced
- repo diagnostics on detail page:
  - mode
  - ref
  - last revision
  - auth/account state
  - dirty-state indicator for local repos

**Step 4: Run tests**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx
```

Expected: PASS for source creation and detail rendering flows.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Sources/SourceForm.tsx apps/packages/ui/src/components/Option/Sources/SourceDetailPage.tsx apps/packages/ui/src/components/Option/Sources/SourceStatusPanels.tsx apps/packages/ui/src/assets/locale/en/sources.json apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx
git commit -m "feat(ui): add git repository source management"
```

### Task 9: Add Notes repo-import shortcut and folder-aware Notes UI

**Files:**
- Modify: `apps/packages/ui/src/components/Notes/NotesSidebar.tsx`
- Modify: `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
- Create: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.repo-import.test.tsx`
- Create: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.folder-membership.test.tsx`

**Step 1: Write the failing Notes UI tests**

```tsx
it("shows an import from repo action that routes into Sources creation", async () => {
  render(<NotesManagerPage />)
  expect(screen.getByRole("button", { name: "Import from repo" })).toBeInTheDocument()
})
```

**Step 2: Run tests to verify failure**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.repo-import.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.folder-membership.test.tsx
```

Expected: FAIL because the shortcut and folder-aware UI are absent.

**Step 3: Write minimal implementation**

Add:

- `Import from repo` shortcut in Notes
- routing into the Sources creation page with repo defaults
- folder-aware note detail/list rendering using dedicated folder APIs
- clear copy that distinguishes folders from existing smart collections

Do not reuse current smart collection controls for repo folders.

**Step 4: Run tests**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.repo-import.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.folder-membership.test.tsx
```

Expected: PASS for Notes shortcut and folder presentation behavior.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Notes/NotesSidebar.tsx apps/packages/ui/src/components/Notes/NotesManagerPage.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.repo-import.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.folder-membership.test.tsx
git commit -m "feat(notes-ui): add repo import shortcut and folder-aware notes views"
```

### Task 10: Full verification, security checks, and documentation touch-ups

**Files:**
- Modify: `Docs/Plans/2026-03-13-git-repo-notes-import-sync-design.md` if implementation decisions drift
- Modify: any touched docs only if behavior changed during implementation

**Step 1: Run focused backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_git_repository_source_contract.py tldw_Server_API/tests/Ingestion_Sources/test_git_repository_snapshot.py tldw_Server_API/tests/Ingestion_Sources/test_github_repository_source.py tldw_Server_API/tests/Ingestion_Sources/test_git_notes_sink.py tldw_Server_API/tests/Ingestion_Sources/integration/test_git_repository_ingestion_source.py tldw_Server_API/tests/Notes_NEW/unit/test_note_folders_db.py tldw_Server_API/tests/Notes_NEW/integration/test_note_folders_api.py -v
```

Expected: PASS.

**Step 2: Run focused frontend tests**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.repo-import.test.tsx apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.folder-membership.test.tsx
```

Expected: PASS.

**Step 3: Run Bandit on touched Python scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Ingestion_Sources tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/api/v1/endpoints/notes.py tldw_Server_API/app/api/v1/endpoints/ingestion_sources.py -f json -o /tmp/bandit_git_repo_notes_sync.json
```

Expected: No new findings in changed code.

**Step 4: Review design doc for drift**

If implementation required any deliberate scope change, update:

```markdown
## Implementation Notes
- V1 remote materialization uses GitHub archive download only.
- Path renames remain delete-plus-create in the initial release.
```

**Step 5: Final commit**

```bash
git add <touched_files>
git commit -m "feat(notes): deliver git repository import and sync foundations"
```
