# Issue #758 Reading Import Quality Implementation Plan

## Stage 1: Normalize Imported Input Before Persistence
**Goal**: Canonicalize import URLs and merge equivalent entries within the same batch.
**Success Criteria**:
- Import normalization removes common tracking parameters where possible.
- Duplicate import entries are merged by canonical URL.
- Merge preserves strongest status and unions tags/favorite flags.
**Tests**:
- Unit tests for normalization and duplicate-merge behavior.
**Status**: Complete

## Stage 2: Enrich Metadata at Upsert Time
**Goal**: Improve stored reading metadata quality from imports.
**Success Criteria**:
- Imported rows persist normalized URL/canonical URL and derived domain.
- Missing titles are backfilled from URL path/domain.
- `read_at` is auto-populated when status is read and timestamp is missing.
**Tests**:
- Reading service import test for normalized URL/domain/read timestamp.
**Status**: Complete

## Stage 3: Verify, Security Scan, and Document
**Goal**: Validate behavior and update API docs for users.
**Success Criteria**:
- Targeted import normalization/service tests pass.
- Bandit is clean on touched reading paths.
- Reading API docs include normalization semantics.
**Tests**:
- `pytest` targeted import normalization and reading service tests.
- `bandit` on touched reading modules.
**Status**: Complete
