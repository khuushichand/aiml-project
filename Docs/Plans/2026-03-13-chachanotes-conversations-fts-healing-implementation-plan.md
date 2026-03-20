# ChaChaNotes Conversations FTS Healing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Repair legacy SQLite `conversations_fts` state so ChaChaNotes V31->V32 migration and recent persona schema backfills stop failing during workspace generation.

**Architecture:** Add a SQLite-specific conversations FTS trigger normalizer and rebuild helper in `ChaChaNotes_DB.py`, invoke them before conversation assistant-field backfills, and cover the regression with a minimal failing reproduction plus migration-level verification.

**Tech Stack:** Python, SQLite, pytest, FastAPI backend database layer

---

### Task 1: Capture the FTS Regression in a Failing Unit Test

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/DB_Management/test_chacha_postgres_migration_v15.py` if there is already a nearby SQLite migration pattern worth reusing, otherwise inspect only
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

**Step 1: Write the failing test**

Create a test that:

- builds a temp SQLite database with `conversations`, `conversations_fts`, and the legacy `conversations_ai/au/ad` triggers
- inserts a `conversations` row while FTS is stale or missing
- reproduces the legacy failure on an assistant-field update
- instantiates `CharactersRAGDB` or calls the new helper path once it exists
- asserts that the repaired path lets the same update succeed

The test should be narrowly named, for example:

```python
def test_conversations_fts_heal_allows_assistant_identity_backfill_on_legacy_sqlite_db():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py
```

Expected: FAIL because the helper does not exist or the legacy update still throws `database disk image is malformed`.

**Step 3: Commit red test scaffold only if it is readable**

Do not commit yet if the test file is still in a broken drafting state.

### Task 2: Implement Conversations FTS Healing in `ChaChaNotes_DB.py`

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py`

**Step 1: Add the failing helper API surface**

Add:

- `_ensure_conversations_fts_triggers_sqlite(self, conn)`
- `_rebuild_conversations_fts_sqlite(self, conn)`

Model them after the existing notes/character-cards FTS helpers.

**Step 2: Implement minimal trigger normalization**

The SQLite trigger definitions should:

- only delete from `conversations_fts` when the old row was indexed
- only insert into `conversations_fts` when the new row should be indexed
- avoid FTS churn when only non-search columns changed

**Step 3: Implement minimal rebuild helper**

Run:

```python
conn.execute("INSERT INTO conversations_fts(conversations_fts) VALUES('rebuild')")
```

Wrap SQLite errors in `SchemaError`.

**Step 4: Re-run the focused test**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py
git commit -m "fix: heal legacy conversations fts state in chachanotes"
```

### Task 3: Wire the Repair Into Migration and Backfill Paths

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py`

**Step 1: Write or extend a failing migration-level test**

Add a second test that exercises either:

- `_migrate_from_v31_to_v32`, or
- `_ensure_recent_persona_schema_sqlite`

through a real temp DB at schema version 31 with legacy conversation triggers.

Assert that the code path:

- advances schema
- backfills assistant identity fields
- does not raise `SchemaError`

**Step 2: Run the focused migration test to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py -k "migration or recent persona"
```

Expected: FAIL before the code is wired in.

**Step 3: Implement the integration**

In `ChaChaNotes_DB.py`:

- call `_ensure_conversations_fts_triggers_sqlite(conn)` before the V31->V32 assistant-field updates
- call `_rebuild_conversations_fts_sqlite(conn)` before those updates
- repeat the same sequence in `_ensure_recent_persona_schema_sqlite`

Keep the change local to SQLite code paths.

**Step 4: Re-run the focused file**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py
git commit -m "fix: repair conversations fts before persona backfill"
```

### Task 4: Verify the Real Initialization Path and Security Baseline

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/2026-03-13-chachanotes-conversations-fts-healing-implementation-plan.md`
- Verify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Verify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py`

**Step 1: Run the focused DB tests**

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py
```

Expected: PASS.

**Step 2: Run one higher-level path that exercises initialization**

Use the narrowest existing backend test that hits ChaChaNotes initialization without unrelated provider dependencies. If no suitable existing test is stable, use a one-off Python import/probe command and record that limitation in the final report.

Suggested command pattern:

```bash
source .venv/bin/activate && python -m pytest -v <existing_chachanotes_or_rag_test>
```

**Step 3: Run Bandit on touched backend files**

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py -f json -o /tmp/bandit_chachanotes_conversations_fts_healing.json
```

Expected: no new findings in touched code.

**Step 4: Update this plan with verification notes if needed**

Record any substitutions or higher-level verification limitations directly in this plan file.

**Step 5: Commit verification-only follow-up if code changed during validation**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/DB_Management/test_chacha_conversations_fts_healing.py Docs/Plans/2026-03-13-chachanotes-conversations-fts-healing-implementation-plan.md
git commit -m "test: verify chachanotes conversations fts repair"
```

## Execution Notes

- The focused conversations-FTS regression passed after adding `_ensure_conversations_fts_triggers_sqlite()` and `_rebuild_conversations_fts_sqlite()` and wiring them into both V31->V32 and recent-persona schema backfills.
- Verification against a copied real `ChaChaNotes.db` then surfaced a second legacy SQLite blocker in the V36->V37 flashcard scheduler path. That follow-on issue came from legacy `flashcards_fts` triggers firing during flashcard shadow/scheduler backfills.
- The final fix set therefore also normalizes flashcard FTS before flashcard asset/scheduler backfills and adds a dedicated regression for that legacy path.
- Live workspace verification was completed against a fresh backend instance on `http://127.0.0.1:8002`, because the long-running server on `:8000` was still serving the pre-fix code path.
