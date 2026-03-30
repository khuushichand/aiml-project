# Media DB V2 Helper-Cluster Rebinding Design

## Goal

Reduce the remaining runtime dependency of the canonical package-native `MediaDatabase`
class on `tldw_Server_API.app.core.DB_Management.Media_DB_v2` by rebinding
selected method clusters to package-native helper ownership, while preserving the
legacy shell contract and existing monkeypatch seams.

## Current State

The class-chain severing tranche is complete:

- `MediaDatabase` is now canonically owned by
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py).
- [media_database.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database.py),
  [native_class.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/native_class.py),
  and [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  all resolve the same class object.
- `Media_DB_v2.__all__` now explicitly declares the supported compatibility surface.

But the runtime still depends heavily on `Media_DB_v2` as a global host:

- the cloned canonical class still has `278` methods whose function globals resolve to
  `tldw_Server_API.app.core.DB_Management.Media_DB_v2`
- those methods read helpers, constants, repositories, logging, and utility functions
  from the legacy module namespace

That means `Media_DB_v2.py` is no longer the class owner, but it is still the
effective dependency host for most of the class body.

## Design Corrections Incorporated

This tranche uses the corrected design constraints from review:

1. **Rebind methods, not just helpers**
   Moving a helper function to a new module is not sufficient unless the affected
   canonical methods stop resolving globals from `Media_DB_v2`.

2. **Preserve monkeypatch seams explicitly**
   Existing regressions patch shell-level names like
   `Media_DB_v2.begin_immediate_if_needed` and
   `Media_DB_v2.configure_sqlite_connection`.
   Native method ownership must preserve those patchpoints.

3. **Treat backup as instance-method ownership**
   The meaningful runtime dependency is `MediaDatabase.backup_database` and
   `MediaDatabase._backup_non_sqlite_database`, not just the module-level backup
   export functions.

4. **Measure progress by method ownership**
   The success metric is a reduction in named canonical methods that resolve globals
   from `Media_DB_v2`, not just the existence of new helper modules.

## Recommended Approach

Use **helper-cluster rebinding** in small, verifiable slices.

Each slice should:

- extract one helper cluster into package-native code
- rebind the affected canonical `MediaDatabase` methods so their globals no longer
  resolve to `Media_DB_v2`
- keep `Media_DB_v2` as the compat shell and patchpoint surface
- add ownership assertions for the named methods in that slice

This is safer than a large rewrite because it:

- keeps the existing class object stable
- preserves the compat shell
- reduces legacy runtime ownership incrementally
- produces measurable ownership reduction after each commit

## Tranche Structure

### 1. Bootstrap Rebinding Tranche

Scope:

- `_apply_sqlite_connection_pragmas`
- the SQLite bootstrap path inside `transaction`

Why first:

- this is small
- it has dedicated regression coverage already
- it exercises the main monkeypatch-compat requirement

Design:

- create a package-native bootstrap helper module under `media_db`
- native methods should call package-native wrappers
- those wrappers must still dereference shell-exported patchpoints so that
  `Media_DB_v2.begin_immediate_if_needed` and
  `Media_DB_v2.configure_sqlite_connection` remain effective test seams

### 2. Backup Rebinding Tranche

Scope:

- `backup_database`
- `_backup_non_sqlite_database`

Why second:

- narrow instance-method surface
- clear behavior boundary
- low interaction with the rest of the DB API

Design:

- move the implementation into a package-native helper module
- rebind the canonical instance methods to native ownership
- keep `Media_DB_v2` module-level exports as thin shell wrappers

### 3. Chunk Tranche A

Scope:

- `add_media_chunks_in_batches`
- `batch_insert_chunks`
- `process_chunks`

Why third:

- these are coherent user-visible chunk insertion methods
- they already lean on repositories, so rebinding should be localized

Design:

- move the shared chunk-processing logic into package-native code
- rebind the canonical methods to native ownership
- preserve repository behavior unchanged

### 4. Chunk Tranche B

Scope:

- `clear_unvectorized_chunks`
- `process_unvectorized_chunks`
- chunking-template CRUD methods near the same cluster

Why split from tranche A:

- keeps the first chunk slice smaller and easier to verify
- avoids mixing the main insertion path with template/unvectorized maintenance

## Explicitly Deferred

This tranche does **not** attempt to:

- remove `Media_DB_v2.py`
- collapse the broad read/query surface
- move all remaining methods out of legacy globals in one pass
- rewrite behavior beyond ownership rebinding

The broader read/query layer should be reconsidered only after the bootstrap,
backup, and chunk clusters have materially reduced the legacy global count.

## Success Criteria

This design is successful if all of the following are true:

1. Named methods in each completed slice no longer resolve globals from
   `Media_DB_v2`.
2. Shell patchpoint regressions still pass.
3. Runtime schema-version lookup remains green.
4. The counted number of canonical methods whose globals resolve to
   `Media_DB_v2` drops materially from the current `278`.
5. `Media_DB_v2` remains a supported compat shell rather than becoming a hidden
   active implementation owner again.

## Verification Strategy

Each slice should include both behavior and ownership checks.

At minimum:

- ownership tests for the specific rebound methods
- existing bootstrap monkeypatch regressions
- backup helper regressions
- chunk insertion regressions
- focused import/shell contract tests
- Bandit on touched production files
- `git diff --check`

## Recommendation

Proceed with the helper-cluster rebinding tranche in this order:

1. bootstrap
2. backup
3. chunk A
4. chunk B

That sequence is the best balance of risk reduction and meaningful legacy
ownership removal.
