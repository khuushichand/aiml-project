# M1.2 Navigation Terminology Matrix and Triage

Status: Complete (Engineering Closeout)  
Owner: WebUI + Product  
Milestone: M1.2 (February 18-February 24, 2026)  
Last Updated: February 13, 2026  
Related: `Docs/Product/Completed/WebUI-related/M1_Navigation_IA_Execution_Plan_2026_02.md`  
Related: `Docs/Product/Completed/WebUI-related/M1_1_Canonical_Route_Inventory_2026_02.md`

## Purpose

Establish one naming system for high-traffic routes across:
- Header shortcuts
- Sidebar shortcuts
- Command palette
- Settings navigation

This document is the triage baseline before string and UI updates.

## Source Files Reviewed

- `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- `apps/packages/ui/src/components/Common/ChatSidebar.tsx`
- `apps/packages/ui/src/components/Common/CommandPalette.tsx`
- `apps/packages/ui/src/components/Layouts/settings-nav.ts`
- `apps/packages/ui/src/assets/locale/en/option.json`
- `apps/packages/ui/src/assets/locale/en/common.json`
- `apps/packages/ui/src/assets/locale/en/settings.json`

## Canonical Naming Rules (M1.2)

1. Same route should use one primary noun phrase in all surfaces.
2. If a destination has tabs (example: Prompts + Studio), label the destination, not one internal tab.
3. Avoid generic labels when an action-specific one exists (example: use `Health & Diagnostics` consistently instead of mixed `Health`).
4. Avoid directional synonyms for the same route (`Review`, `Multi-Item`, `Multi-Item Review`) unless one is a subtitle.
5. Playground naming must align route intent and route slug (no swapped terms).

## Cross-Surface Label Matrix (Core Routes)

| Route | Header/Sidebar Label | Command Palette Label | Settings Nav Label | Assessment | Proposed Canonical Label |
|---|---|---|---|---|---|
| `/` | `Chat` | `Go to Chat` | — | Aligned | `Chat` |
| `/knowledge` | `Knowledge QA` | — | — | Missing quick-nav parity | `Knowledge QA` |
| `/media` | `Media` | `Go to Media` | `Media` | Aligned | `Media` |
| `/notes` | `Notes` | `Go to Notes` | — | Aligned | `Notes` |
| `/flashcards` | `Flashcards` | `Go to Flashcards` | — | Aligned | `Flashcards` |
| `/prompts` | `Prompts` | — | — | Missing quick-nav parity | `Prompts` |
| `/prompt-studio` (alias) | `Prompt Studio` (legacy concept) | — | `Prompt Studio` | Collides with unified prompts model | `Prompts (Studio tab)` |
| `/world-books` | `World Books` | — | `World Books` | Aligned | `World Books` |
| `/dictionaries` | `Chat dictionaries` | — | `Chat Dictionaries` | Case/style mismatch | `Chat Dictionaries` |
| `/characters` | `Characters` | — | `Characters` | Aligned | `Characters` |
| `/media-multi` | `Multi-Item Review` | — | — | Competes with `/review` label | `Multi-Item Review` |
| `/review` (candidate alias) | `Review` | — | — | Ambiguous with content review workflows | `Multi-Item Review` (or retire `/review`) |
| `/settings` | `Settings` | `Go to Settings` | Settings groups | Aligned | `Settings` |
| `/settings/health` | — | `Health & Diagnostics` | `Health` | Mismatch | `Health & Diagnostics` |
| `/workspace-playground` | `Research Studio` (via mode label token) | — | — | Label token currently maps inconsistently with model playground keys | `Research Studio` |
| `/model-playground` | `Workspace Playground` | — | — | Swapped semantics with `/workspace-playground` | `Model Playground` |
| `/document-workspace` | `Document Workspace` | — | — | Aligned | `Document Workspace` |
| `/data-tables` | `Data Tables` | — | `Data Tables` (via header token in settings nav) | Aligned | `Data Tables` |

## Priority Triage and Assignment

| Priority | Issue | Impact | Owner | Target | File Targets | Status |
|---|---|---|---|---|---|---|
| P1 | `/workspace-playground` and `/model-playground` naming is inverted across labels/tokens | High route confusion | WebUI + Product | M1.2 | `apps/packages/ui/src/assets/locale/en/settings.json`, `apps/packages/ui/src/routes/route-registry.tsx`, `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts` | Implemented (QA Verified) |
| P1 | `/review` label ambiguity vs `/media-multi` (`Review` vs `Multi-Item Review`) | Wrong-route landings | Product + WebUI | M1.2 | `apps/packages/ui/src/routes/route-registry.tsx`, `apps/tldw-frontend/pages/review.tsx` | Implemented (QA Verified) |
| P1 | Health naming mismatch (`Health` vs `Health & Diagnostics`) | Diagnostic discoverability gap | WebUI | M1.2 | `apps/packages/ui/src/assets/locale/en/settings.json`, `apps/packages/ui/src/components/Common/CommandPalette.tsx` | Implemented (QA Verified) |
| P2 | `Chat dictionaries` style/case mismatch across surfaces | Taxonomy inconsistency | WebUI | M1.2 | `apps/packages/ui/src/components/Layouts/ModeSelector.tsx`, `apps/packages/ui/src/assets/locale/en/settings.json` | Implemented (QA Verified) |
| P2 | Missing command palette entry for `Knowledge QA` | Slower expert navigation | WebUI | M1.2 | `apps/packages/ui/src/components/Common/CommandPalette.tsx` | Implemented (QA Verified) |
| P2 | Missing command palette entry for `Prompts` | Slower workflow switching | WebUI | M1.2 | `apps/packages/ui/src/components/Common/CommandPalette.tsx` | Implemented (QA Verified) |
| P2 | Prompt Studio label appears as destination despite alias status | IA drift after unification | Product + WebUI | M1.2 | `apps/packages/ui/src/routes/route-registry.tsx`, `apps/packages/ui/src/assets/locale/en/settings.json` | Triaged |
| P3 | Quick Ingest capitalization (`Quick ingest` vs `Quick Ingest`) | Minor polish issue | WebUI | M1.2 | `apps/packages/ui/src/assets/locale/en/sidepanel.json`, `apps/packages/ui/src/components/Layouts/QuickIngestButton.tsx`, `apps/packages/ui/src/components/Option/Playground/PlaygroundEmpty.tsx`, `apps/packages/ui/src/components/Sidepanel/Chat/ControlRow.tsx` | Implemented (QA Verified) |

## Recommended Canonical Vocabulary (Approved Pending Product Sign-off)

- `Chat`
- `Knowledge QA`
- `Media`
- `Multi-Item Review`
- `Content Review`
- `Prompts`
- `Chat Dictionaries`
- `Health & Diagnostics`
- `Research Studio` (`/workspace-playground`)
- `Model Playground` (`/model-playground`)

## Exit Criteria for M1.2

- [x] Cross-surface label matrix created.
- [x] Navigation terminology inconsistencies triaged and assigned.
- [x] Product sign-off on canonical vocabulary.
- [x] String/token updates implemented.
- [x] Smoke verification confirms no route-label regressions.

## Implementation Progress (February 12, 2026)

Implemented in tracked files:
- Added command palette navigation entries for `Knowledge QA` and `Prompts`.
- Normalized `Health` to `Health & Diagnostics` in settings navigation.
- Standardized `Quick Ingest` capitalization in sidepanel and fallback UI strings.
- Standardized `Chat Dictionaries` casing in mode selector fallback.
- Added explicit settings-nav labels for `Research Studio` and `Model Playground` and mapped routes to those labels.
- Converted `/review` into an explicit alias redirect to `/media-multi` in both registry and Next page wrapper.

## Verification Evidence (February 13, 2026)

Automated verification:
- `bunx vitest run src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx` (1 passed).
- `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding)" --reporter=line` (10 passed, 13.4s).
- `bunx playwright test e2e/smoke/all-pages.spec.ts --reporter=line` (150 passed, 1.8m).
- `bunx playwright test e2e/smoke/m1-2-label-evidence.spec.ts --reporter=line` (2 passed, desktop/mobile evidence capture).

Screenshot evidence:
- Captured in the February 13 closeout run (`bunx playwright test e2e/smoke/m1-2-label-evidence.spec.ts --reporter=line`); raw screenshot files are not retained in-repo.

## Change Log

- February 12, 2026: Initial matrix and triage assignments published.
- February 12, 2026: Implemented first-pass label consistency updates in tracked UI/settings files (pending QA smoke).
- February 13, 2026: Completed engineering closeout verification (unit + focused smoke + full smoke) and captured desktop/mobile evidence screenshots.
- February 13, 2026: Product approved canonical vocabulary and M1.2 sign-off checkbox was closed.
