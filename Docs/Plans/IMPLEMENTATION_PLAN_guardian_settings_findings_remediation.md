## Stage 1: API Contract Alignment
**Goal**: Fix frontend service contracts so query params and response typing match backend behavior.
**Success Criteria**:
- `apps/packages/ui/src/services/guardian.ts` uses backend-aligned query params:
- `enabled_only` instead of `enabled` for rules listing.
- `unread_only` instead of `is_read` for alerts listing.
- `offset` instead of `skip` for alerts and audit log pagination.
- `deactivateRule()` response type reflects backend payload (`ok/status/deactivation_at/reason`) instead of `DetailResponse`.
**Tests**:
- Add/adjust service tests for query string generation and response typing.
- Manual smoke: fetch rules/alerts/audit with filters and verify backend receives expected params.
**Status**: Complete

## Stage 2: Self-Monitoring Rules Safety Fixes
**Goal**: Eliminate invalid rule action values and prevent failed create/update submissions.
**Success Criteria**:
- Remove `warn` as a selectable action for self-monitoring rules in `GuardianSettings.tsx`.
- Ensure form defaults and edit flows only submit `block | redact | notify`.
- Keep guardian policy action options unchanged (`warn` remains valid there).
**Tests**:
- Component test: self-monitoring action dropdown excludes `warn`.
- Manual smoke: create/update self-monitoring rule succeeds for each allowed action.
**Status**: Not Started

## Stage 3: Guardian Relationship Lifecycle Correctness
**Goal**: Make relationship actions consistent with backend role rules and keep selected relationship state current.
**Success Criteria**:
- Update relationship list service/API usage to support role-aware views (`guardian` and `dependent`).
- Only render `Accept` action in dependent context (or remove from guardian context entirely).
- After accept/suspend/reactivate/dissolve, selected relationship state is refreshed from query data (no stale status in UI).
- Audit query invalidated on relationship and policy mutations that log audit entries.
**Tests**:
- Component test: `Accept` button visibility depends on role.
- Component test: policy section enablement updates after status mutation.
- Manual smoke: dependent can accept; guardian can suspend/reactivate; audit panel updates without manual refresh.
**Status**: Not Started

## Stage 4: Governance Policies UI Completion
**Goal**: Implement missing governance policy CRUD in Self-Monitoring tab (or clearly scope it out with explicit deferral).
**Success Criteria**:
- Add governance policies section in `GuardianSettings.tsx` with list/create/delete using existing service calls.
- Remove unused governance imports/types if deferring, and document deferral in plan/change notes.
- Query invalidation wired for governance mutations.
**Tests**:
- Component test: governance list renders and updates after create/delete.
- Manual smoke: create governance policy, assign/use in rule workflow (if supported), delete policy.
**Status**: Not Started

## Stage 5: i18n Wiring, Hardening, and Verification
**Goal**: Replace hardcoded UI strings with translation keys and complete end-to-end verification.
**Success Criteria**:
- Wire `settings.guardian.*` locale keys via `useTranslation()` in `GuardianSettings.tsx`.
- Remove new unused imports/types and ensure lint cleanliness for changed files.
- Add targeted tests for core regressions found in review.
**Tests**:
- `bun run --cwd apps/tldw-frontend lint`
- Targeted frontend tests for guardian/self-monitoring settings page.
- Manual verification checklist:
- Rules CRUD (including deactivate),
- Alerts mark-read and unread polling,
- Relationship lifecycle by role,
- Policies CRUD,
- Governance CRUD,
- Crisis resources load,
- Offline banner display.
**Status**: Not Started
