# Media DB V2 Class-Chain Severing Design

**Status:** Proposed, review-corrected, and approved on 2026-03-20.

**Goal:** Sever the canonical `MediaDatabase` class-definition chain from `Media_DB_v2.py` without breaking runtime loading, compatibility imports, or legacy monkeypatch seams that current regressions still rely on.

## Why This Tranche Exists

The previous compat-reduction work drained most non-compat production callers
off the `legacy_*` helper modules and moved the runtime loader to the
package-native path under `media_db.runtime`.

That did **not** sever the actual class-definition chain.

Today:

- `media_db.runtime.media_class` loads `media_db.native_class`
- `media_db.native_class` re-exports `media_db.media_database.MediaDatabase`
- `media_db.media_database.MediaDatabase` subclasses
  `_LegacyMediaDatabase` from `Media_DB_v2.py`

So the runtime import path is native, but the defining implementation still
lives in the legacy module.

This tranche fixes that architectural mismatch while preserving the explicit
compatibility surface still used by tests and a few shell-level import paths.

## Review Corrections Incorporated

### 1. Extract the full effective implementation surface, not just the class block

`Media_DB_v2.py` does not define the final runtime class surface in one place.
It defines `_LegacyMediaDatabase`, then later patches additional methods and
helpers onto that class object.

Examples include:

- `get_media_by_uuid`
- backup helpers
- chunk-processing helpers
- runtime fallback method patching such as `get_media_by_title`

The extraction must therefore move the **effective** class definition:

1. the `_LegacyMediaDatabase` class block
2. the post-definition method attachments that extend it
3. the class attributes and module-level dependencies that those methods use

Anything less risks producing a native class that loads but silently loses
behavior.

### 2. Define the supported `Media_DB_v2` shell surface up front

`Media_DB_v2.py` is not just a `MediaDatabase` import path today. Tests still
import multiple symbol categories from it:

- `MediaDatabase`
- error types like `DatabaseError`, `InputError`, `ConflictError`, `SchemaError`
- helper functions such as `get_media_prompts`, `get_document_version`,
  `create_automated_backup`, `rotate_backups`, and related utilities

This tranche must inventory that still-supported surface before reducing
`Media_DB_v2.py` to a shell. The shell should re-export that exact supported
surface and nothing more.

### 3. Preserve legacy monkeypatch seams in this tranche

Current regression coverage patches names on `Media_DB_v2.py` directly for
behavior such as:

- `begin_immediate_if_needed`
- `configure_sqlite_connection`
- other shell-level helpers read by methods on the class

If the class body moves to a new module and those methods resolve helpers only
from the new module, those patches will stop affecting runtime behavior even if
imports still work.

This tranche therefore preserves shell-level monkeypatch compatibility:

- methods on the extracted class should continue reading the patchable helper
  names from `Media_DB_v2` where compat tests already expect that seam, or
- equivalent shell-level indirection must be provided and verified in the same
  tranche

This is an architectural extraction tranche, not a test-contract rewrite.

### 4. Preserve schema-version continuity

Runtime validation reads `_CURRENT_SCHEMA_VERSION` from the canonical runtime
class. The extracted native class must carry that attribute unchanged so
bootstrap, migration, and validation behavior remain identical.

## Scope

### In scope

- Create a package-native implementation module that owns the canonical
  `MediaDatabase` class definition.
- Move the full effective class surface from `Media_DB_v2.py` into that native
  module.
- Rewire `media_db.media_database` and `media_db.native_class` to export from
  the native implementation module.
- Reduce `Media_DB_v2.py` to an explicit compat shell that re-exports the
  inventoried supported surface.
- Preserve existing `Media_DB_v2` monkeypatch seams relied on by regression
  tests.
- Add focused identity/runtime/compat tests for class identity, schema version,
  and shell-level patch behavior.

### Out of scope

- Removing the `Media_DB_v2` import path entirely.
- Broad migration of remaining compat tests off `Media_DB_v2`.
- Deleting `DB_Manager.py`.
- Deleting all `legacy_*` helper modules.
- Redesigning runtime/session behavior beyond the defining-class handoff.

## Architecture

### A. Create a native implementation owner under `media_db`

Introduce a new module under `media_db`, for example:

- `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

That module becomes the canonical owner of:

- the `MediaDatabase` class definition
- `_CURRENT_SCHEMA_VERSION`
- all methods that are part of the class's effective runtime surface

The simplest safe pattern is:

1. move `_LegacyMediaDatabase` and rename it to `MediaDatabase`, or
2. keep an internal base name during extraction and export `MediaDatabase`
   directly from the native module

The key requirement is that the canonical class object is defined there, not in
`Media_DB_v2.py`.

### B. Keep `media_database.py` and `native_class.py` as thin native exports

After extraction:

- `media_db.media_database` should import and export the canonical class from
  the new native implementation module
- `media_db.native_class` should do the same

This preserves the existing package-native import paths while severing their
hidden dependency on `_LegacyMediaDatabase`.

### C. Reduce `Media_DB_v2.py` to a shell, but keep explicit compat support

`Media_DB_v2.py` should no longer own the class definition. Instead, it should
become a compatibility module that re-exports:

- the canonical native `MediaDatabase`
- supported error classes
- supported helper functions still intentionally imported from the legacy path
- patchable helper names needed to preserve existing shell-level monkeypatch
  tests

This shell should be explicit, not magical: compatibility surface declared
intentionally, not inherited accidentally.

### D. Preserve patch seams where regressions already depend on them

Methods that today rely on patching `Media_DB_v2.configure_sqlite_connection`
or `Media_DB_v2.begin_immediate_if_needed` should continue to honor that shell
surface during this tranche.

The cleanest approach is:

1. keep those shell-level names exported from `Media_DB_v2.py`
2. ensure the moved implementation resolves them through the compat module
   where required
3. add tests proving those patches still affect the class behavior

This allows later removal of those seams in a dedicated follow-up tranche rather
than hiding a contract break inside the extraction.

## Supported Compat Surface Inventory

Before the shell rewrite, build an explicit inventory of symbols still imported
from `Media_DB_v2.py` across tests and retained compat paths.

At minimum, the shell is expected to continue exporting:

- `MediaDatabase`
- `ConflictError`
- `DatabaseError`
- `InputError`
- `SchemaError`
- `get_document_version`
- `get_media_prompts`
- `get_latest_transcription`
- `get_media_transcripts`
- `create_automated_backup`
- `create_incremental_backup`
- `rotate_backups`
- `configure_sqlite_connection`
- `begin_immediate_if_needed`

The exact export set should be based on a fresh source scan and documented in
the implementation plan.

## Migration Shape

### 1. Inventory and tests first

- enumerate supported shell exports
- add failing tests for:
  - canonical class ownership moving out of `Media_DB_v2.py`
  - class identity across `media_database`, `native_class`, and `Media_DB_v2`
  - shell-level monkeypatch compatibility
  - schema-version continuity

### 2. Extract the class implementation

- create the native implementation module
- move the effective class surface there
- preserve method behavior and imports

### 3. Rewire native exports

- update `media_db.media_database`
- update `media_db.native_class`
- keep runtime loader unchanged except that it now reaches a truly native class

### 4. Reduce `Media_DB_v2.py` to compat shell

- re-export the inventoried supported surface
- preserve patch seams
- stop owning the class definition

## Testing Strategy

### Identity tests

Prove that:

- `media_db.media_database.MediaDatabase`
- `media_db.native_class.MediaDatabase`
- `Media_DB_v2.MediaDatabase`

all resolve to the same class object.

### Ownership tests

Prove that the defining module for the canonical class is the new native
implementation module, not `Media_DB_v2.py`.

### Runtime tests

Reuse existing runtime factory/session tests to prove that:

- the runtime loader still works
- schema-version access still works
- class construction is unchanged

### Compat seam tests

Retain or add focused tests proving that monkeypatches on shell-level helpers in
`Media_DB_v2.py` still affect the relevant methods during this tranche.

## Success Criteria

- The canonical `MediaDatabase` class is defined under `media_db`, not inside
  `Media_DB_v2.py`.
- `media_db.media_database`, `media_db.native_class`, and `Media_DB_v2`
  resolve the same class object.
- `_CURRENT_SCHEMA_VERSION` remains unchanged on the canonical class.
- `Media_DB_v2.py` remains import-compatible for the explicitly supported
  surface.
- Existing shell-level monkeypatch regressions continue to pass.
- Focused runtime/import/regression suites pass without changing caller
  behavior.
