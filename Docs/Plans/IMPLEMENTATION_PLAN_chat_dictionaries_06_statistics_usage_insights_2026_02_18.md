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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Per-entry usage data may require schema migration in ChaChaNotes dictionary-entry tables.
- Conflict analysis messaging should align with validation language in Category 4.
