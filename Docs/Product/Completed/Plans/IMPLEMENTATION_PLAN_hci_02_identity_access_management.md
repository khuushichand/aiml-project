# Implementation Plan: HCI Review - Identity & Access Management

## Scope

Pages: `app/users/`, `app/organizations/`, `app/teams/`, `app/roles/`
Finding IDs: `2.1` through `2.11`

## Finding Coverage

- `2.1` (Critical): No admin password reset capability
- `2.2` (Critical): Cannot edit or delete organizations
- `2.3` (Critical): Cannot edit or delete teams
- `2.4` (Important): Permission matrix is read-only
- `2.5` (Important): No role comparison/diff view
- `2.6` (Important): No login history on user detail page
- `2.7` (Important): No bulk password reset or bulk role assignment
- `2.8` (Important): Cannot filter users by MFA-disabled, locked, or inactive status
- `2.9` (Nice-to-Have): Cannot change team member roles
- `2.10` (Nice-to-Have): "View Organizations" and "View Teams" buttons disabled on user detail
- `2.11` (Nice-to-Have): Effective permissions view doesn't show permission source

## Key Files

- `admin-ui/app/users/page.tsx` -- User list with bulk actions
- `admin-ui/app/users/[id]/page.tsx` -- User detail (info, security, rate limits, permission overrides, sessions)
- `admin-ui/app/organizations/page.tsx` -- Org list (create only)
- `admin-ui/app/organizations/[id]/page.tsx` -- Org detail (members, teams, BYOK, watchlists)
- `admin-ui/app/teams/page.tsx` -- Team list (requires org selection)
- `admin-ui/app/teams/[id]/page.tsx` -- Team detail (members only)
- `admin-ui/app/roles/page.tsx` -- Role + permission CRUD
- `admin-ui/app/roles/[id]/page.tsx` -- Role detail with permission toggles, rate limits, tool permissions
- `admin-ui/app/roles/matrix/page.tsx` -- Read-only permission matrix
- `admin-ui/components/users/UserPicker.tsx` -- Autocomplete user search
- `admin-ui/lib/api-client.ts` -- API methods

## Stage 1: Critical CRUD Gaps (Password Reset, Org/Team Edit & Delete)

**Goal**: Unblock the three most fundamental admin operations that are currently impossible.
**Success Criteria**:
- User detail page has "Reset Password" button that calls backend endpoint and shows confirmation.
- User detail page has "Force Password Change on Next Login" toggle.
- Organization list/detail page has edit dialog (name, slug) and delete button with confirmation.
- Organization delete requires member count acknowledgment ("This org has N members").
- Team list/detail page has edit dialog (name, description) and delete button with confirmation.
- All operations use existing ConfirmDialog patterns.
**Tests**:
- Unit test for password reset button + API call mock.
- Unit test for org edit dialog form validation (slug uniqueness hint).
- Unit test for org delete confirmation flow with member count.
- Unit test for team edit and delete flows.
**Status**: Complete

## Stage 2: Permission Matrix Editing + Role Comparison

**Goal**: Make the permission matrix interactive and let admins compare roles side-by-side.
**Success Criteria**:
- Permission matrix cells are clickable to toggle permission grants (with save/discard controls).
- Matrix supports multi-edit mode: make changes to multiple cells, then save all at once.
- Unsaved changes shown with visual diff (highlighted cells).
- New "Compare Roles" page or dialog: select 2-3 roles, see side-by-side permission table with diff highlighting (green = only in role A, red = only in role B, white = shared).
- Link to comparison from role detail page ("Compare with...").
**Tests**:
- Unit tests for matrix cell toggle state management.
- Unit tests for batch save of permission changes.
- Unit tests for role comparison diff calculation.
- Snapshot tests for comparison view with highlighted diffs.
**Status**: Complete

## Stage 3: User Filters + Login History + Bulk Operations

**Goal**: Help admins quickly find problematic accounts and take bulk actions.
**Success Criteria**:
- User list page has filter dropdowns: Status (Active/Inactive), MFA (Enabled/Disabled), Verified (Yes/No).
- Filters combine with existing search (AND logic).
- User detail page has "Login History" section showing last 20 logins with timestamp, IP, user agent, success/failure status.
- Login history sourced from audit log filtered by `action=login` for that user.
- Bulk actions expanded: bulk role assignment (dropdown to select role), bulk password reset (sends reset to all selected).
- Bulk MFA enforcement toggle (enable MFA requirement for selected users).
**Tests**:
- Unit tests for filter dropdown state and API parameter construction.
- Unit tests for login history rendering with success/failure badges.
- Unit tests for bulk role assignment dialog and confirmation.
- Integration test for filter + search combination.
**Status**: Complete

## Stage 4: Team Roles + User Memberships + Permission Source

**Goal**: Complete the remaining Nice-to-Have findings to round out the IAM experience.
**Success Criteria**:
- Team member rows have role change dropdown (member/lead/admin) with save.
- User detail "View Organizations" button works: shows list of orgs the user belongs to with role.
- User detail "View Teams" button works: shows list of teams with org context.
- Effective permissions view annotates each permission with source: role name badge, "direct override" badge, or "inherited" badge.
**Tests**:
- Unit test for team member role change dropdown + API call.
- Unit test for user membership list rendering.
- Unit test for permission source annotation rendering.
**Status**: Complete

## Dependencies

- Stage 1 requires backend endpoints for: `POST /admin/users/{id}/reset-password`, `PATCH/DELETE /orgs/{id}`, `PATCH/DELETE /orgs/{org_id}/teams/{team_id}`. Verify these exist in `api-client.ts` or backend routes before implementing.
- Stage 3 login history can be sourced from existing audit log endpoint with `action` and `user_id` filters.
- Stage 4 user membership requires: `GET /admin/users/{id}/organizations` and `GET /admin/users/{id}/teams` or equivalent.
