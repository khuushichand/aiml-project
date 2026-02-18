# Implementation Plan Index: Prompts Page UX/HCI Remediation

## Purpose

This index maps the 10 Prompts page category plans into one prioritized delivery sequence aligned to the 2026-02-17 review roadmap.

## Plan Catalog

| # | Plan | Category | Primary Scope |
|---|---|---|---|
| 1 | `IMPLEMENTATION_PLAN_prompts_page_01_custom_prompts_tab_2026_02_18.md` | Custom Prompts Tab | Search, pagination, sorting, metadata visibility, import/export, bulk ops |
| 2 | `IMPLEMENTATION_PLAN_prompts_page_02_prompt_drawer_create_edit_2026_02_18.md` | Prompt Drawer (Create/Edit) | Token/char visibility, templates, few-shot editing, draft safety |
| 3 | `IMPLEMENTATION_PLAN_prompts_page_03_sync_conflict_management_2026_02_18.md` | Sync & Conflict Management | Conflict resolution UI, batch sync, failure visibility, detection hardening |
| 4 | `IMPLEMENTATION_PLAN_prompts_page_04_copilot_tab_2026_02_18.md` | Copilot Tab | `{text}` guidance, copy-to-custom, search/filter, update-contract safety |
| 5 | `IMPLEMENTATION_PLAN_prompts_page_05_trash_tab_2026_02_18.md` | Trash Tab | Search, time-to-purge visibility, bulk restore, preview |
| 6 | `IMPLEMENTATION_PLAN_prompts_page_06_studio_tab_2026_02_18.md` | Studio Tab | Disabled-state guidance, queue interpretation, provider/model validation |
| 7 | `IMPLEMENTATION_PLAN_prompts_page_07_accessibility_2026_02_18.md` | Accessibility | Critical control labeling, focus/target size, shortcut help |
| 8 | `IMPLEMENTATION_PLAN_prompts_page_08_responsive_mobile_experience_2026_02_18.md` | Responsive & Mobile | Toolbar responsiveness, table overflow affordance, touch ergonomics |
| 9 | `IMPLEMENTATION_PLAN_prompts_page_09_error_handling_edge_cases_2026_02_18.md` | Error Handling & Edge Cases | Bulk partial-success handling, import diagnostics, error boundary |
| 10 | `IMPLEMENTATION_PLAN_prompts_page_10_missing_functionality_backend_gaps_2026_02_18.md` | Missing Functionality & Backend Gaps | Collections, sharing, usage tracking, quick test, settings UI |

## Priority Order (Recommended)

| Rank | Plan | Primary Phase | Why Now | Depends On |
|---|---|---|---|---|
| 1 | `IMPLEMENTATION_PLAN_prompts_page_03_sync_conflict_management_2026_02_18.md` | Phase 1 | Resolves highest-risk data-integrity gap: no conflict resolution UI. | None |
| 2 | `IMPLEMENTATION_PLAN_prompts_page_01_custom_prompts_tab_2026_02_18.md` | Phase 1 -> 2 | Replaces client-only search and no-pagination bottlenecks with backend FTS flow. | 3 (sync/bulk semantics alignment) |
| 3 | `IMPLEMENTATION_PLAN_prompts_page_09_error_handling_edge_cases_2026_02_18.md` | Phase 1 | Adds page-level crash containment and robust bulk/import failure handling. | None |
| 4 | `IMPLEMENTATION_PLAN_prompts_page_02_prompt_drawer_create_edit_2026_02_18.md` | Phase 1 -> 2 | Adds token visibility and editing safety for the core authoring path. | 1 (table/create-edit flow context) |
| 5 | `IMPLEMENTATION_PLAN_prompts_page_06_studio_tab_2026_02_18.md` | Phase 1 -> 2 | Fixes disabled-tab ambiguity and execution-config validation gaps. | 7 (mobile/a11y label semantics) |
| 6 | `IMPLEMENTATION_PLAN_prompts_page_07_accessibility_2026_02_18.md` | Phase 1 -> 3 | Closes important accessibility gaps while preserving current strengths. | None |
| 7 | `IMPLEMENTATION_PLAN_prompts_page_04_copilot_tab_2026_02_18.md` | Phase 2 | Improves copilot iteration speed and avoids accidental prompt replacement risk. | 1 (shared prompt create/edit patterns) |
| 8 | `IMPLEMENTATION_PLAN_prompts_page_08_responsive_mobile_experience_2026_02_18.md` | Phase 2 -> 3 | Improves mobile operability once core interaction regressions are stabilized. | 1, 7 |
| 9 | `IMPLEMENTATION_PLAN_prompts_page_05_trash_tab_2026_02_18.md` | Phase 3 | Adds recovery ergonomics after primary create/sync workflows are solid. | 9 (bulk partial-success patterns) |
| 10 | `IMPLEMENTATION_PLAN_prompts_page_10_missing_functionality_backend_gaps_2026_02_18.md` | Phase 3 | Lands larger net-new features after reliability and usability baselines are met. | 1, 3, 6 |

## Phase Mapping (Roadmap-Aligned)

### Phase 1: Critical Fixes (1-2 weeks)
- `IMPLEMENTATION_PLAN_prompts_page_03_sync_conflict_management_2026_02_18.md`
  - Stage 1: conflict modal + resolution actions (`3.1`)
  - Stage 2: sync failure visibility (`3.2`) and offline status context (`3.6`)
- `IMPLEMENTATION_PLAN_prompts_page_01_custom_prompts_tab_2026_02_18.md`
  - Stage 1: backend search + pagination baseline (`1.1`, `1.2`)
- `IMPLEMENTATION_PLAN_prompts_page_02_prompt_drawer_create_edit_2026_02_18.md`
  - Stage 1: character/token counts (`2.1`)
- `IMPLEMENTATION_PLAN_prompts_page_06_studio_tab_2026_02_18.md`
  - Stage 1: disabled-tab explanation (`6.1`) and mobile navigation clarity (`6.3`)
- `IMPLEMENTATION_PLAN_prompts_page_07_accessibility_2026_02_18.md`
  - Stage 2: icon labeling/focus/target-size remediation (`7.6`, `7.7`, `7.8`)
- `IMPLEMENTATION_PLAN_prompts_page_09_error_handling_edge_cases_2026_02_18.md`
  - Stage 4: Prompts page error boundary (`9.6`)

### Phase 2: Core UX Improvements (2-4 weeks)
- `IMPLEMENTATION_PLAN_prompts_page_01_custom_prompts_tab_2026_02_18.md`
  - Stage 2/3: sorting, modified column, export formats, bulk actions (`1.4`, `1.5`, `1.6`, `1.8`)
- `IMPLEMENTATION_PLAN_prompts_page_02_prompt_drawer_create_edit_2026_02_18.md`
  - Stage 2/3/4: templates, few-shot inline editing, version history access, unsaved-change handling (`2.2`, `2.3`, `2.4`, `2.7`)
- `IMPLEMENTATION_PLAN_prompts_page_03_sync_conflict_management_2026_02_18.md`
  - Stage 3/4: sync-all and content-hash conflict hardening (`3.3`, `3.4`)
- `IMPLEMENTATION_PLAN_prompts_page_04_copilot_tab_2026_02_18.md`
  - Stage 1/2/3: placeholder guidance, copy-to-custom, search/filter (`4.1`, `4.2`, `4.3`)
- `IMPLEMENTATION_PLAN_prompts_page_06_studio_tab_2026_02_18.md`
  - Stage 2/3: queue-health interpretation, provider/model selects/defaults (`6.2`, `6.5`, `6.6`)
- `IMPLEMENTATION_PLAN_prompts_page_08_responsive_mobile_experience_2026_02_18.md`
  - Stage 1/2: responsive toolbar + table overflow affordances (`8.1`, `8.2`)
- `IMPLEMENTATION_PLAN_prompts_page_09_error_handling_edge_cases_2026_02_18.md`
  - Stage 2/3: settle-all bulk handling and precise import diagnostics (`9.3`, `9.5`)

### Phase 3: Feature Enrichment (4-8 weeks)
- `IMPLEMENTATION_PLAN_prompts_page_10_missing_functionality_backend_gaps_2026_02_18.md`
  - Stage 1-5: collections, usage tracking, sharing, quick test, settings UI (`10.1`-`10.6`)
- `IMPLEMENTATION_PLAN_prompts_page_05_trash_tab_2026_02_18.md`
  - Stage 1-3: trash search/preview, retention visibility, bulk restore (`5.1`-`5.4`)
- `IMPLEMENTATION_PLAN_prompts_page_08_responsive_mobile_experience_2026_02_18.md`
  - Stage 3: touch-target compliance (`8.3`)
- `IMPLEMENTATION_PLAN_prompts_page_07_accessibility_2026_02_18.md`
  - Stage 3: keyboard shortcut help surface (`7.9`)
- `IMPLEMENTATION_PLAN_prompts_page_06_studio_tab_2026_02_18.md`
  - Stage 4: WebSocket status pipeline (`6.4`)

## Critical Path Checkpoints

1. Ship conflict resolution (plan 3) before enabling larger sync and bulk workflows (plans 1 and 10).
2. Land error boundary and settle-all bulk patterns (plan 9) before large feature additions to reduce regression risk.
3. Coordinate Studio mobile labeling across plans 6 and 7 so accessibility and responsive changes do not diverge.
4. Defer collections/sharing/usage expansion (plan 10) until Phase 1 and Phase 2 stability metrics are acceptable.
