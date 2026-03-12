# Companion Capture Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** Planned on 2026-03-12

**Goal:** Extend explicit companion capture into lower-risk notes and watchlists bulk/import flows without creating new event families or hidden tracking behavior.

**Architecture:** Add a shared personalization-layer bulk/import adapter that builds existing companion activity events from actual successful create/update branches, performs a single consent check, and writes through a conflict-tolerant bulk path. Keep endpoint ownership of parsing and DB writes, require post-write rereads where final object state is needed, and only emit events when the route can prove state changed.

**Tech Stack:** FastAPI, Pydantic, SQLite/WAL (`PersonalizationDB`), existing notes/watchlists DB helpers, pytest, Bandit.

**Shell Convention:** Command snippets below assume `PROJECT_ROOT` points at the repository root. If it is not already set, run `PROJECT_ROOT="$(pwd)"` from the repo root before executing them.

---

### Task 1: Add Conflict-Tolerant Companion Bulk Insert Support

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Personalization_DB.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py`

**Step 1: Write the failing tests**

```python
def test_insert_companion_activity_events_bulk_skips_duplicate_dedupe_keys(personalization_db):
    personalization_db.update_profile("1", enabled=1)
    events = [
        {
            "event_type": "note_created",
            "source_type": "note",
            "source_id": "n1",
            "surface": "api.notes.import",
            "dedupe_key": "notes.create:n1",
            "provenance": {"capture_mode": "explicit"},
            "metadata": {"title": "One"},
        },
        {
            "event_type": "note_created",
            "source_type": "note",
            "source_id": "n1",
            "surface": "api.notes.import",
            "dedupe_key": "notes.create:n1",
            "provenance": {"capture_mode": "explicit"},
            "metadata": {"title": "One duplicate"},
        },
    ]

    inserted = personalization_db.insert_companion_activity_events_bulk(user_id="1", events=events)

    assert len(inserted) == 1
    rows, total = personalization_db.list_companion_activity_events("1", limit=10)
    assert total == 1


def test_insert_companion_activity_events_bulk_keeps_unique_rows_when_one_conflicts(personalization_db):
    personalization_db.update_profile("1", enabled=1)
    personalization_db.insert_companion_activity_event(
        user_id="1",
        event_type="note_created",
        source_type="note",
        source_id="n1",
        surface="api.notes.import",
        dedupe_key="notes.create:n1",
        provenance={"capture_mode": "explicit"},
        metadata={"title": "Existing"},
    )

    inserted = personalization_db.insert_companion_activity_events_bulk(
        user_id="1",
        events=[
            {
                "event_type": "note_created",
                "source_type": "note",
                "source_id": "n1",
                "surface": "api.notes.import",
                "dedupe_key": "notes.create:n1",
                "provenance": {"capture_mode": "explicit"},
                "metadata": {"title": "Duplicate"},
            },
            {
                "event_type": "note_created",
                "source_type": "note",
                "source_id": "n2",
                "surface": "api.notes.import",
                "dedupe_key": "notes.create:n2",
                "provenance": {"capture_mode": "explicit"},
                "metadata": {"title": "Fresh"},
            },
        ],
    )

    assert len(inserted) == 1
    rows, total = personalization_db.list_companion_activity_events("1", limit=10)
    assert total == 2
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source "$PROJECT_ROOT/.venv/bin/activate" && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py -k "bulk_skips_duplicate or one_conflicts"
```

Expected: FAIL because the current bulk insert path is all-or-nothing on duplicate dedupe keys.

**Step 3: Write minimal implementation**

- Update `insert_companion_activity_events_bulk(...)` in `Personalization_DB.py` so one duplicate does not fail the whole batch.
- Accept either implementation:
  - prefiltering existing dedupe keys before insert, or
  - per-row conflict-tolerant inserts inside one transaction.
- Preserve current return semantics by returning only inserted event IDs.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/Personalization_DB.py \
  tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py
git commit -m "feat: make companion bulk activity inserts conflict tolerant"
```

### Task 2: Add Shared Companion Bulk/Import Event Builders

**Files:**
- Modify: `tldw_Server_API/app/core/Personalization/companion_activity.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py`

**Step 1: Write the failing tests**

```python
def test_build_note_import_created_activity_uses_import_surface_and_route():
    note = {
        "id": "note-1",
        "title": "Imported note",
        "content": "Imported content",
        "version": 1,
        "created_at": "2026-03-12T00:00:00+00:00",
        "last_modified": "2026-03-12T00:00:00+00:00",
        "keywords": [{"keyword": "import"}],
    }

    payload = build_note_bulk_import_activity(
        note=note,
        operation="import_create",
        route="/api/v1/notes/import",
        surface="api.notes.import",
    )

    assert payload["event_type"] == "note_created"
    assert payload["surface"] == "api.notes.import"
    assert payload["provenance"]["route"] == "/api/v1/notes/import"
    assert payload["provenance"]["action"] == "import_create"


def test_build_watchlist_source_bulk_activity_uses_bulk_surface_and_route():
    source = {
        "id": 12,
        "name": "Bulk source",
        "url": "https://example.com/feed.xml",
        "source_type": "rss",
        "active": True,
        "status": None,
        "group_ids": [2],
        "tags": ["feeds"],
        "created_at": "2026-03-12T00:00:00+00:00",
        "updated_at": "2026-03-12T00:00:00+00:00",
    }

    payload = build_watchlist_source_bulk_import_activity(
        source=source,
        operation="bulk_create",
        route="/api/v1/watchlists/sources/bulk",
        surface="api.watchlists.sources.bulk",
    )

    assert payload["event_type"] == "watchlist_source_created"
    assert payload["surface"] == "api.watchlists.sources.bulk"
    assert payload["provenance"]["action"] == "bulk_create"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source "$PROJECT_ROOT/.venv/bin/activate" && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py -k "import_surface_and_route or bulk_surface_and_route"
```

Expected: FAIL because shared bulk/import event builders do not exist yet.

**Step 3: Write minimal implementation**

- Add helper builders in `companion_activity.py` for:
  - notes import/bulk create payloads
  - notes import overwrite payloads
  - watchlist source import/bulk create payloads
- Reuse existing metadata helpers and event families.
- Keep provenance origin-specific:
  - `import_create`
  - `import_overwrite`
  - `bulk_create`
- Do not write to the DB in these helpers; only build event payloads.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_activity.py \
  tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py
git commit -m "feat: add companion bulk import activity builders"
```

### Task 3: Add Notes Import Companion Capture With Post-Write Rereads

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/notes.py`
- Test: `tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py`
- Test: `tldw_Server_API/tests/Notes_NEW/integration/test_notes_api.py`

**Step 1: Write the failing tests**

```python
def test_notes_import_create_records_companion_note_created(client, personalization_db):
    response = client.post(
        "/api/v1/notes/import",
        json={
            "duplicate_strategy": "create_copy",
            "items": [
                {
                    "file_name": "note.json",
                    "format": "json",
                    "content": "{\"title\": \"Imported Note\", \"content\": \"Body\", \"keywords\": [\"alpha\"]}",
                }
            ],
        },
    )

    assert response.status_code == 200
    events, total = personalization_db.list_companion_activity_events("333", limit=10)
    assert total == 1
    assert events[0]["event_type"] == "note_created"
    assert events[0]["surface"] == "api.notes.import"
    assert events[0]["provenance"]["action"] == "import_create"


def test_notes_import_overwrite_records_companion_note_updated(client, personalization_db):
    note_id = seed_note(client, title="Original", content="Before")

    response = client.post(
        "/api/v1/notes/import",
        json={
            "duplicate_strategy": "overwrite",
            "items": [
                {
                    "file_name": "note.json",
                    "format": "json",
                    "content": f"{{\"id\": \"{note_id}\", \"title\": \"Updated\", \"content\": \"After\"}}",
                }
            ],
        },
    )

    assert response.status_code == 200
    events, _ = personalization_db.list_companion_activity_events("333", limit=10)
    updated = next(event for event in events if event["event_type"] == "note_updated")
    assert updated["source_id"] == note_id
    assert updated["surface"] == "api.notes.import"
    assert updated["provenance"]["action"] == "import_overwrite"
    assert updated["metadata"]["changed_fields"] == ["content", "title"]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source "$PROJECT_ROOT/.venv/bin/activate" && python -m pytest -v \
  tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_notes_api.py -k "import"
```

Expected: FAIL because `notes/import` does not record companion activity yet.

**Step 3: Write minimal implementation**

- In `notes.py`, collect successful import-create and import-overwrite rows inside their actual success branches.
- After each successful create or overwrite, reread the final note row with `db.get_note_by_id(...)`.
- For overwrite paths, compute the patch fields used by the companion builder.
- After processing a file or request, send the built events through the shared bulk/import adapter.
- Keep skips and failures out of the companion ledger.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/notes.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_notes_api.py
git commit -m "feat: capture companion activity for notes import"
```

### Task 4: Add Notes Bulk Companion Capture

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/notes.py`
- Test: `tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py`
- Test: `tldw_Server_API/tests/Notes_NEW/integration/test_notes_api.py`

**Step 1: Write the failing tests**

```python
def test_notes_bulk_success_rows_record_companion_activity(client, personalization_db):
    response = client.post(
        "/api/v1/notes/bulk",
        json={
            "notes": [
                {"title": "Bulk One", "content": "One"},
                {"title": "Bulk Two", "content": "Two"},
            ]
        },
    )

    assert response.status_code == 200
    events, total = personalization_db.list_companion_activity_events("333", limit=10)
    assert total == 2
    assert all(event["event_type"] == "note_created" for event in events)
    assert all(event["surface"] == "api.notes.bulk" for event in events)
    assert all(event["provenance"]["action"] == "bulk_create" for event in events)


def test_notes_bulk_failed_rows_do_not_record_companion_activity(client, personalization_db):
    response = client.post(
        "/api/v1/notes/bulk",
        json={
            "notes": [
                {"title": "Bulk Good", "content": "Good"},
                {"content": "Missing title and no auto title"},
            ]
        },
    )

    assert response.status_code == 200
    events, total = personalization_db.list_companion_activity_events("333", limit=10)
    assert total == 1
    assert events[0]["metadata"]["title"] == "Bulk Good"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source "$PROJECT_ROOT/.venv/bin/activate" && python -m pytest -v \
  tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_notes_api.py -k "bulk"
```

Expected: FAIL because `notes/bulk` does not record companion activity yet.

**Step 3: Write minimal implementation**

- Reuse the already hydrated created note rows returned inside `notes/bulk`.
- Build `note_created` companion payloads only for successful rows.
- Batch write those payloads after the bulk loop finishes.
- Leave all existing API result counting and per-row error reporting unchanged.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/notes.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_notes_api.py
git commit -m "feat: capture companion activity for notes bulk create"
```

### Task 5: Add Watchlists OPML Import Companion Capture

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Test: `tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py`
- Test: `tldw_Server_API/tests/Watchlists/test_watchlists_api.py`

**Step 1: Write the failing tests**

```python
def test_watchlists_sources_import_created_rows_record_companion_activity(client, personalization_db, opml_bytes):
    response = client.post(
        "/api/v1/watchlists/sources/import",
        files={"file": ("feeds.opml", opml_bytes, "text/xml")},
    )

    assert response.status_code == 200
    events, total = personalization_db.list_companion_activity_events("906", limit=10)
    assert total == 1
    assert events[0]["event_type"] == "watchlist_source_created"
    assert events[0]["surface"] == "api.watchlists.sources.import"
    assert events[0]["provenance"]["action"] == "import_create"


def test_watchlists_sources_import_duplicate_skip_does_not_record_companion_activity(client, personalization_db, opml_bytes):
    client.post("/api/v1/watchlists/sources/import", files={"file": ("feeds.opml", opml_bytes, "text/xml")})

    response = client.post(
        "/api/v1/watchlists/sources/import",
        files={"file": ("feeds.opml", opml_bytes, "text/xml")},
    )

    assert response.status_code == 200
    events, total = personalization_db.list_companion_activity_events("906", limit=20)
    assert total == 1
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source "$PROJECT_ROOT/.venv/bin/activate" && python -m pytest -v \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py \
  tldw_Server_API/tests/Watchlists/test_watchlists_api.py -k "sources_import"
```

Expected: FAIL because the OPML import route does not record companion activity yet.

**Step 3: Write minimal implementation**

- In `watchlists.py`, build companion payloads only inside the actual create branch of `/sources/import`.
- Do not derive companion writes from final `items` response rows.
- Batch write after the import loop completes.
- Leave skipped duplicate and invalid-row behavior unchanged.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/watchlists.py \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py \
  tldw_Server_API/tests/Watchlists/test_watchlists_api.py
git commit -m "feat: capture companion activity for watchlists opml import"
```

### Task 6: Add Watchlists Bulk Companion Capture With Actual-Create Detection

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Watchlists_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Test: `tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py`
- Test: `tldw_Server_API/tests/Watchlists/test_watchlists_api.py`

**Step 1: Write the failing tests**

```python
def test_watchlists_bulk_new_source_records_companion_activity(client, personalization_db):
    response = client.post(
        "/api/v1/watchlists/sources/bulk",
        json={"sources": [{"name": "Feed A", "url": "https://example.com/a.xml", "source_type": "rss"}]},
    )

    assert response.status_code == 200
    events, total = personalization_db.list_companion_activity_events("906", limit=10)
    assert total == 1
    assert events[0]["event_type"] == "watchlist_source_created"
    assert events[0]["surface"] == "api.watchlists.sources.bulk"
    assert events[0]["provenance"]["action"] == "bulk_create"


def test_watchlists_bulk_idempotent_existing_source_does_not_record_companion_activity(client, personalization_db):
    client.post(
        "/api/v1/watchlists/sources/bulk",
        json={"sources": [{"name": "Feed A", "url": "https://example.com/a.xml", "source_type": "rss"}]},
    )

    response = client.post(
        "/api/v1/watchlists/sources/bulk",
        json={"sources": [{"name": "Feed A Again", "url": "https://example.com/a.xml", "source_type": "rss"}]},
    )

    assert response.status_code == 200
    events, total = personalization_db.list_companion_activity_events("906", limit=20)
    assert total == 1
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source "$PROJECT_ROOT/.venv/bin/activate" && python -m pytest -v \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py \
  tldw_Server_API/tests/Watchlists/test_watchlists_api.py -k "bulk"
```

Expected: FAIL because the bulk route does not capture companion activity and cannot yet distinguish real creates from idempotent existing-row returns.

**Step 3: Write minimal implementation**

- Extend `Watchlists_DB.create_source(...)` to expose whether a source was newly created.
- Update `/sources/bulk` to use that signal and only build companion payloads for real creates.
- Preserve current API behavior unless a safer response clarification is needed for tests.
- Keep validation errors and idempotent existing-source rows out of the companion ledger.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/Watchlists_DB.py \
  tldw_Server_API/app/api/v1/endpoints/watchlists.py \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py \
  tldw_Server_API/tests/Watchlists/test_watchlists_api.py
git commit -m "feat: capture companion activity for watchlists bulk create"
```

### Task 7: Add Consent-Gated Bulk Adapter Wiring And End-to-End Verification

**Files:**
- Modify: `tldw_Server_API/app/core/Personalization/companion_activity.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/notes.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Test: `tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py`
- Test: `tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py`

**Step 1: Write the failing tests**

```python
def test_notes_import_succeeds_without_companion_when_profile_disabled(client, personalization_db):
    personalization_db.update_profile("333", enabled=0)

    response = client.post(
        "/api/v1/notes/import",
        json={
            "duplicate_strategy": "create_copy",
            "items": [{"file_name": "note.md", "format": "markdown", "content": "# Title\n\nBody"}],
        },
    )

    assert response.status_code == 200
    _, total = personalization_db.list_companion_activity_events("333", limit=10)
    assert total == 0


def test_watchlists_bulk_succeeds_without_companion_when_profile_disabled(client, personalization_db):
    personalization_db.update_profile("906", enabled=0)

    response = client.post(
        "/api/v1/watchlists/sources/bulk",
        json={"sources": [{"name": "Feed A", "url": "https://example.com/a.xml", "source_type": "rss"}]},
    )

    assert response.status_code == 200
    _, total = personalization_db.list_companion_activity_events("906", limit=10)
    assert total == 0
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source "$PROJECT_ROOT/.venv/bin/activate" && python -m pytest -v \
  tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py -k "profile_disabled"
```

Expected: FAIL until the shared adapter is wired with one consent check and no-op behavior when the profile is not enabled.

**Step 3: Write minimal implementation**

- Add a shared write helper in `companion_activity.py` for bulk/import event payloads that:
  - opens personalization storage once
  - checks profile consent once
  - writes through the conflict-tolerant bulk insert path
  - logs and returns cleanly on companion-side failure
- Use that helper from the updated notes and watchlists handlers.
- Keep import/bulk response payloads and counters unchanged.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Run focused verification**

Run:

```bash
source "$PROJECT_ROOT/.venv/bin/activate" && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_notes_api.py \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py \
  tldw_Server_API/tests/Watchlists/test_watchlists_api.py \
  tldw_Server_API/tests/Watchlists/test_youtube_normalization_more.py -k "bulk or import"
```

Expected: PASS

**Step 6: Run security and diff verification**

Run:

```bash
source "$PROJECT_ROOT/.venv/bin/activate" && python -m bandit -r \
  tldw_Server_API/app/core/Personalization/companion_activity.py \
  tldw_Server_API/app/core/DB_Management/Personalization_DB.py \
  tldw_Server_API/app/core/DB_Management/Watchlists_DB.py \
  tldw_Server_API/app/api/v1/endpoints/notes.py \
  tldw_Server_API/app/api/v1/endpoints/watchlists.py
git diff --check
```

Expected:

- Bandit reports no new findings in touched code
- `git diff --check` is clean

**Step 7: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_activity.py \
  tldw_Server_API/app/api/v1/endpoints/notes.py \
  tldw_Server_API/app/api/v1/endpoints/watchlists.py \
  tldw_Server_API/tests/Notes_NEW/integration/test_companion_notes_activity_bridge.py \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py
git commit -m "feat: wire consent gated companion bulk import capture"
```
