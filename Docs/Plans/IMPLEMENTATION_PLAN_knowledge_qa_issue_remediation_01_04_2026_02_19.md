# Implementation Plan: Knowledge QA Issue Remediation (1-4)

## Scope

Components:
- `apps/packages/ui/src/components/Option/KnowledgeQA/ExportDialog.tsx`
- `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- `apps/packages/ui/src/components/Option/KnowledgeQA/FollowUpInput.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/*`
- `apps/packages/ui/src/routes/route-registry.tsx`
- `apps/tldw-frontend/extension/routes/route-registry.tsx` (TBD scope)

Target issues:
- `1` Chatbook export contract/auth mismatch
- `2` Missing coverage for export success + API contract shape
- `3` Follow-up queued-state copy/behavior mismatch
- `4` Extension shared-link route parity (explicitly TBD per product direction)

## Stage 1: Chatbook Export Contract And Auth Alignment
**Goal**: Replace broken raw export call with API-client-backed flow that matches backend contract.
**Success Criteria**:
- `ExportDialog.tsx` no longer uses raw `fetch("/api/v1/chatbooks/export", ...)`.
- Export uses `tldwClient` methods with authenticated/background request path.
- Request payload conforms to `CreateChatbookRequest` (`name`, `description`, `content_selections`, optional flags).
- Download behavior uses returned `job_id`/`download_url` contract instead of treating `/export` response as a zip blob.
**Tests**:
- Component/integration tests for successful chatbook export path (including download trigger path).
- Component/integration tests for server validation error path (400/422) and auth/network failure path.
**Validation Notes (2026-02-19)**:
- Replaced raw chatbook `fetch` flow in `ExportDialog.tsx` with `tldwClient.exportChatbook(...)` and `tldwClient.downloadChatbookExport(...)`.
- Request now sends `CreateChatbookRequest`-compatible payload (`name`, `description`, `content_selections.conversation`, export flags).
- Download now resolves from returned `job_id`/`download_url` contract (no longer assumes `/export` returns zip bytes).
- Added/updated test coverage in `ExportDialog.a11y.test.tsx` for chatbook contract success path and failure mapping path.
- Validation command passed: `bunx vitest run src/components/Option/KnowledgeQA/__tests__/ExportDialog.a11y.test.tsx` (10 passed).
**Status**: Complete

## Stage 2: Export Flow Reliability And Regression Guardrails
**Goal**: Ensure export behavior is resilient and does not regress existing workflow actions.
**Success Criteria**:
- Existing markdown/pdf export behavior remains unchanged.
- Save-to-notes and token share-link actions still work from the same dialog.
- Export error messaging remains actionable and non-generic.
**Tests**:
- Extend `ExportDialog` tests to cover:
- chatbook success (valid payload + downstream download handling)
- chatbook failure classes (validation, unauthorized, unavailable server)
- no regression in save-to-notes/share-link controls
**Validation Notes (2026-02-19)**:
- Added explicit export-failure class coverage in `ExportDialog.a11y.test.tsx`:
- unauthorized (`401`)
- validation/unprocessable (`422`)
- network unavailable
- Added regression test for PDF browser-print fallback behavior to lock current export UX.
- Save-to-notes and share-link controls remain covered and passing in the same suite.
**Status**: Complete

## Stage 3: Follow-Up Queued-State UX Consistency
**Goal**: Make follow-up state copy consistent with actual interaction rules.
**Success Criteria**:
- One behavior is chosen and implemented consistently:
- Option A: keep disabled input while searching and update helper/placeholder copy accordingly.
- Option B: allow true queued follow-up entry while searching and persist queued value.
- Accessibility label and mobile sticky behavior remain intact.
**Tests**:
- Update `FollowUpInput` tests for selected behavior and helper text truthfulness.
- Add/adjust assertions for disabled/enabled state, placeholder text, and helper copy.
**Validation Notes (2026-02-19)**:
- Chosen behavior: **Option A** (keep input disabled during active search).
- Updated queued-state placeholder/copy to accurately reflect disabled behavior:
- placeholder: `"Current search in progress..."`
- helper text: `"Follow-up input unlocks when the current search completes."`
- Updated `FollowUpInput.accessibility.test.tsx` assertions to match.
**Status**: Complete

## Stage 4: Extension Shared-Link Scope (TBD Decision Track)
**Goal**: Prevent ambiguity and runtime surprises while extension support is undecided.
**Success Criteria**:
- Decision is documented as one of:
- `defer`: explicitly unsupported in extension for now, with doc note and no broken assumptions.
- `implement`: add `/knowledge/shared/:shareToken` route parity in extension registry.
- If deferred, user-facing behavior is explicit and non-broken (no implied extension-only support claim).
**Tests**:
- If `implement`: route registry test/assertion for shared token path in extension.
- If `defer`: documentation/test assertion that extension route set intentionally excludes shared route.
**Validation Notes (2026-02-19)**:
- Decision: **defer** extension shared-token route support (per product direction).
- Added explicit defer comment in extension route registry near knowledge routes.
- Updated share-link help copy in `ExportDialog.tsx` to note extension shared-link routing is currently TBD.
**Status**: Complete

## Stage 5: Validation, Evidence, And Plan Closure
**Goal**: Verify fixes, capture evidence, and close plan with clear status.
**Success Criteria**:
- Targeted frontend tests pass for updated Knowledge QA modules.
- Any touched backend contract tests remain green.
- Plan statuses updated to complete with command evidence.
**Tests**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/ExportDialog*.test.tsx src/components/Option/KnowledgeQA/__tests__/FollowUpInput*.test.tsx`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_share_links_api.py -q`
- Additional targeted chatbook endpoint tests if added.
**Validation Notes (2026-02-19)**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/ExportDialog.a11y.test.tsx src/components/Option/KnowledgeQA/__tests__/errorMessages.test.ts src/components/Option/KnowledgeQA/__tests__/FollowUpInput.accessibility.test.tsx` passed (`20 passed`).
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_share_links_api.py -q` passed (`2 passed`).
**Status**: Complete

## Notes

- Issue `4` is intentionally tracked as a decision gate because extension link-sharing support is currently TBD.
- Stage 1 must complete before Stage 2 test hardening to avoid codifying incorrect API assumptions.
