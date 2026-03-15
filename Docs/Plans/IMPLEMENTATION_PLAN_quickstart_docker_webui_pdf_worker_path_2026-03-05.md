## Stage 1: Confirm Root Cause
**Goal**: Reproduce `make quickstart-docker-webui` and isolate the exact failing command.
**Success Criteria**: Build failure is reproduced with logs showing concrete error location.
**Tests**: Manual repro via `make quickstart-docker-webui`.
**Status**: Complete

## Stage 2: Add Regression Test (Red)
**Goal**: Add a test that fails when the PDF worker copy script only supports one node_modules layout.
**Success Criteria**: New test fails against current script behavior.
**Tests**: Targeted pytest case for `apps/tldw-frontend/scripts/copy-pdf-worker.mjs` path resolution strategy.
**Status**: Complete

## Stage 3: Implement Fix (Green)
**Goal**: Update the script to resolve `pdfjs-dist` worker path across local and hoisted workspace installs.
**Success Criteria**: New test passes and script remains backward compatible.
**Tests**: Re-run targeted pytest tests.
**Status**: Complete

## Stage 4: Verify Docker Quickstart Path
**Goal**: Validate `make quickstart-docker-webui` proceeds past dependency install and completes build/start.
**Success Criteria**: Compose stack starts (`app`, `webui`) without the prior postinstall failure.
**Tests**: Manual run of `make quickstart-docker-webui`.
**Status**: Blocked (local port conflict on 5432 from existing container `tldw_postgres_test`)
