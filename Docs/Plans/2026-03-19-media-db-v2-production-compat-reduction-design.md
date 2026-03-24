# Media DB V2 Production Compat Reduction Design

**Status:** Proposed, reviewed, and approved on 2026-03-19.

**Goal:** Reduce production reliance on Media DB compatibility helpers by moving a bounded set of media endpoints off `legacy_*` imports and off the `DB_Manager` listing wrapper path, while keeping runtime/class-chain work out of scope.

## Why This Tranche Exists

The previous tranche completed the caller-import cleanup for many test domains and
made `media_db.native_class` the preferred import surface for most non-compat
callers. That reduced test churn, but it did not materially reduce the remaining
production compatibility surface.

Fresh source review shows that production code still depends on:

- `media_db.legacy_content_queries`
- `media_db.legacy_wrappers`
- `media_db.legacy_state`
- `media_db.legacy_maintenance`
- `media_db.legacy_reads`
- `DB_Manager.get_paginated_files`
- `DB_Manager.get_paginated_trash_files`

across a number of media endpoints and service modules.

This tranche intentionally does **not** try to solve all of that at once. It
targets the most user-facing and lowest-risk production callers first, while
keeping the actual implementation behavior stable by adding thin package-native
facades instead of rewriting logic.

## Review Corrections Incorporated

### 1. Include the `DB_Manager` listing path in scope

The first draft focused on `legacy_*` imports in a few endpoints, but
`media/listing.py` still reaches compatibility logic through:

- `DB_Manager.get_paginated_files`
- `DB_Manager.get_paginated_trash_files`

So a meaningful production compat-reduction slice must include the listing
wrapper path as well.

### 2. Add native facades first, do not rewrite helper behavior in endpoints

Several target endpoints still depend on helper-specific operations:

- keyword fetch helpers
- permanent delete
- media existence checks
- document-version lookup
- transcript lookup

Those operations already exist in extracted compatibility modules and mostly
delegate into repositories or DB methods. The safest next step is to expose
package-native API facades that call the existing implementations, then migrate
callers to those facades. This avoids endpoint-level SQL rewrites or direct DB
method sprawl.

### 3. Keep permanent-delete semantics intact

Permanent delete currently does more than a row removal. The extracted helper
still performs FTS cleanup and vector invalidation hooks. This tranche must not
silently replace that behavior with a simpler deletion path. The package-native
facade should delegate to the existing maintenance implementation first.

### 4. Scope boundary guards to the tranche, not the whole app

Production app code outside the tranche still uses `legacy_*` modules. A broad
“no app legacy imports” guard would immediately fail and provide little value.

Instead, this tranche adds source guards only for:

- the selected media endpoints
- the `DB_Manager` listing wrapper boundary

and keeps explicit allowlists for:

- `Media_DB_v2.py`
- `DB_Manager.py`
- out-of-scope production modules such as Data Tables, MCP media, quiz source
  resolution, and ingestion persistence

### 5. Keep class-chain severing out of scope

`media_database.py` still subclasses the legacy class defined in
`Media_DB_v2.py`. That is real debt, but it is a separate and wider refactor.
Mixing it into this tranche would increase runtime risk substantially. This
tranche stays focused on production caller reduction only.

## Scope

### In scope

- Add thin package-native facades to `media_db.api` for the exact helper surface
  needed by this slice:
  - paginated media list
  - paginated trash list
  - keyword fetch single/batch
  - document version lookup
  - media existence check
  - permanent delete
  - latest transcription
- Migrate these endpoints off `legacy_*` imports and the listing wrapper path:
  - `app/api/v1/endpoints/media/item.py`
  - `app/api/v1/endpoints/media/listing.py`
  - `app/api/v1/endpoints/media/versions.py`
  - `app/api/v1/endpoints/media/document_insights.py`
  - `app/api/v1/endpoints/media/document_references.py`
- Remove the listing endpoint’s dependency on `DB_Manager.get_paginated_files`
  and `get_paginated_trash_files`.
- Add tranche-scoped source guards in tests.

### Out of scope

- Rewriting the actual underlying helper implementations in
  `legacy_content_queries.py`, `legacy_wrappers.py`, `legacy_state.py`,
  `legacy_maintenance.py`, or `legacy_reads.py`
- `navigation.py` contract cleanup
- Data Tables, MCP media, quiz source resolution, ingestion persistence, or
  audio-streaming transcript caller cleanup
- Class-definition chain severing for `MediaDatabase`
- Deleting the `legacy_*` modules touched by this tranche

## Architecture

### A. `media_db.api` becomes the caller-facing package boundary

The next safe step is not to delete the extracted compatibility helper modules,
but to stop importing them directly from production callers.

`media_db.api` should expose a narrow surface for the operations this tranche
needs, while delegating internally to the currently extracted implementations.

That keeps the behavior stable and gives future tranches a single caller-facing
package boundary to harden or replace.

### B. Endpoint migration should be import-only plus minimal call-site cleanup

The chosen endpoints are all already on a request-scoped Media DB dependency.
The migration should not alter dependency injection or invent new local
protocols.

Expected change shape:

- replace direct imports from `legacy_*` modules with `media_db.api`
- update call sites to use the new API wrappers
- preserve existing error handling and response shapes

### C. Remove the listing endpoint’s `DB_Manager` dependency now

The listing endpoint is a public production media surface. Leaving it on
`DB_Manager` would preserve the old compat path in one of the most frequently
used endpoints.

The package-native listing API should call the same underlying DB methods the
wrapper uses today:

- `get_paginated_files`
- `get_paginated_media_list`
- `get_paginated_trash_list`

The behavioral goal is parity, not novelty.

### D. Boundary tests should be tranche-shaped

The tests for this slice should answer:

1. do the chosen endpoints still import `legacy_*` helpers directly?
2. does `media/listing.py` still import the `DB_Manager` listing wrappers?
3. does the new `media_db.api` surface exist and stay callable?

That is enough to prevent regression without forcing unrelated modules into the
same tranche.

## Migration Order

### 1. Add source guards and API-surface tests

Start with failing tests that codify the new intended boundary:

- selected endpoints no longer import the targeted `legacy_*` modules
- `listing.py` no longer imports the `DB_Manager` listing wrappers
- `media_db.api` exposes the new package-native helper surface

### 2. Add thin `media_db.api` facades

Implement the new package-native functions as delegates to the current extracted
helper modules or DB methods.

This is the lowest-risk way to create a native caller boundary quickly.

### 3. Migrate the selected endpoints

Move the five production endpoints to the new API imports, keeping behavior and
error handling unchanged.

### 4. Verify the slice

Run focused endpoint, import-boundary, and helper tests; then run Bandit and
diff checks on the touched scope.

## Testing Strategy

### Boundary tests

Add tranche-scoped tests in `tests/DB_Management/test_media_db_api_imports.py`
that fail if:

- the selected endpoint files still import the targeted `legacy_*` modules
- `media/listing.py` still imports `get_paginated_files` or
  `get_paginated_trash_files` from `DB_Manager`

### Behavior tests

Use the existing endpoint and helper tests for:

- media item deletion and keyword updates
- media listing and trash listing
- media versions
- document insights
- document references

No new large integration harness is needed for this slice.

### Security and quality checks

- `git diff --check`
- Bandit on the touched Python paths
- focused pytest bundle covering the migrated endpoints and import guards

## Success Criteria

- The selected production endpoints no longer import `legacy_*` helpers
  directly.
- `media/listing.py` no longer depends on the `DB_Manager` listing wrappers.
- `media_db.api` exposes the helper surface needed by those endpoints.
- Behavior remains unchanged in the focused endpoint test suite.
- The remaining out-of-scope compat debt is smaller and more explicit.

## Deferred Follow-On Work

After this tranche, the next logical production compat slices are:

1. `navigation.py` alignment with the shared read contract
2. Data Tables and MCP media caller cleanup
3. quiz source resolution and ingestion transcript/state helper cleanup
4. true class-chain severing for `MediaDatabase`
