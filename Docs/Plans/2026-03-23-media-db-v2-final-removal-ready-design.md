# Media DB V2 Final Removal-Ready Design

**Status:** Proposed, reviewed in-session, and approved on 2026-03-23.

**Goal:** Finish the Media DB v2 de-monolithing by removing the remaining
structural dependence on `Media_DB_v2.py`, migrating live code/tests/active
docs off the legacy import path, and leaving the legacy module either deleted
or reduced to a trivially removable shim.

## Why This Tranche Exists

The caller-first refactor is functionally complete:

- canonical `MediaDatabase` method ownership is now package-native
- normalized legacy-owned method count is `0`
- runtime loader handoff to `media_db.native_class` already exists

That does **not** mean the monolith is gone.

Today, the remaining compatibility debt is structural:

- `media_database_impl.py` still imports `Media_DB_v2` and assembles the
  canonical class by cloning `_LegacyMediaDatabase`
- `Media_DB_v2.py` is still an 8k-line implementation-bearing module
- several package-internal runtime/schema helpers still import
  `Media_DB_v2` as a support seam
- tests and active documentation still reference the legacy import path

So the next tranche is no longer about extracting individual methods. It is
about severing the final class-definition chain and collapsing the compatibility
surface.

## Current Ground Truth

As of this design:

- `media_db.runtime.media_class` already resolves the canonical class through
  `media_db.native_class`
- `media_db.native_class` already re-exports the canonical class
- `media_db.media_database_impl.MediaDatabase` is still assembled by cloning the
  final `_LegacyMediaDatabase` class dictionary from `Media_DB_v2.py`
- `Media_DB_v2.py` already has a lazy `__getattr__` re-export for
  `MediaDatabase`, but it still contains the full legacy implementation

This means the runtime import path is native, but the implementation root is
still legacy-shaped.

## Design Principles

### 1. Remove structure, not behavior

This tranche should change ownership and import boundaries, not runtime
behavior. The canonical class, helper seams, and bootstrap behavior should stay
semantically identical.

### 2. Treat deletion as a gated outcome

The user asked for a full removal-ready plan. That does **not** justify a blind
hard delete of `Media_DB_v2.py`.

Actual deletion should happen only if all of the following become true in the
same tranche:

- no package-internal production module imports `Media_DB_v2`
- no active tests import `Media_DB_v2`
- no active non-historical docs instruct users to import `Media_DB_v2`
- the retained compatibility exports have package-native replacements

If any of those remain, the acceptable fallback is a tiny explicit shim with
recorded blockers.

### 3. Exclude historical plan documents from the zero-ref target

Historical records under `Docs/Plans/` are design history. They can still
mention `Media_DB_v2` without blocking the runtime cleanup. The live boundary
for this tranche is:

- production app/runtime code
- active tests
- active user-facing or developer-facing docs outside historical plans/artifacts

## Scope

### In scope

- Remove the canonical class-clone dependency on `Media_DB_v2.py`
- Make `media_database_impl.py` the real owner of the canonical class object
- Remove package-internal helper imports of `Media_DB_v2`
- Migrate active tests and active docs off `Media_DB_v2`
- Narrow any remaining `DB_Manager` media compatibility surface that still
  points back toward the legacy module
- Delete `Media_DB_v2.py` if the deletion gate passes, or reduce it to a tiny
  explicit shim if not

### Out of scope

- Rewriting historical design documents
- Broad redesign of media DB semantics
- Reopening previously completed helper/body extraction work
- Unrelated `DB_Manager` non-media factories or backend/config helpers

## Architecture

### A. Make `media_database_impl.py` the direct class owner

The canonical `MediaDatabase` class should stop being created through
`_clone_legacy_media_database()`.

Instead:

- define `MediaDatabase` directly in
  `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`
- preserve the already-rebound package-native methods and class attributes
- preserve any required non-method attributes previously inherited from the
  legacy class

After this step, the canonical class must no longer require importing
`Media_DB_v2` for assembly.

### B. Keep `media_database.py` and `native_class.py` as thin exports

These modules already represent the desired package-native import surface and
should remain thin:

- `media_db.media_database`
- `media_db.native_class`

They should both re-export the class from `media_database_impl.py`, with no
back-reference to `Media_DB_v2`.

### C. Replace package-internal legacy imports with explicit native seams

A small number of runtime/schema helper modules still import `Media_DB_v2`
directly. Those imports should be eliminated by moving them to explicit
package-native helpers or constants.

Examples already visible in the tree include:

- runtime FTS helpers
- execution helpers
- SQLite bootstrap helpers
- backup helpers
- a small number of schema/migration helpers

The target state is that `app/core/DB_Management/media_db/**` does not import
`Media_DB_v2` at all.

### D. Convert `Media_DB_v2.py` from implementation module to boundary artifact

Once the class clone and package-internal imports are gone, `Media_DB_v2.py`
should no longer own:

- `_LegacyMediaDatabase`
- the full method surface
- canonical bootstrap or rollback behavior

At that point it should become one of two things:

1. preferred outcome: deleted entirely
2. fallback outcome: a tiny explicit compatibility shim that re-exports the
   surviving package-native symbols and nothing else

If a shim remains, it should be measured in tens of lines, not thousands.

### E. Move active tests and docs to the native import path

The remaining direct references to `Media_DB_v2` are now mostly in:

- tests
- active code documentation and product docs

These should migrate to:

- `media_db.native_class.MediaDatabase`
- `media_db.media_database.MediaDatabase`
- package-native services/APIs where appropriate

Compatibility-specific tests may remain only if the final tranche intentionally
keeps a tiny shim. If the file is deleted, those tests must be replaced by
native-boundary tests.

### F. Keep `DB_Manager` as a separate cleanup boundary

`DB_Manager` is no longer the canonical media surface, but it still needs a
light audit during this tranche so it does not preserve a hidden path back into
`Media_DB_v2`.

The requirement is not to delete `DB_Manager`, only to ensure any retained media
forwards delegate to package-native modules rather than the legacy monolith.

## Deletion Gate

`Media_DB_v2.py` may be deleted in this tranche only if all of the following
pass:

1. source scan of `tldw_Server_API/app/` finds zero imports of `Media_DB_v2`
2. source scan of active tests finds zero imports of `Media_DB_v2`
3. source scan of active docs finds zero instructional references to
   `Media_DB_v2`
4. focused runtime tests pass using only package-native imports
5. `DB_Manager` media forwards, if any remain, do not depend on `Media_DB_v2`

If any of these fail, the tranche should stop at a tiny shim and document the
remaining blockers explicitly.

## Testing Strategy

### Boundary tests

Add or update tests that prove:

- `media_database_impl.py` no longer imports `Media_DB_v2`
- `_clone_legacy_media_database()` no longer exists
- package-internal `media_db/**` modules no longer import `Media_DB_v2`
- active tests/docs no longer reference `Media_DB_v2`

### Identity/runtime tests

Retain or add tests proving:

- `native_class.MediaDatabase`
- `media_database.MediaDatabase`
- runtime loader/session helpers

all resolve the same direct native class object.

### Compatibility gate tests

If a tiny shim remains, add focused tests proving the shim is intentionally
small and only re-exports approved symbols. If the file is deleted, replace
those tests with a deletion guard scan.

## Success Criteria

The tranche is successful when:

- `media_database_impl.py` no longer clones `_LegacyMediaDatabase`
- `app/core/DB_Management/media_db/**` has zero imports of `Media_DB_v2`
- active tests and active docs no longer rely on `Media_DB_v2`
- `DB_Manager` media compatibility does not route through the monolith
- `Media_DB_v2.py` is either deleted or reduced to a tiny explicit shim
- focused runtime/boundary verification is clean

## Recommendation

Implement this as a staged, TDD-driven cleanup with a hard deletion gate at the
end. That keeps the tranche deletion-ready without turning it into an unsafe
big-bang rewrite.
