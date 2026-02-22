# Implementation Plan Index: World Books UX/HCI Remediation

## Execution Status (2026-02-18)

- All 12 category plans are currently implemented with stages marked complete.
- Stable verification command for this workstream:
  - `cd apps/packages/ui && bun run test:worldbooks`
  - This runs `src/components/Option/WorldBooks/__tests__` with `--maxWorkers=1` to avoid timeout noise from high-parallel execution.

## Purpose

This index maps the 12 world-books category plans into one prioritized delivery sequence aligned to the roadmap phases from the 2026-02-17 review.

## Priority Order (Recommended)

| Rank | Plan | Primary Phase | Why Now | Depends On |
|---|---|---|---|---|
| 1 | `IMPLEMENTATION_PLAN_world_books_02_creation_editing_2026_02_18.md` | Phase 1 | Fixes default mismatches and form clarity issues that can silently misconfigure new books. | None |
| 2 | `IMPLEMENTATION_PLAN_world_books_01_list_overview_2026_02_18.md` | Phase 1 | Adds table search/filter/sort and at-a-glance metadata, removing immediate list-management friction. | None |
| 3 | `IMPLEMENTATION_PLAN_world_books_03_entry_management_2026_02_18.md` | Phase 1 -> 2 | Delivers drawer width fix, content/token feedback, appendable clarity, and bulk-add batching; then virtualization and advanced authoring upgrades. | 2 (shared form/tooltip conventions) |
| 4 | `IMPLEMENTATION_PLAN_world_books_10_error_handling_edge_cases_2026_02_18.md` | Phase 1 | Establishes resilience baselines (import diagnostics, optimistic concurrency, delete/undo clarity). | 3 (entry rendering strategy alignment) |
| 5 | `IMPLEMENTATION_PLAN_world_books_08_cross_feature_integration_2026_02_18.md` | Phase 2 -> 4 | Exposes test-matching in authoring flow and links world books with character/chat workflows. | 3 (stable entry interactions), 11 (test-match product scope) |
| 6 | `IMPLEMENTATION_PLAN_world_books_11_information_gaps_missing_functionality_2026_02_18.md` | Phase 2 -> 4 | Implements high-impact missing capabilities (test-match, budget visibility), then advanced organization/AI features. | 5 (shared test-match surface), 7 (budget visualization consistency) |
| 7 | `IMPLEMENTATION_PLAN_world_books_07_statistics_modal_2026_02_18.md` | Phase 2 -> 4 | Adds budget utilization and actionable statistics that feed remediation workflows. | 3 (token estimator exposure), 11 (budget bar semantics) |
| 8 | `IMPLEMENTATION_PLAN_world_books_06_import_export_2026_02_18.md` | Phase 2 | Enables SillyTavern/Kobold interoperability and better import confidence. | None |
| 9 | `IMPLEMENTATION_PLAN_world_books_04_bulk_operations_2026_02_18.md` | Phase 2 -> 4 | Adds missing bulk operations; interop import stage should reuse converters from plan 6. | 6 (format converters), 3 (selection model parity) |
| 10 | `IMPLEMENTATION_PLAN_world_books_09_responsive_mobile_2026_02_18.md` | Phase 3 | Restores mobile usability for core list and entry workflows. | 1, 3 (stable desktop behavior before responsive branching) |
| 11 | `IMPLEMENTATION_PLAN_world_books_12_accessibility_2026_02_18.md` | Phase 3 | Closes ARIA/focus/validation gaps once key responsive layouts are in place. | 9 (final responsive DOM structure), None for Stage 1 audit |
| 12 | `IMPLEMENTATION_PLAN_world_books_05_character_attachment_2026_02_18.md` | Phase 3 -> 4 | Finalizes scalable matrix/list attachment UX and metadata controls after mobile and a11y foundations. | 9 (mobile fallback patterns), 12 (keyboard model guidance) |

## Phase Mapping (Roadmap-Aligned)

### Phase 1: Fixes and Foundation (1-2 days)
- `IMPLEMENTATION_PLAN_world_books_02_creation_editing_2026_02_18.md`
  - Stage 1 (defaults parity, optional/required clarity) -> covers `2.2`, `2.1`, `2.3`
- `IMPLEMENTATION_PLAN_world_books_01_list_overview_2026_02_18.md`
  - Stage 2 (search/filter/sorting) -> covers `1.5`, `1.6`
  - Stage 1 metadata uplift can run in parallel for `1.1`, `1.2`
- `IMPLEMENTATION_PLAN_world_books_03_entry_management_2026_02_18.md`
  - Stage 1 (drawer width fix) -> covers `3.1`
  - Stage 2 (appendable help + char/token count) -> covers `3.6`, `3.4`
  - Stage 4 (batch bulk add with progress) -> covers `3.13`
- `IMPLEMENTATION_PLAN_world_books_10_error_handling_edge_cases_2026_02_18.md`
  - Stage 2/3 foundation hardening (import errors + optimistic concurrency) -> covers `10.2`, `10.3`

### Phase 2: Power User Features (3-5 days)
- `IMPLEMENTATION_PLAN_world_books_08_cross_feature_integration_2026_02_18.md`
  - Stage 2 (`Test matching` UI using `processWorldBookContext`) -> covers `8.3`
- `IMPLEMENTATION_PLAN_world_books_11_information_gaps_missing_functionality_2026_02_18.md`
  - Stage 1 (`Test Match` authoring loop) -> covers `11.1`
  - Stage 3 (budget bars in authoring surfaces) -> covers `11.5`
- `IMPLEMENTATION_PLAN_world_books_03_entry_management_2026_02_18.md`
  - Stage 1 virtualization -> covers `3.2`
  - Stage 3 entry search/filter -> covers `3.7`
  - Stage 2 tag-style keyword editor -> covers `3.3`
- `IMPLEMENTATION_PLAN_world_books_07_statistics_modal_2026_02_18.md`
  - Stage 2 budget utilization and over-budget signaling -> covers `7.4`
- `IMPLEMENTATION_PLAN_world_books_06_import_export_2026_02_18.md`
  - Stage 3 SillyTavern/Kobold conversion -> covers `6.3`
- `IMPLEMENTATION_PLAN_world_books_04_bulk_operations_2026_02_18.md`
  - Stage 4 interop import path reuse -> covers `4.4`

### Phase 3: Mobile and Accessibility (2-3 days)
- `IMPLEMENTATION_PLAN_world_books_09_responsive_mobile_2026_02_18.md`
  - Stage 1 responsive world-book table -> covers `9.1`
  - Stage 2 touch target sizing -> covers `9.3`
  - Stage 3 matrix mobile fallback -> covers `9.4`
- `IMPLEMENTATION_PLAN_world_books_12_accessibility_2026_02_18.md`
  - Stage 2 disclosure semantics -> covers `12.3`
  - Stage 4 conflict and validation announcements -> covers `12.4`, `12.8`
  - Stage 3 matrix keyboard model -> covers `12.6`
- `IMPLEMENTATION_PLAN_world_books_05_character_attachment_2026_02_18.md`
  - Stage 1 scalable matrix/list behavior complements mobile fallback execution for attachment workflows.

### Phase 4: Polish and Differentiation (ongoing)
- `IMPLEMENTATION_PLAN_world_books_01_list_overview_2026_02_18.md`
  - Stage 4 onboarding empty state + world-book bulk ops -> covers `1.10`, `1.8`
- `IMPLEMENTATION_PLAN_world_books_02_creation_editing_2026_02_18.md`
  - Stage 4 duplicate/template bootstrapping -> covers `2.4`, `2.5`
- `IMPLEMENTATION_PLAN_world_books_11_information_gaps_missing_functionality_2026_02_18.md`
  - Stage 2 entry groups -> covers `11.2`
  - Stage 4 AI generation -> covers `11.4`
  - Stage 5 relationship insight strategy -> covers `11.6`, `11.3`
- `IMPLEMENTATION_PLAN_world_books_08_cross_feature_integration_2026_02_18.md`
  - Stage 1 character <-> world-book navigation -> covers `8.1`
  - Stage 4 chat lorebook activity -> covers `8.4`
- `IMPLEMENTATION_PLAN_world_books_07_statistics_modal_2026_02_18.md`
  - Stage 1 actionable stats and Stage 3 global stats -> covers `7.1`, `7.2`
- `IMPLEMENTATION_PLAN_world_books_04_bulk_operations_2026_02_18.md`
  - Stage 2/3 advanced bulk set-priority and cross-book move workflows.
- `IMPLEMENTATION_PLAN_world_books_05_character_attachment_2026_02_18.md`
  - Stage 3/4 per-attachment metadata and quick-attach/full-matrix clarity.
- `IMPLEMENTATION_PLAN_world_books_06_import_export_2026_02_18.md`
  - Stage 4 export-all and upload/dropzone polish.

## Critical Path Checkpoints

1. Complete Phase 1 before introducing net-new authoring surfaces in Phase 2.
2. Treat `Test Match` as one coordinated delivery across plans 8 and 11 to avoid duplicate UIs.
3. Finish format conversion core in plan 6 before plan 4 bulk import extensions.
4. Land responsive structure changes (plan 9) before final keyboard/focus a11y hardening (plan 12).
5. Reassess phase gates after Phase 2 with performance and error telemetry from large-lorebook fixtures.
