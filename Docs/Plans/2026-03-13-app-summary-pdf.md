# App Summary PDF Implementation Plan

## Stage 1: Confirm repo-backed content
**Goal**: Extract only evidence-supported product, architecture, and setup facts from the repository.
**Success Criteria**: All PDF copy maps back to README, package metadata, or source tree evidence.
**Tests**: Manual source cross-check before generation.
**Status**: Complete

## Stage 2: Generate a compact two-page PDF
**Goal**: Build a reproducible generator that writes the summary PDF to `output/pdf/`.
**Success Criteria**: PDF contains the required sections and fits within two pages.
**Tests**: Run generator and confirm the output file exists.
**Status**: Complete

## Stage 3: Render and visually inspect both pages
**Goal**: Verify spacing, clipping, hierarchy, and readability from rendered page images.
**Success Criteria**: No clipped text, overlap, or overflow on either page.
**Tests**: Render PDF pages to PNG and inspect both images.
**Status**: Complete

## Stage 4: Final verification
**Goal**: Run Bandit on the touched script and confirm deliverable path.
**Success Criteria**: No new high-signal security issues in changed code; final artifact path is stable.
**Tests**: `source .venv/bin/activate && python -m bandit -r tmp/pdfs/generate_tldw_server_repo_summary_pdf.py -f json -o /tmp/bandit_app_summary_pdf.json`
**Status**: Complete
