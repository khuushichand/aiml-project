## Stage 1: Reading Import/Export UX
**Goal**: Ship a self-service Pocket/Instapaper import + export experience in the Reading List UI with clear validation and results feedback.
**Success Criteria**: Users can import Pocket JSON and Instapaper CSV via modal/drag-drop; results show imported/updated/skipped/errors; export panel supports jsonl/zip with current filters preserved; error states surfaced for 400/413 responses.
**Tests**: Frontend unit tests for import modal and export panel; mock API responses for success/failure; coverage for file type validation.
**Status**: Not Started

## Stage 2: Output Template Editor (Watchlists)
**Goal**: Provide a template editor with list/create/edit/preview flows and wire defaults into job output preferences.
**Success Criteria**: Template list loads from `/api/v1/outputs/templates`; create/edit/delete works; preview renders; job editor can assign default templates without leaving the flow.
**Tests**: Frontend unit tests for template list/editor; mock preview API; regression test for job editor template selection persistence.
**Status**: Not Started

## Stage 3: Bulk Item Actions
**Goal**: Add multi-select bulk actions to Items and Reading lists for tag/status/favorite/delete and output generation.
**Success Criteria**: Multi-select is stable across pagination; bulk actions show progress and per-item failures; actions are reversible where supported.
**Tests**: Frontend unit tests for selection state and bulk action summaries; mock API success/partial failure cases.
**Status**: Not Started

## Stage 4: Reader Highlights + Notes Dirty Indicator
**Goal**: Complete highlight creation/edit/delete UI in the reader view and add a clear unsaved-notes indicator with autosave or save prompt.
**Success Criteria**: Highlights can be created/edited/deleted via `/reading/items/{id}/highlight` and `/reading/highlights/{id}`; stale highlights display a badge; notes edits show a dirty indicator and persist safely before navigation.
**Tests**: Frontend unit tests for highlight CRUD flows; dirty indicator state transitions; navigation guard/autosave behavior.
**Status**: Not Started
