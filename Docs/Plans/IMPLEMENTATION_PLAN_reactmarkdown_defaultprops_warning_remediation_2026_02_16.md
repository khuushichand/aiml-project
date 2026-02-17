# Implementation Plan: ReactMarkdown defaultProps Warning Remediation (2026-02-16)

## Scope

Remove the temporary smoke allowlist for the `ReactMarkdown` `defaultProps` warning and restore strict console-clean behavior on routes that render markdown-heavy UI.

Current affected routes:
- `/flashcards`
- `/settings/chat`

Parity requirement:
- Any fix in shared UI code must apply to both WebUI and extension surfaces.

## Stage 1: Baseline and Source Attribution
**Goal**: Confirm exact warning origin(s) and all impacted shared components.
**Success Criteria**:
- Warning stack traces are mapped to concrete component entry points.
- Affected markdown wrappers/components are listed with owner files.
- Candidate remediation options are documented with risk notes.
**Tests**:
- `playwright test e2e/smoke/all-pages.spec.ts --grep "(\\/flashcards|\\/settings\\/chat)" --reporter=line --workers=1`
- Local component rendering check for shared markdown components in `apps/packages/ui/src/components/Common`.
**Status**: Complete

## Stage 2: Primary Remediation (Dependency/Wrapper Upgrade)
**Goal**: Eliminate runtime warning at source via package update or wrapper migration.
**Success Criteria**:
- `ReactMarkdown` warning no longer appears on `/flashcards` and `/settings/chat` without allowlist support.
- No regressions in markdown rendering behavior (tables, code, math, links, sanitization).
- Shared implementation remains single-source for web + extension parity.
**Tests**:
- Focused route smoke check above (same grep).
- Targeted UI tests for markdown rendering paths (flashcards and chat settings markdown previews).
- Existing markdown-related unit tests in `apps/packages/ui/src`.
**Status**: Complete

## Stage 3: Compatibility Fallback (If Stage 2 is Blocked)
**Goal**: Provide a controlled compatibility shim that prevents warning noise while preserving output fidelity.
**Success Criteria**:
- Shim is scoped to shared markdown component(s), not ad-hoc per route.
- Behavior parity maintained across web and extension.
- Clear rollback path retained once upstream dependency path is viable.
**Tests**:
- Same focused route smoke.
- Regression checks for markdown interactions on both affected routes.
**Status**: Complete
**Outcome**: Not required; Stage 2 resolved warning and route stability without a fallback shim.

## Stage 4: Remove Temporary Allowlist and Re-Harden Gate
**Goal**: Delete the temporary allowlist entry and re-enable strict hard-gate enforcement.
**Success Criteria**:
- `m5-react-defaultprops-warning` allowlist entry removed from smoke setup.
- Focused and full smoke suites pass with zero unexpected console warnings on affected routes.
- Plan and evidence docs updated with final outcome.
**Tests**:
- `playwright test e2e/smoke/all-pages.spec.ts --grep "(\\/flashcards|\\/settings\\/chat)" --reporter=line --workers=1`
- `playwright test e2e/smoke/all-pages.spec.ts --reporter=line --workers=1`
- `playwright test e2e/smoke/stage5-release-gate.spec.ts --reporter=line --workers=1`
**Status**: Complete

## Validation Evidence (2026-02-16)

- Root cause confirmed: shared UI resolved legacy markdown stack while WebUI resolved modern stack.
  - `apps/packages/ui` resolved:
    - `react-markdown@8.0.0`
    - `remark-gfm@3.0.1`
    - `remark-math@5.1.1`
    - `rehype-katex@6.0.3`
  - `apps/tldw-frontend` resolved:
    - `react-markdown@10.1.0`
    - `remark-gfm@4.0.1`
    - `remark-math@6.0.0`
    - `rehype-katex@7.0.1`
- Shared parity upgrade completed:
  - Updated shared UI peer ranges in `apps/packages/ui/package.json` to ReactMarkdown v10 stack.
  - Updated extension dependency ranges in `apps/extension/package.json` to matching ReactMarkdown v10 stack.
  - Ran `bun install` from `apps/` to apply lockfile updates.
- ReactMarkdown v10 API migration completed in shared components:
  - Removed unsupported `className` prop from direct `ReactMarkdown` usage and moved styling to wrapper containers in:
    - `apps/packages/ui/src/components/Common/Markdown.tsx`
    - `apps/packages/ui/src/components/Knowledge/QASearchTab/GeneratedAnswerCard.tsx`
- Temporary allowlist removed:
  - Deleted `m5-react-defaultprops-warning` from `apps/tldw-frontend/e2e/smoke/smoke.setup.ts`.
- Gate verification after allowlist removal:
  - Focused routes: `4 passed`
    - `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/all-pages.spec.ts --grep "(\\/settings\\/chat|\\/flashcards)" --reporter=line --workers=1`
  - Stage 5 audited-route release gate: `11 passed`
    - `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/stage5-release-gate.spec.ts --reporter=line --workers=1`
  - Full all-pages smoke: `165 expected, 0 unexpected, 0 flaky`
    - JSON artifact: `/tmp/all-pages-after-reactmarkdown-remediation.json`

## Notes

- Keep `apps/tldw-frontend/e2e/smoke/smoke.setup.ts` allowlist in place until Stage 4.
- Prefer changes in shared markdown primitives (`apps/packages/ui/src/components/Common/Markdown.tsx` and related wrappers) over route-local patches.
