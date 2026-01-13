## Stage 1: Scope + Design
**Goal**: Define provider key sources/targets and MCP client config format/paths.
**Success Criteria**: Provider env mapping and MCP path table documented in code or plan; CLI options finalized.
**Tests**: N/A (design stage).
**Status**: Complete

## Stage 2: Providers Command Implementation
**Goal**: Write provider keys to `.env` with masking/backups and optional `config.txt` updates.
**Success Criteria**: `providers` supports `--dry-run`, optional config write, JSON output includes actions/paths.
**Tests**: Unit/integration tests for dry-run, env updates, and optional config write.
**Status**: Complete

## Stage 3: MCP Client Config Implementation
**Goal**: Add/remove MCP client configs with path detection, diff preview, backups, and confirmation.
**Success Criteria**: `mcp add/remove` updates per-client config with dry-run diff and duplicate avoidance.
**Tests**: Unit/integration tests for add/remove/dry-run paths and backup behavior.
**Status**: Complete

## Stage 4: Docs + PRD Updates
**Goal**: Align wizard docs and PRD Stage 5 status with implementation.
**Success Criteria**: `Docs/Development/Wizard.md` reflects new options; PRD Stage 5 updated.
**Tests**: N/A (doc stage).
**Status**: Complete
