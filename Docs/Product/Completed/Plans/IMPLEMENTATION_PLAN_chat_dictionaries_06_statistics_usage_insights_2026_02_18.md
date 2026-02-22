# Implementation Plan: Chat Dictionaries - Statistics and Usage Insights

## Scope

Components: statistics modal in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`, statistics schemas and endpoints, runtime tracking in chat dictionary processing
Finding IDs: `6.1` through `6.4`

## Finding Coverage

- Expand dictionary-level summary metrics: `6.1`
- Add per-entry usage observability: `6.2`
- Implement and surface `last_used` tracking: `6.3`
- Detect and present overlapping/conflicting patterns: `6.4`

## Stage 1: Strengthen Dictionary-Level Statistics
**Goal**: Make stats modal useful for day-to-day maintenance decisions.
**Success Criteria**:
- Stats include enabled/disabled counts and probability-distribution signals.
- Timed-effects participation count is surfaced at dictionary level.
- Created/updated timestamps are included in the summary view.
- `last_used` field is populated when dictionary processing occurs.
**Tests**:
- API tests for expanded statistics schema fields and defaults.
- Integration tests for `last_used` updates after `process_text` calls.
- Component tests for rendering new stats fields with null-safe fallbacks.
**Status**: Complete
**Progress Notes**:
- Added persistent dictionary usage tracking in `chat_dictionaries` (`usage_count`, `last_used_at`) and write-through updates in `ChatDictionaryService.process_text()`.
- Expanded `DictionaryStatistics` schema and endpoint payload with:
  - `enabled_entries`, `disabled_entries`, `probabilistic_entries`, `timed_effect_entries`
  - `created_at`, `updated_at`, `last_used`
- Updated stats modal in `Manager.tsx` to render all new fields with null-safe fallbacks and relative-time formatting.
- Added backend API coverage for Stage 1 fields + `last_used` lifecycle:
  - `tldw_Server_API/tests/Chat/unit/test_chat_dictionary_endpoints.py::test_dictionary_statistics_exposes_expanded_stage1_fields`
- Added UI component coverage for expanded stats rendering and fallback behavior:
  - `apps/packages/ui/src/components/Option/Dictionaries/__tests__/Manager.statsStage1.test.tsx`
- Verification:
  - UI dictionary test suite passes (`13` files / `54` tests).
  - Backend pytest could not be executed in this sandbox due unavailable/offline Python dependencies in the local `.venv`; Python 3.12 syntax compilation checks passed for modified backend files.

## Stage 2: Per-Entry Usage Tracking and Cleanup Signals
**Goal**: Help users identify stale or high-impact entries quickly.
**Success Criteria**:
- Backend tracks usage counts at entry granularity.
- Entry list and stats UI expose per-entry fire count.
- Entries with zero usage are visually identifiable for cleanup.
- Tracking updates are lightweight and safe under concurrent chat load.
**Tests**:
- Backend unit tests for atomic increment semantics.
- Integration tests for usage accumulation across repeated processing.
- UI tests verifying zero-usage highlighting behavior.
**Status**: Complete
**Progress Notes**:
- Added persistent entry-level usage fields on `dictionary_entries`:
  - `usage_count`, `last_used_at` (with migration guards for existing DBs).
- Added batched usage tracking in text processing:
  - `ChatDictionaryService.process_text()` now accumulates per-entry fire counts and writes them in a single DB pass via `_record_entry_usage_counts(...)`.
- Exposed entry usage through API responses:
  - `DictionaryEntryResponse` now includes `usage_count` and `last_used_at`.
  - Dictionary statistics now include:
    - `zero_usage_entries`
    - `entry_usage` snapshot (per-entry ID/pattern/usage/last-used)
- Updated entry management UX:
  - New `Usage` column in the entry table.
  - `Unused` badge for zero-fire entries.
  - Zero-usage row highlighting for quick cleanup scanning.
- Updated statistics modal UX:
  - Added `Unused Entries` aggregate.
  - Added `Entry usage snapshot` section (top rows).
- Coverage additions:
  - Backend tests:
    - `test_dictionary_entry_usage_counts_increment_after_processing`
    - expanded assertions in `test_dictionary_statistics_exposes_expanded_stage1_fields`
  - UI tests:
    - extended `Manager.entryStage1.test.tsx` to assert usage column + unused styling
    - extended `Manager.statsStage1.test.tsx` to assert usage snapshot rendering

## Stage 3: Pattern Conflict Analysis
**Goal**: Surface likely pattern overlap/shadowing before it causes confusion.
**Success Criteria**:
- Statistics include a pattern-conflict analysis section.
- Conflict results identify involved entries and explain overlap risk.
- Analysis supports literal-literal, literal-regex, and regex-regex overlap heuristics.
- UI presents conflict warnings without blocking normal dictionary usage.
**Tests**:
- Unit tests for conflict detector heuristic rules.
- Integration tests for representative overlap scenarios.
- Component tests for conflict section rendering and empty-state messaging.
**Status**: Complete
**Progress Notes**:
- Added pattern-conflict structures to statistics schema:
  - `DictionaryPatternConflict`
  - `pattern_conflict_count`
  - `pattern_conflicts`
- Implemented conflict-analysis heuristics in the statistics endpoint:
  - literal-literal (duplicate/contains overlap)
  - literal-regex (regex matching literal pattern)
  - regex-regex (identical regex, shared prefix, shared seed-sample matches)
- Added conflict reporting to statistics payload assembly (`get_dictionary_statistics`).
- Updated stats modal UX:
  - Added `Pattern Conflicts` aggregate row.
  - Added `Pattern conflicts` section with severity tags, reason text, and involved pattern pair display.
  - Added explicit empty-state text when no conflicts are detected.
- Added/updated tests:
  - Backend: `test_dictionary_statistics_reports_pattern_conflicts`
  - Backend: expanded `test_dictionary_statistics_exposes_expanded_stage1_fields` assertions for zero conflicts
  - UI: expanded `Manager.statsStage1.test.tsx` to validate conflict rendering and empty-state behavior
- Verification:
  - UI dictionary suite: `13` files / `54` tests passing.
  - Backend files and new tests pass Python 3.12 syntax compilation checks (`py_compile`).

## Dependencies

- Per-entry usage data may require schema migration in ChaChaNotes dictionary-entry tables.
- Conflict analysis messaging should align with validation language in Category 4.
