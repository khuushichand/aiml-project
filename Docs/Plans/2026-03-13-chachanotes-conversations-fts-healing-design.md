# ChaChaNotes Conversations FTS Healing Design

## Context

Live `/workspace-playground` generation is currently blocked by backend `POST /api/v1/rag/search` failures while the per-user `ChaChaNotes.db` is initialized. The failing path is the SQLite schema migration from V31 to V32 in `rag_char_chat_schema`.

The affected database passes `PRAGMA integrity_check`, but updating rows in `conversations` still raises `database disk image is malformed`. A minimal reproduction shows that the legacy `conversations_fts` update trigger can emit that error when a row exists in `conversations` but is missing from the FTS index. The V31->V32 migration now updates `conversations` to backfill assistant identity fields, so older databases hit this latent FTS inconsistency during startup.

## Problem

`ChaChaNotes_DB.py` already contains SQLite self-heal logic for `character_cards_fts` and `notes_fts`, but there is no equivalent repair path for `conversations_fts`.

That leaves two unsafe behaviors in legacy SQLite databases:

1. The `conversations_au` trigger always issues an FTS delete on every update, even when the title and deleted state did not change.
2. The migration and recent-persona backfill paths update `conversations`, which triggers the legacy FTS delete/insert behavior before the FTS index has been normalized or rebuilt.

## Chosen Approach

Add a conversation-FTS repair path in `ChaChaNotes_DB.py`, and use it in both:

1. `_migrate_from_v31_to_v32`
2. `_ensure_recent_persona_schema_sqlite`

This repair path will:

1. Normalize the SQLite `conversations_fts` triggers so they only perform FTS delete/insert work when title or deleted state actually changes.
2. Rebuild `conversations_fts` once to heal stale legacy indexes.
3. Allow the assistant-identity backfill to run safely on older databases.

## Design Details

### 1. New SQLite trigger normalizer

Add `_ensure_conversations_fts_triggers_sqlite(conn)` alongside the existing notes and character-card helpers.

The normalized trigger behavior should:

- `conversations_ai`: insert into `conversations_fts` only when `new.deleted = 0` and `new.title IS NOT NULL`
- `conversations_au`: perform the FTS delete only when the old row was indexed and either `title` or `deleted` changed
- `conversations_au`: perform the FTS insert only when the new row should be indexed and either `title` or `deleted` changed
- `conversations_ad`: perform the FTS delete only when `old.deleted = 0`

This avoids spurious FTS delete operations during assistant-field backfills that do not change searchable content.

### 2. New SQLite conversations FTS rebuild helper

Add `_rebuild_conversations_fts_sqlite(conn)` that runs:

`INSERT INTO conversations_fts(conversations_fts) VALUES('rebuild')`

This should raise `SchemaError` on SQLite failure so the initialization path reports a precise migration problem instead of silently proceeding with a broken index.

### 3. Migration integration

Before the V31->V32 assistant-field backfill runs:

- normalize conversation FTS triggers
- rebuild `conversations_fts`

Then perform the existing `assistant_kind` / `assistant_id` backfill and advance schema version.

This heals older databases before the first `UPDATE conversations` statement runs.

### 4. Recent persona schema backfill integration

Apply the same normalization + rebuild sequence in `_ensure_recent_persona_schema_sqlite`.

This protects the version-collision / post-migration repair path as well, so startup remains safe even when a database reaches recent persona schema fields through the fallback initializer instead of the linear migration path.

## Testing Strategy

Add a regression test that constructs a temporary SQLite `ChaChaNotes`-style database with:

- a `conversations` row
- a legacy `conversations_fts` trigger shape
- a deliberately stale `conversations_fts` index state

The test should prove:

1. the legacy update path reproduces `database disk image is malformed`
2. the new repair helper normalizes triggers and rebuilds `conversations_fts`
3. after repair, the V31->V32-style assistant-field update succeeds

Add at least one higher-level test around the DB migration/init path so the repair is exercised through the real migration code, not only the helper.

## Success Criteria

- Initializing an older SQLite `ChaChaNotes.db` no longer fails during V31->V32 assistant identity migration.
- `POST /api/v1/rag/search` can progress past ChaChaNotes initialization for the affected local user DB.
- Workspace studio generation is no longer blocked by the conversation-FTS migration failure.
