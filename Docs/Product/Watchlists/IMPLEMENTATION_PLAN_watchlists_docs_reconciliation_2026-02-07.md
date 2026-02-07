## Stage 1: Audit Target Docs
**Goal**: Confirm stale statements and path mismatches across Watchlists docs.
**Success Criteria**: All stale claims are enumerated with file anchors and expected corrected wording.
**Tests**: `rg`/manual pass to verify each stale line is identified before edits.
**Status**: Complete

## Stage 2: Apply Documentation Corrections
**Goal**: Update implementation plan/PRD/filters/checklist docs to match shipped behavior.
**Success Criteria**: Stale "planned/not implemented" claims are corrected; status markers updated; checklist items reconciled.
**Tests**: Manual diff review for each edited file.
**Status**: In Progress

## Stage 3: Reconcile API Doc References
**Goal**: Replace stale Watchlists API doc path references with current path.
**Success Criteria**: All relevant docs point to `Docs/API-related/Watchlists_API.md`.
**Tests**: `rg` search for stale paths under `Docs/Product/Watchlists`.
**Status**: Not Started

## Stage 4: Final Validation and Closeout
**Goal**: Verify resulting docs are internally consistent and remove this temporary plan file.
**Success Criteria**: Final scan shows no remaining stale claims in scope; temporary plan removed.
**Tests**: `rg` + spot-read of edited sections.
**Status**: Not Started
