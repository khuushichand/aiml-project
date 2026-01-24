## Stage 1: Diff and scope alignment
**Goal**: Identify all extension-side changes for Flashcards, Evaluations, Collections, and Multi-Item Review that must be mirrored in the web UI.
**Success Criteria**: File-level diff list captured; required hooks/settings/locales identified.
**Tests**: Not applicable (analysis stage).
**Status**: Complete

## Stage 2: Sync feature code
**Goal**: Update web UI components/hooks/routes/settings to match the extension refactors for the four features.
**Success Criteria**: Web UI uses the extension-side implementations for the four areas; new hooks/settings compile.
**Tests**: `bunx next build`.
**Status**: Complete

## Stage 3: Locale updates and verification
**Goal**: Align English locale strings with updated UI behavior and validate build.
**Success Criteria**: `en` locale strings updated for the changed UI; build completes.
**Tests**: `bunx next build`.
**Status**: Complete
